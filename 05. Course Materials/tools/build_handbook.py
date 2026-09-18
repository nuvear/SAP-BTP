"""Build the interactive HTML handbook ("active notebook") from a Markdown source.

    python build_handbook.py SOURCE.md OUT.html --lang en --title "Northwind Advisor Student Handbook" \
        --switch "en=../English/03_Student_Handbook.html,ja=../Japanese/03_Student_Handbook.html,zh=../Chinese/03_Student_Handbook.html"

What the page does for the student (no server, works from a file on disk):
  - every "- [ ]" item becomes a real checkbox; a progress bar counts them
  - every "Question ..." paragraph and every reflection item gets an answer box
  - every section gets a "My notes" box
  - everything typed is kept in the browser (localStorage) and, with "Save my copy", written INTO the HTML
    file itself and downloaded, so the filled-in handbook is one portable file that reopens with its state
  - the answer key is folded away until the student opens it
The same template is used for every language; keys of checkboxes and boxes come from their position, so a
student can open the Japanese page and still see the ticks they made on the English one when they load a saved copy.
"""
from __future__ import annotations
import argparse, datetime, html, json, re
from pathlib import Path
import markdown

UI = {
    "en": dict(progress="Progress", save="Save my copy", reset="Clear everything", print="Print",
               notes="My notes", answer="My answer", key="Answer key (open when you have tried the exercises)",
               saved="Saved in this browser", saved_file="This file carries your saved answers from",
               hint="Tick boxes and type as you go. Your work stays in this browser; click Save my copy to download a file that keeps it.",
               reset_confirm="Clear all ticks and answers on this page?", lang="Language"),
    "ja": dict(progress="進捗", save="自分のコピーを保存", reset="すべて消去", print="印刷",
               notes="メモ", answer="自分の答え", key="解答例（演習を試してから開いてください）",
               saved="このブラウザーに保存済み", saved_file="このファイルには次の時点の保存内容が含まれています:",
               hint="チェックを入れ、記入しながら進めてください。内容はこのブラウザーに残ります。「自分のコピーを保存」で内容を含むファイルをダウンロードできます。",
               reset_confirm="このページのチェックと回答をすべて消去しますか？", lang="言語"),
    "zh": dict(progress="进度", save="保存我的副本", reset="全部清除", print="打印",
               notes="我的笔记", answer="我的答案", key="参考答案（请先尝试练习再打开）",
               saved="已保存在此浏览器中", saved_file="此文件包含以下时间保存的内容:",
               hint="边做边勾选和填写。内容会保留在此浏览器中；点击“保存我的副本”可下载包含内容的文件。",
               reset_confirm="清除此页面上的所有勾选和答案？", lang="语言"),
}
LANG_NAMES = {"en": "English", "ja": "日本語", "zh": "简体中文"}

CSS = """
:root{--ink:#1c2430;--muted:#5b6673;--line:#d9dee5;--bg:#fbfbf9;--card:#ffffff;--accent:#0a6ed1;--accent-ink:#ffffff;--ok:#2e7d32;--soft:#eef3f8;--code:#f4f5f7}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans","Noto Sans JP","Noto Sans SC","Hiragino Sans","PingFang SC",Roboto,Helvetica,Arial,sans-serif}
header.hb{position:sticky;top:0;z-index:5;background:var(--card);border-bottom:1px solid var(--line);padding:10px 16px;display:flex;flex-wrap:wrap;gap:10px 18px;align-items:center}
header.hb .t{font-weight:700;margin-right:auto}
header.hb .prog{display:flex;align-items:center;gap:8px;font-size:14px;color:var(--muted)}
header.hb .bar{width:140px;height:8px;background:var(--soft);border-radius:4px;overflow:hidden}
header.hb .bar i{display:block;height:100%;width:0;background:var(--ok);transition:width .2s}
header.hb button{border:1px solid var(--line);background:var(--card);color:var(--ink);padding:6px 12px;border-radius:6px;cursor:pointer;font-size:14px}
header.hb button.primary{background:var(--accent);border-color:var(--accent);color:var(--accent-ink)}
header.hb .langs a{margin-left:6px;font-size:14px;text-decoration:none;color:var(--accent)}
header.hb .langs a.cur{font-weight:700;color:var(--ink)}
main{max-width:860px;margin:0 auto;padding:24px 16px 80px}
.hint{background:var(--soft);border:1px solid var(--line);border-radius:8px;padding:10px 14px;font-size:14px;color:var(--muted);margin:0 0 18px}
h1{font-size:30px;line-height:1.2;margin:.2em 0 .4em}h2{font-size:22px;margin:1.8em 0 .5em;padding-top:.4em;border-top:1px solid var(--line)}h3{font-size:18px}
h1.part{margin-top:2.2em;font-size:24px;color:var(--accent)}
p,li{max-width:72ch}
a{color:var(--accent)}
code{background:var(--code);padding:1px 5px;border-radius:4px;font-size:.92em;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
pre{background:#1f2937;color:#e5e7eb;padding:12px 14px;border-radius:8px;overflow-x:auto;position:relative;font-size:14px}
pre code{background:none;color:inherit;padding:0;font-size:inherit}
pre .copy{position:absolute;top:6px;right:6px;font-size:12px;border:1px solid #4b5563;background:#374151;color:#e5e7eb;border-radius:5px;padding:2px 8px;cursor:pointer}
table{border-collapse:collapse;width:100%;font-size:15px;margin:10px 0 16px;display:block;overflow-x:auto}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}th{background:var(--soft)}
ul.tasks{list-style:none;padding-left:0}ul.tasks li{margin:6px 0;padding:8px 10px;border:1px solid var(--line);border-radius:6px;background:var(--card);display:flex;gap:10px;align-items:flex-start}
ul.tasks input{margin-top:5px;width:18px;height:18px;flex:none}
ul.tasks li.done{background:#f1f8f1;border-color:#c8e6c9}ul.tasks li.done label{color:var(--muted);text-decoration:line-through}
.box{margin:8px 0 16px}.box label{display:block;font-size:13px;color:var(--muted);margin-bottom:4px;text-transform:uppercase;letter-spacing:.04em}
.box textarea{width:100%;min-height:72px;border:1px solid var(--line);border-radius:6px;padding:8px 10px;font:inherit;font-size:15px;background:var(--card);resize:vertical}
.box textarea:focus{outline:2px solid var(--accent);border-color:var(--accent)}
.notes textarea{min-height:56px;background:#fffdf3}
details.key{border:1px dashed var(--line);border-radius:8px;padding:8px 14px;margin:12px 0}details.key summary{cursor:pointer;font-weight:600}
.saved{font-size:13px;color:var(--muted)}
footer{max-width:860px;margin:0 auto;padding:0 16px 40px;font-size:13px;color:var(--muted)}
@media print{header.hb,.hint,pre .copy{display:none}body{background:#fff}main{max-width:none;padding:0}.box textarea{border:1px solid #999;min-height:40px}details.key{display:block}details.key[open] summary{display:none}}
"""

JS = r"""
(function(){
  const DOC = document.documentElement.dataset.doc, LANG = document.documentElement.dataset.lang;
  const KEY = 'hb:' + DOC;                         // shared across languages: same keys, same ticks
  const T = JSON.parse(document.getElementById('hb-ui').textContent);
  const fields = () => Array.from(document.querySelectorAll('[data-key]'));
  function collect(){ const s = {}; for (const el of fields()) { s[el.dataset.key] = el.type === 'checkbox' ? el.checked : el.value; } return s; }
  function apply(s){ if (!s) return; for (const el of fields()) { if (!(el.dataset.key in s)) continue; if (el.type === 'checkbox') el.checked = !!s[el.dataset.key]; else el.value = s[el.dataset.key] || ''; } refresh(); }
  function refresh(){
    const boxes = Array.from(document.querySelectorAll('input[type=checkbox][data-key]'));
    const done = boxes.filter(b => b.checked).length;
    for (const b of boxes) b.closest('li').classList.toggle('done', b.checked);
    const pct = boxes.length ? Math.round(100 * done / boxes.length) : 0;
    document.querySelector('header.hb .prog').style.display = boxes.length ? '' : 'none';
    document.getElementById('hb-bar').style.width = pct + '%';
    document.getElementById('hb-count').textContent = done + ' / ' + boxes.length;
  }
  function persist(){ try { localStorage.setItem(KEY, JSON.stringify({at: new Date().toISOString(), state: collect()})); document.getElementById('hb-saved').textContent = T.saved + ' · ' + new Date().toLocaleTimeString(); } catch (e) {} }
  function embedded(){ try { return JSON.parse(document.getElementById('hb-state').textContent || 'null'); } catch (e) { return null; } }
  function saveCopy(){
    const payload = {at: new Date().toISOString(), lang: LANG, state: collect()};
    const clone = document.documentElement.cloneNode(true);
    clone.querySelector('#hb-state').textContent = JSON.stringify(payload).replace(/<\//g, '<\\/');
    for (const ta of clone.querySelectorAll('textarea[data-key]')) ta.textContent = payload.state[ta.dataset.key] || '';
    for (const cb of clone.querySelectorAll('input[type=checkbox][data-key]')) { if (payload.state[cb.dataset.key]) cb.setAttribute('checked', ''); else cb.removeAttribute('checked'); }
    const blob = new Blob(['<!doctype html>\n' + clone.outerHTML], {type: 'text/html'});
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = DOC + '_' + LANG + '_' + payload.at.slice(0, 10) + '.html'; document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
  }
  function reset(){ if (!confirm(T.reset_confirm)) return; for (const el of fields()) { if (el.type === 'checkbox') el.checked = false; else el.value = ''; } try { localStorage.removeItem(KEY); } catch (e) {} refresh(); document.getElementById('hb-saved').textContent = ''; }
  document.addEventListener('DOMContentLoaded', () => {
    const emb = embedded(); let local = null; try { local = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) {}
    if (emb && emb.state) { apply(emb.state); document.getElementById('hb-saved').textContent = T.saved_file + ' ' + new Date(emb.at).toLocaleString(); }
    else if (local && local.state) { apply(local.state); document.getElementById('hb-saved').textContent = T.saved + ' · ' + new Date(local.at).toLocaleString(); }
    else refresh();
    document.addEventListener('input', e => { if (e.target.dataset && e.target.dataset.key) { refresh(); persist(); } });
    document.getElementById('hb-save').addEventListener('click', saveCopy);
    document.getElementById('hb-reset').addEventListener('click', reset);
    document.getElementById('hb-print').addEventListener('click', () => window.print());
    for (const pre of document.querySelectorAll('pre')) { const b = document.createElement('button'); b.className = 'copy'; b.textContent = 'copy'; b.addEventListener('click', () => { navigator.clipboard.writeText(pre.querySelector('code').textContent).then(() => { b.textContent = 'copied'; setTimeout(() => b.textContent = 'copy', 1200); }); }); pre.appendChild(b); }
  });
})();
"""


def preprocess(md_text: str, t: dict) -> str:
    """Insert markers for answer boxes before conversion; keys are positional so every language lines up."""
    out, sec, q, ref = [], 0, 0, 0
    in_reflection = False
    for line in md_text.splitlines():
        if line.startswith("## "):
            if sec:                                             # notes box at the end of the previous section
                out.append(f'\n<div class="box notes"><label>{html.escape(t["notes"])}</label><textarea data-key="s{sec}-notes"></textarea></div>\n')
            sec += 1
            in_reflection = False
        if re.match(r"^(Question|質問|问题)", line):
            q += 1
            out.append(line)
            out.append(f'\n<div class="box"><label>{html.escape(t["answer"])}</label><textarea data-key="q{q}"></textarea></div>\n')
            continue
        if re.match(r"^(Reflection|振り返り|反思)", line):
            in_reflection = True
        if in_reflection and re.match(r"^\d+\. ", line):
            ref += 1
            out.append(line + f'<div class="box"><label>{html.escape(t["answer"])}</label><textarea data-key="r{ref}"></textarea></div>')
            continue
        out.append(line)
    if sec:
        out.append(f'\n<div class="box notes"><label>{html.escape(t["notes"])}</label><textarea data-key="s{sec}-notes"></textarea></div>\n')
    return "\n".join(out)


def postprocess(body: str, t: dict) -> str:
    # task lists: "- [ ] text" arrives as <li>[ ] text</li>
    n = 0
    def task(m):
        nonlocal n; n += 1
        return f'<li><input type="checkbox" id="t{n}" data-key="t{n}"><label for="t{n}">{m.group(1)}</label></li>'
    body = re.sub(r"<li>\[ \] (.*?)</li>", task, body, flags=re.S)
    body = re.sub(r"<li>\[x\] (.*?)</li>", lambda m: task(m).replace('data-key', 'checked data-key'), body, flags=re.S)
    body = re.sub(r"<ul>(\s*<li><input type=\"checkbox\")", r'<ul class="tasks">\1', body)
    # answer key folded away: from the "Answer key" h2 up to the next h1
    body = re.sub(r'(<h2[^>]*>)(Answer key[^<]*|解答例[^<]*|参考答案[^<]*)(</h2>)(.*?)(?=<h1|\Z)',
                  lambda m: f'<details class="key"><summary>{html.escape(t["key"])}</summary>{m.group(4)}</details>', body, flags=re.S)
    # part headings
    body = re.sub(r'<h1([^>]*)>(Part [AB]:|パート[AB]:|第[AB]部分:)', r'<h1 class="part"\1>\2', body)
    return body


def build(src: Path, out: Path, lang: str, title: str, switch: dict[str, str], doc_id: str):
    t = UI[lang]
    text = src.read_text(encoding="utf-8")
    text = preprocess(text, t)
    body = markdown.markdown(text, extensions=["tables", "fenced_code", "toc", "md_in_html"], output_format="html5")
    body = postprocess(body, t)
    langs = " ".join(f'<a href="{html.escape(p)}" class="{"cur" if code == lang else ""}">{LANG_NAMES[code]}</a>' for code, p in switch.items())
    page = f"""<!doctype html>
<html lang="{lang}" data-doc="{html.escape(doc_id)}" data-lang="{lang}">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<style>{CSS}</style>
<script type="application/json" id="hb-ui">{json.dumps(t, ensure_ascii=False)}</script>
<script type="application/json" id="hb-state"></script>
</head>
<body>
<header class="hb">
  <span class="t">{html.escape(title)}</span>
  <span class="prog">{html.escape(t["progress"])} <span class="bar"><i id="hb-bar"></i></span> <span id="hb-count">0 / 0</span></span>
  <span class="langs">{html.escape(t["lang"])}: {langs}</span>
  <button id="hb-print">{html.escape(t["print"])}</button>
  <button id="hb-reset">{html.escape(t["reset"])}</button>
  <button id="hb-save" class="primary">{html.escape(t["save"])}</button>
  <span id="hb-saved" class="saved"></span>
</header>
<main>
<p class="hint">{html.escape(t["hint"])}</p>
{body}
</main>
<footer>Raj Academy · Governed AI on SAP BTP · generated {datetime.date.today().isoformat()} from {html.escape(src.name)}</footer>
<script>{JS}</script>
</body>
</html>
"""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("out")
    ap.add_argument("--lang", default="en"); ap.add_argument("--title", required=True)
    ap.add_argument("--doc", default="Northwind_Handbook")
    ap.add_argument("--switch", default="", help="lang=path,lang=path")
    a = ap.parse_args()
    switch = dict(kv.split("=", 1) for kv in a.switch.split(",") if kv)
    print(build(Path(a.src), Path(a.out), a.lang, a.title, switch, a.doc))

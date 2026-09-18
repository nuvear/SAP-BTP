"""Policy loader, stages 1 and 2 of RAG: load the documents and split them into passages.

Reads   data/northwind/manifest.json and the 14 documents it lists (text files and PDFs).
Writes  chunks.jsonl: one passage per line, each carrying the metadata the Policy server filters on
        (status, effective dates, audience, classification).

Stage 3 (embedding) happens in the database, see apps/mcp-servers/hana_store.py.

Run:  python loader.py --data ../../data/northwind --out chunks.jsonl
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
import pdfplumber

MAX_CHARS = 1000          # a passage longer than this is split at paragraph boundaries
META_KEYS = ["doc_id", "version", "title", "doc_type", "status", "effective_from", "effective_to",
             "classification", "audience", "owner"]


# ---------------------------------------------------------------- text files
def parse_txt(path: Path) -> list[tuple[str, str]]:
    """Return (section heading, section text) pairs. The '---' metadata header is skipped:
    the manifest is the single source of metadata."""
    raw = path.read_text(encoding="utf-8")
    body = re.sub(r"\A---\n.*?\n---\n", "", raw, flags=re.S)
    raw_blocks = [b.strip() for b in re.split(r"\n\s*\n", body) if b.strip()]
    sections, heading, buf = [], "Introduction", []
    for i, original in enumerate(raw_blocks):
        block = " ".join(original.split())               # re-join the hard-wrapped lines
        # a heading is a single short line that does not end like a sentence
        is_heading = "\n" not in original and len(block) < 80 and not block.endswith((".", "?", ","))
        if i == 0:                                       # the first block is the document title
            continue
        if is_heading:
            if buf: sections.append((heading, buf))
            heading, buf = block, []
        else:
            buf.append(block)
    if buf: sections.append((heading, buf))
    return [(h, p) for h, paras in sections for p in split_long(paras)]


# ---------------------------------------------------------------- PDF files
HEADING_RX = re.compile(r"^(\d+\. [A-Z].{2,70}|Situation \d+: .{3,80}|How to use this runbook|Who to contact)$")
FOOTER_RX = re.compile(r"^(NW-[A-Z]+-\d+ .*Fictional training data.*|Page \d+)$")

def table_to_sentences(table: list[list[str | None]]) -> list[str]:
    """A table row becomes one sentence, 'Header: value; Header: value.', so a row survives as a unit."""
    rows = [[" ".join((c or "").split()) for c in row] for row in table]
    if not rows or rows[0][0] == "Document ID":          # the document-control table on page 1
        return []
    header, out = rows[0], []
    for row in rows[1:]:
        out.append("; ".join(f"{h}: {v}" for h, v in zip(header, row) if v) + ".")
    return out

def parse_pdf(path: Path) -> list[tuple[str, str]]:
    items = []                                           # (page, top, kind, payload)
    with pdfplumber.open(path) as pdf:
        for pno, page in enumerate(pdf.pages):
            tables = page.find_tables()
            boxes = [t.bbox for t in tables]
            for t in tables:
                for s in table_to_sentences(t.extract()):
                    items.append((pno, t.bbox[1], "table", s))
            for line in page.extract_text_lines():
                mid = (line["top"] + line["bottom"]) / 2
                if any(b[1] <= mid <= b[3] for b in boxes):   # text inside a table is handled above
                    continue
                text = " ".join(line["text"].split())
                if text and not FOOTER_RX.match(text):
                    items.append((pno, line["top"], "line", text))
    items.sort(key=lambda it: (it[0], it[1]))

    sections, heading, paras, current = [], "Introduction", [], []
    started = False
    for _, _, kind, text in items:
        if kind == "line" and HEADING_RX.match(text):
            if current: paras.append(" ".join(current)); current = []
            if paras and started: sections.append((heading, paras))
            heading, paras, started = text, [], True
        elif not started:
            continue                                     # title block before the first heading
        elif kind == "table":
            if current: paras.append(" ".join(current)); current = []
            paras.append(text)
        else:
            current.append(text)
            if text.endswith((".", ":")) and len(" ".join(current)) > 350:   # paragraph break heuristic
                paras.append(" ".join(current)); current = []
    if current: paras.append(" ".join(current))
    if paras: sections.append((heading, paras))
    return [(h, p) for h, ps in sections for p in split_long(ps)]


def split_long(paragraphs: list[str]) -> list[str]:
    """Join paragraphs into passages of at most MAX_CHARS, never cutting inside a paragraph."""
    out, cur = [], ""
    for para in paragraphs:
        if cur and len(cur) + len(para) + 1 > MAX_CHARS:
            out.append(cur); cur = ""
        cur = f"{cur} {para}".strip()
    if cur: out.append(cur)
    return out


# ---------------------------------------------------------------- main
def build_chunks(data_dir: Path) -> list[dict]:
    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))["documents"]
    chunks = []
    for doc in manifest:
        path = data_dir / doc["file"]
        sections = parse_pdf(path) if doc["format"] == "pdf" else parse_txt(path)
        for n, (heading, text) in enumerate(sections, 1):
            meta = {k: doc.get(k, "") for k in META_KEYS}
            chunks.append({
                "chunk_id": f"{doc['doc_id']}@{doc['version']}#{n:02d}",
                **meta,
                "effective_to": meta["effective_to"] or None,
                "effective_from": meta["effective_from"] or None,
                "folder": doc["file"].split("/")[0],              # corpus | robustness
                "section": heading,
                # the title and heading travel with the text, so a passage still makes sense on its own
                "text": f"{doc['title']} - {heading}. {text}",
            })
    return chunks


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../../data/northwind")
    ap.add_argument("--out", default="chunks.jsonl")
    args = ap.parse_args()
    chunks = build_chunks(Path(args.data))
    with open(args.out, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    docs = {c["chunk_id"].split("#")[0] for c in chunks}
    print(f"{len(chunks)} passages from {len(docs)} documents -> {args.out}")

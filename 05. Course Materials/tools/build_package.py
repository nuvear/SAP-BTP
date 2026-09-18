"""Build the three-language HTML package from markdown/{en,ja,zh}.

    python3 build_package.py ROOT      # ROOT = the "05. Course Materials" folder (contains markdown/, tools/)

Output: English/, Japanese/, Chinese/ with the student pages and an instructor/ subfolder each.
"""
import re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_handbook import build

LANG_DIR = {"en": "English", "ja": "Japanese", "zh": "Chinese"}
STUDENT = {"03_Student_Workbook": "Northwind_Workbook", "04_Lab_Guide": "Northwind_Lab_Guide", "00_README": "Northwind_README"}
INSTRUCTOR = {"01_Session_Runbook": "Northwind_Runbook", "02_Demo_Script": "Northwind_Demo_Script", "05_Answer_Key": "Northwind_Answer_Key"}


def title_of(md: Path) -> str:
    for line in md.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return md.stem


def main(root: Path):
    src = root / "markdown"
    for lang, folder in LANG_DIR.items():
        for stem, doc in {**STUDENT, **INSTRUCTOR}.items():
            md = src / lang / f"{stem}.md"
            if not md.exists():
                print("missing", md); continue
            sub = "instructor/" if stem in INSTRUCTOR else ""
            name = "index.html" if stem == "00_README" else f"{stem}.html"
            out = root / folder / sub / name
            switch = {l: f"{'../' if sub else ''}../{LANG_DIR[l]}/{sub}{name}" for l in LANG_DIR}
            build(md, out, lang, title_of(md), switch, doc)
            print(out.relative_to(root))


if __name__ == "__main__":
    main(Path(sys.argv[1]).resolve())

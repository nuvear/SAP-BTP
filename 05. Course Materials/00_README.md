# Course materials: Governed AI on SAP BTP

Raj Academy, hands-on course for SAP engineers. Everything in this folder exists in English, Japanese and Simplified Chinese; the code, commands, file names and citations are the same in all three.

## For students

| Page | What it is |
|---|---|
| `03_Student_Workbook.html` | The hands-on workbook: Part A, the laptop lab (no SAP account), and Part B, your own SAP BTP trial tenant. Tick the tasks, type your answers and notes, and click "Save my copy" to download the filled-in file. |
| `04_Lab_Guide.html` | One section per lab: what each persona asks, what comes back, whether it is correct and why. Read after the session. |

Open the page in your language: `English/`, `Japanese/`, `Chinese/`. Every page has a language switch at the top; your ticks and answers are kept per browser and carry over between languages.

The code lives at <https://github.com/nuvear/SAP-BTP>: `apps/` (data service, policy loader, MCP server, deployment guides, the lab conductor) and `data/northwind/` (the 11 policy documents and the 3 robustness documents).

## For the instructor

`instructor/` inside each language folder holds the Session Runbook (the one-day agenda mapped to the deck), the Demo Script (the live demo, question by question) and the Answer Key. These folders are excluded from the public repository by `.gitignore`. The deck is `../04. Governed_AI_on_SAP_BTP.pptx`; the in-session Stage page (one step at a time, with the lab diagrams and the recorded evidence) is a private Claude artifact.

## How the files are made

`markdown/en`, `markdown/ja` and `markdown/zh` hold the sources. The English sources are snapshots of the live Claude Docs (the runbook, the demo script, the workbook and the lab guide); the translations were made from those snapshots. `tools/build_package.py` builds every HTML page from the sources with `tools/build_handbook.py`. After editing a live document, export it again and rebuild.

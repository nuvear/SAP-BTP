# SAP-BTP

Raj Academy teaching material on governed AI on SAP BTP: Claude, MCP and RAG around a protected SAP core.

## Contents

| File | What it is |
|---|---|
| `00. SAP_BTP-_Purpose_and_Recommended_Priority_Order.pptx` | SAP BTP purpose and recommended priority order (deck) |
| `01. Protect_the_Core_and_Platform_Foundation.md` / `.pptx` | Priority 1: protect the core and platform foundation |
| `02. Claude_BTP_MCP_RAG_Protection_Ready_Scenario.md` | Protection-ready scenario: Claude Procurement Exception Advisor on SAP BTP |
| `Claude_BTP_MCP_RAG_Protection_Ready_Architecture.mmd` | Mermaid architecture diagram for the scenario above |
| `03. Northwind_Advisor_BTP_Architecture.mmd` / `.svg` / `.png` | Northwind Advisor architecture on BTP (Mermaid source and renders) |
| `04. Governed_AI_on_SAP_BTP.pptx` / `.pdf` | Governed AI on SAP BTP (deck and PDF export) |
| `data/northwind/` | Fictional Northwind RAG corpus for the labs. See `data/northwind/README.txt` |

## Course materials

`05. Course Materials/` holds the student workbook and the lab guide as interactive HTML pages in English (`English/`), Japanese (`Japanese/`) and Simplified Chinese (`Chinese/`), with the Markdown sources under `markdown/`. Start at `05. Course Materials/00_README.md`. The code for the labs is in `apps/` (data service, policy loader, MCP server, deployment guides, the lab conductor in `apps/lab/`). Instructor materials are not published in this repository.

## Lab data

Everything under `data/northwind/` is fictional training data built on Microsoft's Northwind sample database.

- `corpus/` holds the 11 documents to ingest for the RAG and capstone labs.
- `robustness/` holds 3 extra documents for the robustness lab only (superseded policy, conflicting memo, prompt-injection email).
- `manifest.json` holds the metadata for all 14 documents.

The instructor answer key (`data/northwind/instructor/`) is deliberately excluded from this repository via `.gitignore`.

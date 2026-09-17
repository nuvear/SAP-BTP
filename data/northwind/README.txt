Northwind RAG corpus for Raj Academy
====================================

Everything in this folder is fictional training data. Northwind is
Microsoft's sample database. The policies, memos and notes here were
invented for teaching and are not Microsoft's or any real company's.

Folders
-------

corpus/
    The 11 documents to ingest for the RAG and capstone labs
    (7 text files and 4 PDFs). All are current and consistent with each
    other. One memo is restricted to the London office, and it contains
    one deliberately stale stock figure.

robustness/
    3 extra documents for the robustness lab only: a superseded policy
    version (PDF), an unapproved memo that conflicts with policy, and a
    supplier email that contains a prompt-injection attempt. Load these
    only when you want to test freshness filters, source authority and
    injection handling.

instructor/
    The fact sheet (the single source of truth for every rule) and the
    evaluation set of 32 questions in Markdown and JSON.
    DO NOT ingest this folder. It contains the answers.

manifest.json
    Metadata for all 14 documents: doc_id, version, status, effective
    dates, classification, audience and related entities. The text files
    carry the same metadata in a header block between "---" lines. The
    PDFs carry it in a document-control table on page 1 and in the PDF
    keywords field.

Assumptions
-----------

1. Northwind data is the canonical set (830 orders, 77 products).
2. Every date in the data is shifted forward by exactly 28 years when
   it is loaded. This keeps weekdays and leap years intact. Order dates
   then run from 2024-07-04 to 2026-05-06.
3. The labs use a fixed "today" of Thursday 2026-05-07.
4. The design rule is: numbers that live in tables (stock, prices,
   dates, freight) are never stated in documents. Documents hold the
   rules; the MCP tools supply the facts. The one exception is the
   stale figure in the London memo, which is there on purpose.

Metadata fields used for filtering
----------------------------------

status          current | superseded | unapproved | unverified-external
effective_from  first day the document applies
effective_to    last day it applies (empty means open-ended)
classification  internal | restricted
audience        all-staff | sales | sales-london

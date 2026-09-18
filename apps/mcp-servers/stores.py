"""Policy passage stores.

visible()      the filter that keeps superseded, unapproved, expired and restricted passages out.
               It is pure Python so that it can be tested without a database, and the HANA store
               applies the SAME conditions in SQL (see hana_store.py).
LocalStore     keyword ranking (BM25) over chunks.jsonl. For tests and for laptops without HANA.
               It is NOT semantic search: 'rush job' finds the glossary only because the words match.
"""
from __future__ import annotations
import json, math, re
from collections import Counter
from datetime import date
from pathlib import Path


def visible(chunk: dict, audiences: tuple[str, ...] | list[str], today: date) -> bool:
    """May this passage be shown to this user today?"""
    if chunk["status"] != "current":                       # superseded, unapproved, unverified-external
        return False
    if chunk.get("effective_from") and date.fromisoformat(chunk["effective_from"]) > today:
        return False                                       # not in force yet
    if chunk.get("effective_to") and date.fromisoformat(chunk["effective_to"]) < today:
        return False                                       # expired
    return chunk["audience"] in audiences                  # restricted documents stay with their audience


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class LocalStore:
    def __init__(self, chunks_file: str | Path):
        self.chunks = [json.loads(line) for line in Path(chunks_file).read_text(encoding="utf-8").splitlines() if line]
        self.docs = [_tokens(c["text"]) for c in self.chunks]
        self.df = Counter(t for d in self.docs for t in set(d))
        self.avg_len = sum(len(d) for d in self.docs) / len(self.docs)

    def _score(self, query: list[str], i: int, k1: float = 1.5, b: float = 0.75) -> float:
        doc, tf, n = self.docs[i], Counter(self.docs[i]), len(self.docs)
        score = 0.0
        for t in query:
            if t in tf:
                idf = math.log(1 + (n - self.df[t] + 0.5) / (self.df[t] + 0.5))
                score += idf * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * len(doc) / self.avg_len))
        return score

    def search(self, question: str, audiences, today: date, k: int = 4, strict: bool = True) -> list[dict]:
        """Filter FIRST, rank SECOND. A passage the user may not see is never scored, so it cannot leak
        through a high similarity. strict=False switches the filter off: use it only in the robustness
        lab, to watch what goes wrong without it."""
        query = _tokens(question)
        candidates = [i for i, c in enumerate(self.chunks) if not strict or visible(c, audiences, today)]
        ranked = sorted(((self._score(query, i), i) for i in candidates), reverse=True)
        return [dict(self.chunks[i], score=round(s, 3)) for s, i in ranked[:k] if s > 0]

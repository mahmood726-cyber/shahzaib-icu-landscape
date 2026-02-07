"""
Crossref REST API adapter.

Fetches journal metadata and citation counts for DOIs linked
to enriched publications.  Uses polite pool via mailto header.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Dict, List
from urllib.parse import quote

from sources.base_adapter import BaseAdapter, FetchResult


class CrossrefAdapter(BaseAdapter):

    def fetch_for_trial(self, nct_id: str, context: Dict[str, Any]) -> FetchResult:
        dois = self._get_trial_dois(nct_id)
        if not dois:
            return FetchResult(nct_id, self.source_name, "empty", records=0)

        works: List[Dict[str, Any]] = []
        for doi in dois:
            work = self._get_work(doi)
            if work:
                works.append(work)

        context["_crossref_works"] = works
        if not works:
            return FetchResult(nct_id, self.source_name, "empty", records=0)
        return FetchResult(nct_id, self.source_name, "ok", records=len(works))

    def store_results(self, result: FetchResult, context: Dict[str, Any]) -> None:
        works = context.get("_crossref_works", [])
        if not works:
            return

        now = self._now_utc()
        conn = self._get_conn()
        try:
            for work in works:
                doi = work.get("doi")
                if not doi:
                    continue
                conn.execute(
                    """INSERT OR REPLACE INTO citations
                       (doi, cited_by_count, references_count, source, fetched_utc)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        doi,
                        work.get("cited_by_count", 0),
                        work.get("references_count", 0),
                        self.source_name,
                        now,
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def _get_trial_dois(self, nct_id: str) -> List[str]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT DISTINCT doi FROM publications WHERE nct_id = ? AND doi IS NOT NULL AND doi != ''",
                (nct_id,),
            ).fetchall()
        finally:
            conn.close()
        return [row[0] for row in rows]

    def _get_work(self, doi: str) -> Dict[str, Any] | None:
        """Fetch a single work by DOI from Crossref."""
        safe_doi = quote(doi, safe="")
        url = f"{self.config.base_url}/works/{safe_doi}"
        try:
            data = self._get_json(url)
        except Exception:
            return None

        message = data.get("message", {})
        return {
            "doi": doi,
            "cited_by_count": message.get("is-referenced-by-count", 0),
            "references_count": message.get("references-count", 0),
        }

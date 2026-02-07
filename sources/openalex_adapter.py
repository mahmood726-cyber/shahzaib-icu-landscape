"""
OpenAlex API adapter.

Fetches citation counts, topics, and OA status for DOIs
linked to enriched publications.  Batches up to 50 DOIs per request.
Uses the polite pool (email in User-Agent header).
"""
from __future__ import annotations

import sqlite3
from typing import Any, Dict, List
from urllib.parse import quote

from sources.base_adapter import BaseAdapter, FetchResult


class OpenAlexAdapter(BaseAdapter):

    def fetch_for_trial(self, nct_id: str, context: Dict[str, Any]) -> FetchResult:
        """Fetch OpenAlex works for DOIs associated with this trial."""
        dois = self._get_trial_dois(nct_id)
        if not dois:
            return FetchResult(nct_id, self.source_name, "empty", records=0)

        works = self._get_works_batch(dois)
        context["_openalex_works"] = works
        return FetchResult(nct_id, self.source_name, "ok", records=len(works))

    def store_results(self, result: FetchResult, context: Dict[str, Any]) -> None:
        works = context.get("_openalex_works", [])
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
        """Look up DOIs from the publications table for this trial."""
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT DISTINCT doi FROM publications WHERE nct_id = ? AND doi IS NOT NULL AND doi != ''",
                (nct_id,),
            ).fetchall()
        finally:
            conn.close()
        return [row[0] for row in rows]

    def _get_works_batch(self, dois: List[str]) -> List[Dict[str, Any]]:
        """Fetch OpenAlex works for a batch of DOIs (max 50 per request)."""
        all_works: List[Dict[str, Any]] = []
        for i in range(0, len(dois), 50):
            batch = dois[i : i + 50]
            doi_filter = "|".join(quote(d, safe="/:") for d in batch)
            url = (
                f"{self.config.base_url}/works"
                f"?filter=doi:{doi_filter}"
                f"&per_page=50&select=doi,cited_by_count,referenced_works_count"
            )
            try:
                data = self._get_json(url)
            except Exception:
                continue

            results = data.get("results", [])
            for work in results:
                # Normalize the DOI (OpenAlex returns full URL)
                raw_doi = work.get("doi", "")
                doi = raw_doi.replace("https://doi.org/", "") if raw_doi else ""
                all_works.append({
                    "doi": doi,
                    "cited_by_count": work.get("cited_by_count", 0),
                    "references_count": work.get("referenced_works_count", 0),
                })
        return all_works

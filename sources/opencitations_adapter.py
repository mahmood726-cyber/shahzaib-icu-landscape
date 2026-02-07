"""
OpenCitations COCI adapter.

Fetches citation edges (citing→cited links) for DOIs linked
to enriched publications.
"""
from __future__ import annotations

import sqlite3
from typing import Any, Dict, List
from urllib.parse import quote

from sources.base_adapter import BaseAdapter, FetchResult


class OpenCitationsAdapter(BaseAdapter):

    def fetch_for_trial(self, nct_id: str, context: Dict[str, Any]) -> FetchResult:
        dois = self._get_trial_dois(nct_id)
        if not dois:
            return FetchResult(nct_id, self.source_name, "empty", records=0)

        all_edges: List[Dict[str, Any]] = []
        for doi in dois:
            incoming = self._get_citations(doi)
            outgoing = self._get_references(doi)
            all_edges.extend(incoming)
            all_edges.extend(outgoing)

        context["_opencit_edges"] = all_edges
        if not all_edges:
            return FetchResult(nct_id, self.source_name, "empty", records=0)
        return FetchResult(nct_id, self.source_name, "ok", records=len(all_edges))

    def store_results(self, result: FetchResult, context: Dict[str, Any]) -> None:
        edges = context.get("_opencit_edges", [])
        if not edges:
            return

        now = self._now_utc()
        conn = self._get_conn()
        try:
            for edge in edges:
                conn.execute(
                    """INSERT OR IGNORE INTO citation_edges
                       (citing_doi, cited_doi, direction, source, fetched_utc)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        edge["citing"],
                        edge["cited"],
                        edge["direction"],
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

    def _get_citations(self, doi: str) -> List[Dict[str, str]]:
        """Get incoming citations (papers that cite this DOI)."""
        safe_doi = quote(doi, safe="")
        url = f"{self.config.base_url}/citations/{safe_doi}"
        try:
            data = self._get_json(url)
        except Exception:
            return []

        edges: List[Dict[str, str]] = []
        if isinstance(data, list):
            for item in data:
                citing = item.get("citing", "")
                cited = item.get("cited", "")
                if citing and cited:
                    edges.append({
                        "citing": citing,
                        "cited": cited,
                        "direction": "incoming",
                    })
        return edges

    def _get_references(self, doi: str) -> List[Dict[str, str]]:
        """Get outgoing references (papers this DOI cites)."""
        safe_doi = quote(doi, safe="")
        url = f"{self.config.base_url}/references/{safe_doi}"
        try:
            data = self._get_json(url)
        except Exception:
            return []

        edges: List[Dict[str, str]] = []
        if isinstance(data, list):
            for item in data:
                citing = item.get("citing", "")
                cited = item.get("cited", "")
                if citing and cited:
                    edges.append({
                        "citing": citing,
                        "cited": cited,
                        "direction": "outgoing",
                    })
        return edges

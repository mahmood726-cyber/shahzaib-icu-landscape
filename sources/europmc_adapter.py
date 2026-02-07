"""
Europe PMC REST API adapter.

Searches for publications linked to NCT IDs and retrieves
text-mined annotations (drugs, diseases, organisms).
"""
from __future__ import annotations

import sqlite3
from typing import Any, Dict, List
from urllib.parse import quote_plus

from sources.base_adapter import BaseAdapter, FetchResult


def _name_from_uri(uri: str) -> str:
    """Extract a short name from an annotation URI (last path segment)."""
    if not uri:
        return ""
    stripped = uri.rstrip("/")
    if "/" not in stripped:
        return stripped
    segment = stripped.rsplit("/", 1)[-1]
    return segment or ""


class EuropePMCAdapter(BaseAdapter):

    def fetch_for_trial(self, nct_id: str, context: Dict[str, Any]) -> FetchResult:
        pubs = self._search_nct(nct_id)
        if not pubs:
            return FetchResult(nct_id, self.source_name, "empty", records=0)

        # Fetch annotations for each PMC article
        all_annotations: List[Dict[str, Any]] = []
        for pub in pubs:
            pmcid = pub.get("pmcid")
            # Validate PMCID format before making API call (P-19)
            if pmcid and isinstance(pmcid, str) and pmcid.startswith("PMC"):
                anns = self._get_annotations(pmcid)
                all_annotations.extend(anns)

        context["_europmc_pubs"] = pubs
        context["_europmc_annotations"] = all_annotations
        # Report publication count only (annotations are supplementary)
        return FetchResult(nct_id, self.source_name, "ok", records=len(pubs))

    def store_results(self, result: FetchResult, context: Dict[str, Any]) -> None:
        pubs = context.get("_europmc_pubs", [])
        annotations = context.get("_europmc_annotations", [])
        now = self._now_utc()
        conn = self._get_conn()
        try:
            for pub in pubs:
                conn.execute(
                    """INSERT OR IGNORE INTO publications
                       (nct_id, pmid, pmcid, doi, title, journal, pub_date, pub_type,
                        source, fetched_utc)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        result.nct_id,
                        pub.get("pmid"),
                        pub.get("pmcid"),
                        pub.get("doi"),
                        pub.get("title"),
                        pub.get("journal"),
                        pub.get("pub_date"),
                        pub.get("pub_type"),
                        self.source_name,
                        now,
                    ),
                )

            for ann in annotations:
                conn.execute(
                    """INSERT OR IGNORE INTO annotations
                       (pmid, pmcid, ann_type, ann_name, ann_uri,
                        prefix, exact, suffix, source, fetched_utc)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        ann.get("pmid"),
                        ann.get("pmcid"),
                        ann.get("type", ""),
                        ann.get("name", ""),
                        ann.get("uri"),
                        ann.get("prefix"),
                        ann.get("exact"),
                        ann.get("suffix"),
                        self.source_name,
                        now,
                    ),
                )

            conn.commit()
        finally:
            conn.close()

        # Store content hash for provenance (deterministic via sorted JSON)
        import json
        raw_data = json.dumps(pubs, sort_keys=True).encode("utf-8")
        self.store_hash(f"europmc:{result.nct_id}", self._hash_bytes(raw_data))

    def _search_nct(self, nct_id: str) -> List[Dict[str, Any]]:
        """Search Europe PMC for publications referencing this NCT ID."""
        safe_nct = quote_plus(nct_id)
        url = (
            f"{self.config.base_url}/search"
            f"?query={safe_nct}&format=json&resultType=core&pageSize=100"
        )
        data = self._get_json(url)
        results = data.get("resultList", {}).get("result", [])

        pubs: List[Dict[str, Any]] = []
        for item in results:
            pubs.append({
                "pmid": item.get("pmid"),
                "pmcid": item.get("pmcid"),
                "doi": item.get("doi"),
                "title": item.get("title"),
                "journal": item.get("journalTitle"),
                "pub_date": item.get("firstPublicationDate"),
                "pub_type": item.get("pubType"),
            })
        return pubs

    def _get_annotations(self, pmcid: str) -> List[Dict[str, Any]]:
        """Fetch text-mined annotations for a PMC article."""
        url = f"{self.config.base_url}/{pmcid}/annotations?format=JSON"
        try:
            data = self._get_json(url)
        except Exception as exc:
            import sys
            print(f"    [europmc] annotations failed for {pmcid}: {exc}", file=sys.stderr)
            return []

        annotations: List[Dict[str, Any]] = []
        if not isinstance(data, list):
            return annotations

        for ann in data:
            tags = ann.get("tags", [])
            for tag in tags:
                annotations.append({
                    "pmcid": pmcid,
                    "pmid": ann.get("pmid"),
                    "type": tag.get("name", ""),
                    "name": _name_from_uri(tag.get("uri", "")),
                    "uri": tag.get("uri"),
                    "prefix": ann.get("prefix"),
                    "exact": ann.get("exact"),
                    "suffix": ann.get("suffix"),
                })
        return annotations

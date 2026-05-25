"""
Unpaywall API adapter.

Fetches open access status for DOIs linked to enriched publications.
Disabled by default (requires email configuration).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

from sources.base_adapter import AdapterConfig, BaseAdapter, FetchResult


class UnpaywallAdapter(BaseAdapter):

    def __init__(self, db_path: Path, config: AdapterConfig) -> None:
        super().__init__(db_path, config)
        # Auto-disable if no email configured
        if not config.email:
            self.config.enabled = False

    def fetch_for_trial(self, nct_id: str, context: dict[str, Any]) -> FetchResult:
        if not self.config.email:
            return FetchResult(nct_id, self.source_name, "skipped",
                               error="no email configured")

        dois = self._get_trial_dois(nct_id)
        if not dois:
            return FetchResult(nct_id, self.source_name, "empty", records=0)

        oa_records: list[dict[str, Any]] = []
        for doi in dois:
            record = self._get_oa_status(doi)
            if record:
                oa_records.append(record)

        context["_unpaywall_records"] = oa_records
        if not oa_records:
            return FetchResult(nct_id, self.source_name, "empty", records=0)
        return FetchResult(nct_id, self.source_name, "ok", records=len(oa_records))

    def store_results(self, result: FetchResult, context: dict[str, Any]) -> None:
        records = context.get("_unpaywall_records", [])
        if not records:
            return

        now = self._now_utc()
        conn = self._get_conn()
        try:
            for rec in records:
                conn.execute(
                    """INSERT OR REPLACE INTO open_access
                       (doi, is_oa, oa_status, best_oa_url, license,
                        source, fetched_utc)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        rec["doi"],
                        1 if rec["is_oa"] else 0,
                        rec.get("oa_status"),
                        rec.get("best_oa_url"),
                        rec.get("license"),
                        self.source_name,
                        now,
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def _get_trial_dois(self, nct_id: str) -> list[str]:
        conn = self._get_conn()
        try:
            rows = conn.execute(
                "SELECT DISTINCT doi FROM publications WHERE nct_id = ? AND doi IS NOT NULL AND doi != ''",
                (nct_id,),
            ).fetchall()
        finally:
            conn.close()
        return [row[0] for row in rows]

    def _get_oa_status(self, doi: str) -> dict[str, Any] | None:
        """Fetch OA status for a single DOI."""
        safe_doi = quote(doi, safe="")
        email = quote(self.config.email, safe="@.")
        url = f"{self.config.base_url}/{safe_doi}?email={email}"
        try:
            data = self._get_json(url)
        except Exception:
            return None

        best_oa = data.get("best_oa_location", {}) or {}
        return {
            "doi": doi,
            "is_oa": data.get("is_oa", False),
            "oa_status": data.get("oa_status"),
            "best_oa_url": best_oa.get("url_for_pdf") or best_oa.get("url"),
            "license": best_oa.get("license"),
        }

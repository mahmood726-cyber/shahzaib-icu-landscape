"""
WHO ICTRP adapter.

Parses WHO ICTRP CSV data to find cross-references for NCT IDs.
Uses Python's csv.DictReader for streaming, RFC 4180-compliant parsing.
Supports both automatic download and manual CSV file placement.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from sources.base_adapter import BaseAdapter, AdapterConfig, FetchResult

_NCT_RE = re.compile(r"NCT\d{8}(?!\d)", re.IGNORECASE)


class WHOICTRPAdapter(BaseAdapter):

    def __init__(self, db_path: Path, config: AdapterConfig) -> None:
        super().__init__(db_path, config)
        self._ictrp_index: Optional[Dict[str, List[Dict[str, Any]]]] = None

    def fetch_for_trial(self, nct_id: str, context: Dict[str, Any]) -> FetchResult:
        # Lazy-load the ICTRP index on first call
        if self._ictrp_index is None:
            csv_path = self._find_ictrp_csv()
            if csv_path is None:
                return FetchResult(nct_id, self.source_name, "skipped",
                                   error="WHO ICTRP CSV not found")
            self._ictrp_index = self._load_ictrp_csv(csv_path)

        records = self._ictrp_index.get(nct_id, [])
        if not records:
            return FetchResult(nct_id, self.source_name, "empty", records=0)

        context["_who_records"] = records
        return FetchResult(nct_id, self.source_name, "ok", records=len(records))

    def store_results(self, result: FetchResult, context: Dict[str, Any]) -> None:
        records = context.get("_who_records", [])
        if not records:
            return

        now = self._now_utc()
        conn = self._get_conn()
        try:
            for rec in records:
                conn.execute(
                    """INSERT OR IGNORE INTO who_ictrp
                       (nct_id, trial_id, registry, public_title,
                        recruitment_status, countries, url, source, fetched_utc)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        result.nct_id,
                        rec.get("trial_id", ""),
                        rec.get("registry"),
                        rec.get("public_title"),
                        rec.get("recruitment_status"),
                        rec.get("countries"),
                        rec.get("url"),
                        self.source_name,
                        now,
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def _find_ictrp_csv(self) -> Optional[Path]:
        """Look for WHO ICTRP CSV in enrichment directory (same dir as the DB)."""
        enrichment_dir = self.db_path.parent
        candidates = [
            enrichment_dir / "ICTRPFullExport.csv",
            enrichment_dir / "ictrp_export.csv",
            enrichment_dir / "who_ictrp.csv",
        ]
        # Also check for any CSV starting with ICTRP
        if enrichment_dir.exists():
            for p in enrichment_dir.glob("ICTRP*.csv"):
                candidates.insert(0, p)
            for p in enrichment_dir.glob("ictrp*.csv"):
                candidates.insert(0, p)

        for path in candidates:
            if path.exists():
                return path
        return None

    def _load_ictrp_csv(self, path: Path) -> Dict[str, List[Dict[str, Any]]]:
        """Parse ICTRP CSV and build NCT ID index.

        Uses Python's built-in csv module in streaming mode to handle
        large WHO ICTRP exports (2+ GB) without loading entire file into memory.
        Tries UTF-8 first, falls back to latin-1 for non-UTF-8 WHO exports.
        """
        import csv as csv_mod
        import hashlib

        index: Dict[str, List[Dict[str, Any]]] = {}
        sha = hashlib.sha256()

        # Try UTF-8 first; fall back to latin-1 for WHO exports with accented chars
        encoding = "utf-8"
        try:
            with path.open("r", encoding="utf-8", newline="") as test_fh:
                test_fh.read(4096)
        except UnicodeDecodeError:
            encoding = "latin-1"

        with path.open("r", encoding=encoding, newline="") as fh:
            reader = csv_mod.DictReader(fh)
            # Normalize header names to lowercase for case-insensitive lookup
            if reader.fieldnames:
                reader.fieldnames = [h.strip().lower() for h in reader.fieldnames]

            for row in reader:
                # Hash first 64KB of file content for provenance
                if sha is not None:
                    line_bytes = json.dumps(dict(row), sort_keys=True).encode("utf-8")
                    sha.update(line_bytes)
                    # Stop hashing after ~64KB to keep performance reasonable
                    if fh.tell() > 65536:
                        self.store_hash("who_ictrp:csv", f"sha256:{sha.hexdigest()}")
                        sha = None

                trial_id = row.get("trialid", "")
                secondary_ids = row.get("secondaryids", "")
                nct_ids = _extract_nct_ids(trial_id, secondary_ids)
                if not nct_ids:
                    continue

                record = {
                    "trial_id": trial_id.strip(),
                    "registry": row.get("source_register", "").strip(),
                    "public_title": row.get("public_title", "").strip()[:500],
                    "recruitment_status": row.get("recruitment_status", "").strip(),
                    "countries": row.get("countries", "").strip(),
                    "url": row.get("url", "").strip(),
                }
                for nct in nct_ids:
                    if nct not in index:
                        index[nct] = []
                    index[nct].append(record)

        # Store final hash if file was < 64KB
        if sha is not None:
            self.store_hash("who_ictrp:csv", f"sha256:{sha.hexdigest()}")

        return index


def _extract_nct_ids(trial_id: str, secondary_ids: str) -> List[str]:
    """Extract NCT IDs from trial ID and secondary IDs fields."""
    combined = f"{trial_id};{secondary_ids}"
    matches = _NCT_RE.findall(combined)
    return [m.upper() for m in set(matches)]

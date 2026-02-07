"""
openFDA FAERS API adapter.

Fetches adverse event signal counts for drugs mentioned in trials.
Parses intervention names from the trial context, normalizes drug names,
and queries the FAERS adverse event database.
"""
from __future__ import annotations

import re
import sqlite3
from typing import Any, Dict, List
from urllib.parse import quote_plus

from sources.base_adapter import BaseAdapter, FetchResult


# Dosage/formulation patterns to strip from drug names
_DOSAGE_RE = re.compile(
    r"\b\d+\s*(?:mg|mcg|µg|g|ml|iu|units?|%)\b"
    r"|\b(?:tablet|capsule|injection|infusion|solution|suspension|cream|gel|patch)\b"
    r"|\b(?:oral|iv|im|sc|topical|inhaled)\b"
    r"|\([^)]*\)",
    re.IGNORECASE,
)


class OpenFDAAdapter(BaseAdapter):

    def fetch_for_trial(self, nct_id: str, context: Dict[str, Any]) -> FetchResult:
        drug_names = self._extract_drug_names(nct_id, context)
        if not drug_names:
            return FetchResult(nct_id, self.source_name, "empty", records=0)

        all_signals: List[Dict[str, Any]] = []
        for drug in drug_names:
            signals = self._search_faers(drug)
            for sig in signals:
                sig["drug_name"] = drug
            all_signals.extend(signals)

        context["_openfda_signals"] = all_signals
        if not all_signals:
            return FetchResult(nct_id, self.source_name, "empty", records=0)
        return FetchResult(nct_id, self.source_name, "ok", records=len(all_signals))

    def store_results(self, result: FetchResult, context: Dict[str, Any]) -> None:
        signals = context.get("_openfda_signals", [])
        if not signals:
            return

        now = self._now_utc()
        conn = self._get_conn()
        try:
            for sig in signals:
                conn.execute(
                    """INSERT OR REPLACE INTO faers_signals
                       (nct_id, drug_name, reaction, serious_count, total_count,
                        source, fetched_utc)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        result.nct_id,
                        sig["drug_name"],
                        sig["reaction"],
                        sig.get("serious_count"),
                        sig.get("total_count"),
                        self.source_name,
                        now,
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def _extract_drug_names(self, nct_id: str, context: Dict[str, Any]) -> List[str]:
        """Extract and normalize drug names from trial context or DB."""
        # Try context first (from studies CSV intervention_names)
        raw_names = context.get("intervention_names", "")

        if not raw_names:
            # Fall back to DB trials table
            conn = self._get_conn()
            try:
                row = conn.execute(
                    "SELECT intervention_names FROM trials WHERE nct_id = ?",
                    (nct_id,),
                ).fetchone()
            finally:
                conn.close()
            if row:
                raw_names = row[0] or ""

        if not raw_names:
            return []

        # Split on semicolons and pipes (not / — drug names like "IV/oral" are valid)
        parts = re.split(r"[;|]", raw_names)
        normalized: List[str] = []
        seen: set = set()
        for part in parts:
            name = _normalize_drug_name(part)
            if name and name not in seen and len(name) >= 3:
                seen.add(name)
                normalized.append(name)

        return normalized[:10]  # Cap at 10 drugs per trial

    def _search_faers(self, drug_name: str) -> List[Dict[str, Any]]:
        """Search openFDA FAERS for top adverse reactions for a drug."""
        safe_name = quote_plus(f'"{drug_name}"')
        url = (
            f"{self.config.base_url}"
            f"?search=patient.drug.openfda.generic_name:{safe_name}"
            f"&count=patient.reaction.reactionmeddrapt.exact"
            f"&limit=10"
        )
        try:
            data = self._get_json(url)
        except Exception:
            return []

        results = data.get("results", [])
        signals: List[Dict[str, Any]] = []
        for item in results:
            signals.append({
                "reaction": item.get("term", ""),
                "total_count": item.get("count", 0),
                "serious_count": None,  # FAERS count endpoint doesn't split by seriousness
            })
        return signals


def _normalize_drug_name(name: str) -> str:
    """Normalize a drug name: lowercase, strip dosage/formulation info."""
    name = name.strip()
    name = _DOSAGE_RE.sub("", name)
    name = re.sub(r"\s+", " ", name).strip().lower()
    # Remove trailing/leading punctuation
    name = name.strip(".,;:-")
    # Strip internal double quotes that would break openFDA query syntax
    name = name.replace('"', "")
    return name

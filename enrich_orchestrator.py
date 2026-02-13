#!/usr/bin/env python3
"""
Enrichment orchestrator for the ICU Living Map pipeline.

Queries 8 external data sources and stores results in SQLite.
Respects dependency chain: Phase 1 (PubMed, EuropePMC, openFDA)
runs first to collect PMIDs/DOIs (and drug signals), then Phase 2
(OpenAlex, Crossref, OpenCitations, Unpaywall) uses those DOIs.

Usage:
  python enrich_orchestrator.py --studies output/icu_rct_broad_studies.csv
  python enrich_orchestrator.py --studies output/icu_rct_broad_studies.csv --sources pubmed,openalex --limit 10
  python enrich_orchestrator.py --studies output/icu_rct_broad_studies.csv --max-age-days 7
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = ROOT / "enrichment" / "enrichment_db.sqlite"
DEFAULT_CONFIG_PATH = ROOT / "enrichment_config.json"
DEFAULT_STUDIES_CSV = ROOT / "output" / "icu_rct_broad_studies.csv"
SCHEMA_PATH = ROOT / "enrichment" / "schema.sql"


def init_db(db_path: Path) -> None:
    """Create or verify the enrichment database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = sqlite3.connect(str(db_path))
    try:
        # WAL pragma must be set outside executescript (B-6)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        conn.executescript(schema)
        conn.commit()
    finally:
        conn.close()


def load_config(config_path: Path) -> Dict[str, Any]:
    """Load enrichment configuration.

    The global ``email`` field (used by polite-pool APIs like Unpaywall,
    Crossref, OpenAlex) is resolved from:
      1. ``ENRICHMENT_EMAIL`` environment variable, then
      2. the ``email`` key in the config JSON.
    """
    default: Dict[str, Any] = {"sources": {}, "max_age_days": 30, "email": ""}
    if not config_path.exists():
        cfg = default
    else:
        try:
            cfg = json.loads(config_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"Warning: malformed config {config_path}: {exc}. Using defaults.")
            cfg = default
    # Env var override for email (avoids committing PII into repo)
    env_email = os.environ.get("ENRICHMENT_EMAIL", "")
    if env_email:
        cfg["email"] = env_email

    # Warn if email is empty — polite-pool APIs (Unpaywall, Crossref, OpenAlex)
    # will use default rate-limited endpoints or may reject requests
    if not cfg.get("email"):
        polite_pool_sources = {"unpaywall", "crossref", "openalex"}
        enabled_polite = [
            s for s, sc in cfg.get("sources", {}).items()
            if sc.get("enabled", True) and s in polite_pool_sources
        ]
        if enabled_polite:
            print(
                f"Warning: no email configured for polite-pool APIs ({', '.join(enabled_polite)}). "
                "Set ENRICHMENT_EMAIL env var or 'email' in config for higher rate limits.",
                file=sys.stderr,
            )

    return cfg


_NCT_RE = re.compile(r"^NCT\d{8}$")


def load_trials(studies_csv: Path, db_path: Path, limit: Optional[int] = None) -> List[Dict[str, str]]:
    """Load trial NCT IDs from studies CSV and populate the trials table."""
    trials: List[Dict[str, str]] = []
    with studies_csv.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            nct_id = row.get("nct_id", "").strip().upper()
            if not nct_id or not _NCT_RE.match(nct_id):
                continue
            row["nct_id"] = nct_id  # store normalized
            trials.append(row)
            if limit and len(trials) >= limit:
                break

    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        for row in trials:
            nct_id = row.get("nct_id", "").strip()
            # Build intervention names from arms if available
            intervention_names = ""
            # Try common CSV column names
            for col in ["intervention_names", "interventions", "drug_names"]:
                if row.get(col):
                    intervention_names = row[col]
                    break

            conn.execute(
                """INSERT OR REPLACE INTO trials
                   (nct_id, brief_title, intervention_names, added_utc)
                   VALUES (?, ?, ?, ?)""",
                (nct_id, row.get("brief_title", ""), intervention_names, now),
            )
        conn.commit()
    finally:
        conn.close()

    return trials


class EnrichmentOrchestrator:
    """Orchestrates multi-source enrichment with dependency chain."""

    def __init__(self, db_path: Path, config: Dict[str, Any]) -> None:
        self.db_path = db_path
        self.config = config
        self._adapters: Dict[str, Any] = {}
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        """Return a reusable SQLite connection (avoids open/close churn)."""
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout = 30000")
        return self._conn

    def close(self) -> None:
        """Close the cached SQLite connection."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _load_adapters(
        self, source_names: List[str], effective_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Lazy-load requested adapters."""
        from sources import get_adapter, SOURCE_PHASES
        cfg = effective_config or self.config
        for name in source_names:
            if name not in self._adapters:
                adapter = get_adapter(name, self.db_path, cfg, cfg)
                self._adapters[name] = adapter

    def run(
        self,
        studies_csv: Path,
        sources: Optional[List[str]] = None,
        max_age_days: Optional[int] = None,
        nct_limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Run enrichment pipeline."""
        from sources import SOURCE_PHASES

        # Deep copy to avoid mutating the shared config dict (B-3/P-2)
        effective_config = copy.deepcopy(self.config)
        if max_age_days is not None:
            effective_config["max_age_days"] = max_age_days

        # Determine which sources to run
        all_source_names = list(SOURCE_PHASES.keys())
        if sources:
            requested = [s.strip() for s in sources if s.strip() in SOURCE_PHASES]
        else:
            requested = all_source_names

        # Filter to enabled sources
        enabled = []
        for name in requested:
            src_cfg = self.config.get("sources", {}).get(name, {})
            if src_cfg.get("enabled", True):
                enabled.append(name)

        if not enabled:
            print("No enabled sources to run.")
            return {"status": "empty", "sources": []}

        # Load adapters (pass effective_config so --max-age-days override works)
        self._load_adapters(enabled, effective_config=effective_config)

        # Load trials (deduplicate NCT IDs, preserve order)
        trials = load_trials(studies_csv, self.db_path, limit=nct_limit)
        trial_context = {row.get("nct_id", "").strip(): row for row in trials}
        nct_ids = list(dict.fromkeys(
            row.get("nct_id", "").strip() for row in trials if row.get("nct_id", "").strip()
        ))

        print(f"Enriching {len(nct_ids)} trials from {len(enabled)} sources...")

        # Log run start
        run_id = self._start_run(enabled, len(nct_ids))

        # Guard: every enabled source must have a phase entry (P-3)
        for name in enabled:
            if name not in SOURCE_PHASES:
                raise ValueError(
                    f"Source '{name}' is enabled but not in SOURCE_PHASES. "
                    "Add it to sources/__init__.py before running."
                )
            cfg_phase = self.config.get("sources", {}).get(name, {}).get("phase")
            if cfg_phase is not None and cfg_phase != SOURCE_PHASES.get(name):
                print(
                    f"Warning: config phase {cfg_phase} for '{name}' ignored; "
                    f"using SOURCE_PHASES={SOURCE_PHASES.get(name)}",
                    file=sys.stderr,
                )

        # Split sources by phase — dynamically iterate ALL phases present
        # in SOURCE_PHASES (not just 1 and 2) to avoid silently dropping
        # sources assigned to phase 3+ (e.g., openfda).
        all_phases = sorted(set(SOURCE_PHASES[s] for s in enabled))

        stats: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

        for phase_num in all_phases:
            phase_sources = sorted([s for s in enabled if SOURCE_PHASES[s] == phase_num])
            if not phase_sources:
                continue
            print(f"\n--- Phase {phase_num}: {phase_sources} ---")
            for source_name in phase_sources:
                adapter = self._adapters.get(source_name)
                if not adapter:
                    continue
                print(f"  [{source_name}] processing {len(nct_ids)} trials...")
                for i, nct_id in enumerate(nct_ids):
                    context = dict(trial_context.get(nct_id, {}))
                    result = adapter.enrich(nct_id, context)
                    stats[source_name][result.status] += 1
                    if (i + 1) % 100 == 0:
                        print(f"    {i + 1}/{len(nct_ids)} ({result.status})")
                self._print_source_stats(source_name, stats[source_name])

        # Finish run
        self._finish_run(run_id)

        summary = {
            "status": "ok",
            "nct_count": len(nct_ids),
            "sources": {name: dict(counts) for name, counts in stats.items()},
        }
        print(f"\nEnrichment complete: {len(nct_ids)} trials, {len(enabled)} sources.")
        return summary

    def get_enrichment_summary(self, nct_id: str) -> Dict[str, Any]:
        """Get enrichment summary for a single trial (for dashboard)."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        return self._enrichment_for_nct(conn, nct_id)

    def get_enrichment_summaries(self, nct_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Batch enrichment summaries — single DB connection for all NCT IDs."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        return {nct_id: self._enrichment_for_nct(conn, nct_id) for nct_id in nct_ids}

    @staticmethod
    def _enrichment_for_nct(conn: sqlite3.Connection, nct_id: str) -> Dict[str, Any]:
        """Build enrichment summary for one NCT ID using an existing connection."""
        summary: Dict[str, Any] = {"nct_id": nct_id, "sources": []}

        # Publications
        pubs = conn.execute(
            "SELECT pmid, doi, title, source FROM publications WHERE nct_id = ?",
            (nct_id,),
        ).fetchall()
        summary["pub_count"] = len(pubs)
        summary["pmid_list"] = [r["pmid"] for r in pubs if r["pmid"]]
        summary["doi_list"] = [r["doi"] for r in pubs if r["doi"]]

        # MeSH terms
        pmids = summary["pmid_list"]
        if pmids:
            placeholders = ",".join("?" * len(pmids))
            mesh = conn.execute(
                f"SELECT DISTINCT descriptor_name FROM mesh_terms WHERE pmid IN ({placeholders})",
                pmids,
            ).fetchall()
            summary["mesh_terms"] = [r["descriptor_name"] for r in mesh]
        else:
            summary["mesh_terms"] = []

        # Citations (best from any source)
        dois = summary["doi_list"]
        if dois:
            placeholders = ",".join("?" * len(dois))
            cit = conn.execute(
                f"""SELECT doi, MAX(cited_by_count) as cited_by
                    FROM citations WHERE doi IN ({placeholders})
                    GROUP BY doi""",
                dois,
            ).fetchall()
            summary["cited_by_total"] = sum(r["cited_by"] or 0 for r in cit)
        else:
            summary["cited_by_total"] = 0

        # Open access
        if dois:
            placeholders = ",".join("?" * len(dois))
            oa = conn.execute(
                f"SELECT is_oa, oa_status FROM open_access WHERE doi IN ({placeholders})",
                dois,
            ).fetchall()
            summary["is_oa"] = any(r["is_oa"] for r in oa) if oa else False
            summary["oa_status"] = oa[0]["oa_status"] if oa else None
        else:
            summary["is_oa"] = False
            summary["oa_status"] = None

        # FAERS
        faers = conn.execute(
            "SELECT drug_name, reaction, total_count FROM faers_signals WHERE nct_id = ? ORDER BY total_count DESC LIMIT 10",
            (nct_id,),
        ).fetchall()
        summary["faers_top_reactions"] = [
            {"drug": r["drug_name"], "reaction": r["reaction"], "count": r["total_count"]}
            for r in faers
        ]

        # Sources that contributed data
        sources = conn.execute(
            "SELECT DISTINCT source FROM enrichment_log WHERE nct_id = ? AND status = 'ok'",
            (nct_id,),
        ).fetchall()
        summary["enrichment_sources"] = [r["source"] for r in sources]

        return summary

    def export_dashboard_enrichment(
        self,
        nct_ids: List[str],
        output_path: Path,
    ) -> None:
        """Export per-trial enrichment summaries as JSON for the dashboard."""
        # Use batch method to avoid N+1 DB connections (R7-P0-1)
        enrichment = self.get_enrichment_summaries(nct_ids)
        coverage: Dict[str, int] = defaultdict(int)

        for nct_id, summary in enrichment.items():
            for source in summary.get("enrichment_sources", []):
                coverage[source] += 1

        output = {
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "trial_count": len(nct_ids),
            "source_coverage": dict(coverage),
            "trials": enrichment,
        }

        tmp = output_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(output, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(output_path)
        print(f"Enrichment summary exported to {output_path}")

    def _start_run(self, sources: List[str], nct_count: int) -> int:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        cursor = conn.execute(
            """INSERT INTO enrichment_runs
               (started_utc, sources_requested, nct_count, status)
               VALUES (?, ?, ?, 'running')""",
            (now, ",".join(sources), nct_count),
        )
        conn.commit()
        return cursor.lastrowid

    def _finish_run(self, run_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        conn.execute(
            "UPDATE enrichment_runs SET finished_utc = ?, status = 'done' WHERE run_id = ?",
            (now, run_id),
        )
        conn.commit()

    @staticmethod
    def _print_source_stats(source_name: str, counts: Dict[str, int]) -> None:
        parts = [f"{k}={v}" for k, v in sorted(counts.items())]
        print(f"    [{source_name}] done: {', '.join(parts)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich ICU Living Map with external sources")
    parser.add_argument(
        "--studies",
        default=str(DEFAULT_STUDIES_CSV),
        help="Path to studies CSV with NCT IDs",
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="Path to enrichment SQLite database",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to enrichment config JSON",
    )
    parser.add_argument(
        "--sources",
        default=None,
        help="Comma-separated list of sources to run (default: all enabled)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of NCT IDs to process",
    )
    parser.add_argument(
        "--max-age-days",
        type=int,
        default=None,
        help="Override max age in days for incremental fetching",
    )
    parser.add_argument(
        "--export-dashboard",
        default=None,
        help="Path to write dashboard enrichment JSON",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    config = load_config(Path(args.config))

    # Initialize database
    init_db(db_path)

    orchestrator = EnrichmentOrchestrator(db_path, config)

    source_list = args.sources.split(",") if args.sources else None

    result = orchestrator.run(
        studies_csv=Path(args.studies),
        sources=source_list,
        max_age_days=args.max_age_days,
        nct_limit=args.limit,
    )

    if args.export_dashboard:
        # Load all NCT IDs from DB using orchestrator's shared connection
        conn = orchestrator._get_conn()
        rows = conn.execute("SELECT nct_id FROM trials").fetchall()
        nct_ids = [r[0] for r in rows]
        orchestrator.export_dashboard_enrichment(nct_ids, Path(args.export_dashboard))

    orchestrator.close()
    return 0 if result.get("status") != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())

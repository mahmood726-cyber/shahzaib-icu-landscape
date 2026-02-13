#!/usr/bin/env python3
"""
TruthCert validators for the ICU Living Map pipeline.

16 base validation rules (+ 5 enrichment-conditional) across three severity classes:
  P0 (Block)  — hard failures that invalidate the capsule
  P1 (Warn)   — quality concerns that degrade the badge
  P2 (Info)   — informational checks logged for provenance
"""
from __future__ import annotations

import csv
import os
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set


@dataclass
class ValidationResult:
    rule_id: str
    severity: str  # "P0", "P1", "P2"
    passed: bool
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── Expected CSV headers ─────────────────────────────────────────────

STUDIES_COLUMNS = [
    "nct_id", "brief_title", "official_title", "overall_status", "study_type",
    "allocation", "primary_purpose", "intervention_model", "masking",
    "masking_description", "masking_subjects", "phase", "start_date",
    "completion_date", "last_update_posted", "results_first_posted",
    "has_results", "enrollment_count", "enrollment_type", "conditions",
    "keywords", "arm_count", "placebo_arm_count", "outcome_count",
    "hemo_outcome_count", "countries", "updated_since", "query_name",
]

HEMO_COLUMNS = [
    "nct_id", "outcome_type", "measure", "keyword", "matched_text", "query_name",
]

OUTPUT_COLUMNS = [
    "nct_id", "brief_title", "overall_status", "allocation",
    "intervention_model", "masking", "masking_description", "masking_subjects",
    "phase", "start_date", "completion_date", "last_update_posted",
    "results_first_posted", "enrollment_count", "enrollment_type",
    "conditions", "study_keywords", "arm_count", "placebo_arm_count",
    "has_placebo_arm", "outcome_type", "measure", "keyword",
    "normalized_keyword", "unit_raw", "normalized_unit", "matched_text",
    "query_name", "countries", "data_sources",
]

SUMMARY_TOTAL_FIELDS = [
    "total_studies", "studies_with_placebo", "studies_with_hemo_mentions",
    "studies_with_hemo_and_placebo", "total_hemo_mentions",
    "core_hemo_mentions", "adjunct_mentions",
    "placebo_hemo_mentions", "non_placebo_hemo_mentions",
]

_NCT_RE = re.compile(r"^NCT\d{8}$")


def _read_csv_header(path: Path) -> Optional[List[str]]:
    """Return the header row of a CSV file, or None if file is missing/empty."""
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        try:
            return next(reader)
        except StopIteration:
            return None


def _read_csv_column(path: Path, column: str, max_rows: int = 500) -> List[str]:
    """Read up to max_rows values from a single CSV column."""
    values: List[str] = []
    if not path.exists():
        return values
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            val = row.get(column, "").strip()
            if val:
                values.append(val)
    return values


# ── P0 validators (Block) ────────────────────────────────────────────

def validate_schema_studies(studies_csv: Path) -> ValidationResult:
    """P0-schema-studies: Verify studies CSV has the expected header columns."""
    header = _read_csv_header(studies_csv)
    if header is None:
        return ValidationResult("P0-schema-studies", "P0", False,
                                f"Studies CSV not found or empty: {studies_csv}")
    missing = [c for c in STUDIES_COLUMNS if c not in header]
    if missing:
        return ValidationResult("P0-schema-studies", "P0", False,
                                f"Missing columns in studies CSV: {missing}")
    return ValidationResult("P0-schema-studies", "P0", True,
                            f"Studies CSV has all {len(STUDIES_COLUMNS)} expected columns")


def validate_schema_hemo(hemo_csv: Path) -> ValidationResult:
    """P0-schema-hemo: Verify hemodynamic mentions CSV has the expected header."""
    header = _read_csv_header(hemo_csv)
    if header is None:
        return ValidationResult("P0-schema-hemo", "P0", False,
                                f"Hemo CSV not found or empty: {hemo_csv}")
    missing = [c for c in HEMO_COLUMNS if c not in header]
    if missing:
        return ValidationResult("P0-schema-hemo", "P0", False,
                                f"Missing columns in hemo CSV: {missing}")
    return ValidationResult("P0-schema-hemo", "P0", True,
                            f"Hemo CSV has all {len(HEMO_COLUMNS)} expected columns")


def validate_schema_output(output_csv: Path) -> ValidationResult:
    """P0-schema-output: Verify output living map CSV has the expected header."""
    header = _read_csv_header(output_csv)
    if header is None:
        return ValidationResult("P0-schema-output", "P0", False,
                                f"Output CSV not found or empty: {output_csv}")
    missing = [c for c in OUTPUT_COLUMNS if c not in header]
    if missing:
        return ValidationResult("P0-schema-output", "P0", False,
                                f"Missing columns in output CSV: {missing}")
    return ValidationResult("P0-schema-output", "P0", True,
                            f"Output CSV has all {len(OUTPUT_COLUMNS)} expected columns")


def validate_summary_totals(summary: Dict[str, Any]) -> ValidationResult:
    """P0-summary-totals: All expected total fields present and non-negative integers."""
    totals = summary.get("totals", {})
    problems: List[str] = []
    for field in SUMMARY_TOTAL_FIELDS:
        val = totals.get(field)
        if val is None:
            problems.append(f"{field} missing")
        elif not isinstance(val, int) or val < 0:
            problems.append(f"{field}={val} (not non-negative int)")
    if problems:
        return ValidationResult("P0-summary-totals", "P0", False,
                                f"Summary totals issues: {'; '.join(problems)}")
    return ValidationResult("P0-summary-totals", "P0", True,
                            f"All {len(SUMMARY_TOTAL_FIELDS)} summary total fields are valid non-negative integers")


_TRIAL_ID_RE = re.compile(
    r"^(?:"
    r"NCT\d{8}"              # ClinicalTrials.gov
    r"|PMID:\d+"             # PubMed primary
    r"|EUCTR[-\d]+"          # EU Clinical Trials Register
    r"|ISRCTN\d+"            # ISRCTN
    r"|ACTRN\d+"             # Australian NZ CTR
    r"|ChiCTR[-\w]+"         # Chinese CTR
    r"|DRKS\d+"              # German CTR
    r"|JPRN[-\w]+"           # Japan CTR
    r"|CTRI/[-\w/]+"         # India CTR
    r"|PACTR\d+"             # Pan African CTR
    r"|REBEC[-\w]+"          # Brazilian CTR
    r"|KCT\d+"               # Korean CTR
    r"|IRCT[-\w]+"           # Iranian CTR
    r"|TCTR\d+"              # Thai CTR
    r"|SLCTR/[-\w/]+"        # Sri Lanka CTR
    r"|RPCEC[-\w]+"          # Cuban CTR
    r"|PER[-\w]+"            # Peruvian CTR
    r"|NTR\d+"               # Netherlands CTR
    r"|[\w]+-[\w]+-\d+"      # Other registry formats (e.g., LBCTR-xxx-nnn)
    r")$"
)


def validate_nct_format(output_csv: Path) -> ValidationResult:
    """P0-nct-format: ALL trial IDs match a known registry pattern (V-7).

    Accepts NCT IDs (ClinicalTrials.gov) and PMID:nnn (PubMed primary).
    """
    nct_ids = _read_csv_column(output_csv, "nct_id", max_rows=50_000)
    if not nct_ids:
        return ValidationResult("P0-nct-format", "P0", False,
                                "No trial IDs found in output CSV")
    bad = [nid for nid in nct_ids if not _TRIAL_ID_RE.match(nid)]
    if bad:
        sample = bad[:5]
        return ValidationResult("P0-nct-format", "P0", False,
                                f"{len(bad)} malformed trial IDs (sample: {sample})")
    nct_count = sum(1 for nid in nct_ids if nid.startswith("NCT"))
    non_nct = len(nct_ids) - nct_count
    msg = f"All {len(nct_ids)} sampled trial IDs are valid"
    if non_nct > 0:
        msg += f" ({nct_count} NCT, {non_nct} other registries)"
    return ValidationResult("P0-nct-format", "P0", True, msg)


def validate_total_consistency(summary: Dict[str, Any]) -> ValidationResult:
    """P0-total-consistency: total_hemo == placebo + non_placebo == core + adjunct."""
    totals = summary.get("totals", {})
    total = totals.get("total_hemo_mentions", 0)
    placebo = totals.get("placebo_hemo_mentions", 0)
    non_placebo = totals.get("non_placebo_hemo_mentions", 0)
    core = totals.get("core_hemo_mentions", 0)
    adjunct = totals.get("adjunct_mentions", 0)
    problems = []
    if total != placebo + non_placebo:
        problems.append(f"total({total}) != placebo({placebo}) + non_placebo({non_placebo})")
    if total != core + adjunct:
        problems.append(f"total({total}) != core({core}) + adjunct({adjunct})")
    if problems:
        return ValidationResult(
            "P0-total-consistency", "P0", False,
            f"Mention totals inconsistent: {'; '.join(problems)}")
    return ValidationResult("P0-total-consistency", "P0", True,
                            f"Mention totals consistent: {total} = {placebo}+{non_placebo} = {core}+{adjunct}")


def validate_referential_integrity(summary: Dict[str, Any]) -> ValidationResult:
    """P1-referential-integrity: No orphan hemo NCT IDs missing from studies CSV."""
    totals = summary.get("totals", {})
    orphans = totals.get("orphan_hemo_nct_ids", 0)
    if orphans > 0:
        return ValidationResult(
            "P1-referential-integrity", "P1", False,
            f"{orphans} hemo NCT ID(s) not found in studies CSV (orphan rows with blank metadata)")
    return ValidationResult("P1-referential-integrity", "P1", True,
                            "All hemo NCT IDs have corresponding study records")


# ── P1 validators (Warn) ─────────────────────────────────────────────

def validate_keyword_coverage(summary: Dict[str, Any], config_keywords: List[str]) -> ValidationResult:
    """P1-keyword-coverage: >=80% of config keywords appear in normalized_keywords."""
    found = {item["keyword"] for item in summary.get("normalized_keywords", [])}
    if not config_keywords:
        return ValidationResult("P1-keyword-coverage", "P1", True,
                                "No config keywords to check")
    present = sum(1 for kw in config_keywords if kw in found)
    ratio = present / len(config_keywords)
    passed = ratio >= 0.80
    return ValidationResult(
        "P1-keyword-coverage", "P1", passed,
        f"{present}/{len(config_keywords)} config keywords found ({ratio:.0%}); threshold 80%")


def validate_normalization_coverage(summary: Dict[str, Any]) -> ValidationResult:
    """P1-normalization-coverage: <=5% of normalized keywords are 'Unmapped'."""
    keywords = summary.get("normalized_keywords", [])
    total_mentions = sum(item.get("mention_count", 0) for item in keywords)
    unmapped_mentions = sum(
        item.get("mention_count", 0) for item in keywords
        if item.get("keyword", "").lower() == "unmapped"
    )
    if total_mentions == 0:
        return ValidationResult("P1-normalization-coverage", "P1", True,
                                "No keyword mentions to evaluate")
    ratio = unmapped_mentions / total_mentions
    passed = ratio <= 0.05
    return ValidationResult(
        "P1-normalization-coverage", "P1", passed,
        f"{unmapped_mentions}/{total_mentions} mentions unmapped ({ratio:.1%}); threshold 5%")


def validate_unit_coverage(summary: Dict[str, Any]) -> ValidationResult:
    """P1-unit-coverage: <=40% of mentions have empty/Unspecified units."""
    units = summary.get("units", [])
    total_mentions = sum(item.get("mention_count", 0) for item in units)
    unspecified = sum(
        item.get("mention_count", 0) for item in units
        if item.get("unit", "").lower() in ("", "unspecified")
    )
    if total_mentions == 0:
        return ValidationResult("P1-unit-coverage", "P1", True,
                                "No unit mentions to evaluate")
    ratio = unspecified / total_mentions
    passed = ratio <= 0.40
    return ValidationResult(
        "P1-unit-coverage", "P1", passed,
        f"{unspecified}/{total_mentions} mentions unspecified ({ratio:.1%}); threshold 40%")


def validate_empty_summary_sections(summary: Dict[str, Any]) -> ValidationResult:
    """P1-empty-summary-sections: All 5 list sections (keywords, normalized_keywords,
    units, outcome_types, conditions) are non-empty."""
    sections = ["keywords", "normalized_keywords", "units", "outcome_types", "conditions"]
    empty = [s for s in sections if not summary.get(s)]
    if empty:
        return ValidationResult("P1-empty-summary-sections", "P1", False,
                                f"Empty summary sections: {empty}")
    return ValidationResult("P1-empty-summary-sections", "P1", True,
                            "All 5 summary sections are non-empty")


# ── P2 validators (Info) ─────────────────────────────────────────────

def validate_ontology_version_logged(ontology_version: Optional[str]) -> ValidationResult:
    """P2-ontology-version-logged: Ontology version string is present."""
    if ontology_version:
        return ValidationResult("P2-ontology-version-logged", "P2", True,
                                f"Ontology version: {ontology_version[:24]}...")
    return ValidationResult("P2-ontology-version-logged", "P2", False,
                            "Ontology version not computed")


def validate_raw_input_hashed(input_hashes: Dict[str, str]) -> ValidationResult:
    """P2-raw-input-hashed: At least one raw input file hash is recorded."""
    if input_hashes:
        return ValidationResult("P2-raw-input-hashed", "P2", True,
                                f"{len(input_hashes)} input file(s) hashed")
    return ValidationResult("P2-raw-input-hashed", "P2", False,
                            "No input file hashes recorded")


def validate_parquet_generated(summary: Dict[str, Any]) -> ValidationResult:
    """P2-parquet-generated: Parquet export succeeded."""
    parquet = summary.get("parquet", {})
    if parquet.get("status") == "ok":
        return ValidationResult("P2-parquet-generated", "P2", True,
                                f"Parquet generated via {parquet.get('method', '?')}")
    return ValidationResult("P2-parquet-generated", "P2", False,
                            f"Parquet not generated: {parquet.get('reason', 'unknown')}")


# ── Enrichment validators (only run when enrichment present) ────────

def validate_enrichment_coverage(summary: Dict[str, Any]) -> ValidationResult:
    """P1-enrichment-coverage: >=30% of hemo-trial NCT IDs have linked publications."""
    enrichment = summary.get("enrichment", {})
    if not enrichment.get("enabled"):
        return ValidationResult("P1-enrichment-coverage", "P1", True,
                                "Enrichment not enabled — skipped")
    enriched = enrichment.get("enriched_trials", 0)
    totals = summary.get("totals", {})
    total_hemo = totals.get("studies_with_hemo_mentions", 0)
    if total_hemo == 0:
        return ValidationResult("P1-enrichment-coverage", "P1", True,
                                "No hemo trials to check")
    ratio = min(enriched / total_hemo, 1.0)  # Cap at 100% (enriched may include non-hemo trials)
    passed = ratio >= 0.30
    return ValidationResult(
        "P1-enrichment-coverage", "P1", passed,
        f"{enriched}/{total_hemo} trials enriched ({ratio:.0%}); threshold 30%")


def validate_enrichment_staleness(enrich_db: Optional[Path]) -> ValidationResult:
    """P1-enrichment-staleness: Oldest enrichment record < 60 days."""
    if enrich_db is None or not enrich_db.exists():
        return ValidationResult("P1-enrichment-staleness", "P1", True,
                                "No enrichment DB — skipped")
    import sqlite3
    from datetime import datetime, timezone
    conn = None
    try:
        conn = sqlite3.connect(str(enrich_db))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        # Check oldest of the most-recent fetches per (nct_id, source),
        # not MIN across all history (which anchors to first-ever fetch)
        row = conn.execute(
            """SELECT MIN(latest_utc) FROM (
                SELECT MAX(fetched_utc) AS latest_utc
                FROM enrichment_log
                WHERE status = 'ok'
                GROUP BY nct_id, source
            )"""
        ).fetchone()
    except sqlite3.DatabaseError as exc:
        return ValidationResult("P1-enrichment-staleness", "P1", False,
                                f"Enrichment DB error: {exc}")
    finally:
        if conn is not None:
            conn.close()

    if row is None or row[0] is None:
        return ValidationResult("P1-enrichment-staleness", "P1", True,
                                "No enrichment records to check")
    try:
        # Python <3.11 fromisoformat() cannot parse "+00:00" TZ suffix — strip it
        ts_str = row[0]
        if ts_str.endswith("+00:00"):
            ts_str = ts_str[:-6]
        elif ts_str.endswith("Z"):
            ts_str = ts_str[:-1]
        oldest = datetime.fromisoformat(ts_str)
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=timezone.utc)
        else:
            oldest = oldest.astimezone(timezone.utc)
        age_days = (datetime.now(timezone.utc) - oldest).total_seconds() / 86400
    except (ValueError, TypeError):
        return ValidationResult("P1-enrichment-staleness", "P1", False,
                                "Cannot parse oldest enrichment timestamp")

    passed = age_days < 60
    return ValidationResult(
        "P1-enrichment-staleness", "P1", passed,
        f"Oldest enrichment record is {age_days:.0f} days old; threshold 60 days")


def validate_enrichment_source_diversity(summary: Dict[str, Any]) -> ValidationResult:
    """P1-enrichment-source-diversity: >=3 of 8 sources contributed data."""
    enrichment = summary.get("enrichment", {})
    if not enrichment.get("enabled"):
        return ValidationResult("P1-enrichment-source-diversity", "P1", True,
                                "Enrichment not enabled — skipped")
    coverage = enrichment.get("source_coverage", {})
    active_sources = sum(1 for v in coverage.values() if v > 0)
    passed = active_sources >= 3
    return ValidationResult(
        "P1-enrichment-source-diversity", "P1", passed,
        f"{active_sources} active sources; threshold 3")


def validate_enrichment_db_exists(enrich_db: Optional[Path]) -> ValidationResult:
    """P2-enrichment-db-exists: SQLite file exists and is readable."""
    if enrich_db is None:
        return ValidationResult("P2-enrichment-db-exists", "P2", True,
                                "No enrichment DB path specified — skipped")
    if enrich_db.exists():
        size_kb = enrich_db.stat().st_size / 1024
        return ValidationResult("P2-enrichment-db-exists", "P2", True,
                                f"Enrichment DB exists ({size_kb:.0f} KB)")
    return ValidationResult("P2-enrichment-db-exists", "P2", False,
                            f"Enrichment DB not found: {enrich_db}")


def validate_enrichment_hashes(enrich_db: Optional[Path]) -> ValidationResult:
    """P2-enrichment-hashes: At least one source hash recorded in DB."""
    if enrich_db is None or not enrich_db.exists():
        return ValidationResult("P2-enrichment-hashes", "P2", True,
                                "No enrichment DB — skipped")
    import sqlite3
    conn = None
    try:
        conn = sqlite3.connect(str(enrich_db))
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout = 30000")
        row = conn.execute("SELECT COUNT(*) FROM source_hashes").fetchone()
    except sqlite3.DatabaseError as exc:
        return ValidationResult("P2-enrichment-hashes", "P2", False,
                                f"Enrichment DB error: {exc}")
    finally:
        if conn is not None:
            conn.close()
    count = row[0] if row else 0
    passed = count > 0
    return ValidationResult(
        "P2-enrichment-hashes", "P2", passed,
        f"{count} source hash(es) recorded")


# ── P2 search quality validators ──────────────────────────────────────

def _get_tooling_root() -> Path:
    """Resolve ctgov-search-strategies toolkit root (shared with fetch script)."""
    return Path(
        os.environ.get("CTGOV_TOOLING_ROOT",
                       Path(__file__).resolve().parent.parent / "ctgov-search-strategies")
    )


def validate_search_quality(summary: Dict[str, Any]) -> ValidationResult:
    """P2-search-quality: Run PRESS 2015 syntax check on the search query.

    Note: PRESS 2015 (McGowan et al.) was designed for bibliographic database
    searches (MEDLINE/Embase), not registry queries. CT.gov lacks MeSH headings
    and proximity operators, so PRESS element scores for those categories are
    not meaningful. The overall score is reported as indicative only.
    """
    search_strategy = summary.get("search_strategy", {})
    query_text = search_strategy.get("query_text", "")
    if not query_text:
        return ValidationResult("P2-search-quality", "P2", True,
                                "No query text available — skipped")
    try:
        tooling_root = _get_tooling_root()
        if str(tooling_root) not in sys.path:
            sys.path.insert(0, str(tooling_root))
        from search_methodology import PRESSValidator  # type: ignore
        report = PRESSValidator().validate(query_text, database="ClinicalTrials.gov")
        passed = report.is_acceptable
        return ValidationResult(
            "P2-search-quality", "P2", passed,
            f"PRESS score {report.overall_score:.2f} "
            f"({'acceptable' if passed else 'below 0.70'}) "
            f"— indicative only (PRESS designed for bibliographic DBs, not registry queries)")
    except ImportError:
        return ValidationResult("P2-search-quality", "P2", True,
                                "PRESSValidator not available (ctgov-search-strategies not on path) — skipped")
    except Exception as exc:
        return ValidationResult("P2-search-quality", "P2", False,
                                f"PRESS validation error: {exc}")


def validate_recall_reference_standard(
    summary: Dict[str, Any],
    studies_csv: Path,
) -> ValidationResult:
    """P2-recall-reference: Check recall against curated reference-standard NCT IDs.

    Checks the studies CSV (raw search results) rather than the output CSV
    (post-hemo filtering), because this validates search query coverage,
    not downstream outcome filtering.

    Uses "reference standard" (not "gold standard") per Cochrane Handbook
    terminology — this is a curated convenience set, not an exhaustive truth.
    """
    search_strategy = summary.get("search_strategy", {})
    ref_ids = search_strategy.get("recall_reference_nct_ids", [])
    if not ref_ids:
        return ValidationResult("P2-recall-reference", "P2", True,
                                "No reference-standard NCT IDs configured — skipped")
    # Read NCT IDs from the studies CSV (search results, pre-hemo filtering)
    found_ids = set(_read_csv_column(studies_csv, "nct_id", max_rows=100_000))
    ref_set = set(ref_ids)
    matched = ref_set & found_ids
    recall = len(matched) / len(ref_set) if ref_set else 0.0
    missed = sorted(ref_set - found_ids)
    msg = f"{len(matched)}/{len(ref_set)} reference-standard NCT IDs found ({recall:.0%})"
    if missed:
        msg += f"; missed: {missed[:5]}"
    return ValidationResult("P2-recall-reference", "P2", recall >= 0.50, msg)


# ── Multi-source validators ──────────────────────────────────────────

def validate_multi_source_coverage(summary: Dict[str, Any]) -> ValidationResult:
    """P1-multi-source-coverage: At least 2 of 2 primary sources contributed records."""
    flow = summary.get("prisma_flow", {})
    ctgov = flow.get("ctgov_retrieved", 0)
    pubmed = flow.get("pubmed_retrieved", 0)
    active = sum(1 for count in [ctgov, pubmed] if count > 0)
    passed = active >= 2
    return ValidationResult(
        "P1-multi-source-coverage", "P1", passed,
        f"{active}/2 primary sources active (CT.gov={ctgov}, PubMed={pubmed}); threshold 2")


def validate_dedup_integrity(output_csv: Path) -> ValidationResult:
    """P1-dedup-integrity: No duplicate trial IDs from different sources without merge.

    Multiple rows per trial is expected (one per hemo mention). But the same
    trial_id should NOT appear with conflicting data_sources — that indicates
    the multi-source dedup failed to merge records properly.
    """
    if not output_csv.exists():
        return ValidationResult("P1-dedup-integrity", "P1", True,
                                "Output CSV not found — skipped")
    trial_sources: Dict[str, Set[str]] = {}
    with output_csv.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for i, row in enumerate(reader):
            if i >= 100_000:
                break
            nct_id = (row.get("nct_id") or "").strip()
            sources = (row.get("data_sources") or "ctgov").strip()
            if nct_id:
                if nct_id not in trial_sources:
                    trial_sources[nct_id] = set()
                trial_sources[nct_id].add(sources)
    if not trial_sources:
        return ValidationResult("P1-dedup-integrity", "P1", True,
                                "No trial IDs to check")
    # Flag trials that appear with inconsistent data_sources strings
    # (e.g., same NCT ID with "ctgov" in one row and "ctgov;pubmed" in another)
    inconsistent = [
        tid for tid, src_set in trial_sources.items()
        if len(src_set) > 1
    ]
    if inconsistent:
        sample = inconsistent[:5]
        return ValidationResult(
            "P1-dedup-integrity", "P1", False,
            f"{len(inconsistent)} trial(s) with inconsistent data_sources (sample: {sample})")
    return ValidationResult("P1-dedup-integrity", "P1", True,
                            f"{len(trial_sources)} unique trials checked — dedup consistent")


def validate_registry_diversity(summary: Dict[str, Any]) -> ValidationResult:
    """P2-registry-diversity: Report number of distinct registries represented."""
    registries = summary.get("registries", {})
    count = len(registries)
    total_trials = sum(registries.values()) if registries else 0
    return ValidationResult(
        "P2-registry-diversity", "P2", True,
        f"{count} distinct registries represented ({total_trials} total trials)")


def validate_enrollment_plausibility(studies_csv: Path) -> ValidationResult:
    """P1-enrollment-plausibility: Flag studies with implausible enrollment counts."""
    if not studies_csv.exists():
        return ValidationResult("P1-enrollment-plausibility", "P1", True, "no studies CSV")
    flagged = []
    try:
        with studies_csv.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                enr = row.get("enrollment_count", "")
                if not enr:
                    continue
                try:
                    n = int(enr)
                except (ValueError, TypeError):
                    continue
                etype = (row.get("enrollment_type") or "").upper()
                nct = row.get("nct_id", "?")
                if n > 50000:
                    flagged.append(f"{nct}: enrollment={n} (>50K)")
                elif n == 0 and etype == "ACTUAL":
                    flagged.append(f"{nct}: enrollment=0 (ACTUAL)")
    except OSError:
        return ValidationResult("P1-enrollment-plausibility", "P1", True, "could not read CSV")
    if flagged:
        return ValidationResult(
            "P1-enrollment-plausibility", "P1", False,
            f"{len(flagged)} implausible enrollment(s): {'; '.join(flagged[:5])}")
    return ValidationResult("P1-enrollment-plausibility", "P1", True, "all enrollments plausible")


# ── Orchestrator ──────────────────────────────────────────────────────

def run_validators(
    studies_csv: Path,
    hemo_csv: Path,
    output_csv: Path,
    summary: Dict[str, Any],
    ontology_version: Optional[str],
    input_hashes: Dict[str, str],
    config_keywords: Optional[List[str]] = None,
    enrich_db: Optional[Path] = None,
) -> List[ValidationResult]:
    """Run all validators and return the results."""
    if config_keywords is None:
        config_keywords = []

    results: List[ValidationResult] = [
        # P0 — Block
        validate_schema_studies(studies_csv),
        validate_schema_hemo(hemo_csv),
        validate_schema_output(output_csv),
        validate_summary_totals(summary),
        validate_nct_format(output_csv),
        validate_total_consistency(summary),
        # P1 — Warn
        validate_referential_integrity(summary),
        validate_keyword_coverage(summary, config_keywords),
        validate_normalization_coverage(summary),
        validate_unit_coverage(summary),
        validate_empty_summary_sections(summary),
        # P2 — Info
        validate_ontology_version_logged(ontology_version),
        validate_raw_input_hashed(input_hashes),
        validate_parquet_generated(summary),
        # P2 — Search strategy
        validate_search_quality(summary),
        validate_recall_reference_standard(summary, studies_csv),
        # P1 — Enrollment plausibility
        validate_enrollment_plausibility(studies_csv),
        # Multi-source validators
        validate_multi_source_coverage(summary),
        validate_dedup_integrity(output_csv),
        validate_registry_diversity(summary),
    ]

    # Enrichment validators (only when enrichment data is present)
    enrichment = summary.get("enrichment", {})
    if enrichment.get("enabled"):
        results.extend([
            validate_enrichment_coverage(summary),
            validate_enrichment_staleness(enrich_db),
            validate_enrichment_source_diversity(summary),
            validate_enrichment_db_exists(enrich_db),
            validate_enrichment_hashes(enrich_db),
        ])

    return results

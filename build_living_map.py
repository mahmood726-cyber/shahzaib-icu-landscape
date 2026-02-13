#!/usr/bin/env python3
"""
Build a living map dataset from CT.gov ICU RCT exports.
"""
from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from truthcert import build_capsule

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = ROOT / "output"
DEFAULT_DASHBOARD_DIR = ROOT / "dashboard" / "data"
DEFAULT_LABEL = "broad"


# Categories that are NOT pure hemodynamic parameters. These are included
# for clinical relevance but are reported separately from core hemodynamic
# totals to avoid inflating the evidence count.
#   - ICU Severity Score: SOFA/APACHE/SAPS are multi-organ composite indices;
#     only the cardiovascular subscore is hemodynamic.
#   - Ventilation duration: respiratory outcome, not hemodynamic.
#   - Resuscitation Endpoints: metabolic markers (base deficit, anion gap).
NON_HEMODYNAMIC_ADJUNCTS = frozenset([
    "ICU Severity Score",
    "Ventilation duration",
    "Resuscitation Endpoints",
])

CANONICAL_RULES = [
    # Specific multi-word rules MUST come before their general counterparts
    # to prevent substring shadowing (e.g., "vasopressor-free days" must not
    # match "vasopressor" from the Vasopressor/Inotrope rule).
    ("Vasopressor-free days", ["vasopressor-free days"]),
    ("Vasopressor dose", ["vasopressor dose"]),
    ("Ventilation duration", ["ventilator-free days", "mechanical ventilation duration"]),
    ("Shock index", ["shock index"]),
    ("Capillary Refill", ["capillary refill", "capillary refill time"]),
    ("MAP", ["mean arterial pressure", "map"]),
    ("Blood Pressure", ["blood pressure", "systolic", "diastolic"]),
    ("Heart Rate", ["heart rate", "hr"]),
    ("Cardiac Output/Index", ["cardiac output", "cardiac index"]),
    ("Cardiac Power Output", ["cardiac power output", "cpo"]),
    ("Stroke Volume", ["stroke volume", "sv"]),
    ("SVV", ["stroke volume variation", "svv"]),
    ("PPV", ["pulse pressure variation", "ppv"]),
    ("CVP", ["central venous pressure", "cvp"]),
    ("PAP", ["pulmonary artery pressure", "pap"]),
    ("PCWP", ["pulmonary capillary wedge pressure", "pcwp"]),
    ("SVR", ["systemic vascular resistance", "systemic vascular resistance index", "svr", "svri"]),
    ("PVR", ["pulmonary vascular resistance", "pvr"]),
    (
        "Venous O2 Saturation",
        [
            "mixed venous oxygen saturation",
            "central venous oxygen saturation",
            "svo2",
            "scvo2",
        ],
    ),
    ("Lactate Clearance", ["lactate clearance"]),
    ("Lactate", ["lactate"]),
    ("Oxygen Delivery", ["oxygen delivery", "do2"]),
    ("Oxygen Consumption", ["oxygen consumption", "vo2"]),
    ("Ejection Fraction", ["ejection fraction", "ef"]),
    ("Hemodynamics (general)", ["hemodynamic", "haemodynamic"]),
    (
        "Vasopressor/Inotrope",
        [
            "vasopressor",
            "vasoactive",
            "norepinephrine",
            "noradrenaline",
            "epinephrine",
            "adrenaline",
            "dopamine",
            "dobutamine",
            "phenylephrine",
            "vasopressin",
            "milrinone",
            "levosimendan",
            "inotrope",
            "inotropic",
        ],
    ),
    ("Tissue Perfusion", ["tissue perfusion", "peripheral perfusion", "perfusion index"]),
    ("Perfusion", ["perfusion"]),
    ("Fluid Responsiveness", [
        "passive leg raising", "fluid responsiveness", "fluid challenge",
        "pulse contour",
    ]),
    ("Echocardiographic", [
        "tapse", "global longitudinal strain", "gls",
        "e/e' ratio", "lvot", "velocity time integral", "vti",
    ]),
    ("Volumetric Hemodynamics", [
        "global end-diastolic volume", "gedv",
        "intrathoracic blood volume", "itbv",
        "extravascular lung water", "evlw",
    ]),
    ("Tissue Oxygenation", ["tissue oxygenation", "sto2", "nirs"]),
    ("dP/dt", ["dp/dt"]),
    ("Resuscitation Endpoints", ["base deficit", "base excess", "anion gap"]),
    ("ICU Severity Score", ["apache ii", "apache", "saps ii", "saps", "qsofa", "sofa", "mods"]),
]

UNIT_PATTERNS: List[Tuple[str, str]] = [
    # mmHg/s MUST come before mmHg (longest match first — P0 unit ordering)
    (r"\bmm\s?hg\s*/\s*s\b", "mmHg/s"),
    (r"\bmm\s?hg\b", "mmHg"),
    (r"\bcm\s?h2o\b", "cmH2O"),
    (r"\bmmol\s*/\s*l\b|\bmmol per l\b", "mmol/L"),
    (r"\bmeq\s*/\s*l\b", "mEq/L"),
    (r"\bmg\s*/\s*dl\b", "mg/dL"),
    # Vasopressor dosing units (must come before generic mL/min patterns)
    (r"\b(?:mcg|ug|µg)\s*/\s*kg\s*/\s*min\b", "mcg/kg/min"),
    (r"\bng\s*/\s*kg\s*/\s*min\b", "ng/kg/min"),
    (r"\bunits?\s*/\s*(?:hr|hour|min)\b", "units/hr"),
    (r"\bml\s*/\s*kg\s*/\s*min\b", "mL/kg/min"),
    (r"\bl\s*/\s*min\s*/\s*m2\b|\bl\s*/\s*min\s*/\s*m\^?2\b", "L/min/m2"),
    (r"\bml\s*/\s*min\s*/\s*m2\b|\bml\s*/\s*min\s*/\s*m\^?2\b", "mL/min/m2"),
    (r"\bml\s*/\s*m2\b|\bml\s*/\s*m\^?2\b", "mL/m2"),
    (r"\bl\s*/\s*min\b", "L/min"),
    (r"\bml\s*/\s*min\b", "mL/min"),
    (r"\bml\s*/\s*beat\b", "mL/beat"),
    (
        r"\bbeats\s*/\s*min\b|\bbeats per minute\b|\bbpm\b",
        "bpm",
    ),
    (r"\bdyn(?:es)?\s*\*?\s*s\s*/\s*cm\^?5\s*/\s*m\^?2\b", "dyn*s/cm5/m2"),
    (r"\bdyn(?:es)?\s*\*?\s*s\s*/\s*cm\^?5\b", "dyn*s/cm5"),
    (r"\bwood\s+units?\b", "Wood units"),
    (r"\bwatt(?:s)?\b", "W"),
    (r"\bms\b|\bmillisec(?:onds?)?\b", "ms"),
    (r"(?<=\d\s)sec(?:onds)?(?!\w)|(?<=\d)sec(?:onds)?(?!\w)", "s"),
]


def _csv_safe(value: str) -> str:
    """Guard against CSV formula injection in Excel/Sheets.

    Note: '-' excluded — too many false positives in medical data
    (e.g. '-0.5 mmHg'). Only '=' '+' '@' '\\t' '\\r' are dangerous
    formula prefixes per OWASP guidance.
    """
    if not value:
        return value
    needs_prefix = value[0] in ("=", "+", "@", "\t", "\r")
    if not needs_prefix:
        for prefix in ("\n=", "\n+", "\n@", "\r=", "\r+", "\r@"):
            if prefix in value:
                needs_prefix = True
                break
    return "'" + value if needs_prefix else value


@dataclass
class KeywordStats:
    mention_count: int = 0
    study_ids: Set[str] = field(default_factory=set)
    placebo_study_ids: Set[str] = field(default_factory=set)


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [row for row in reader]


def normalize_int(value: Optional[str]) -> int:
    try:
        return int(value) if value is not None and value != "" else 0
    except ValueError:
        print(f"Warning: non-numeric integer value '{value}', defaulting to 0",
              file=sys.stderr)
        return 0


def split_list(value: str) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(";") if item.strip()]


# Negative-context patterns for ambiguous abbreviations.
# HR = "Heart Rate" but also "Hazard Ratio" — exclude statistical contexts.
# SV = "Stroke Volume" but also "SV40" in oncology.
_ABBREVIATION_NEGATIVE_CONTEXT = {
    "hr": re.compile(
        r"(?:"
        r"hazard\s+ratio"
        r"|adjusted\s+hr\b"
        r"|\bahr\b"
        r"|\bchr\b"
        r"|\bhr\s*[=:]\s*\d+\.\d"         # HR=0.85 or HR=1.47 (hazard ratio pattern)
        r"|\bhr\s+\d+\.\d"                # HR 0.85 or HR 1.47
        r"|\bhr\s*\(\s*95\s*%"            # HR (95% CI
        r"|\bhr\s*\[\s*95\s*%"            # HR [95% CI
        r"|\bhr\s*;?\s*95\s*%\s*ci"       # HR; 95% CI or HR 95% CI
        r"|\bhr\s+\d\.\d+\s*[,;(]"        # HR 1.23, or HR 1.23;
        r")",
        re.IGNORECASE,
    ),
    "sv": re.compile(r"\bsv40\b", re.IGNORECASE),
    "pap": re.compile(r"\bpap\s+(?:smear|test)\b", re.IGNORECASE),
}


def _normalize_quotes(s: str) -> str:
    """Replace typographic apostrophes/quotes with ASCII for matching."""
    return s.replace("\u2018", "'").replace("\u2019", "'").replace("\u2032", "'")


def token_in_text(token: str, text: str) -> bool:
    if not token or not text:
        return False
    token = _normalize_quotes(token).lower()
    text = _normalize_quotes(text).lower()
    # Check negative context for ambiguous abbreviations
    neg_re = _ABBREVIATION_NEGATIVE_CONTEXT.get(token)
    if neg_re and neg_re.search(text):
        return False
    if len(token) <= 3:
        # Strip parens, hyphens, and other delimiters so "(EF)" and "EF-reduced" match "ef"
        # Include ,;[] so short tokens are found in "MAP,CVP" or "[HR]" contexts
        parts = text.replace("/", " ").replace("(", " ").replace(")", " ").replace("-", " ").replace(",", " ").replace(";", " ").replace("[", " ").replace("]", " ").split()
        return any(part == token for part in parts)
    # Use word boundary for longer tokens to prevent substring matches
    # (e.g., "perfusion" should not match "hypoperfusion")
    return re.search(r"\b" + re.escape(token) + r"\b", text) is not None


def normalize_keyword(keyword: str, text: str) -> str:
    # Try matching the keyword alone first to avoid misclassification
    # (e.g., "heart rate" keyword with text mentioning "map" should not
    # be classified as "MAP" just because the MAP rule comes first).
    kw_lower = keyword.strip().lower()
    if kw_lower:
        for canonical, tokens in CANONICAL_RULES:
            for token in tokens:
                if token_in_text(token, kw_lower):
                    return canonical
    # Fall back to combined keyword + matched text
    combined = f"{keyword} {text}".strip().lower()
    for canonical, tokens in CANONICAL_RULES:
        for token in tokens:
            if token_in_text(token, combined):
                return canonical
    # No canonical rule matched — mark as "Unmapped" so TruthCert
    # abstention checker correctly flags these keywords.
    return "Unmapped"


# Fallback units for canonical keywords where:
#   - the unit is unambiguous (scores, days, ratios), OR
#   - the keyword category genuinely has no single unit ("varies", "N/A")
# These are applied only when extract_unit() finds no explicit unit in
# the measure/matched_text, so explicit units always take precedence.
KEYWORD_FALLBACK_UNITS: Dict[str, str] = {
    "ICU Severity Score": "score",
    "Vasopressor-free days": "days",
    "Ventilation duration": "days",
    "Hemodynamics (general)": "N/A",
    "Vasopressor/Inotrope": "varies",
    "Perfusion": "N/A",
    "Tissue Perfusion": "N/A",
    "Fluid Responsiveness": "N/A",
    "Echocardiographic": "N/A",
    "Lactate Clearance": "%",
    "Resuscitation Endpoints": "mmol/L",
    "Shock index": "ratio",
    "MAP": "mmHg",
    "Blood Pressure": "mmHg",
    "Heart Rate": "bpm",
    "Ejection Fraction": "%",
    "SVV": "%",
    "PPV": "%",
    "Capillary Refill": "s",
    "Volumetric Hemodynamics": "mL/m2",
    "Tissue Oxygenation": "%",
    "dP/dt": "mmHg/s",
}

_PERCENT_CONTEXT_RE = re.compile(
    r"(?:percent(?:age)?|%)\s*(?:change|reduction|increase|decrease|improvement|of\s)",
    re.IGNORECASE,
)


def extract_unit(text: str) -> Tuple[str, str]:
    if not text:
        return "", ""
    lower = text.lower()
    # Check specific unit patterns first (mmHg, bpm, etc.)
    for pattern, normalized in UNIT_PATTERNS:
        match = re.search(pattern, lower)
        if match:
            return match.group(0), normalized
    # Only match % as a unit when it's NOT in a change/reduction context
    # (e.g., "50% reduction in SOFA" or "Percent change in CO" are not units)
    if "%" in text or "percent" in lower:
        if not _PERCENT_CONTEXT_RE.search(lower):
            return "%", "%"
    return "", ""


def write_parquet(csv_path: Path, parquet_path: Path) -> Dict[str, str]:
    pyarrow_err = None
    try:
        import pyarrow.csv as pv  # type: ignore
        import pyarrow.parquet as pq  # type: ignore

        table = pv.read_csv(str(csv_path))
        pq.write_table(table, str(parquet_path))
        return {"status": "ok", "method": "pyarrow", "path": str(parquet_path)}
    except Exception as exc:
        pyarrow_err = str(exc)

    try:
        import duckdb  # type: ignore

        duckdb.execute(
            "COPY (SELECT * FROM read_csv_auto(?)) TO ? (FORMAT PARQUET)",
            [str(csv_path), str(parquet_path)],
        )
        return {"status": "ok", "method": "duckdb", "path": str(parquet_path)}
    except Exception as exc:
        return {
            "status": "skipped",
            "reason": f"pyarrow: {pyarrow_err}; duckdb: {exc}",
            "path": str(parquet_path),
        }


def _load_enrichment(
    enrich_db: Path,
    nct_ids: Set[str],
    config_path: Optional[Path] = None,
) -> Dict[str, Dict[str, Any]]:
    """Load enrichment data from SQLite using the orchestrator's query logic.

    Uses batch method (single DB connection) instead of per-NCT connections.
    """
    from enrich_orchestrator import EnrichmentOrchestrator, load_config, DEFAULT_CONFIG_PATH
    effective_config_path = config_path or DEFAULT_CONFIG_PATH
    config = load_config(effective_config_path)
    orch = EnrichmentOrchestrator(enrich_db, config)
    return orch.get_enrichment_summaries(list(nct_ids))


def _fuzzy_title_match(title_a: str, title_b: str, threshold: float = 0.85) -> bool:
    """Normalized Levenshtein similarity > threshold."""
    a = title_a.strip().lower()
    b = title_b.strip().lower()
    if not a or not b:
        return False
    if a == b:
        return True
    # Quick length check — if lengths differ by >30%, skip expensive computation
    if abs(len(a) - len(b)) / max(len(a), len(b)) > 0.3:
        return False
    # Simple Levenshtein via dynamic programming (single-row optimization)
    if len(a) > len(b):
        a, b = b, a
    prev = list(range(len(a) + 1))
    for j in range(1, len(b) + 1):
        curr = [j] + [0] * len(a)
        for i in range(1, len(a) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[i] = min(curr[i - 1] + 1, prev[i] + 1, prev[i - 1] + cost)
        prev = curr
    dist = prev[len(a)]
    similarity = 1.0 - dist / max(len(a), len(b))
    return similarity >= threshold


def _title_words(s: str) -> Set[str]:
    """Extract significant words (length >= 4) for fast Jaccard pre-filter."""
    return {w for w in re.split(r'\W+', s.lower()) if len(w) >= 4}


def merge_multi_source(
    ctgov_studies: List[Dict[str, str]],
    pubmed_studies: Optional[List[Dict[str, str]]] = None,
) -> Tuple[List[Dict[str, str]], Dict[str, str]]:
    """Merge multi-source study records with deduplication.

    Priority order:
    1. NCT ID match (WHO/PubMed record has NCT ID -> merge into CT.gov record)
    2. Title fuzzy match (word-Jaccard pre-filter + Levenshtein > 0.85)
    3. Unique: records with no match are new non-CT.gov trials
    """
    # Index CT.gov studies by NCT ID and title
    merged: Dict[str, Dict[str, str]] = {}
    title_index: Dict[str, str] = {}  # lowercase title -> nct_id
    # Map non-CT trial IDs (e.g., PMID:xxxx) to matched NCT IDs
    trial_id_map: Dict[str, str] = {}

    # Word-level inverted index for O(1) candidate filtering
    # Maps each significant word -> set of titles containing it
    word_index: Dict[str, Set[str]] = defaultdict(set)
    title_words_cache: Dict[str, Set[str]] = {}

    for row in ctgov_studies:
        nct_id = row.get("nct_id", "").strip()
        if nct_id:
            row["data_sources"] = row.get("data_sources", "ctgov")
            merged[nct_id] = row
            title = row.get("brief_title", "").strip().lower()
            if title:
                title_index[title] = nct_id
                words = _title_words(title)
                title_words_cache[title] = words
                for w in words:
                    word_index[w].add(title)

    def _find_fuzzy_match(ext_title: str) -> Optional[str]:
        """Find a fuzzy title match using word-Jaccard candidate filter."""
        # Exact match first
        if ext_title in title_index:
            return title_index[ext_title]
        ext_words = _title_words(ext_title)
        if not ext_words:
            return None
        # Count how many words each existing title shares
        candidate_counts: Dict[str, int] = defaultdict(int)
        for w in ext_words:
            for title in word_index.get(w, ()):
                candidate_counts[title] += 1
        # Only run Levenshtein on candidates sharing >= 50% of words (Jaccard proxy)
        min_shared = max(2, len(ext_words) // 2)
        for cand_title, shared in candidate_counts.items():
            if shared >= min_shared:
                cand_words = title_words_cache.get(cand_title, set())
                union_size = len(ext_words | cand_words)
                if union_size > 0 and shared / union_size >= 0.5:
                    if _fuzzy_title_match(ext_title, cand_title):
                        return title_index[cand_title]
        return None

    def _try_merge(ext_row: Dict[str, str], source_label: str) -> None:
        """Try to merge an external record into existing, or add as new."""
        ext_nct = ext_row.get("nct_id", "").strip()
        ext_trial_id = ext_row.get("trial_id", "").strip()
        primary_id = ext_nct or ext_trial_id

        # Strategy 1: NCT ID match
        if ext_nct and ext_nct in merged:
            if source_label == "pubmed" and ext_trial_id:
                trial_id_map[ext_trial_id] = ext_nct
            existing_sources = merged[ext_nct].get("data_sources", "ctgov")
            if source_label not in existing_sources:
                merged[ext_nct]["data_sources"] = f"{existing_sources};{source_label}"
            # Merge countries if available and not already present
            ext_countries = ext_row.get("countries", "").strip()
            if ext_countries and not merged[ext_nct].get("countries", "").strip():
                merged[ext_nct]["countries"] = ext_countries
            return

        # Strategy 2: Title fuzzy match (word-Jaccard accelerated)
        ext_title = ext_row.get("brief_title", "").strip().lower()
        if ext_title:
            matched_id = _find_fuzzy_match(ext_title)
            if matched_id:
                if source_label == "pubmed" and ext_trial_id:
                    trial_id_map[ext_trial_id] = matched_id
                existing_sources = merged[matched_id].get("data_sources", "ctgov")
                if source_label not in existing_sources:
                    merged[matched_id]["data_sources"] = f"{existing_sources};{source_label}"
                return

        # Strategy 3: New unique record
        if primary_id and primary_id not in merged:
            ext_row["data_sources"] = source_label
            if not ext_row.get("nct_id"):
                ext_row["nct_id"] = ext_trial_id
            merged[primary_id] = ext_row
            if ext_title:
                title_index[ext_title] = primary_id
                words = _title_words(ext_title)
                title_words_cache[ext_title] = words
                for w in words:
                    word_index[w].add(ext_title)

    if pubmed_studies:
        for row in pubmed_studies:
            _try_merge(row, "pubmed")

    return list(merged.values()), trial_id_map


def merge_multi_source_hemo(
    ctgov_hemo: List[Dict[str, str]],
    pubmed_hemo: Optional[List[Dict[str, str]]] = None,
    trial_id_map: Optional[Dict[str, str]] = None,
) -> List[Dict[str, str]]:
    """Merge hemodynamic mention records from multiple sources.

    Dedup by (nct_id/trial_id, keyword, measure) tuple.
    """
    seen: Set[Tuple[str, str, str]] = set()
    result: List[Dict[str, str]] = []

    id_map = trial_id_map or {}

    def _add_rows(rows: List[Dict[str, str]]) -> None:
        for row in rows:
            nct_id = row.get("nct_id", "").strip() or row.get("trial_id", "").strip()
            mapped = id_map.get(nct_id)
            if mapped:
                nct_id = mapped
            keyword = row.get("keyword", "").strip()
            measure = row.get("measure", "").strip()
            key = (nct_id, keyword, measure)
            if key not in seen and nct_id:
                seen.add(key)
                # Ensure hemo row uses mapped NCT ID when available
                row["nct_id"] = nct_id
                result.append(row)

    _add_rows(ctgov_hemo)
    if pubmed_hemo:
        _add_rows(pubmed_hemo)

    return result


def build_living_map(
    studies_csv: Path,
    hemo_csv: Path,
    output_dir: Path,
    dashboard_dir: Optional[Path] = None,
    label: str = DEFAULT_LABEL,
    write_parquet_output: bool = True,
    raw_jsonl: Optional[Path] = None,
    enrich_db: Optional[Path] = None,
    pubmed_studies_csv: Optional[Path] = None,
    pubmed_hemo_csv: Optional[Path] = None,
) -> Dict[str, object]:
    # Validate label to prevent path traversal and cross-label contamination
    if not re.match(r"^[a-zA-Z0-9_-]+$", label):
        raise ValueError(f"Invalid label '{label}': must be alphanumeric/hyphen/underscore only")
    studies_rows = read_csv(studies_csv)
    hemo_rows = read_csv(hemo_csv)

    # Multi-source merge if additional sources provided
    pubmed_studies_rows = read_csv(pubmed_studies_csv) if pubmed_studies_csv and pubmed_studies_csv.exists() else None
    pubmed_hemo_rows = read_csv(pubmed_hemo_csv) if pubmed_hemo_csv and pubmed_hemo_csv.exists() else None

    trial_id_map: Dict[str, str] = {}
    if pubmed_studies_rows:
        studies_rows, trial_id_map = merge_multi_source(studies_rows, pubmed_studies_rows)
        print(f"  Multi-source merge: {len(studies_rows)} studies after dedup", file=sys.stderr)

    if pubmed_hemo_rows:
        hemo_rows = merge_multi_source_hemo(hemo_rows, pubmed_hemo_rows, trial_id_map)
        print(f"  Multi-source merge: {len(hemo_rows)} hemo mentions after dedup", file=sys.stderr)

    studies_map: Dict[str, Dict[str, str]] = {}
    for row in studies_rows:
        nct_id = row.get("nct_id", "").strip()
        if nct_id:
            studies_map[nct_id] = row

    # Load enrichment data if available
    enrichment_map: Dict[str, Dict[str, Any]] = {}
    if enrich_db and enrich_db.exists():
        try:
            enrichment_map = _load_enrichment(enrich_db, set(studies_map.keys()))
        except Exception as exc:
            print(f"Warning: enrichment loading failed, continuing without: {exc}")
            enrichment_map = {}

    suffix = "" if label == DEFAULT_LABEL else f"_{label}"
    detailed_path = output_dir / f"icu_hemodynamic_living_map{suffix}.csv"
    output_dir.mkdir(parents=True, exist_ok=True)

    detailed_fields = [
        "nct_id",
        "brief_title",
        "overall_status",
        "allocation",
        "intervention_model",
        "masking",
        "masking_description",
        "masking_subjects",
        "phase",
        "start_date",
        "completion_date",
        "last_update_posted",
        "results_first_posted",
        "enrollment_count",
        "enrollment_type",
        "conditions",
        "study_keywords",
        "arm_count",
        "placebo_arm_count",
        "has_placebo_arm",
        "outcome_type",
        "measure",
        "keyword",
        "normalized_keyword",
        "unit_raw",
        "normalized_unit",
        "matched_text",
        "query_name",
        "countries",
        "data_sources",
    ]

    # Add enrichment columns when enrichment data is available
    enrichment_fields = [
        "pub_count", "pmid_list", "doi_list", "mesh_terms",
        "cited_by_total", "is_oa", "oa_status",
        "faers_top_reactions", "enrichment_sources",
    ]
    if enrichment_map:
        detailed_fields.extend(enrichment_fields)

    keyword_stats: Dict[str, KeywordStats] = defaultdict(KeywordStats)
    normalized_keyword_stats: Dict[str, KeywordStats] = defaultdict(KeywordStats)
    unit_stats: Dict[str, KeywordStats] = defaultdict(KeywordStats)
    outcome_stats: Dict[str, KeywordStats] = defaultdict(KeywordStats)
    condition_stats: Dict[str, KeywordStats] = defaultdict(KeywordStats)

    studies_with_hemo: Set[str] = set()
    studies_with_hemo_and_placebo: Set[str] = set()

    total_mentions = 0
    placebo_mentions = 0
    adjunct_mentions = 0  # Non-hemodynamic adjuncts (severity scores, ventilation, metabolic)
    orphan_nct_ids: Set[str] = set()  # hemo NCT IDs missing from studies CSV

    detailed_tmp = detailed_path.with_suffix(".csv.tmp")
    with detailed_tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=detailed_fields)
        writer.writeheader()

        for row in hemo_rows:
            nct_id = row.get("nct_id", "").strip()
            if not nct_id:
                continue
            study = studies_map.get(nct_id, {})
            if not study:
                orphan_nct_ids.add(nct_id)
            placebo_arm_count = normalize_int(study.get("placebo_arm_count"))
            has_placebo = placebo_arm_count > 0

            detailed_row = {
                "nct_id": nct_id,
                "brief_title": _csv_safe(study.get("brief_title", "").strip()),
                "overall_status": study.get("overall_status", "").strip(),
                "allocation": study.get("allocation", "").strip(),
                "intervention_model": study.get("intervention_model", "").strip(),
                "masking": study.get("masking", "").strip(),
                "masking_description": _csv_safe(study.get("masking_description", "").strip()),
                "masking_subjects": study.get("masking_subjects", "").strip(),
                "phase": study.get("phase", "").strip(),
                "start_date": study.get("start_date", "").strip(),
                "completion_date": study.get("completion_date", "").strip(),
                "last_update_posted": study.get("last_update_posted", "").strip(),
                "results_first_posted": study.get("results_first_posted", "").strip(),
                "enrollment_count": study.get("enrollment_count", "").strip(),
                "enrollment_type": study.get("enrollment_type", "").strip(),
                "conditions": _csv_safe(study.get("conditions", "").strip()),
                "study_keywords": _csv_safe(study.get("keywords", "").strip()),
                "arm_count": study.get("arm_count", "").strip(),
                "placebo_arm_count": str(placebo_arm_count),
                "has_placebo_arm": str(has_placebo),
                "outcome_type": row.get("outcome_type", "").strip(),
                "measure": _csv_safe(row.get("measure", "").strip()),
                "keyword": row.get("keyword", "").strip(),
                "normalized_keyword": "",
                "unit_raw": "",
                "normalized_unit": "",
                "matched_text": _csv_safe(row.get("matched_text", "").strip()),
                "query_name": row.get("query_name", "").strip(),
                "countries": _csv_safe(study.get("countries", "").strip()),
                "data_sources": study.get("data_sources", "ctgov").strip(),
            }
            detailed_row["normalized_keyword"] = normalize_keyword(
                detailed_row["keyword"], detailed_row["matched_text"]
            )
            unit_raw, unit_normalized = extract_unit(
                f"{detailed_row['measure']} {detailed_row['matched_text']}"
            )
            # Apply keyword-implied fallback when no explicit unit found
            if not unit_normalized:
                fallback = KEYWORD_FALLBACK_UNITS.get(detailed_row["normalized_keyword"], "")
                if fallback:
                    unit_normalized = fallback
            detailed_row["unit_raw"] = unit_raw
            detailed_row["normalized_unit"] = unit_normalized

            # Merge enrichment columns if available
            if enrichment_map:
                enr = enrichment_map.get(nct_id, {})
                detailed_row["pub_count"] = str(enr.get("pub_count", 0))
                detailed_row["pmid_list"] = _csv_safe(";".join(enr.get("pmid_list", [])))
                detailed_row["doi_list"] = _csv_safe(";".join(enr.get("doi_list", [])))
                detailed_row["mesh_terms"] = _csv_safe("|".join(enr.get("mesh_terms", [])))
                detailed_row["cited_by_total"] = str(enr.get("cited_by_total", 0))
                detailed_row["is_oa"] = str(bool(enr.get("is_oa", False))).lower()
                detailed_row["oa_status"] = enr.get("oa_status") or ""

                faers = enr.get("faers_top_reactions", [])
                # Use ;; between records and :: between fields within a record
                # to avoid delimiter collision (P0 fix — prior version used | for both)
                detailed_row["faers_top_reactions"] = ";;".join(
                    "{drug}::{reaction}::{count}".format(
                        drug=f.get('drug', '').replace('::', ': '),
                        reaction=f.get('reaction', '').replace('::', ': '),
                        count=f.get('count', 0),
                    )
                    for f in faers
                )
                detailed_row["enrichment_sources"] = ";".join(enr.get("enrichment_sources", []))

            writer.writerow(detailed_row)

            total_mentions += 1
            if detailed_row["normalized_keyword"] in NON_HEMODYNAMIC_ADJUNCTS:
                adjunct_mentions += 1
            studies_with_hemo.add(nct_id)
            if has_placebo:
                placebo_mentions += 1
                studies_with_hemo_and_placebo.add(nct_id)

            keyword = detailed_row["keyword"]
            outcome_type = detailed_row["outcome_type"]
            if keyword:
                stats = keyword_stats[keyword]
                stats.mention_count += 1
                stats.study_ids.add(nct_id)
                if has_placebo:
                    stats.placebo_study_ids.add(nct_id)
            normalized_keyword = detailed_row["normalized_keyword"]
            if normalized_keyword:
                stats = normalized_keyword_stats[normalized_keyword]
                stats.mention_count += 1
                stats.study_ids.add(nct_id)
                if has_placebo:
                    stats.placebo_study_ids.add(nct_id)
            normalized_unit = detailed_row["normalized_unit"] or "Unspecified"
            stats = unit_stats[normalized_unit]
            stats.mention_count += 1
            stats.study_ids.add(nct_id)
            if has_placebo:
                stats.placebo_study_ids.add(nct_id)
            if outcome_type:
                stats = outcome_stats[outcome_type]
                stats.mention_count += 1
                stats.study_ids.add(nct_id)
                if has_placebo:
                    stats.placebo_study_ids.add(nct_id)

            for condition in split_list(detailed_row["conditions"]):
                stats = condition_stats[condition]
                stats.mention_count += 1
                stats.study_ids.add(nct_id)
                if has_placebo:
                    stats.placebo_study_ids.add(nct_id)

    detailed_tmp.replace(detailed_path)

    # Warn about orphan NCT IDs (hemo mentions without study metadata)
    if orphan_nct_ids:
        print(
            f"Warning: {len(orphan_nct_ids)} NCT ID(s) in hemo CSV not found in studies CSV "
            f"(orphan rows with blank metadata): {sorted(orphan_nct_ids)[:5]}",
            file=sys.stderr,
        )

    total_studies = len(studies_map)
    studies_with_placebo = sum(
        1 for row in studies_rows if normalize_int(row.get("placebo_arm_count")) > 0
    )

    # Year distribution — extract year from start_date (format: "YYYY-MM-DD" or "YYYY-MM" or "YYYY")
    year_counts: Dict[str, int] = defaultdict(int)
    for row in studies_rows:
        start_date = row.get("start_date", "").strip()
        if start_date and len(start_date) >= 4:
            year = start_date[:4]
            if year.isdigit():
                year_counts[year] += 1

    # Country aggregation from studies CSV
    country_counts: Dict[str, int] = defaultdict(int)
    for row in studies_rows:
        countries_str = row.get("countries", "").strip()
        if countries_str:
            for country in countries_str.split(";"):
                country = country.strip()
                if country:
                    country_counts[country] += 1

    # Registry distribution (from data_sources column)
    registry_counts: Dict[str, int] = defaultdict(int)
    for row in studies_rows:
        sources = row.get("data_sources", "ctgov").strip()
        for src in sources.split(";"):
            src = src.strip()
            if src:
                registry_counts[src] += 1

    # Keyword co-occurrence — top 20 pairs of normalized keywords co-occurring in same study
    from itertools import combinations
    study_keywords_map: Dict[str, Set[str]] = defaultdict(set)
    for row in hemo_rows:
        nct_id = row.get("nct_id", "").strip()
        if nct_id:
            kw = normalize_keyword(row.get("keyword", ""), row.get("matched_text", ""))
            study_keywords_map[nct_id].add(kw)

    pair_counts: Dict[Tuple[str, str], int] = defaultdict(int)
    for nct_id, kw_set in study_keywords_map.items():
        sorted_kws = sorted(kw_set)
        for kw_a, kw_b in combinations(sorted_kws, 2):
            if kw_a != "Unmapped" and kw_b != "Unmapped":
                pair_counts[(kw_a, kw_b)] += 1

    top_cooccurrence = sorted(pair_counts.items(), key=lambda x: x[1], reverse=True)[:20]
    keyword_cooccurrence = [
        {"keyword_a": pair[0], "keyword_b": pair[1], "shared_study_count": count}
        for pair, count in top_cooccurrence
    ]

    # Single timestamp for the entire run — propagated to summary, capsule,
    # and enrichment export for deterministic ordering (editor review #9).
    run_timestamp = datetime.now(timezone.utc).isoformat()

    # PRISMA-S compliance: record the search date from the fetch step.
    # The fetch summary contains search_date_utc and query_text per query.
    search_date_utc = None
    fetch_query_text = ""
    try:
        fetch_summary_path = studies_csv.parent.parent / "logs" / "ctgov_icu_fetch_summary.json"
        if fetch_summary_path.exists():
            fs = json.loads(fetch_summary_path.read_text(encoding="utf-8"))
            # Find matching query's search date and query text
            for qname, qdata in fs.items():
                if isinstance(qdata, dict):
                    if qdata.get("search_date_utc") and not search_date_utc:
                        search_date_utc = qdata["search_date_utc"]
                    if qdata.get("query_text") and not fetch_query_text:
                        fetch_query_text = qdata["query_text"]
    except (json.JSONDecodeError, OSError, KeyError):
        pass  # Graceful degradation — search_date is supplementary

    # Build search_strategy metadata for TruthCert provenance
    config_path = ROOT / "ctgov_icu_placebo_strategy.json"
    config_data: Dict[str, Any] = {}
    try:
        if config_path.exists():
            config_data = json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        pass
    config_notes = config_data.get("notes", {})
    config_limitations = config_notes.get("limitations", [])
    grey_literature_note = config_notes.get("grey_literature_note", "")
    ref_standard = config_data.get("recall_reference_standard", {})
    ref_nct_ids = ref_standard.get("nct_ids", [])

    # ref_nct_ids included here for capsule self-containedness (E-10) —
    # duplicates config, but capsule must be independently verifiable.
    search_strategy: Dict[str, Any] = {
        "query_text": fetch_query_text,
        "database": "ClinicalTrials.gov",
        "limitations": config_limitations,
        "recall_reference_nct_ids": ref_nct_ids,
        "grey_literature_note": grey_literature_note,
    }

    # Status stratification (editor review #7)
    status_counts: Dict[str, int] = defaultdict(int)
    for row in studies_rows:
        status = row.get("overall_status", "Unknown").strip() or "Unknown"
        status_counts[status] += 1

    summary = {
        "generated_at": run_timestamp,
        "search_date_utc": search_date_utc,
        "label": label,
        "population_scope": "Adult, pediatric, and neonatal ICU (includes PICU/NICU search terms)",
        "source": {
            "studies_csv": studies_csv.name,
            "hemo_csv": hemo_csv.name,
            "registry": "ClinicalTrials.gov",
            "api_version": "v2",
        },
        "totals": {
            "total_studies": total_studies,
            "studies_with_placebo": studies_with_placebo,
            "studies_with_hemo_mentions": len(studies_with_hemo),
            "studies_with_hemo_and_placebo": len(studies_with_hemo_and_placebo),
            "total_hemo_mentions": total_mentions,
            "core_hemo_mentions": total_mentions - adjunct_mentions,
            "adjunct_mentions": adjunct_mentions,
            "adjunct_note": "ICU Severity Score, Ventilation duration, and Resuscitation Endpoints are non-hemodynamic adjuncts reported separately",
            "placebo_hemo_mentions": placebo_mentions,
            "non_placebo_hemo_mentions": total_mentions - placebo_mentions,
            "orphan_hemo_nct_ids": len(orphan_nct_ids),
        },
        "status_stratification": dict(sorted(status_counts.items())),
        "prisma_flow": {
            "note": "Adapted PRISMA-S flow for automated evidence gap mapping (not a full PRISMA 2020 flow diagram)",
            "search_date_utc": search_date_utc,
            "ctgov_retrieved": sum(1 for r in studies_rows if r.get("data_sources", "ctgov") == "ctgov" or "ctgov" in r.get("data_sources", "")),

            "pubmed_retrieved": sum(1 for r in studies_rows if "pubmed" in r.get("data_sources", "")),
            "total_after_dedup": total_studies,
            "with_hemodynamic_outcomes": len(studies_with_hemo),
            "with_placebo_arms": studies_with_placebo,
            "with_hemo_and_placebo": len(studies_with_hemo_and_placebo),
            "excluded_no_hemo": total_studies - len(studies_with_hemo),
        },
        "keywords": sorted(
            [
                {
                    "keyword": key,
                    "mention_count": stats.mention_count,
                    "study_count": len(stats.study_ids),
                    "placebo_study_count": len(stats.placebo_study_ids),
                }
                for key, stats in keyword_stats.items()
            ],
            key=lambda x: x["keyword"],
        ),
        "normalized_keywords": sorted(
            [
                {
                    "keyword": key,
                    "mention_count": stats.mention_count,
                    "study_count": len(stats.study_ids),
                    "placebo_study_count": len(stats.placebo_study_ids),
                }
                for key, stats in normalized_keyword_stats.items()
            ],
            key=lambda x: x["keyword"],
        ),
        "units": sorted(
            [
                {
                    "unit": key,
                    "mention_count": stats.mention_count,
                    "study_count": len(stats.study_ids),
                    "placebo_study_count": len(stats.placebo_study_ids),
                }
                for key, stats in unit_stats.items()
            ],
            key=lambda x: x["unit"],
        ),
        "outcome_types": sorted(
            [
                {
                    "outcome_type": key,
                    "mention_count": stats.mention_count,
                    "study_count": len(stats.study_ids),
                    "placebo_study_count": len(stats.placebo_study_ids),
                }
                for key, stats in outcome_stats.items()
            ],
            key=lambda x: x["outcome_type"],
        ),
        "conditions": sorted(
            [
                {
                    "condition": key,
                    "mention_count": stats.mention_count,
                    "study_count": len(stats.study_ids),
                    "placebo_study_count": len(stats.placebo_study_ids),
                }
                for key, stats in condition_stats.items()
            ],
            key=lambda x: x["condition"],
        ),
        "year_distribution": dict(sorted(year_counts.items())),
        "countries": dict(sorted(country_counts.items(), key=lambda x: x[1], reverse=True)),
        "registries": dict(sorted(registry_counts.items(), key=lambda x: x[1], reverse=True)),
        "keyword_cooccurrence": keyword_cooccurrence,
        "last_update_info": {
            "last_update_utc": run_timestamp,
            "sources_active": sorted(set(
                src.strip()
                for row in studies_rows
                for src in row.get("data_sources", "ctgov").split(";")
                if src.strip()
            )),
        },
    }

    # Add enrichment summary section
    if enrichment_map:
        source_counts: Dict[str, int] = defaultdict(int)
        enriched_nct_ids = 0
        for nct_id, enr in enrichment_map.items():
            if enr.get("enrichment_sources"):
                enriched_nct_ids += 1
            for src in enr.get("enrichment_sources", []):
                source_counts[src] += 1
        summary["enrichment"] = {
            "enabled": True,
            "enriched_trials": enriched_nct_ids,
            "source_coverage": dict(sorted(source_counts.items())),
        }
    else:
        summary["enrichment"] = {"enabled": False}

    # Attach search_strategy to summary so validators can access query_text
    # and gold-standard NCT IDs for P2 search quality checks.
    summary["search_strategy"] = search_strategy

    parquet_info: Dict[str, str] = {"status": "skipped", "reason": "disabled"}
    if write_parquet_output:
        parquet_path = output_dir / f"icu_hemodynamic_living_map{suffix}.parquet"
        try:
            parquet_info = write_parquet(detailed_path, parquet_path)
        except Exception as exc:
            parquet_info = {"status": "error", "reason": str(exc)}
            print(f"Warning: parquet export failed, continuing: {exc}", file=sys.stderr)

    summary["parquet"] = parquet_info

    summary_path = output_dir / f"icu_hemodynamic_summary{suffix}.json"
    summary_tmp = summary_path.with_suffix(".json.tmp")
    summary_tmp.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary_tmp.replace(summary_path)

    if dashboard_dir:
        dashboard_dir.mkdir(parents=True, exist_ok=True)
        # Copy summary JSON atomically
        summary_name = f"icu_hemodynamic_summary{suffix}.json"
        tmp = dashboard_dir / f"{summary_name}.tmp"
        final = dashboard_dir / summary_name
        tmp.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        tmp.replace(final)
        # Copy CSV via shutil instead of reading back into memory
        csv_name = f"icu_hemodynamic_living_map{suffix}.csv"
        csv_tmp = dashboard_dir / f"{csv_name}.tmp"
        csv_final = dashboard_dir / csv_name
        shutil.copy2(str(detailed_path), str(csv_tmp))
        csv_tmp.replace(csv_final)

        # Export enrichment summary for dashboard
        if enrichment_map and enrich_db and enrich_db.exists():
            try:
                enr_output = {
                    "generated_utc": run_timestamp,
                    "trial_count": len(studies_map),
                    "source_coverage": dict(summary.get("enrichment", {}).get("source_coverage", {})),
                    "trials": enrichment_map,
                }
                enr_path = dashboard_dir / f"enrichment_summary{suffix}.json"
                enr_tmp = enr_path.with_suffix(".json.tmp")
                enr_tmp.write_text(json.dumps(enr_output, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
                enr_tmp.replace(enr_path)
            except Exception as exc:
                print(f"Warning: enrichment dashboard export failed: {exc}")

    # TruthCert: build provenance capsule (pass run_timestamp for determinism)
    extra_inputs = [p for p in [pubmed_studies_csv, pubmed_hemo_csv] if p]
    build_capsule(
        label=label,
        studies_csv=studies_csv,
        hemo_csv=hemo_csv,
        output_csv=detailed_path,
        summary=summary,
        canonical_rules=CANONICAL_RULES,
        unit_patterns=UNIT_PATTERNS,
        output_dir=output_dir,
        dashboard_dir=dashboard_dir,
        raw_jsonl=raw_jsonl,
        enrich_db=enrich_db,
        run_timestamp=run_timestamp,
        search_strategy=search_strategy,
        extra_input_files=extra_inputs or None,
    )

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ICU hemodynamic living map")
    parser.add_argument(
        "--studies",
        default=str(DEFAULT_OUTPUT_DIR / "icu_rct_broad_studies.csv"),
        help="Path to studies CSV",
    )
    parser.add_argument(
        "--hemo",
        default=str(DEFAULT_OUTPUT_DIR / "icu_rct_broad_hemodynamic_mentions.csv"),
        help="Path to hemodynamic mentions CSV",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Output directory",
    )
    parser.add_argument(
        "--dashboard-dir",
        default=str(DEFAULT_DASHBOARD_DIR),
        help="Dashboard data directory",
    )
    parser.add_argument(
        "--label",
        default=DEFAULT_LABEL,
        help="Label used for output file suffix (default: broad)",
    )
    parser.add_argument(
        "--no-write-parquet",
        action="store_true",
        default=False,
        help="Skip writing a parquet version of the living map",
    )
    parser.add_argument(
        "--raw-jsonl",
        default=None,
        help="Path to raw JSONL from CT.gov fetch (for TruthCert provenance hashing)",
    )
    parser.add_argument(
        "--enrich",
        action="store_true",
        default=False,
        help="Merge enrichment data from SQLite into output CSV",
    )
    parser.add_argument(
        "--enrich-db",
        default=None,
        help="Path to enrichment SQLite database (default: enrichment/enrichment_db.sqlite)",
    )
    parser.add_argument(
        "--pubmed-studies",
        default=None,
        help="Path to PubMed primary studies CSV for multi-source merge",
    )
    parser.add_argument(
        "--pubmed-hemo",
        default=None,
        help="Path to PubMed primary hemodynamic mentions CSV for multi-source merge",
    )
    args = parser.parse_args()

    enrich_db = None
    if args.enrich or args.enrich_db:
        # --enrich-db implies --enrich (don't silently ignore the DB path)
        if args.enrich_db:
            enrich_db = Path(args.enrich_db)
        else:
            enrich_db = ROOT / "enrichment" / "enrichment_db.sqlite"

    summary = build_living_map(
        Path(args.studies),
        Path(args.hemo),
        Path(args.output_dir),
        Path(args.dashboard_dir),
        label=args.label,
        write_parquet_output=not args.no_write_parquet,
        raw_jsonl=Path(args.raw_jsonl) if args.raw_jsonl else None,
        enrich_db=enrich_db,
        pubmed_studies_csv=Path(args.pubmed_studies) if args.pubmed_studies else None,
        pubmed_hemo_csv=Path(args.pubmed_hemo) if args.pubmed_hemo else None,
    )

    print("Living map created.")
    print(f"Studies: {summary['totals']['total_studies']}")
    print(f"Hemo mentions: {summary['totals']['total_hemo_mentions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

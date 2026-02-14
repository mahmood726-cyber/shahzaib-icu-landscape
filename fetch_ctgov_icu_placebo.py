#!/usr/bin/env python3
"""
Fetch ICU/critical care RCTs from ClinicalTrials.gov and extract placebo-arm
and hemodynamic outcome signals for a living trial landscape map.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "ctgov_icu_placebo_strategy.json"

_NCT_RE = re.compile(r"^NCT\d{8}$")
# Module-level (needed for ctgov_config/ctgov_utils imports below).
# validators.py has its own _get_tooling_root() for runtime use — intentional
# duplication because import-time vs runtime resolution differ.
TOOLING_ROOT = Path(
    os.environ.get("CTGOV_TOOLING_ROOT", ROOT.parent / "ctgov-search-strategies")
)

if str(TOOLING_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLING_ROOT))

from ctgov_config import DEFAULT_PAGE_SIZE, DEFAULT_RATE_LIMIT, DEFAULT_TIMEOUT, DEFAULT_USER_AGENT  # type: ignore
from ctgov_utils import get_session, iter_study_pages  # type: ignore

# TRUE placebo tokens — inert comparators only.
# "usual care" / "standard care" are active comparators, NOT placebos.
# They are classified separately via COMPARATOR_RULES and comparator_type.
PLACEBO_TOKENS = (
    "placebo",
    "sham",
)

COMPARATOR_RULES = [
    ("placebo", ["placebo"]),
    ("sham", ["sham"]),
    ("usual_care", ["usual care", "standard care", "standard of care", "routine care",
                    "best supportive care", "guideline-based care"]),
    ("no_intervention", ["no intervention", "no treatment"]),
    ("active_control", ["active control", "active comparator"]),
    ("control", ["control arm", "control group", "comparator arm", "comparator group"]),
]


@dataclass
class OutcomeRecord:
    outcome_type: str
    measure: str
    time_frame: str
    description: str


@dataclass
class ArmRecord:
    label: str
    description: str
    intervention_names: str
    is_placebo: bool
    comparator_type: str
    arm_role: str


def classify_arm(text: str) -> str:
    lowered = text.lower()
    for label, tokens in COMPARATOR_RULES:
        if any(token in lowered for token in tokens):
            return label
    return "experimental"


def load_config(path: Path) -> Dict:
    if not path.exists():
        raise FileNotFoundError(f"Missing config: {path}")
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def normalize_text(value: Optional[str]) -> str:
    if value is None or value == "":
        return ""
    return " ".join(str(value).split())


def extract_list(values: Optional[Iterable[str]]) -> List[str]:
    return [t for v in (values or []) if (t := normalize_text(v))]


def is_placebo_text(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in PLACEBO_TOKENS)


# Negative-context patterns for ambiguous abbreviations (shared with build_living_map.py).
_ABBREVIATION_NEGATIVE_CONTEXT = {
    "hr": re.compile(
        r"(?:"
        r"hazard\s+ratio"
        r"|adjusted\s+hr\b"
        r"|\bahr\b"
        r"|\bchr\b"
        r"|\bcshr\b"                          # cause-specific hazard ratio
        r"|\bshr\b"                            # sub-distribution hazard ratio
        r"|\bcox\s+hr\b"                       # Cox HR
        r"|sub-?distribution\s+hazard"         # subdistribution hazard ratio
        r"|cause-specific\s+hazard"            # cause-specific hazard ratio
        r"|proportional\s+hazards?\s+.{0,80}\bhr\b"
        r"|\bhr\s*[=:]\s*\d+\.\d"
        r"|\bhr\s+\d+\.\d"
        r"|\bhr\s*\(\s*95\s*%"
        r"|\bhr\s*\[\s*95\s*%"
        r"|\bhr\s*;?\s*95\s*%\s*ci"
        r"|\bhr\s+\d\.\d+\s*[,;(]"
        r")",
        re.IGNORECASE,
    ),
    "sv": re.compile(r"\bsv40\b", re.IGNORECASE),
    "pap": re.compile(r"\bpap\s+(?:smear|test)\b", re.IGNORECASE),
    "map": re.compile(
        r"(?:map\s*(?:kinase|pathway)|mapk|\bmitogen[-\s]activated\s+protein)",
        re.IGNORECASE,
    ),
    "ef": re.compile(
        r"(?:elongation\s+factor|enhancement\s+factor)",
        re.IGNORECASE,
    ),
    "perfusion": re.compile(
        r"(?:cerebral\s+perfusion(?!\s+pressure)"
        r"|myocardial\s+perfusion\s+(?:scan|imaging|study|scintigraphy|spect|pet)"
        r"|perfusion\s+(?:scan|imaging|study|scintigraphy))",
        re.IGNORECASE,
    ),
    "dopamine": re.compile(
        r"(?:dopamine\s+receptor|dopaminergic|dopamine\s+pathway"
        r"|dopamine\s+D[12345]|dopamine\s+transporter"
        r"|dopamine\s+(?:agonist|antagonist)\s+(?:for|in)\s+(?:delirium|parkinson|restless))",
        re.IGNORECASE,
    ),
}


def _normalize_quotes(s: str) -> str:
    """Replace typographic apostrophes/quotes with ASCII for matching."""
    return s.replace("\u2018", "'").replace("\u2019", "'").replace("\u2032", "'")


def keyword_in_text(keyword: str, text: str) -> bool:
    if not keyword or not text:
        return False
    k = _normalize_quotes(keyword).lower()
    t = _normalize_quotes(text).lower()
    # Check negative context for ambiguous abbreviations
    neg_re = _ABBREVIATION_NEGATIVE_CONTEXT.get(k)
    if neg_re and neg_re.search(t):
        return False
    if len(k) <= 3:
        # Exact word match; strip parens, hyphens, and other delimiters
        # Include ,;[] so short tokens are found in "MAP,CVP" or "[HR]" contexts
        parts = t.replace("/", " ").replace("(", " ").replace(")", " ").replace("-", " ").replace(",", " ").replace(";", " ").replace("[", " ").replace("]", " ").split()
        return any(part == k for part in parts)
    # Use word boundary to prevent substring matches (e.g., "perfusion"
    # should not match "hypoperfusion") — consistent with build_living_map.py
    return re.search(r"\b" + re.escape(k) + r"\b", t) is not None


def find_hemodynamic_keywords(keywords: List[str], text: str) -> List[str]:
    matches = []
    for kw in keywords:
        if keyword_in_text(kw, text):
            matches.append(kw)
    return matches


_API_TYPE_MAP = {
    "PLACEBO_COMPARATOR": ("placebo", True),
    "SHAM_COMPARATOR": ("sham", True),
    "NO_INTERVENTION": ("no_intervention", False),
    "ACTIVE_COMPARATOR": ("active_control", False),
}


def extract_arms(study: Dict) -> List[ArmRecord]:
    arms_module = study.get("protocolSection", {}).get("armsInterventionsModule", {})
    arms = []
    for arm in arms_module.get("armGroups", []) or []:
        label = normalize_text(arm.get("label"))
        description = normalize_text(arm.get("description"))
        names = extract_list(arm.get("interventionNames"))
        combined = " ".join([label, description, " ".join(names)])

        # Prefer the structured API type field over text heuristics
        api_type = normalize_text(arm.get("type") or arm.get("armGroupType"))
        api_match = _API_TYPE_MAP.get(api_type.upper()) if api_type else None

        if api_match:
            comparator_type, is_placebo = api_match
        else:
            comparator_type = classify_arm(combined)
            is_placebo = is_placebo_text(combined)

        arm_role = "control" if comparator_type != "experimental" else "experimental"
        arms.append(
            ArmRecord(
                label=label,
                description=description,
                intervention_names="; ".join(names),
                is_placebo=is_placebo,
                comparator_type=comparator_type,
                arm_role=arm_role,
            )
        )
    return arms


def extract_outcomes(study: Dict) -> List[OutcomeRecord]:
    outcomes_module = study.get("protocolSection", {}).get("outcomesModule", {})
    outcome_records: List[OutcomeRecord] = []

    def add_outcomes(items: Iterable[Dict], outcome_type: str) -> None:
        for item in items or []:
            outcome_records.append(
                OutcomeRecord(
                    outcome_type=outcome_type,
                    measure=normalize_text(item.get("measure")),
                    time_frame=normalize_text(item.get("timeFrame")),
                    description=normalize_text(item.get("description")),
                )
            )

    add_outcomes(outcomes_module.get("primaryOutcomes", []), "primary")
    add_outcomes(outcomes_module.get("secondaryOutcomes", []), "secondary")
    add_outcomes(outcomes_module.get("otherOutcomes", []), "other")

    return outcome_records


def extract_study_fields(study: Dict) -> Dict[str, str]:
    protocol = study.get("protocolSection", {})
    ident = protocol.get("identificationModule", {})
    status = protocol.get("statusModule", {})
    design = protocol.get("designModule", {})
    conditions = protocol.get("conditionsModule", {})
    keywords = conditions.get("keywords", []) or []
    design_info = design.get("designInfo", {})
    masking_info = design_info.get("maskingInfo", {})
    phases = design.get("phases") or []
    phase_value = ""
    if isinstance(phases, list) and phases:
        phase_value = "; ".join(extract_list(phases))
    else:
        phase_value = normalize_text(design.get("phase"))

    # Extract countries from locations module
    locations_module = protocol.get("contactsLocationsModule", {})
    locations = locations_module.get("locations", []) or []
    country_set: Set[str] = set()
    for loc in locations:
        country = normalize_text(loc.get("country"))
        if country:
            country_set.add(country)
    countries_str = "; ".join(sorted(country_set))

    return {
        "nct_id": normalize_text(ident.get("nctId")),
        "brief_title": normalize_text(ident.get("briefTitle")),
        "official_title": normalize_text(ident.get("officialTitle")),
        "overall_status": normalize_text(status.get("overallStatus")),
        "study_type": normalize_text(design.get("studyType")),
        "allocation": normalize_text(design_info.get("allocation")),
        "primary_purpose": normalize_text(design_info.get("primaryPurpose")),
        "intervention_model": normalize_text(design_info.get("interventionModel")),
        "masking": normalize_text(masking_info.get("masking") or design_info.get("masking")),
        "masking_description": normalize_text(masking_info.get("maskingDescription")),
        "masking_subjects": "; ".join(
            extract_list(masking_info.get("maskingSubjects", []))
        ),
        "phase": phase_value,
        "start_date": normalize_text(status.get("startDateStruct", {}).get("date")),
        "completion_date": normalize_text(status.get("completionDateStruct", {}).get("date")),
        "last_update_posted": normalize_text(
            status.get("lastUpdatePostDateStruct", {}).get("date")
        ),
        "results_first_posted": normalize_text(
            status.get("resultsFirstPostDateStruct", {}).get("date")
        ),
        "has_results": str(bool(study.get("hasResults"))),
        "enrollment_count": str(
            (design.get("enrollmentInfo", {}) or {}).get("count", "")
        ),
        "enrollment_type": normalize_text(
            (design.get("enrollmentInfo", {}) or {}).get("type")
        ),
        "conditions": "; ".join(extract_list(conditions.get("conditions", []))),
        "keywords": "; ".join(extract_list(keywords)),
        "countries": countries_str,
    }


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


def open_csv(path: Path, header: List[str]) -> csv.DictWriter:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".csv.tmp")
    handle = tmp_path.open("w", encoding="utf-8", newline="")
    try:
        writer = csv.DictWriter(handle, fieldnames=header)
        writer.writeheader()
        writer._handle = handle  # type: ignore[attr-defined]
        writer._tmp_path = tmp_path  # type: ignore[attr-defined]
        writer._final_path = path  # type: ignore[attr-defined]
    except Exception:
        handle.close()
        raise
    return writer


def close_csv(writer: csv.DictWriter) -> None:
    handle = getattr(writer, "_handle", None)
    if handle:
        handle.close()


def finalize_csv(writer: csv.DictWriter) -> None:
    """Rename temp file to final path (atomic on same filesystem)."""
    tmp_path = getattr(writer, "_tmp_path", None)
    final_path = getattr(writer, "_final_path", None)
    if tmp_path and final_path and tmp_path.exists():
        tmp_path.replace(final_path)


def run_query(
    query_name: str,
    query_term: str,
    keywords: List[str],
    output_dir: Path,
    raw_dir: Path,
    max_pages: Optional[int],
    page_size: int,
    updated_since: Optional[str],
) -> Dict[str, int]:
    session = get_session(user_agent=DEFAULT_USER_AGENT)
    query_text_base = query_term  # Original query from config (before date filter)
    if updated_since:
        query_term = (
            f"{query_term} AND AREA[LastUpdatePostDate]RANGE[{updated_since},MAX]"
        )
    params = {"query.term": query_term}

    raw_path = raw_dir / f"{query_name}_studies.jsonl"
    studies_path = output_dir / f"{query_name}_studies.csv"
    arms_path = output_dir / f"{query_name}_arms.csv"
    outcomes_path = output_dir / f"{query_name}_outcomes.csv"
    hemo_path = output_dir / f"{query_name}_hemodynamic_mentions.csv"

    studies_writer = open_csv(
        studies_path,
        [
            "nct_id",
            "brief_title",
            "official_title",
            "overall_status",
            "study_type",
            "allocation",
            "primary_purpose",
            "intervention_model",
            "masking",
            "masking_description",
            "masking_subjects",
            "phase",
            "start_date",
            "completion_date",
            "last_update_posted",
            "results_first_posted",
            "has_results",
            "enrollment_count",
            "enrollment_type",
            "conditions",
            "keywords",
            "arm_count",
            "placebo_arm_count",
            "outcome_count",
            "hemo_outcome_count",
            "countries",
            "updated_since",
            "query_name",
        ],
    )
    arms_writer = open_csv(
        arms_path,
        [
            "nct_id",
            "arm_label",
            "arm_description",
            "intervention_names",
            "is_placebo_arm",
            "comparator_type",
            "arm_role",
            "query_name",
        ],
    )
    outcomes_writer = open_csv(
        outcomes_path,
        [
            "nct_id",
            "outcome_type",
            "measure",
            "time_frame",
            "description",
            "query_name",
        ],
    )
    hemo_writer = open_csv(
        hemo_path,
        [
            "nct_id",
            "outcome_type",
            "measure",
            "keyword",
            "matched_text",
            "query_name",
        ],
    )

    total = 0
    total_count = 0
    arm_rows = 0
    placebo_arm_rows = 0
    outcome_rows = 0
    hemo_rows = 0
    unique_hemo_keywords: Set[str] = set()

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with raw_path.open("w", encoding="utf-8") as raw_handle:
            for idx, page in enumerate(
                iter_study_pages(
                    session,
                    params,
                    timeout=DEFAULT_TIMEOUT,
                    page_size=page_size,
                    max_pages=max_pages,
                )
            ):
                if idx == 0:
                    total_count = page.get("totalCount", 0)
                    print(
                        f"  [{query_name}] {total_count} studies found, fetching...",
                        flush=True,
                    )
                studies = page.get("studies", []) or []
                for study in studies:
                    raw_handle.write(json.dumps(study, ensure_ascii=True) + "\n")
                    total += 1

                    fields = extract_study_fields(study)
                    # Validate NCT ID format (V-2)
                    nct_id = fields.get("nct_id", "")
                    if not _NCT_RE.match(nct_id):
                        continue
                    # Sanitize text fields against CSV formula injection (V-14)
                    for key in ("brief_title", "official_title", "conditions", "keywords", "countries"):
                        fields[key] = _csv_safe(fields.get(key, ""))
                    arms = extract_arms(study)
                    outcomes = extract_outcomes(study)

                    placebo_arms = [arm for arm in arms if arm.is_placebo]

                    hemo_matches = []
                    for outcome in outcomes:
                        outcome_text = " ".join(
                            [outcome.measure, outcome.description, outcome.time_frame]
                        ).strip()
                        matches = find_hemodynamic_keywords(keywords, outcome_text)
                        if matches:
                            for kw in matches:
                                hemo_matches.append((outcome, kw, outcome_text))

                    fields.update(
                        {
                            "arm_count": str(len(arms)),
                            "placebo_arm_count": str(len(placebo_arms)),
                            "outcome_count": str(len(outcomes)),
                            "hemo_outcome_count": str(len(hemo_matches)),
                            "updated_since": updated_since or "",
                            "query_name": query_name,
                        }
                    )
                    studies_writer.writerow(fields)

                    for arm in arms:
                        arms_writer.writerow(
                            {
                                "nct_id": fields["nct_id"],
                                "arm_label": _csv_safe(arm.label),
                                "arm_description": _csv_safe(arm.description),
                                "intervention_names": _csv_safe(arm.intervention_names),
                                "is_placebo_arm": str(arm.is_placebo),
                                "comparator_type": arm.comparator_type,
                                "arm_role": arm.arm_role,
                                "query_name": query_name,
                            }
                        )
                        arm_rows += 1
                        if arm.is_placebo:
                            placebo_arm_rows += 1

                    for outcome in outcomes:
                        outcomes_writer.writerow(
                            {
                                "nct_id": fields["nct_id"],
                                "outcome_type": outcome.outcome_type,
                                "measure": _csv_safe(outcome.measure),
                                "time_frame": _csv_safe(outcome.time_frame),
                                "description": _csv_safe(outcome.description),
                                "query_name": query_name,
                            }
                        )
                        outcome_rows += 1

                    for outcome, kw, text in hemo_matches:
                        hemo_writer.writerow(
                            {
                                "nct_id": fields["nct_id"],
                                "outcome_type": outcome.outcome_type,
                                "measure": _csv_safe(outcome.measure),
                                "keyword": kw,
                                "matched_text": _csv_safe(text),
                                "query_name": query_name,
                            }
                        )
                        hemo_rows += 1
                        unique_hemo_keywords.add(kw)

                print(
                    f"  [{query_name}] page {idx + 1}: {total}/{total_count} studies, "
                    f"{hemo_rows} hemo mentions",
                    flush=True,
                )
                time.sleep(DEFAULT_RATE_LIMIT)
    except Exception:
        close_csv(studies_writer)
        close_csv(arms_writer)
        close_csv(outcomes_writer)
        close_csv(hemo_writer)
        # Remove incomplete temp files so stale data isn't mistaken for good data
        for w in (studies_writer, arms_writer, outcomes_writer, hemo_writer):
            tmp = getattr(w, "_tmp_path", None)
            if tmp and tmp.exists():
                tmp.unlink()
        raise
    else:
        close_csv(studies_writer)
        close_csv(arms_writer)
        close_csv(outcomes_writer)
        close_csv(hemo_writer)
        # Atomically promote temp files to final paths
        finalize_csv(studies_writer)
        finalize_csv(arms_writer)
        finalize_csv(outcomes_writer)
        finalize_csv(hemo_writer)

    return {
        "search_date_utc": datetime.now(timezone.utc).isoformat(),
        "query_text": query_text_base,
        "query_text_executed": query_term,
        "total_count": total_count,
        "returned_count": total,
        "arm_rows": arm_rows,
        "placebo_arm_rows": placebo_arm_rows,
        "outcome_rows": outcome_rows,
        "hemo_rows": hemo_rows,
        "unique_hemo_keywords": len(unique_hemo_keywords),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch ICU/critical care RCTs from CT.gov")
    parser.add_argument(
        "--query",
        action="append",
        dest="queries",
        help="Query name from config (repeatable). Default: icu_rct_broad",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Optional max pages to fetch (for testing).",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help="CT.gov API page size (default from config).",
    )
    parser.add_argument(
        "--updated-since",
        default=None,
        help="Optional YYYY-MM-DD to fetch trials updated since that date.",
    )
    args = parser.parse_args()

    if args.updated_since:
        from datetime import datetime as _dt

        try:
            _dt.strptime(args.updated_since, "%Y-%m-%d")
        except ValueError:
            parser.error(
                f"--updated-since must be YYYY-MM-DD, got: {args.updated_since}"
            )

    config = load_config(CONFIG_PATH)
    keywords = config.get("hemodynamic_keywords", [])
    query_map = config.get("queries", {})

    if not query_map:
        raise ValueError("No queries found in config")

    queries = args.queries or ["icu_rct_broad"]

    output_dir = ROOT / "output"
    raw_dir = ROOT / "raw"
    log_dir = ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    summary_path = log_dir / "ctgov_icu_fetch_summary.json"

    summary: Dict[str, Dict[str, int]] = {}
    for query_name in queries:
        if query_name not in query_map:
            raise KeyError(f"Query not found in config: {query_name}")
        query_term = query_map[query_name].get("query.term")
        if not query_term:
            raise ValueError(f"Missing query.term for {query_name}")
        summary[query_name] = run_query(
            query_name=query_name,
            query_term=query_term,
            keywords=keywords,
            output_dir=output_dir,
            raw_dir=raw_dir,
            max_pages=args.max_pages,
            page_size=args.page_size,
            updated_since=args.updated_since,
        )

    # Merge into existing summary to avoid clobbering results from prior runs
    existing: Dict[str, Dict[str, int]] = {}
    if summary_path.exists():
        try:
            existing = json.loads(summary_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}
    existing.update(summary)
    summary_tmp = summary_path.with_suffix(".json.tmp")
    summary_tmp.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    summary_tmp.replace(summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

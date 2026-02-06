#!/usr/bin/env python3
"""
Build a living map dataset from CT.gov ICU RCT exports.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Dict, Iterable, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = ROOT / "output"
DEFAULT_DASHBOARD_DIR = ROOT / "dashboard" / "data"
DEFAULT_LABEL = "broad"

CANONICAL_RULES = [
    # Specific multi-word rules MUST come before their general counterparts
    # to prevent substring shadowing (e.g., "vasopressor-free days" must not
    # match "vasopressor" from the Vasopressor/Inotrope rule).
    ("Vasopressor-free days", ["vasopressor-free days"]),
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
    ("SVR", ["systemic vascular resistance", "svr", "svri"]),
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
            "inotrope",
            "inotropic",
        ],
    ),
    ("Perfusion", ["perfusion"]),
    ("Severity score", ["sofa", "apache", "apache ii", "saps", "saps ii", "mods", "qsofa"]),
]

UNIT_PATTERNS: List[Tuple[str, str]] = [
    (r"\bmm\s?hg\b", "mmHg"),
    (r"\bcm\s?h2o\b", "cmH2O"),
    (r"\bmmol\s*/\s*l\b|\bmmol per l\b", "mmol/L"),
    (r"\bmg\s*/\s*dl\b", "mg/dL"),
    (r"\bml\s*/\s*kg\s*/\s*min\b", "mL/kg/min"),
    (r"\bl\s*/\s*min\s*/\s*m2\b|\bl\s*/\s*min\s*/\s*m\^?2\b", "L/min/m2"),
    (r"\bml\s*/\s*min\s*/\s*m2\b|\bml\s*/\s*min\s*/\s*m\^?2\b", "mL/min/m2"),
    (r"\bl\s*/\s*min\b", "L/min"),
    (r"\bml\s*/\s*min\b", "mL/min"),
    (
        r"\bbeats\s*/\s*min\b|\bbeats per minute\b|\bbpm\b",
        "bpm",
    ),
    (r"\bdyn(?:es)?\s*\*?\s*s\s*/\s*cm\^?5\b", "dyn*s/cm5"),
    (r"\bwatt(?:s)?\b", "W"),
    (r"(?<!\w)(?:\d[\d.]*\s*)sec(?:onds)?(?!\w)", "s"),
]


@dataclass
class KeywordStats:
    mention_count: int = 0
    study_ids: Set[str] = None
    placebo_study_ids: Set[str] = None

    def __post_init__(self) -> None:
        if self.study_ids is None:
            self.study_ids = set()
        if self.placebo_study_ids is None:
            self.placebo_study_ids = set()


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [row for row in reader]


def normalize_int(value: Optional[str]) -> int:
    try:
        return int(value) if value is not None and value != "" else 0
    except ValueError:
        return 0


def split_list(value: str) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(";") if item.strip()]


def token_in_text(token: str, text: str) -> bool:
    if not token or not text:
        return False
    token = token.lower()
    text = text.lower()
    if len(token) <= 3:
        return any(part == token for part in text.replace("/", " ").split())
    return token in text


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
    return keyword.strip() or "Unmapped"


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


def build_living_map(
    studies_csv: Path,
    hemo_csv: Path,
    output_dir: Path,
    dashboard_dir: Optional[Path] = None,
    label: str = DEFAULT_LABEL,
    write_parquet_output: bool = True,
) -> Dict[str, object]:
    studies_rows = read_csv(studies_csv)
    hemo_rows = read_csv(hemo_csv)

    studies_map: Dict[str, Dict[str, str]] = {}
    for row in studies_rows:
        nct_id = row.get("nct_id", "").strip()
        if nct_id:
            studies_map[nct_id] = row

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
    ]

    keyword_stats: Dict[str, KeywordStats] = defaultdict(KeywordStats)
    normalized_keyword_stats: Dict[str, KeywordStats] = defaultdict(KeywordStats)
    unit_stats: Dict[str, KeywordStats] = defaultdict(KeywordStats)
    outcome_stats: Dict[str, KeywordStats] = defaultdict(KeywordStats)
    condition_stats: Dict[str, KeywordStats] = defaultdict(KeywordStats)

    studies_with_hemo: Set[str] = set()
    studies_with_hemo_and_placebo: Set[str] = set()

    total_mentions = 0
    placebo_mentions = 0

    detailed_tmp = detailed_path.with_suffix(".csv.tmp")
    with detailed_tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=detailed_fields)
        writer.writeheader()

        for row in hemo_rows:
            nct_id = row.get("nct_id", "").strip()
            if not nct_id:
                continue
            study = studies_map.get(nct_id, {})
            placebo_arm_count = normalize_int(study.get("placebo_arm_count"))
            has_placebo = placebo_arm_count > 0

            detailed_row = {
                "nct_id": nct_id,
                "brief_title": study.get("brief_title", "").strip(),
                "overall_status": study.get("overall_status", "").strip(),
                "allocation": study.get("allocation", "").strip(),
                "intervention_model": study.get("intervention_model", "").strip(),
                "masking": study.get("masking", "").strip(),
                "masking_description": study.get("masking_description", "").strip(),
                "masking_subjects": study.get("masking_subjects", "").strip(),
                "phase": study.get("phase", "").strip(),
                "start_date": study.get("start_date", "").strip(),
                "completion_date": study.get("completion_date", "").strip(),
                "last_update_posted": study.get("last_update_posted", "").strip(),
                "results_first_posted": study.get("results_first_posted", "").strip(),
                "enrollment_count": study.get("enrollment_count", "").strip(),
                "enrollment_type": study.get("enrollment_type", "").strip(),
                "conditions": study.get("conditions", "").strip(),
                "study_keywords": study.get("keywords", "").strip(),
                "arm_count": study.get("arm_count", "").strip(),
                "placebo_arm_count": str(placebo_arm_count),
                "has_placebo_arm": str(has_placebo),
                "outcome_type": row.get("outcome_type", "").strip(),
                "measure": row.get("measure", "").strip(),
                "keyword": row.get("keyword", "").strip(),
                "normalized_keyword": "",
                "unit_raw": "",
                "normalized_unit": "",
                "matched_text": row.get("matched_text", "").strip(),
                "query_name": row.get("query_name", "").strip(),
            }
            detailed_row["normalized_keyword"] = normalize_keyword(
                detailed_row["keyword"], detailed_row["matched_text"]
            )
            unit_raw, unit_normalized = extract_unit(
                f"{detailed_row['measure']} {detailed_row['matched_text']}"
            )
            detailed_row["unit_raw"] = unit_raw
            detailed_row["normalized_unit"] = unit_normalized
            writer.writerow(detailed_row)

            total_mentions += 1
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

    total_studies = len(studies_map)
    studies_with_placebo = sum(
        1 for row in studies_rows if normalize_int(row.get("placebo_arm_count")) > 0
    )

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "source": {
            "studies_csv": str(studies_csv),
            "hemo_csv": str(hemo_csv),
        },
        "totals": {
            "total_studies": total_studies,
            "studies_with_placebo": studies_with_placebo,
            "studies_with_hemo_mentions": len(studies_with_hemo),
            "studies_with_hemo_and_placebo": len(studies_with_hemo_and_placebo),
            "total_hemo_mentions": total_mentions,
            "placebo_hemo_mentions": placebo_mentions,
            "non_placebo_hemo_mentions": total_mentions - placebo_mentions,
        },
        "keywords": [
            {
                "keyword": key,
                "mention_count": stats.mention_count,
                "study_count": len(stats.study_ids),
                "placebo_study_count": len(stats.placebo_study_ids),
            }
            for key, stats in keyword_stats.items()
        ],
        "normalized_keywords": [
            {
                "keyword": key,
                "mention_count": stats.mention_count,
                "study_count": len(stats.study_ids),
                "placebo_study_count": len(stats.placebo_study_ids),
            }
            for key, stats in normalized_keyword_stats.items()
        ],
        "units": [
            {
                "unit": key,
                "mention_count": stats.mention_count,
                "study_count": len(stats.study_ids),
                "placebo_study_count": len(stats.placebo_study_ids),
            }
            for key, stats in unit_stats.items()
        ],
        "outcome_types": [
            {
                "outcome_type": key,
                "mention_count": stats.mention_count,
                "study_count": len(stats.study_ids),
                "placebo_study_count": len(stats.placebo_study_ids),
            }
            for key, stats in outcome_stats.items()
        ],
        "conditions": [
            {
                "condition": key,
                "mention_count": stats.mention_count,
                "study_count": len(stats.study_ids),
                "placebo_study_count": len(stats.placebo_study_ids),
            }
            for key, stats in condition_stats.items()
        ],
    }

    parquet_info: Dict[str, str] = {"status": "skipped", "reason": "disabled"}
    if write_parquet_output:
        parquet_path = output_dir / f"icu_hemodynamic_living_map{suffix}.parquet"
        parquet_info = write_parquet(detailed_path, parquet_path)

    summary["parquet"] = parquet_info

    summary_path = output_dir / f"icu_hemodynamic_summary{suffix}.json"
    summary_tmp = summary_path.with_suffix(".json.tmp")
    summary_tmp.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary_tmp.replace(summary_path)

    if dashboard_dir:
        dashboard_dir.mkdir(parents=True, exist_ok=True)
        for name, content in [
            (f"icu_hemodynamic_summary{suffix}.json", json.dumps(summary, indent=2)),
            (f"icu_hemodynamic_living_map{suffix}.csv", detailed_path.read_text(encoding="utf-8")),
        ]:
            tmp = dashboard_dir / f"{name}.tmp"
            final = dashboard_dir / name
            tmp.write_text(content, encoding="utf-8")
            tmp.replace(final)

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
    args = parser.parse_args()

    summary = build_living_map(
        Path(args.studies),
        Path(args.hemo),
        Path(args.output_dir),
        Path(args.dashboard_dir),
        label=args.label,
        write_parquet_output=not args.no_write_parquet,
    )

    print("Living map created.")
    print(f"Studies: {summary['totals']['total_studies']}")
    print(f"Hemo mentions: {summary['totals']['total_hemo_mentions']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

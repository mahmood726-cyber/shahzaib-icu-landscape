#!/usr/bin/env python3
"""
TruthCert capsule builder for the ICU Living Map pipeline.

Produces proof-carrying provenance bundles:
  - Input/output file hashes (SHA-256)
  - Ontology versioning (deterministic hash of CANONICAL_RULES + UNIT_PATTERNS)
  - Git SHA + machine ID for traceability
  - 16 base validators + 5 enrichment-conditional across P0/P1/P2 severity classes
  - Drift detection against previous capsules
  - Assurance badge (Bronze / Silver / Gold)
  - Abstention list (unmapped keywords)
  - Append-only drift ledger (JSONL)
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from validators import ValidationResult, run_validators


# ── Hashing ───────────────────────────────────────────────────────────

def compute_file_hash(path: Path) -> str:
    """SHA-256 hash of a file using chunked reads."""
    sha = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(65536)
            if not chunk:
                break
            sha.update(chunk)
    return f"sha256:{sha.hexdigest()}"


# Semantic version for the ontology — update when rules change.
# Format: "v{major}.{minor} — {description}"
ONTOLOGY_SEMANTIC_VERSION = "v2.0 — added fluid responsiveness, echo params, resuscitation endpoints, ICU severity score separation, HR/SV negative context, milrinone/levosimendan, tissue perfusion specificity"


def compute_ontology_version(
    canonical_rules: List[Tuple[str, List[str]]],
    unit_patterns: List[Tuple[str, str]],
) -> str:
    """Deterministic SHA-256 of the ontology rules (sorted JSON)."""
    payload = json.dumps(
        {"canonical_rules": canonical_rules, "unit_patterns": unit_patterns},
        sort_keys=True,
        ensure_ascii=True,
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


# ── Environment ───────────────────────────────────────────────────────

def get_git_sha(repo_dir: Path) -> str:
    """Short git SHA of HEAD, or 'unknown' if not a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "unknown"


def get_machine_id() -> str:
    """Return a hashed machine identifier to avoid leaking hostname."""
    raw = socket.gethostname()
    return f"host:{hashlib.sha256(raw.encode()).hexdigest()[:12]}"


# ── Drift Detection ──────────────────────────────────────────────────

def _pct_change(old: int, new: int, has_prev_capsule: bool = False) -> Optional[float]:
    """Percentage change. Returns None only for true first-run bootstrap (no prev capsule).

    When a previous capsule exists, 0→N is flagged as major drift (likely
    recovery from a failed fetch), not silently suppressed as bootstrap.
    """
    if old == 0:
        if new == 0:
            return 0.0
        # True bootstrap (no previous capsule): suppress drift
        # Recovery from error (prev capsule had 0): flag as major
        return 100.0 if has_prev_capsule else None
    return abs(new - old) / old * 100.0


def _drift_severity(pct: float) -> str:
    if pct >= 20.0:
        return "major"
    if pct >= 5.0:
        return "moderate"
    return "minor"


def detect_drift(
    label: str,
    current_totals: Dict[str, int],
    ontology_version: str,
    prev_capsule: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Compare current run to previous capsule and return drift events."""
    events: List[Dict[str, Any]] = []
    if prev_capsule is None:
        return events

    prev_totals = prev_capsule.get("_summary_totals", {})
    prev_ontology = prev_capsule.get("ontology_version", "")

    # Trial count change
    old_trials = prev_totals.get("total_studies", 0)
    new_trials = current_totals.get("total_studies", 0)
    if old_trials != new_trials:
        pct = _pct_change(old_trials, new_trials, has_prev_capsule=True)
        if pct is not None:  # None = true first-run bootstrap only
            events.append({
                "metric": "total_studies",
                "old": old_trials,
                "new": new_trials,
                "pct_change": round(pct, 1),
                "severity": _drift_severity(pct),
            })

    # Hemo mention count change
    old_hemo = prev_totals.get("total_hemo_mentions", 0)
    new_hemo = current_totals.get("total_hemo_mentions", 0)
    if old_hemo != new_hemo:
        pct = _pct_change(old_hemo, new_hemo, has_prev_capsule=True)
        if pct is not None:
            events.append({
                "metric": "total_hemo_mentions",
                "old": old_hemo,
                "new": new_hemo,
                "pct_change": round(pct, 1),
                "severity": _drift_severity(pct),
            })

    # Placebo ratio shift
    old_hemo_total = prev_totals.get("total_hemo_mentions", 0)
    new_hemo_total = current_totals.get("total_hemo_mentions", 0)
    old_placebo_ratio = (
        prev_totals.get("placebo_hemo_mentions", 0) / old_hemo_total * 100.0
        if old_hemo_total > 0 else 0.0
    )
    new_placebo_ratio = (
        current_totals.get("placebo_hemo_mentions", 0) / new_hemo_total * 100.0
        if new_hemo_total > 0 else 0.0
    )
    ratio_shift = abs(new_placebo_ratio - old_placebo_ratio)
    if ratio_shift > 2.0:
        events.append({
            "metric": "placebo_ratio_ppt",
            "old": round(old_placebo_ratio, 1),
            "new": round(new_placebo_ratio, 1),
            "ppt_shift": round(ratio_shift, 1),
            "severity": "moderate" if ratio_shift < 5.0 else "major",
        })

    # Ontology version change
    if prev_ontology and ontology_version != prev_ontology:
        events.append({
            "metric": "ontology_version",
            "old": prev_ontology[:24],
            "new": ontology_version[:24],
            "severity": "major",
        })

    # Source count change (multi-source tracking)
    prev_source_count = prev_capsule.get("_source_count", 0)
    current_source_count = current_totals.get("_source_count", 0)
    if prev_source_count and current_source_count and prev_source_count != current_source_count:
        events.append({
            "metric": "source_count",
            "old": prev_source_count,
            "new": current_source_count,
            "severity": "moderate" if abs(current_source_count - prev_source_count) <= 1 else "major",
        })

    return events


# ── Badge Calculation ─────────────────────────────────────────────────

def calculate_badge(
    validations: List[ValidationResult],
    drift_events: List[Dict[str, Any]],
    prev_capsules: List[Dict[str, Any]],
) -> Tuple[str, List[str]]:
    """
    Determine assurance badge:
      Bronze: Any P0 failure OR any P1 warning
      Silver: All P0 pass + all P1 pass
      Gold:   Silver + last 2 previous capsules were silver/gold + no major drift
    """
    reasons: List[str] = []

    p0_fails = [v for v in validations if v.severity == "P0" and not v.passed]
    p1_fails = [v for v in validations if v.severity == "P1" and not v.passed]

    if p0_fails:
        reasons.append(f"{len(p0_fails)} P0 failure(s): {[v.rule_id for v in p0_fails]}")
        return "bronze", reasons

    if p1_fails:
        reasons.append(f"{len(p1_fails)} P1 warning(s): {[v.rule_id for v in p1_fails]}")
        return "bronze", reasons

    reasons.append("All P0 passed")
    reasons.append("All P1 passed")

    # Check for Gold eligibility
    has_major_drift = any(e.get("severity") == "major" for e in drift_events)
    if has_major_drift:
        reasons.append("Major drift detected — silver only")
        return "silver", reasons

    # Need at least 2 previous capsules at silver or gold
    if len(prev_capsules) < 2:
        reasons.append(f"Only {len(prev_capsules)} previous capsule(s) — need 2 for gold")
        return "silver", reasons

    recent_two = prev_capsules[-2:]
    all_good = all(c.get("badge") in ("silver", "gold") for c in recent_two)
    if not all_good:
        badges = [c.get("badge", "?") for c in recent_two]
        reasons.append(f"Previous badges {badges} — need silver/gold for gold")
        return "silver", reasons

    reasons.append("Last 2 capsules were silver/gold + no major drift")
    return "gold", reasons


# ── Abstentions ───────────────────────────────────────────────────────

def collect_abstentions(
    summary: Dict[str, Any],
    canonical_names: List[str],
    canonical_rules: Optional[List[Any]] = None,
) -> List[Dict[str, Any]]:
    """Identify normalized keywords that mapped to 'Unmapped' — these are abstentions.

    A raw keyword is NOT an abstention if it appears as a token in any
    CANONICAL_RULES entry, because that means normalization handled it.
    Previous versions used case-sensitive comparison which generated
    false-positive abstentions for tokens like "blood pressure" vs
    canonical name "Blood Pressure".
    """
    abstentions: List[Dict[str, Any]] = []
    for item in summary.get("normalized_keywords", []):
        kw = item.get("keyword", "")
        if kw.lower() == "unmapped":
            abstentions.append({
                "keyword": kw,
                "mention_count": item.get("mention_count", 0),
                "reason": "No matching canonical rule",
            })

    # Build a set of all known tokens (lowercase) from CANONICAL_RULES.
    # Any raw keyword that matches a token was successfully normalized
    # and should NOT be flagged as an abstention.
    known_tokens: set = set()
    if canonical_rules:
        for _canonical_name, tokens in canonical_rules:
            for token in tokens:
                known_tokens.add(token.lower())
    # Also add canonical names themselves (case-insensitive)
    canonical_lower = {name.lower() for name in canonical_names}

    # Check raw keywords not handled by normalization
    normalized_set_lower = {
        item.get("keyword", "").lower()
        for item in summary.get("normalized_keywords", [])
    }
    for item in summary.get("keywords", []):
        kw = item.get("keyword", "")
        kw_lower = kw.lower()
        if not kw:
            continue
        # Skip if this raw keyword is a known canonical token — it
        # was normalized successfully
        if kw_lower in known_tokens or kw_lower in canonical_lower:
            continue
        # Skip if it appears in the normalized set (case-insensitive)
        if kw_lower in normalized_set_lower:
            continue
        abstentions.append({
            "keyword": kw,
            "mention_count": item.get("mention_count", 0),
            "reason": "Raw keyword not in normalized set",
        })
    return abstentions


# ── Previous capsule loading ──────────────────────────────────────────

_CAPSULE_REQUIRED_KEYS = {"capsule_id", "generated_utc", "badge"}
_CAPSULE_FN_RE = re.compile(r"^capsule_[a-zA-Z0-9_-]+_\d{8}T\d{6}\d*Z\.json$")


def _load_prev_capsules(
    capsule_dir: Path, label: str, limit: int = 5,
) -> List[Dict[str, Any]]:
    """Load previous capsule JSONs from capsule_dir, sorted by generated_utc.

    Only the most recent `limit` capsules are returned (default 5).
    Capsules missing required keys or with non-conforming filenames are skipped.
    """
    capsules: List[Dict[str, Any]] = []
    if not capsule_dir.exists():
        return capsules
    pattern = f"capsule_{label}_*.json"
    for path in capsule_dir.glob(pattern):
        # Validate filename format to prevent adversarial capsule injection
        if not _CAPSULE_FN_RE.match(path.name):
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # Validate capsule structure (V-18)
            if not isinstance(data, dict):
                continue
            if not _CAPSULE_REQUIRED_KEYS.issubset(data.keys()):
                continue
            capsules.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    capsules.sort(key=lambda c: c.get("generated_utc", ""))
    return capsules[-limit:] if limit else capsules


def _load_latest_capsule(capsule_dir: Path, label: str) -> Optional[Dict[str, Any]]:
    """Load the most recent capsule for this label."""
    capsules = _load_prev_capsules(capsule_dir, label)
    return capsules[-1] if capsules else None


# ── Drift Ledger ──────────────────────────────────────────────────────

def _append_drift_ledger(
    ledger_path: Path,
    capsule_id: str,
    generated_utc: str,
    label: str,
    drift_events: List[Dict[str, Any]],
    badge: str,
    totals: Dict[str, int],
) -> None:
    """Append a single JSONL line to the drift ledger."""
    entry = {
        "capsule_id": capsule_id,
        "generated_utc": generated_utc,
        "label": label,
        "badge": badge,
        "totals": totals,
        "drift_events": drift_events,
    }
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())


# ── Capsule Builder (orchestrator) ────────────────────────────────────

def build_capsule(
    label: str,
    studies_csv: Path,
    hemo_csv: Path,
    output_csv: Path,
    summary: Dict[str, Any],
    canonical_rules: List[Any],
    unit_patterns: List[Any],
    output_dir: Path,
    dashboard_dir: Optional[Path] = None,
    raw_jsonl: Optional[Path] = None,
    enrich_db: Optional[Path] = None,
    run_timestamp: Optional[str] = None,
    search_strategy: Optional[Dict[str, Any]] = None,
    extra_input_files: Optional[List[Path]] = None,
) -> Dict[str, Any]:
    """
    Build a TruthCert capsule:
      1. Hash inputs and outputs
      2. Compute ontology version
      3. Run validators (16 base + 5 enrichment-conditional)
      4. Detect drift against previous capsule
      5. Calculate badge
      6. Collect abstentions
      7. Write capsule JSON + append drift ledger
      8. Copy capsule to dashboard/data/ if specified
    """
    # Validate label to prevent path traversal (defense-in-depth)
    if not re.match(r"^[a-zA-Z0-9_-]+$", label):
        raise ValueError(f"Invalid capsule label '{label}': must be alphanumeric/hyphen/underscore")

    repo_dir = Path(__file__).resolve().parent
    capsule_dir = output_dir / "capsule"
    capsule_dir.mkdir(parents=True, exist_ok=True)

    # Use caller-provided timestamp for determinism (single timestamp per run).
    # datetime.fromisoformat() on Python <3.11 cannot parse timezone offsets
    # like "+00:00", so we strip it and attach UTC explicitly.
    if run_timestamp:
        generated_utc = run_timestamp
        try:
            # Strip trailing timezone offset for Python <3.11 compat
            ts = run_timestamp
            if ts.endswith("+00:00"):
                ts = ts[:-6]
            elif ts.endswith("Z"):
                ts = ts[:-1]
            parsed = datetime.fromisoformat(ts)
            # Use astimezone for TZ-aware datetimes, replace for naive (stripped UTC)
            now = parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            raise ValueError(
                f"Malformed run_timestamp '{run_timestamp}' — capsule generation "
                "requires a valid ISO 8601 timestamp (fail-closed)"
            )
    else:
        now = datetime.now(timezone.utc)
        generated_utc = now.isoformat()
    timestamp = now.strftime("%Y%m%dT%H%M%S%fZ")
    capsule_id = f"TC-{label}-{timestamp}"

    # 1. Hash inputs/outputs
    input_hashes: Dict[str, str] = {}
    for path in [studies_csv, hemo_csv]:
        if path.exists():
            input_hashes[path.name] = compute_file_hash(path)
    if raw_jsonl is not None and raw_jsonl.exists():
        input_hashes[raw_jsonl.name] = compute_file_hash(raw_jsonl)
    # Hash additional source CSVs (PubMed primary)
    if extra_input_files:
        for extra_path in extra_input_files:
            if extra_path is not None and extra_path.exists():
                input_hashes[extra_path.name] = compute_file_hash(extra_path)
    if enrich_db is not None and enrich_db.exists():
        try:
            input_hashes["enrichment_db.sqlite"] = compute_file_hash(enrich_db)
        except (OSError, PermissionError) as exc:
            import sys
            print(f"  [truthcert] Cannot hash enrichment DB (locked?): {exc}", file=sys.stderr)

    output_hashes: Dict[str, str] = {}
    if output_csv.exists():
        output_hashes[output_csv.name] = compute_file_hash(output_csv)
    suffix = "" if label == "broad" else f"_{label}"
    summary_path = output_dir / f"icu_hemodynamic_summary{suffix}.json"
    if summary_path.exists():
        output_hashes[summary_path.name] = compute_file_hash(summary_path)

    # 2. Ontology version
    ontology_version = compute_ontology_version(canonical_rules, unit_patterns)

    # 3. Run validators
    canonical_names = [rule[0] for rule in canonical_rules]
    validations = run_validators(
        studies_csv=studies_csv,
        hemo_csv=hemo_csv,
        output_csv=output_csv,
        summary=summary,
        ontology_version=ontology_version,
        input_hashes=input_hashes,
        config_keywords=canonical_names,
        enrich_db=enrich_db,
    )

    # 4. Drift detection
    prev_capsule = _load_latest_capsule(capsule_dir, label)
    current_totals = summary.get("totals", {})
    drift_events = detect_drift(label, current_totals, ontology_version, prev_capsule)

    # 5. Badge
    prev_capsules = _load_prev_capsules(capsule_dir, label)
    badge, badge_reasons = calculate_badge(validations, drift_events, prev_capsules)

    # 6. Abstentions
    abstentions = collect_abstentions(summary, canonical_names, canonical_rules=canonical_rules)

    # 7. Build capsule dict
    capsule = {
        "capsule_id": capsule_id,
        "generated_utc": generated_utc,
        "pipeline_version": get_git_sha(repo_dir),
        "machine_id": get_machine_id(),
        "python_version": platform.python_version(),
        "ontology_version": ontology_version,
        "ontology_semantic_version": ONTOLOGY_SEMANTIC_VERSION,
        "input_hashes": input_hashes,
        "output_hashes": output_hashes,
        "validations": [v.to_dict() for v in validations],
        "badge": badge,
        "badge_reasons": badge_reasons,
        "drift_events": drift_events,
        "abstentions": abstentions,
        "previous_capsule_id": prev_capsule.get("capsule_id") if prev_capsule else None,
        "enrichment_db_hash": input_hashes.get("enrichment_db.sqlite"),
        "search_strategy": search_strategy,
        "_summary_totals": current_totals,
    }

    # Write capsule JSON (timestamped for history + latest symlink-style copy)
    capsule_path = capsule_dir / f"capsule_{label}_{timestamp}.json"
    capsule_tmp = capsule_path.with_suffix(".json.tmp")
    capsule_tmp.write_text(json.dumps(capsule, indent=2, ensure_ascii=False), encoding="utf-8")
    capsule_tmp.replace(capsule_path)

    # Also write a "latest" capsule for easy dashboard access
    latest_path = capsule_dir / f"capsule{suffix}.json"
    latest_tmp = latest_path.with_suffix(".json.tmp")
    latest_tmp.write_text(json.dumps(capsule, indent=2, ensure_ascii=False), encoding="utf-8")
    latest_tmp.replace(latest_path)

    # 8. Append drift ledger
    ledger_path = capsule_dir / "drift_ledger.jsonl"
    _append_drift_ledger(ledger_path, capsule_id, generated_utc, label,
                         drift_events, badge, current_totals)

    # 9. Copy to dashboard/data/
    if dashboard_dir:
        dashboard_dir.mkdir(parents=True, exist_ok=True)
        dash_name = f"capsule{suffix}.json"
        dash_tmp = dashboard_dir / f"{dash_name}.tmp"
        dash_final = dashboard_dir / dash_name
        dash_tmp.write_text(json.dumps(capsule, indent=2, ensure_ascii=False), encoding="utf-8")
        dash_tmp.replace(dash_final)

    p0_count = sum(1 for v in validations if v.severity == "P0" and v.passed)
    p0_total = sum(1 for v in validations if v.severity == "P0")
    print(f"TruthCert: {capsule_id} | badge={badge} | P0={p0_count}/{p0_total} | drift={len(drift_events)} events")

    return capsule

#!/usr/bin/env python3
"""
Living update orchestrator for the ICU Living Trial Landscape.

Runs the full pipeline with incremental updates:
  1. Determine last successful run date from living_log.jsonl
  2. Fetch new/updated trials from CT.gov
  3. Search PubMed primary (incremental since last run)
  4. Enrich new trials (optional)
  5. Build living map with all source CSVs
  6. Append cycle record to living_log.jsonl

Usage:
  python living_update.py                    # Full living update
  python living_update.py --dry-run          # Show what would execute
  python living_update.py --skip-enrich      # Skip enrichment step
  python living_update.py --sources ctgov    # Only CT.gov source
  python living_update.py --force-full       # Ignore incremental, full refresh
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parent
LIVING_LOG_PATH = ROOT / "living_log.jsonl"
LOCK_PATH = ROOT / ".living_update.lock"
OUTPUT_DIR = ROOT / "output"
DASHBOARD_DIR = ROOT / "dashboard" / "data"
LOG_DIR = ROOT / "logs"


def _get_last_run_date() -> Optional[str]:
    """Read the last successful run date from living_log.jsonl."""
    if not LIVING_LOG_PATH.exists():
        return None
    last_date = None
    try:
        with LIVING_LOG_PATH.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("status") == "success":
                        ts = entry.get("completed_utc", "")
                        if ts and len(ts) >= 10:
                            last_date = ts[:10]
                except (json.JSONDecodeError, KeyError):
                    continue
    except OSError:
        return None
    return last_date


def _append_log(entry: Dict[str, Any], max_entries: int = 200) -> None:
    """Append a record to living_log.jsonl, rotating if it exceeds max_entries.

    Uses read-append-write-back approach to avoid race between append and rotate.
    """
    LIVING_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    new_line = json.dumps(entry, ensure_ascii=False) + "\n"

    try:
        # Read existing lines, append new entry, rotate if needed — single pass
        existing = ""
        if LIVING_LOG_PATH.exists():
            existing = LIVING_LOG_PATH.read_text(encoding="utf-8")
        lines = [l for l in existing.splitlines() if l.strip()]
        lines.append(new_line.rstrip("\n"))

        rotated = False
        if len(lines) > max_entries:
            lines = lines[-max_entries:]
            rotated = True

        tmp = LIVING_LOG_PATH.with_suffix(".jsonl.tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        tmp.replace(LIVING_LOG_PATH)

        if rotated:
            print(f"  Log rotated: kept {max_entries} entries", flush=True)
    except OSError:
        # Fallback: just append (non-fatal)
        try:
            with LIVING_LOG_PATH.open("a", encoding="utf-8") as fh:
                fh.write(new_line)
        except OSError:
            pass


def _run_step(cmd: List[str], step_name: str, dry_run: bool = False) -> bool:
    """Run a pipeline step. Returns True on success."""
    print(f"\n{'[DRY RUN] ' if dry_run else ''}Step: {step_name}", flush=True)
    print(f"  Command: {' '.join(cmd)}", flush=True)

    if dry_run:
        return True

    try:
        result = subprocess.run(
            cmd,
            cwd=str(ROOT),
            capture_output=False,
            timeout=3600,  # 1 hour max per step
        )
        if result.returncode != 0:
            print(f"  FAILED: {step_name} (exit code {result.returncode})", file=sys.stderr)
            return False
        return True
    except subprocess.TimeoutExpired:
        print(f"  TIMEOUT: {step_name} (exceeded 1 hour)", file=sys.stderr)
        return False
    except FileNotFoundError as exc:
        print(f"  ERROR: {step_name} — {exc}", file=sys.stderr)
        return False


def _find_python() -> str:
    """Find the Python executable."""
    # On Windows, python3 typically doesn't exist — try python first
    import platform as _plat
    candidates = ["python", "python3"] if _plat.system() == "Windows" else ["python3", "python"]
    for candidate in candidates:
        try:
            result = subprocess.run(
                [candidate, "--version"],
                capture_output=True, timeout=5,
            )
            if result.returncode == 0:
                return candidate
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    return sys.executable


def _backup_csv(path: Path) -> Optional[Path]:
    """Back up a CSV file before incremental fetch. Returns backup path or None."""
    if not path.exists():
        return None
    backup = path.with_suffix(".csv.pre_incremental")
    shutil.copy2(str(path), str(backup))
    return backup


def _merge_incremental_csvs(
    query_name: str,
    output_dir: Path,
    backups: Dict[str, Path],
) -> None:
    """Merge incremental fetch results into the backed-up full CSV files.

    For each CSV type:
    - Read the full (backup) dataset
    - Read the incremental (newly fetched) dataset
    - For studies: update/add rows by nct_id
    - For hemo/arms/outcomes: replace ALL rows for updated nct_ids with new data
    """
    csv_types = {
        "studies": f"{query_name}_studies.csv",
        "hemo": f"{query_name}_hemodynamic_mentions.csv",
        "arms": f"{query_name}_arms.csv",
        "outcomes": f"{query_name}_outcomes.csv",
    }

    # Read incremental studies to get the set of updated nct_ids
    incremental_studies_path = output_dir / csv_types["studies"]
    updated_nct_ids: Set[str] = set()
    if incremental_studies_path.exists():
        with incremental_studies_path.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                nct_id = (row.get("nct_id") or "").strip()
                if nct_id:
                    updated_nct_ids.add(nct_id)

    if not updated_nct_ids:
        # No incremental updates — restore backups
        for label, backup_path in backups.items():
            if backup_path and backup_path.exists():
                filename = csv_types.get(label)
                if filename:
                    target = output_dir / filename
                    shutil.copy2(str(backup_path), str(target))
        print(f"  Merge: no incremental updates, restored backups", flush=True)
        return

    for label, filename in csv_types.items():
        backup_path = backups.get(label)
        current_path = output_dir / filename

        if not backup_path or not backup_path.exists():
            # No backup — the incremental file is all we have
            continue

        if not current_path.exists():
            # Fetch didn't produce this file — restore backup
            shutil.copy2(str(backup_path), str(current_path))
            continue

        # Read backup (full dataset) rows
        old_rows: List[Dict[str, str]] = []
        with backup_path.open("r", encoding="utf-8-sig", newline="") as fh:
            old_rows = list(csv.DictReader(fh))

        # Read incremental (new) rows
        new_rows: List[Dict[str, str]] = []
        with current_path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            fieldnames = reader.fieldnames or []
            new_rows = list(reader)

        if label == "studies":
            # Merge by nct_id: new rows override old, keep non-updated old rows
            old_by_id = {(r.get("nct_id") or "").strip(): r for r in old_rows}
            for row in new_rows:
                nct_id = (row.get("nct_id") or "").strip()
                if nct_id:
                    old_by_id[nct_id] = row
            merged = list(old_by_id.values())
        else:
            # For hemo/arms/outcomes: keep old rows for non-updated nct_ids,
            # replace with new rows for updated nct_ids
            kept = [r for r in old_rows if (r.get("nct_id") or "").strip() not in updated_nct_ids]
            merged = kept + new_rows

        # Determine fieldnames from backup (full schema) + any new columns
        if old_rows:
            with backup_path.open("r", encoding="utf-8-sig", newline="") as bfh:
                backup_reader = csv.DictReader(bfh)
                fieldnames = backup_reader.fieldnames or fieldnames

        # Write merged result
        tmp = current_path.with_suffix(".csv.tmp")
        with tmp.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in merged:
                writer.writerow(row)
        tmp.replace(current_path)

    # Clean up backups
    for backup_path in backups.values():
        if backup_path and backup_path.exists():
            backup_path.unlink()

    print(f"  Merge: {len(updated_nct_ids)} updated NCT IDs merged into full dataset", flush=True)


def _acquire_lock():
    """Acquire a file lock to prevent concurrent living_update.py runs.

    Returns the lock file handle (caller must keep it open until done).
    Raises SystemExit if another instance is already running.
    """
    try:
        # Open in exclusive-create mode — fails if file already exists
        # On Windows, use msvcrt; on Unix, use fcntl
        lock_fh = open(LOCK_PATH, "x", encoding="utf-8")
        lock_fh.write(f"pid={os.getpid()} started={datetime.now(timezone.utc).isoformat()}\n")
        lock_fh.flush()
        return lock_fh
    except FileExistsError:
        # Check if the lock is stale (>24 hours old)
        try:
            age = datetime.now(timezone.utc).timestamp() - LOCK_PATH.stat().st_mtime
            if age > 86400:  # 24 hours
                print(f"WARNING: Stale lock file ({age/3600:.1f}h old) — removing", flush=True)
                LOCK_PATH.unlink(missing_ok=True)
                lock_fh = open(LOCK_PATH, "x", encoding="utf-8")
                lock_fh.write(f"pid={os.getpid()} started={datetime.now(timezone.utc).isoformat()}\n")
                lock_fh.flush()
                return lock_fh
        except OSError:
            pass
        print("ERROR: Another living_update.py instance is already running "
              f"(lock file: {LOCK_PATH}). Remove it manually if this is incorrect.",
              file=sys.stderr, flush=True)
        raise SystemExit(3)


def _release_lock(lock_fh):
    """Release the file lock."""
    try:
        lock_fh.close()
        LOCK_PATH.unlink(missing_ok=True)
    except OSError:
        pass


def main() -> int:
    lock_fh = _acquire_lock()
    try:
        return _main_impl()
    finally:
        _release_lock(lock_fh)


def _main_impl() -> int:
    parser = argparse.ArgumentParser(
        description="ICU Living Map — daily living update",
        epilog="Examples:\n"
               "  python living_update.py                          # Full living update\n"
               "  python living_update.py --dry-run                # Preview without running\n"
               "  python living_update.py --sources ctgov          # Only CT.gov source\n"
               "  python living_update.py --force-full --skip-enrich  # Full refresh, skip enrich\n",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would execute, don't run")
    parser.add_argument("--skip-enrich", action="store_true", help="Skip enrichment step")
    parser.add_argument("--sources", default="ctgov,pubmed", metavar="SRC",
                        help="Comma-separated sources: ctgov,pubmed (default: ctgov,pubmed)")
    parser.add_argument("--force-full", action="store_true",
                        help="Ignore incremental date, full refresh")
    parser.add_argument("--label", default="broad", metavar="LABEL",
                        help="Build label (default: broad)")
    args = parser.parse_args()

    if not re.match(r"^[a-zA-Z0-9_-]+$", args.label):
        parser.error(f"Invalid label: {args.label!r} (must be alphanumeric, hyphens, underscores)")

    python = _find_python()
    sources = set(s.strip().lower() for s in args.sources.split(",") if s.strip())
    run_id = str(uuid.uuid4())[:8]
    started_utc = datetime.now(timezone.utc).isoformat()

    print(f"Living Update — run_id={run_id}, sources={sorted(sources)}", flush=True)

    # Determine incremental date
    last_date = None if args.force_full else _get_last_run_date()
    if last_date:
        print(f"  Incremental since: {last_date}", flush=True)
    else:
        print("  Full refresh (no previous run or --force-full)", flush=True)

    errors: List[str] = []
    warnings: List[str] = []
    sources_run: List[str] = []

    # Step 1: Fetch CT.gov
    if "ctgov" in sources:
        is_incremental = bool(last_date and not args.force_full)
        # Back up existing CSVs before incremental fetch (to merge later)
        ctgov_backups: Dict[str, Path] = {}
        if is_incremental and not args.dry_run:
            query_name = "icu_rct_broad"
            for label, suffix in [("studies", "_studies.csv"), ("hemo", "_hemodynamic_mentions.csv"),
                                  ("arms", "_arms.csv"), ("outcomes", "_outcomes.csv")]:
                path = OUTPUT_DIR / f"{query_name}{suffix}"
                backup = _backup_csv(path)
                if backup:
                    ctgov_backups[label] = backup

        cmd = [python, "fetch_ctgov_icu_placebo.py"]
        if is_incremental:
            cmd.extend(["--updated-since", last_date])
        if _run_step(cmd, "Fetch CT.gov", dry_run=args.dry_run):
            sources_run.append("ctgov")
            # Merge incremental results into full dataset
            if is_incremental and ctgov_backups and not args.dry_run:
                try:
                    _merge_incremental_csvs("icu_rct_broad", OUTPUT_DIR, ctgov_backups)
                except Exception as exc:
                    print(f"  WARNING: merge failed, restoring backups: {exc}", file=sys.stderr)
                    # Restore backups on merge failure
                    for label, backup_path in ctgov_backups.items():
                        if backup_path and backup_path.exists():
                            suffix_map = {"studies": "_studies.csv", "hemo": "_hemodynamic_mentions.csv",
                                         "arms": "_arms.csv", "outcomes": "_outcomes.csv"}
                            target = OUTPUT_DIR / f"icu_rct_broad{suffix_map[label]}"
                            shutil.copy2(str(backup_path), str(target))
                            backup_path.unlink()
                    warnings.append(f"incremental merge failed: {exc}")
        else:
            errors.append("ctgov fetch failed")
            # Restore backups on fetch failure
            for backup_path in ctgov_backups.values():
                if backup_path and backup_path.exists():
                    target_name = backup_path.name.replace(".pre_incremental", "")
                    target = backup_path.parent / target_name
                    shutil.copy2(str(backup_path), str(target))
                    backup_path.unlink()

    # Step 2: Search PubMed primary
    if "pubmed" in sources:
        cmd = [python, "search_pubmed_primary.py"]
        if last_date and not args.force_full:
            cmd.extend(["--updated-since", last_date])
        if _run_step(cmd, "Search PubMed primary", dry_run=args.dry_run):
            sources_run.append("pubmed")
        else:
            errors.append("pubmed search failed")

    # Step 3: Enrich
    if not args.skip_enrich:
        studies_path = OUTPUT_DIR / "icu_rct_broad_studies.csv"
        if not studies_path.exists() and not args.dry_run:
            warnings.append("enrichment skipped: studies CSV missing")
        else:
            cmd = [python, "enrich_orchestrator.py"]
            if not _run_step(cmd, "Enrich trials", dry_run=args.dry_run):
                warnings.append("enrichment failed (non-fatal)")

    # Step 4: Build living map
    cmd = [
        python, "build_living_map.py",
        "--label", args.label,
        "--dashboard-dir", str(DASHBOARD_DIR),
    ]

    # Add multi-source CSVs if available
    pubmed_studies = OUTPUT_DIR / "pubmed_icu_studies.csv"
    pubmed_hemo = OUTPUT_DIR / "pubmed_icu_hemo.csv"

    if pubmed_studies.exists():
        cmd.extend(["--pubmed-studies", str(pubmed_studies)])
    if pubmed_hemo.exists():
        cmd.extend(["--pubmed-hemo", str(pubmed_hemo)])

    # Add enrichment if DB exists and not skipped
    enrich_db = ROOT / "enrichment" / "enrichment_db.sqlite"
    if not args.skip_enrich and enrich_db.exists():
        cmd.extend(["--enrich", "--enrich-db", str(enrich_db)])

    studies_path = OUTPUT_DIR / "icu_rct_broad_studies.csv"
    hemo_path = OUTPUT_DIR / "icu_rct_broad_hemodynamic_mentions.csv"
    build_ok = True
    if not args.dry_run and (not studies_path.exists() or not hemo_path.exists()):
        build_ok = False
        missing = []
        if not studies_path.exists():
            missing.append(str(studies_path))
        if not hemo_path.exists():
            missing.append(str(hemo_path))
        errors.append(f"build skipped: missing required inputs ({'; '.join(missing)})")
        print("  ERROR: build skipped due to missing required inputs", file=sys.stderr)
    else:
        build_ok = _run_step(cmd, "Build living map", dry_run=args.dry_run)
    if not build_ok:
        errors.append("build failed")

    # Step 5: Log
    completed_utc = datetime.now(timezone.utc).isoformat()
    if not build_ok:
        status = "failure"
    elif errors:
        status = "partial_failure"
    else:
        status = "success"

    log_entry = {
        "run_id": run_id,
        "started_utc": started_utc,
        "completed_utc": completed_utc,
        "status": status,
        "sources_run": sources_run,
        "label": args.label,
        "incremental_since": last_date,
        "errors": errors,
        "warnings": warnings,
        "dry_run": args.dry_run,
    }

    if not args.dry_run:
        _append_log(log_entry)
        print(f"\nLiving update {status}: run_id={run_id}, sources={sources_run}", flush=True)
    else:
        print(f"\n[DRY RUN] Would log: {json.dumps(log_entry, indent=2)}", flush=True)

    if errors or warnings:
        print(f"  Warnings: {errors + warnings}", file=sys.stderr)

    # 0=success, 1=failure, 2=partial failure (some sources failed but build succeeded)
    if status == "failure":
        return 1
    elif status == "partial_failure":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

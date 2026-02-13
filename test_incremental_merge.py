"""Tests for the incremental CSV merge logic in living_update.py."""
from __future__ import annotations

import csv
import sys
import tempfile
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from living_update import _backup_csv, _merge_incremental_csvs


def _write_csv(path: Path, fieldnames: list, rows: list[dict]) -> None:
    """Helper: write a CSV with given fieldnames and rows."""
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _read_csv(path: Path) -> list[dict]:
    """Helper: read CSV into list of dicts."""
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


# ── _backup_csv ──────────────────────────────────────────────────────

def test_backup_csv_creates_copy():
    """_backup_csv should create a .pre_incremental copy and return its path."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        orig = td / "data.csv"
        _write_csv(orig, ["a", "b"], [{"a": "1", "b": "2"}])

        backup = _backup_csv(orig)
        assert backup is not None
        assert backup.exists()
        assert backup.suffix == ".pre_incremental"
        assert backup.name == "data.csv.pre_incremental"
        # Content must match
        assert _read_csv(backup) == [{"a": "1", "b": "2"}]
        # Original must still exist
        assert orig.exists()


def test_backup_csv_nonexistent_returns_none():
    """_backup_csv on a missing file should return None."""
    with tempfile.TemporaryDirectory() as td:
        result = _backup_csv(Path(td) / "missing.csv")
        assert result is None


# ── _merge_incremental_csvs — studies merge ──────────────────────────

def test_merge_studies_update_existing():
    """Updated study rows should replace old rows (keyed by nct_id)."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        qname = "test"
        studies_file = td / f"{qname}_studies.csv"
        fields = ["nct_id", "title", "status"]

        # Backup = full dataset (3 studies)
        backup = td / f"{qname}_studies.csv.pre_incremental"
        _write_csv(backup, fields, [
            {"nct_id": "NCT001", "title": "Trial A", "status": "Recruiting"},
            {"nct_id": "NCT002", "title": "Trial B", "status": "Completed"},
            {"nct_id": "NCT003", "title": "Trial C", "status": "Recruiting"},
        ])

        # Incremental = 1 updated + 1 new
        _write_csv(studies_file, fields, [
            {"nct_id": "NCT002", "title": "Trial B v2", "status": "Active"},
            {"nct_id": "NCT004", "title": "Trial D", "status": "Recruiting"},
        ])

        backups = {"studies": backup}
        _merge_incremental_csvs(qname, td, backups)

        merged = _read_csv(studies_file)
        ids = {r["nct_id"] for r in merged}
        assert ids == {"NCT001", "NCT002", "NCT003", "NCT004"}, f"Got {ids}"
        # NCT002 should be updated
        nct002 = [r for r in merged if r["nct_id"] == "NCT002"][0]
        assert nct002["title"] == "Trial B v2"
        assert nct002["status"] == "Active"
        # Backup should be cleaned up
        assert not backup.exists()


def test_merge_studies_add_new_only():
    """New studies (no overlap) should be appended to the full dataset."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        qname = "test"
        fields = ["nct_id", "title"]

        backup = td / f"{qname}_studies.csv.pre_incremental"
        _write_csv(backup, fields, [
            {"nct_id": "NCT001", "title": "Existing"},
        ])

        studies_file = td / f"{qname}_studies.csv"
        _write_csv(studies_file, fields, [
            {"nct_id": "NCT005", "title": "Brand New"},
        ])

        backups = {"studies": backup}
        _merge_incremental_csvs(qname, td, backups)

        merged = _read_csv(studies_file)
        assert len(merged) == 2
        ids = {r["nct_id"] for r in merged}
        assert ids == {"NCT001", "NCT005"}


# ── _merge_incremental_csvs — hemo/arms/outcomes merge ──────────────

def test_merge_hemo_replaces_updated_nctids():
    """Hemo rows for updated nct_ids should be fully replaced, others kept."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        qname = "test"
        hemo_fields = ["nct_id", "drug", "dose"]
        studies_fields = ["nct_id", "title"]

        # Studies incremental — NCT002 was updated
        studies_file = td / f"{qname}_studies.csv"
        _write_csv(studies_file, studies_fields, [
            {"nct_id": "NCT002", "title": "Updated"},
        ])

        # Hemo backup — has rows for NCT001 and NCT002
        hemo_backup = td / f"{qname}_hemodynamic_mentions.csv.pre_incremental"
        _write_csv(hemo_backup, hemo_fields, [
            {"nct_id": "NCT001", "drug": "DrugA", "dose": "10mg"},
            {"nct_id": "NCT002", "drug": "DrugB", "dose": "20mg"},
            {"nct_id": "NCT002", "drug": "DrugC", "dose": "30mg"},
        ])

        # Hemo incremental — new rows for NCT002
        hemo_file = td / f"{qname}_hemodynamic_mentions.csv"
        _write_csv(hemo_file, hemo_fields, [
            {"nct_id": "NCT002", "drug": "DrugB-v2", "dose": "25mg"},
        ])

        # Also need studies backup for the merge to read updated_nct_ids
        studies_backup = td / f"{qname}_studies.csv.pre_incremental"
        _write_csv(studies_backup, studies_fields, [
            {"nct_id": "NCT001", "title": "Old"},
            {"nct_id": "NCT002", "title": "Old"},
        ])

        backups = {"studies": studies_backup, "hemo": hemo_backup}
        _merge_incremental_csvs(qname, td, backups)

        merged = _read_csv(hemo_file)
        # NCT001 row kept, NCT002 old rows removed, NCT002 new row added
        assert len(merged) == 2, f"Expected 2, got {len(merged)}: {merged}"
        nct001 = [r for r in merged if r["nct_id"] == "NCT001"]
        assert len(nct001) == 1
        assert nct001[0]["drug"] == "DrugA"
        nct002 = [r for r in merged if r["nct_id"] == "NCT002"]
        assert len(nct002) == 1
        assert nct002[0]["drug"] == "DrugB-v2"


def test_merge_arms_replaces_updated_nctids():
    """Arms rows follow the same replace-by-nct_id logic as hemo."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        qname = "test"
        arms_fields = ["nct_id", "arm_name", "arm_type"]
        studies_fields = ["nct_id", "title"]

        # Studies incremental
        studies_file = td / f"{qname}_studies.csv"
        _write_csv(studies_file, studies_fields, [
            {"nct_id": "NCT010", "title": "Updated"},
        ])

        # Arms backup
        arms_backup = td / f"{qname}_arms.csv.pre_incremental"
        _write_csv(arms_backup, arms_fields, [
            {"nct_id": "NCT010", "arm_name": "Placebo", "arm_type": "Control"},
            {"nct_id": "NCT010", "arm_name": "Drug", "arm_type": "Experimental"},
            {"nct_id": "NCT020", "arm_name": "Sham", "arm_type": "Control"},
        ])

        # Arms incremental (updated arms for NCT010)
        arms_file = td / f"{qname}_arms.csv"
        _write_csv(arms_file, arms_fields, [
            {"nct_id": "NCT010", "arm_name": "NewDrug", "arm_type": "Experimental"},
        ])

        studies_backup = td / f"{qname}_studies.csv.pre_incremental"
        _write_csv(studies_backup, studies_fields, [
            {"nct_id": "NCT010", "title": "Old"},
            {"nct_id": "NCT020", "title": "Old"},
        ])

        backups = {"studies": studies_backup, "arms": arms_backup}
        _merge_incremental_csvs(qname, td, backups)

        merged = _read_csv(arms_file)
        # NCT020 kept (1 row), NCT010 old removed (2 rows) + new (1 row)
        assert len(merged) == 2, f"Expected 2, got {len(merged)}: {merged}"
        nct020 = [r for r in merged if r["nct_id"] == "NCT020"]
        assert len(nct020) == 1
        nct010 = [r for r in merged if r["nct_id"] == "NCT010"]
        assert len(nct010) == 1
        assert nct010[0]["arm_name"] == "NewDrug"


# ── Edge cases ───────────────────────────────────────────────────────

def test_merge_no_incremental_updates_restores_backups():
    """If incremental studies CSV is empty, backups should be restored."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        qname = "test"
        fields = ["nct_id", "title"]

        # Write an empty incremental studies file (header only)
        studies_file = td / f"{qname}_studies.csv"
        _write_csv(studies_file, fields, [])

        # Backup with actual data
        backup = td / f"{qname}_studies.csv.pre_incremental"
        _write_csv(backup, fields, [
            {"nct_id": "NCT001", "title": "Keep Me"},
        ])

        backups = {"studies": backup}
        _merge_incremental_csvs(qname, td, backups)

        # Original should be restored from backup
        restored = _read_csv(studies_file)
        assert len(restored) == 1
        assert restored[0]["nct_id"] == "NCT001"


def test_merge_missing_backup_keeps_incremental():
    """If there's no backup for a CSV type, the incremental file is kept as-is."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        qname = "test"
        fields = ["nct_id", "title"]

        # Studies file (incremental) exists
        studies_file = td / f"{qname}_studies.csv"
        _write_csv(studies_file, fields, [
            {"nct_id": "NCT099", "title": "New"},
        ])

        # No backup at all
        backups = {}
        _merge_incremental_csvs(qname, td, backups)

        # File should remain untouched
        data = _read_csv(studies_file)
        assert len(data) == 1
        assert data[0]["nct_id"] == "NCT099"


def test_merge_preserves_fieldnames_from_backup():
    """Merged CSV should use fieldnames from the backup (full schema), not incremental."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        qname = "test"

        # Backup has extra columns
        backup_fields = ["nct_id", "title", "extra_col"]
        backup = td / f"{qname}_studies.csv.pre_incremental"
        _write_csv(backup, backup_fields, [
            {"nct_id": "NCT001", "title": "Old", "extra_col": "val1"},
        ])

        # Incremental only has nct_id + title (no extra_col)
        incr_fields = ["nct_id", "title"]
        studies_file = td / f"{qname}_studies.csv"
        _write_csv(studies_file, incr_fields, [
            {"nct_id": "NCT002", "title": "New"},
        ])

        backups = {"studies": backup}
        _merge_incremental_csvs(qname, td, backups)

        # Read and verify fieldnames include extra_col
        with studies_file.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            assert "extra_col" in (reader.fieldnames or [])
            rows = list(reader)
        assert len(rows) == 2
        nct001 = [r for r in rows if r["nct_id"] == "NCT001"][0]
        assert nct001["extra_col"] == "val1"


def test_merge_backup_cleanup():
    """All backup files should be deleted after a successful merge."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        qname = "test"
        fields = ["nct_id", "title"]

        # Create backups for studies and hemo
        s_backup = td / f"{qname}_studies.csv.pre_incremental"
        _write_csv(s_backup, fields, [{"nct_id": "NCT001", "title": "A"}])

        h_fields = ["nct_id", "drug"]
        h_backup = td / f"{qname}_hemodynamic_mentions.csv.pre_incremental"
        _write_csv(h_backup, h_fields, [{"nct_id": "NCT001", "drug": "X"}])

        # Create incremental files
        _write_csv(td / f"{qname}_studies.csv", fields, [
            {"nct_id": "NCT002", "title": "B"},
        ])
        _write_csv(td / f"{qname}_hemodynamic_mentions.csv", h_fields, [
            {"nct_id": "NCT002", "drug": "Y"},
        ])

        backups = {"studies": s_backup, "hemo": h_backup}
        _merge_incremental_csvs(qname, td, backups)

        # Both backups should be deleted
        assert not s_backup.exists(), "Studies backup should be cleaned up"
        assert not h_backup.exists(), "Hemo backup should be cleaned up"


def test_backup_csv_preserves_utf8():
    """Backup should preserve UTF-8 content (unicode apostrophes, etc.)."""
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        orig = td / "data.csv"
        _write_csv(orig, ["nct_id", "title"], [
            {"nct_id": "NCT001", "title": "Crohn\u2019s Disease Trial"},
        ])

        backup = _backup_csv(orig)
        assert backup is not None
        rows = _read_csv(backup)
        assert rows[0]["title"] == "Crohn\u2019s Disease Trial"


if __name__ == "__main__":
    import traceback

    tests = [
        test_backup_csv_creates_copy,
        test_backup_csv_nonexistent_returns_none,
        test_merge_studies_update_existing,
        test_merge_studies_add_new_only,
        test_merge_hemo_replaces_updated_nctids,
        test_merge_arms_replaces_updated_nctids,
        test_merge_no_incremental_updates_restores_backups,
        test_merge_missing_backup_keeps_incremental,
        test_merge_preserves_fieldnames_from_backup,
        test_merge_backup_cleanup,
        test_backup_csv_preserves_utf8,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception:
            print(f"  FAIL  {t.__name__}")
            traceback.print_exc()
            failed += 1

    print(f"\n{passed}/{passed + failed} passed, {failed} failed")
    sys.exit(1 if failed else 0)

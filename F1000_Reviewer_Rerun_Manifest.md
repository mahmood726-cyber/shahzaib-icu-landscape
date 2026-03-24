# ICU Hemodynamic Trial Landscape: reviewer rerun manifest

This manifest is the shortest reviewer-facing rerun path for the local software package. It lists the files that should be sufficient to recreate one worked example, inspect saved outputs, and verify that the manuscript claims remain bounded to what the repository actually demonstrates.

## Reviewer Entry Points
- Project directory: `C:\Models\shahzaib-icu-landscape`.
- Preferred documentation start points: `README.md`, `f1000_artifacts/tutorial_walkthrough.md`.
- Detected public repository root: `https://github.com/mahmood726-cyber/shahzaib-icu-landscape`.
- Detected public source snapshot: Fixed public commit snapshot available at `https://github.com/mahmood726-cyber/shahzaib-icu-landscape/tree/d6f43a844a1c3e2b1971831d9c9eb786ed9ca689`.
- Detected public archive record: No project-specific DOI or Zenodo record URL was detected locally; archive registration pending.
- Environment capture files: `requirements.txt`.
- Validation/test artifacts: `f1000_artifacts/validation_summary.md`, `test_incremental_merge.py`.

## Worked Example Inputs
- Manuscript-named example paths: `dashboard/index.html` for the main living map; `dashboard/insights.html` for the analytical companion view; `living_update.py`, `build_living_map.py`, and `living_log.jsonl` for reproducible update mechanics; validation/dedup_merged_sample.csv; validation/dedup_unmerged_sample.csv; validation/validation_sample_broad_200.csv.
- Auto-detected sample/example files: `validation/dedup_merged_sample.csv`, `validation/dedup_unmerged_sample.csv`, `validation/validation_sample_broad_200.csv`.

## Expected Outputs To Inspect
- Downloadable ICU trial landscape CSV and summary JSON files.
- Interactive evidence-gap and temporal dashboards.
- Living update logs and provenance notes for refresh cycles.

## Minimal Reviewer Rerun Sequence
- Start with the README/tutorial files listed below and keep the manuscript paths synchronized with the public archive.
- Create the local runtime from the detected environment capture files if available: `requirements.txt`.
- Run at least one named example path from the manuscript and confirm that the generated outputs match the saved validation materials.
- Quote one concrete numeric result from the local validation snippets below when preparing the final software paper.
- Open the browser deliverable and confirm that the embedded WebR validation panel completes successfully after the page finishes initializing.

## Local Numeric Evidence Available
- `paper/icu_landscape_manuscript_plos_one.md` reports Results: After deduplication, 27,498 ICU RCTs were identified (22,054 from ClinicalTrials.gov, 5,971 from PubMed; 527 duplicates removed).

## Browser Deliverables
- HTML entry points: `dashboard/index.html`, `dashboard/insights.html`.
- The shipped HTML applications include embedded WebR self-validation and should be checked after any UI or calculation change.

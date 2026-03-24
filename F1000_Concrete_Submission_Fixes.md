# ICU Hemodynamic Trial Landscape: concrete submission fixes

This file converts the multi-persona review into repository-side actions that should be checked before external submission of the F1000 software paper for `shahzaib-icu-landscape`.

## Detectable Local State
- Documentation files detected: `README.md`, `f1000_artifacts/tutorial_walkthrough.md`.
- Environment lock or container files detected: `requirements.txt`.
- Package manifests detected: none detected.
- Example data files detected: `validation/dedup_merged_sample.csv`, `validation/dedup_unmerged_sample.csv`, `validation/validation_sample_broad_200.csv`.
- Validation artifacts detected: `f1000_artifacts/validation_summary.md`, `test_incremental_merge.py`.
- Detected public repository root: `https://github.com/mahmood726-cyber/shahzaib-icu-landscape`.
- Detected public source snapshot: Fixed public commit snapshot available at `https://github.com/mahmood726-cyber/shahzaib-icu-landscape/tree/d6f43a844a1c3e2b1971831d9c9eb786ed9ca689`.
- Detected public archive record: No project-specific DOI or Zenodo record URL was detected locally; archive registration pending.

## High-Priority Fixes
- Check that the manuscript's named example paths exist in the public archive and can be run without repository archaeology.
- Confirm that the cited repository root (`https://github.com/mahmood726-cyber/shahzaib-icu-landscape`) resolves to the same fixed public source snapshot used for submission.
- Archive the tagged release and insert the Zenodo DOI or record URL once it has been minted; no project-specific archive DOI was detected locally.
- Reconfirm the quoted benchmark or validation sentence after the final rerun so the narrative text matches the shipped artifacts.
- Keep the embedded WebR validation panel enabled in shipped HTML files and rerun it after any UI or calculation changes.

## Numeric Evidence Available To Quote
- `paper/icu_landscape_manuscript_plos_one.md` reports Results: After deduplication, 27,498 ICU RCTs were identified (22,054 from ClinicalTrials.gov, 5,971 from PubMed; 527 duplicates removed).

## Manuscript Files To Keep In Sync
- `F1000_Software_Tool_Article.md`
- `F1000_Reviewer_Rerun_Manifest.md`
- `F1000_MultiPersona_Review.md`
- `F1000_Submission_Checklist_RealReview.md` where present
- README/tutorial files and the public repository release metadata

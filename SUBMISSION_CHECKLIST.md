# PLOS ONE Submission Checklist

**Manuscript:** ICU Hemodynamic Trial Landscape: A Living Scoping Review of Registered Randomized Trials with Hemodynamic and Related Outcomes

**Target:** PLOS ONE

**Date:** 2026-03-24

---

## Status: READY (pending 4 author-only items)

### Manuscript Quality Checks (all PASS)

| Check | Status | Details |
|-------|--------|---------|
| Abstract word count | PASS | 267 words (limit: 300) |
| Title length | PASS | 126 chars (limit: 250) |
| References sequential | PASS | [1]-[17], all cited, first-appearance order |
| Figures referenced | PASS | Fig 1-4, all referenced in text |
| Tables referenced | PASS | Table 1-4, all referenced in text |
| Supplementary items cross-checked | PASS | S1 Table, S2 File, S3 Table, S4 Table, S5 File, S6 File -- all referenced in body and declared in SI section |
| PRISMA-ScR checklist complete | PASS | 22/22 items mapped to manuscript sections |
| Ethics statement | PASS | Present (no human subjects) |
| Funding statement | PASS | Present (no funding) |
| Competing interests | PASS | Present (none declared) |
| Author contributions (CRediT) | PASS | Present (9 roles listed) |
| Data availability statement | PASS | Present (public APIs + Zenodo placeholder) |
| Acknowledgments | PASS | Present |

### Supplementary Files (all exist)

| Item | File | Status |
|------|------|--------|
| S1 Table | `PRISMA-ScR_Checklist.md` | EXISTS |
| S2 File | `ctgov_icu_placebo_strategy.json` | EXISTS |
| S3 Table | `output/S3_normalized_keyword_categories.csv` | EXISTS |
| S4 Table | `validation/validation_sample_broad_200.csv` | EXISTS |
| S5 File | `validation/dedup_merged_sample.csv` + `dedup_unmerged_sample.csv` | EXISTS |
| S6 File | `build_living_map.py` + `dashboard/` directory | EXISTS |

### Figures (all generated)

| Figure | TIFF (300 DPI) | EPS | Description |
|--------|---------------|-----|-------------|
| Fig 1 | `paper/figures/Fig1_PRISMA_flow.tiff` | `paper/figures/Fig1_PRISMA_flow.eps` | Adapted PRISMA-ScR flow diagram |
| Fig 2 | `paper/figures/Fig2_temporal_distribution.tiff` | `paper/figures/Fig2_temporal_distribution.eps` | Temporal distribution by decade |
| Fig 3 | `paper/figures/Fig3_geographic_distribution.tiff` | `paper/figures/Fig3_geographic_distribution.eps` | Geographic distribution (top 15 countries) |
| Fig 4 | `paper/figures/Fig4_keyword_signal_map.tiff` | `paper/figures/Fig4_keyword_signal_map.eps` | Total vs. placebo study count scatter |

To regenerate figures: `python paper/generate_figures.py`

### Data Manifest

`output/manifest.json` -- regenerated 2026-03-24 with correct paths and SHA-256 hashes for 14 data files.

---

## Author Action Items (4 placeholders to fill)

These cannot be filled by anyone other than the author. Replace the exact placeholder text in the files listed.

### 1. AFFILIATION

- **File:** `paper/icu_landscape_manuscript_plos_one.md`, line 5
- **Current:** `[AFFILIATION_PLACEHOLDER]`
- **Replace with:** Your institutional affiliation (e.g., "Department of Critical Care Medicine, University of X, City, Country")

### 2. EMAIL

- **File:** `paper/icu_landscape_manuscript_plos_one.md`, line 7
- **Current:** `[EMAIL_PLACEHOLDER]`
- **Replace with:** Your institutional or corresponding author email address

### 3. ORCID

- **File:** `paper/icu_landscape_manuscript_plos_one.md`, line 9
- **Current:** `[ORCID_PLACEHOLDER]`
- **Replace with:** Your ORCID iD (format: 0000-0000-0000-0000)
- **Note:** PLOS ONE requires ORCID for the corresponding author. Register at https://orcid.org/ if needed.

### 4. ZENODO DOI (3 locations)

You must deposit the dataset + code on Zenodo first, then fill in the DOI.

- **File 1:** `paper/icu_landscape_manuscript_plos_one.md`, line 95
  - **Current:** `[ZENODO_DOI_PLACEHOLDER]`
- **File 2:** `paper/icu_landscape_manuscript_plos_one.md`, line 398
  - **Current:** `[ZENODO_DOI_PLACEHOLDER]`
- **File 3:** `DATA_AVAILABILITY.md`, line 37
  - **Current:** `[ZENODO_DOI_PLACEHOLDER]`
- **Replace all with:** The Zenodo DOI URL (format: `https://doi.org/10.5281/zenodo.XXXXXXX`)

**Zenodo deposit should include:**
  - `output/icu_hemodynamic_living_map.csv` (36.6 MB)
  - `output/icu_hemodynamic_living_map.parquet` (6.8 MB)
  - `output/icu_hemodynamic_summary.json` (1.1 MB)
  - `output/S3_normalized_keyword_categories.csv`
  - `validation/validation_sample_broad_200.csv`
  - `validation/dedup_merged_sample.csv` + `dedup_unmerged_sample.csv`
  - `ctgov_icu_placebo_strategy.json`
  - `build_living_map.py` and supporting pipeline code
  - `dashboard/` directory (interactive dashboard)

---

## PLOS ONE Submission Steps

1. Fill the 4 placeholders above
2. Go to https://www.editorialmanager.com/pone/
3. Create account / log in
4. Select "Submit New Manuscript" -> Article Type: "Research Article"
5. Upload:
   - **Manuscript:** Copy/paste or upload `paper/icu_landscape_manuscript_plos_one.md` content (convert to .docx if required)
   - **Figures:** Upload the 4 TIFF files from `paper/figures/`
   - **Supporting Information:** Upload S1-S6 files listed above
   - **Cover letter:** Use `F1000_Cover_Letter.md` as template (adapt for PLOS ONE)
6. Confirm:
   - Data availability: "All relevant data are within the manuscript and its Supporting Information files" + Zenodo DOI
   - Financial disclosure: "The author received no specific funding for this work"
   - Competing interests: "The author declares no competing interests"
   - PLOS ONE ethics: Not applicable (no human subjects)
7. Review and submit

---

## Notes

- The manuscript is formatted for PLOS ONE (abstract structure, CRediT taxonomy, data availability, ethics statement)
- Abstract is 267 words (within 300-word limit)
- References are in Vancouver style with DOIs (PLOS ONE preferred format)
- The PRISMA-ScR checklist (S1 Table) maps all 22 items to manuscript sections
- The interactive dashboard URL should be included in the cover letter once hosted
- The living review specification (Methods section) describes update frequency and stopping criteria

# ICU Hemodynamic Trial Landscape: a software tool for reviewer-auditable evidence synthesis

## Authors
- Mahmood Ahmad [1,2]
- Niraj Kumar [1]
- Bilaal Dar [3]
- Laiba Khan [1]
- Andrew Woo [4]
- Corresponding author: Andrew Woo (andy2709w@gmail.com)

## Affiliations
1. Royal Free Hospital
2. Tahir Heart Institute Rabwah
3. King's College Medical School
4. St George's Medical School

## Abstract
**Background:** Living trial landscape projects need more than a static website: reviewers want explicit search logic, update rules, validation samples, downloadable data, and clarity about whether the tool maps registrations or estimates treatment effects.

**Methods:** This project builds a browser-based ICU trial landscape from ClinicalTrials.gov and PubMed using scripted fetch, keyword normalization, placebo-arm classification, summary JSON generation, and two interactive dashboards (`index.html` and `insights.html`).

**Results:** The software ships downloadable CSV/JSON artifacts, visual trial maps, evidence-gap dashboards, living update scripts, and in-app methods text describing query structure, reference-standard recall checking, and keyword-validation samples.

**Conclusions:** The contribution is a living registry-mapping platform for ICU hemodynamic research; it should be described as a descriptive evidence-mapping tool rather than as a meta-analytic effect-estimation engine.

## Keywords
living evidence map; intensive care; ClinicalTrials.gov; PubMed; dashboard; trial landscape; software tool

## Introduction
The dashboards are designed to make trial registration coverage and placebo-signal gaps inspectable without forcing users into code. Equally important for peer review, the methods and limitations are embedded directly in the application rather than being hidden in unpublished workflow notes.

Relevant comparators include conventional scoping-review tables and hosted dashboards that omit update provenance. This project's distinguishing feature is the coupling of living-update scripts, downloadable artifacts, and explicit in-app methods documentation.

The manuscript structure below is deliberately aligned to common open-software review requests: the rationale is stated explicitly, at least one runnable example path is named, local validation artifacts are listed, and conclusions are bounded to the functions and outputs documented in the repository.

## Methods
### Software architecture and workflow
The repository includes Python scripts for living-map generation and updates, dashboard assets, downloadable summary JSON, and a browser application that renders signal maps, evidence-gap views, co-occurrence plots, and PRISMA-style flow displays.

### Installation, runtime, and reviewer reruns
The local implementation is packaged under `C:\Models\shahzaib-icu-landscape`. The manuscript identifies the local entry points, dependency manifest, fixed example input, and expected saved outputs so that reviewers can rerun the documented workflow without reconstructing it from scratch.

- Entry directory: `C:\Models\shahzaib-icu-landscape`.
- Detected documentation entry points: `README.md`, `f1000_artifacts/tutorial_walkthrough.md`.
- Detected environment capture or packaging files: `requirements.txt`.
- Named worked-example paths in this draft: `dashboard/index.html` for the main living map; `dashboard/insights.html` for the analytical companion view; `living_update.py`, `build_living_map.py`, and `living_log.jsonl` for reproducible update mechanics.
- Detected validation or regression artifacts: `f1000_artifacts/validation_summary.md`, `test_incremental_merge.py`.
- Detected example or sample data files: `validation/dedup_merged_sample.csv`, `validation/dedup_unmerged_sample.csv`, `validation/validation_sample_broad_200.csv`.
- Detected browser deliverables with built-in WebR self-validation: `dashboard/index.html`, `dashboard/insights.html`.

### Worked examples and validation materials
**Example or fixed demonstration paths**
- `dashboard/index.html` for the main living map.
- `dashboard/insights.html` for the analytical companion view.
- `living_update.py`, `build_living_map.py`, and `living_log.jsonl` for reproducible update mechanics.

**Validation and reporting artifacts**
- In-app documentation reports a 21-trial reference standard for recall validation.
- The dashboard methods text describes a stratified keyword-validation sample and deduplication checks.
- `_test_review*.py` files provide local project review scripts.

### Typical outputs and user-facing deliverables
- Downloadable ICU trial landscape CSV and summary JSON files.
- Interactive evidence-gap and temporal dashboards.
- Living update logs and provenance notes for refresh cycles.

### Reviewer-informed safeguards
- Provides a named example workflow or fixed demonstration path.
- Documents local validation artifacts rather than relying on unsupported claims.
- Positions the software against existing tools without claiming blanket superiority.
- States limitations and interpretation boundaries in the manuscript itself.
- Requires explicit environment capture and public example accessibility in the released archive.

## Review-Driven Revisions
This draft has been tightened against recurring open peer-review objections taken from the supplied reviewer reports.
- Reproducibility: the draft names a reviewer rerun path and points readers to validation artifacts instead of assuming interface availability is proof of correctness.
- Validation: claims are anchored to local tests, validation summaries, simulations, or consistency checks rather than to unsupported assertions of performance.
- Comparators and niche: the manuscript now names the relevant comparison class and keeps the claimed niche bounded instead of implying universal superiority.
- Documentation and interpretation: the text expects a worked example, input transparency, and reviewer-verifiable outputs rather than a high-level feature list alone.
- Claims discipline: conclusions are moderated to the documented scope of ICU Hemodynamic Trial Landscape and paired with explicit limitations.
- Browser verification: HTML applications in this directory now include embedded WebR checks so reviewer-facing dashboards can validate their displayed calculations in situ.

## Use Cases and Results
The software outputs should be described in terms of concrete reviewer-verifiable workflows: running the packaged example, inspecting the generated results, and checking that the reported interpretation matches the saved local artifacts. In this project, the most important result layer is the availability of a transparent execution path from input to analysis output.

Representative local result: `paper/icu_landscape_manuscript_plos_one.md` reports Results: After deduplication, 27,498 ICU RCTs were identified (22,054 from ClinicalTrials.gov, 5,971 from PubMed; 527 duplicates removed).

### Concrete local quantitative evidence
- `paper/icu_landscape_manuscript_plos_one.md` reports Results: After deduplication, 27,498 ICU RCTs were identified (22,054 from ClinicalTrials.gov, 5,971 from PubMed; 527 duplicates removed).

## Discussion
Representative local result: `paper/icu_landscape_manuscript_plos_one.md` reports Results: After deduplication, 27,498 ICU RCTs were identified (22,054 from ClinicalTrials.gov, 5,971 from PubMed; 527 duplicates removed).

The software paper foregrounds that the platform maps trial registrations and structured metadata, not pooled treatment effects. That scope boundary directly addresses a common reviewer concern in registry-driven dashboards.

### Limitations
- Coverage is limited by the registries and APIs queried.
- Keyword matching is a proxy for clinical concepts and depends on registration text quality.
- The platform is descriptive and does not perform formal risk-of-bias or effect-size synthesis.

## Software Availability
- Local source package: `shahzaib-icu-landscape` under `C:\Models`.
- Public repository: `https://github.com/mahmood726-cyber/shahzaib-icu-landscape`.
- Public source snapshot: Fixed public commit snapshot available at `https://github.com/mahmood726-cyber/shahzaib-icu-landscape/tree/d6f43a844a1c3e2b1971831d9c9eb786ed9ca689`.
- DOI/archive record: No project-specific DOI or Zenodo record URL was detected locally; archive registration pending.
- Environment capture detected locally: `requirements.txt`.
- Reviewer-facing documentation detected locally: `README.md`, `f1000_artifacts/tutorial_walkthrough.md`.
- Reproducibility walkthrough: `f1000_artifacts/tutorial_walkthrough.md` where present.
- Validation summary: `f1000_artifacts/validation_summary.md` where present.
- Reviewer rerun manifest: `F1000_Reviewer_Rerun_Manifest.md`.
- Multi-persona review memo: `F1000_MultiPersona_Review.md`.
- Concrete submission-fix note: `F1000_Concrete_Submission_Fixes.md`.
- License: see the local `LICENSE` file.

## Data Availability
Downloadable CSV and JSON artifacts are bundled with the dashboard. The project uses publicly accessible registry and bibliographic metadata only.

## Reporting Checklist
Real-peer-review-aligned checklist: `F1000_Submission_Checklist_RealReview.md`.
Reviewer rerun companion: `F1000_Reviewer_Rerun_Manifest.md`.
Companion reviewer-response artifact: `F1000_MultiPersona_Review.md`.
Project-level concrete fix list: `F1000_Concrete_Submission_Fixes.md`.

## Declarations
### Competing interests
The authors declare that no competing interests were disclosed.

### Grant information
No specific grant was declared for this manuscript draft.

### Author contributions (CRediT)
| Author | CRediT roles |
|---|---|
| Mahmood Ahmad | Conceptualization; Software; Validation; Data curation; Writing - original draft; Writing - review and editing |
| Niraj Kumar | Conceptualization |
| Bilaal Dar | Conceptualization |
| Laiba Khan | Conceptualization |
| Andrew Woo | Conceptualization |

### Acknowledgements
The authors acknowledge contributors to open statistical methods, reproducible research software, and reviewer-led software quality improvement.

## References
1. DerSimonian R, Laird N. Meta-analysis in clinical trials. Controlled Clinical Trials. 1986;7(3):177-188.
2. Higgins JPT, Thompson SG. Quantifying heterogeneity in a meta-analysis. Statistics in Medicine. 2002;21(11):1539-1558.
3. Viechtbauer W. Conducting meta-analyses in R with the metafor package. Journal of Statistical Software. 2010;36(3):1-48.
4. Page MJ, McKenzie JE, Bossuyt PM, et al. The PRISMA 2020 statement: an updated guideline for reporting systematic reviews. BMJ. 2021;372:n71.
5. Fay C, Rochette S, Guyader V, Girard C. Engineering Production-Grade Shiny Apps. Chapman and Hall/CRC. 2022.

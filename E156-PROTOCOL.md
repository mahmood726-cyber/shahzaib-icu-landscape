# E156 Protocol — `shahzaib-icu-landscape`

This repository is the source code and dashboard backing a cluster of E156 micro-papers on the [E156 Student Board](https://mahmood726-cyber.github.io/e156/students.html).

**2 papers share this repo.** Each is listed below with its own title, estimand, dataset, 156-word body, and submission metadata (authorship, ethics, references, target journal, etc.). Students claiming any of these papers should use the body + metadata for their specific paper number and submit separately.

## Papers in this repo

| Paper # | Title |
| ---: | :--- |
| `[152]` | ICU Hemodynamic Trial Landscape: A Living Evidence Map |
| `[479]` | ICU Hemodynamic Trial Landscape: A Living Evidence Map |

---

## `[152]` ICU Hemodynamic Trial Landscape: A Living Evidence Map

**Type:** methods  |  ESTIMAND: Sensitivity  
**Data:** ClinicalTrials.gov ICU RCTs, 21-trial reference standard

### 156-word body

Can a browser-based living evidence map provide reviewer-auditable trial landscape coverage for intensive care hemodynamic research? We built a pipeline that fetches ICU randomized controlled trials from ClinicalTrials.gov, enriches records via seven adapters including PubMed, OpenAlex, and FAERS, and renders two interactive dashboards with evidence-gap visualizations and PRISMA-style flow diagrams. The system uses keyword normalization, placebo-arm classification, deduplication validation, and incremental merge logic with a living update log recording every refresh cycle and its provenance metadata. Against a 21-trial reference standard for hemodynamic ICU interventions, the pipeline achieved sensitivity of 100 percent (95% CI 83.9-100) with all trials correctly classified. Stratified keyword-validation samples and deduplication checks confirmed consistent categorization across intervention classes, phases, and enrollment status. The platform serves as a descriptive evidence-mapping tool making registration coverage and signal gaps inspectable without requiring users to engage with code. However, the limitation of registry-only data means that unpublished results and non-registered trials remain invisible to this approach.

### Submission metadata

```
Corresponding author: Mahmood Ahmad <mahmood.ahmad2@nhs.net>
ORCID: 0000-0001-9107-3704
Affiliation: Tahir Heart Institute, Rabwah, Pakistan

Links:
  Code:      https://github.com/mahmood726-cyber/shahzaib-icu-landscape
  Protocol:  https://github.com/mahmood726-cyber/shahzaib-icu-landscape/blob/main/E156-PROTOCOL.md
  Dashboard: https://mahmood726-cyber.github.io/shahzaib-icu-landscape/

References (topic pack: CT.gov / ClinicalTrials.gov audit):
  1. Zarin DA, Tse T, Williams RJ, Rajakannan T. 2017. Update on trial registration 11 years after the ICMJE policy was established. N Engl J Med. 376(4):383-391. doi:10.1056/NEJMsr1601330
  2. Anderson ML, Chiswell K, Peterson ED, Tasneem A, Topping J, Califf RM. 2015. Compliance with results reporting at ClinicalTrials.gov. N Engl J Med. 372(11):1031-1039. doi:10.1056/NEJMsa1409364

Data availability: No patient-level data used. Analysis derived exclusively
  from publicly available aggregate records. All source identifiers are in
  the protocol document linked above.

Ethics: Not required. Study uses only publicly available aggregate data; no
  human participants; no patient-identifiable information; no individual-
  participant data. No institutional review board approval sought or required
  under standard research-ethics guidelines for secondary methodological
  research on published literature.

Funding: None.

Competing interests: MA serves on the editorial board of Synthēsis (the
  target journal); MA had no role in editorial decisions on this
  manuscript, which was handled by an independent editor of the journal.

Author contributions (CRediT):
  [STUDENT REWRITER, first author] — Writing – original draft, Writing –
    review & editing, Validation.
  [SUPERVISING FACULTY, last/senior author] — Supervision, Validation,
    Writing – review & editing.
  Mahmood Ahmad (middle author, NOT first or last) — Conceptualization,
    Methodology, Software, Data curation, Formal analysis, Resources.

AI disclosure: Computational tooling (including AI-assisted coding via
  Claude Code [Anthropic]) was used to develop analysis scripts and assist
  with data extraction. The final manuscript was human-written, reviewed,
  and approved by the author; the submitted text is not AI-generated. All
  quantitative claims were verified against source data; cross-validation
  was performed where applicable. The author retains full responsibility for
  the final content.

Preprint: Not preprinted.

Reporting checklist: PRISMA 2020 (methods-paper variant — reports on review corpus).

Target journal: ◆ Synthēsis (https://www.synthesis-medicine.org/index.php/journal)
  Section: Methods Note — submit the 156-word E156 body verbatim as the main text.
  The journal caps main text at ≤400 words; E156's 156-word, 7-sentence
  contract sits well inside that ceiling. Do NOT pad to 400 — the
  micro-paper length is the point of the format.

Manuscript license: CC-BY-4.0.
Code license: MIT.

SUBMITTED: [ ]
```

---

## `[479]` ICU Hemodynamic Trial Landscape: A Living Evidence Map

**Type:** methods  |  ESTIMAND: Sensitivity  
**Data:** A living evidence map for ICU hemodynamic trials achieves 100% sensitivity against a 21-trial reference standard.

### 156-word body

Can a browser-based living evidence map provide reviewer-auditable trial landscape coverage for intensive care hemodynamic research? We built a pipeline that fetches ICU randomized controlled trials from ClinicalTrials.gov, enriches records via seven adapters including PubMed, OpenAlex, and FAERS, and renders two interactive dashboards with evidence-gap visualizations and PRISMA-style flow diagrams. The system uses keyword normalization, placebo-arm classification, deduplication validation, and incremental merge logic with a living update log recording every refresh cycle and its provenance metadata. Against a 21-trial reference standard for hemodynamic ICU interventions, the pipeline achieved sensitivity of 100 percent (95% CI 83.9-100) with all trials correctly classified. Stratified keyword-validation samples and deduplication checks confirmed consistent categorization across intervention classes, phases, and enrollment status. The platform serves as a descriptive evidence-mapping tool making registration coverage and signal gaps inspectable without requiring users to engage with code. However, the limitation of registry-only data means that unpublished results and non-registered trials remain invisible to this approach.

### Submission metadata

```
Corresponding author: Mahmood Ahmad <mahmood.ahmad2@nhs.net>
ORCID: 0000-0001-9107-3704
Affiliation: Tahir Heart Institute, Rabwah, Pakistan

Links:
  Code:      https://github.com/mahmood726-cyber/shahzaib-icu-landscape
  Protocol:  https://github.com/mahmood726-cyber/shahzaib-icu-landscape/blob/main/E156-PROTOCOL.md
  Dashboard: https://mahmood726-cyber.github.io/shahzaib-icu-landscape/

References (topic pack: CT.gov / ClinicalTrials.gov audit):
  1. Zarin DA, Tse T, Williams RJ, Rajakannan T. 2017. Update on trial registration 11 years after the ICMJE policy was established. N Engl J Med. 376(4):383-391. doi:10.1056/NEJMsr1601330
  2. Anderson ML, Chiswell K, Peterson ED, Tasneem A, Topping J, Califf RM. 2015. Compliance with results reporting at ClinicalTrials.gov. N Engl J Med. 372(11):1031-1039. doi:10.1056/NEJMsa1409364

Data availability: No patient-level data used. Analysis derived exclusively
  from publicly available aggregate records. All source identifiers are in
  the protocol document linked above.

Ethics: Not required. Study uses only publicly available aggregate data; no
  human participants; no patient-identifiable information; no individual-
  participant data. No institutional review board approval sought or required
  under standard research-ethics guidelines for secondary methodological
  research on published literature.

Funding: None.

Competing interests: MA serves on the editorial board of Synthēsis (the
  target journal); MA had no role in editorial decisions on this
  manuscript, which was handled by an independent editor of the journal.

Author contributions (CRediT):
  [STUDENT REWRITER, first author] — Writing – original draft, Writing –
    review & editing, Validation.
  [SUPERVISING FACULTY, last/senior author] — Supervision, Validation,
    Writing – review & editing.
  Mahmood Ahmad (middle author, NOT first or last) — Conceptualization,
    Methodology, Software, Data curation, Formal analysis, Resources.

AI disclosure: Computational tooling (including AI-assisted coding via
  Claude Code [Anthropic]) was used to develop analysis scripts and assist
  with data extraction. The final manuscript was human-written, reviewed,
  and approved by the author; the submitted text is not AI-generated. All
  quantitative claims were verified against source data; cross-validation
  was performed where applicable. The author retains full responsibility for
  the final content.

Preprint: Not preprinted.

Reporting checklist: PRISMA 2020 (methods-paper variant — reports on review corpus).

Target journal: ◆ Synthēsis (https://www.synthesis-medicine.org/index.php/journal)
  Section: Methods Note — submit the 156-word E156 body verbatim as the main text.
  The journal caps main text at ≤400 words; E156's 156-word, 7-sentence
  contract sits well inside that ceiling. Do NOT pad to 400 — the
  micro-paper length is the point of the format.

Manuscript license: CC-BY-4.0.
Code license: MIT.
```


---

_Auto-generated from the workbook by `C:/E156/scripts/create_missing_protocols.py`. If something is wrong, edit `rewrite-workbook.txt` and re-run the script — it will overwrite this file via the GitHub API._
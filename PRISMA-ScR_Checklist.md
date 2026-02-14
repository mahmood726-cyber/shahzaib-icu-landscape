# PRISMA-ScR Checklist — Table S1

**Preferred Reporting Items for Systematic Reviews and Meta-Analyses extension for Scoping Reviews (PRISMA-ScR)**

Tricco AC, Lillie E, Zarin W, et al. PRISMA Extension for Scoping Reviews (PRISMA-ScR): Checklist and Explanation. *Ann Intern Med.* 2018;169(7):467–473. doi:10.7326/M18-0850

**Manuscript:** ICU RCT Living Trial Landscape Map: Hemodynamic and Related Outcomes

| Item | PRISMA-ScR Checklist Item | Reported On |
|------|--------------------------|-------------|
| **TITLE** | | |
| 1 | Identify the report as a scoping review | Dashboard title: "ICU RCT Living Trial Landscape Map" and hero text: "A living landscape map of registered critical care randomized trials with hemodynamic and related ICU outcomes" (index.html, lines 40–47). The term "trial landscape map" distinguishes this from systematic reviews. |
| **ABSTRACT** | | |
| 2 | Structured summary including background, objectives, eligibility criteria, sources of evidence, charting methods, results, and conclusions | Hero lead text (index.html, lines 42–47) provides a structured summary of scope and purpose. A formal structured abstract should accompany the manuscript submission. |
| **INTRODUCTION** | | |
| 3 | Rationale — describe the rationale for the review in the context of existing knowledge | "Rationale and objectives" section (index.html, lines 415–422): "This living trial landscape map aims to characterize the scope, coverage, and temporal trends of registered ICU randomized trials with hemodynamic and related outcomes." |
| 4 | Objectives — provide an explicit statement of the questions and objectives | Same section (lines 418–421): "The objective is descriptive: to identify which hemodynamic parameters are well-represented in trial registrations and where placebo-controlled evidence is sparse. This is not a systematic review and does not synthesize treatment effects." |
| **METHODS** | | |
| 5 | Protocol and registration — indicate whether a protocol exists; state registration ID if registered | Limitations section (index.html, line 561): "This trial landscape map was not prospectively registered. A full protocol describing the search strategy, classification rules, enrichment pipeline, and living update specification is provided as supplementary material. Protocol registration on OSF Registries will be completed before the living update cycle begins." |
| 6 | Eligibility criteria — specify inclusion and exclusion criteria | "Eligibility criteria" section (index.html, lines 424–431): Inclusion: interventional, randomized, CT.gov-registered, ICU population term + hemodynamic keyword. Exclusion: observational, non-randomized, no hemodynamic match. No date, language, or geographic restrictions. |
| 7 | Information sources — describe all information sources and date of search | "Information sources" section (index.html, lines 434–447): Primary: ClinicalTrials.gov API v2. Supplementary: PubMed E-utilities. Enrichment: 7 adapters (PubMed, FAERS, OpenAlex, Crossref, Europe PMC, Unpaywall, OpenCitations). Search date: 14 February 2026 (line 461). |
| 8 | Search — present the full search strategy for at least one database | "CT.gov search strategy" (index.html, lines 450–463): Full query terms listed. "PubMed search strategy" (lines 475–483): Harmonized query described. Full machine-readable queries in `ctgov_icu_placebo_strategy.json` and `search_pubmed_primary.py`. Recall validation: 21/21 reference trials (lines 465–472). |
| 9 | Selection of sources of evidence — state the process for selecting sources | Automated retrieval from CT.gov API (all matching records, no manual screening). PubMed records merged via NCT ID cross-reference and Levenshtein fuzzy title matching (threshold ≥ 0.85 with Jaccard pre-filter ≥ 0.50). Described in "Information sources" (lines 438–443). |
| 10 | Data charting process — describe methods of charting data and any processes for obtaining and confirming data | "Data charting and items" (index.html, lines 510–517): "Charting is fully automated from structured API fields; no manual data extraction is performed. Data dictionary available in the pipeline source code." |
| 11 | Data items — list and define all variables for which data were sought | Same section (lines 512–514): NCT ID, title, conditions, interventions, study status, phase, enrollment, start date, completion date, allocation, masking, arm descriptions, primary/secondary/other outcome measures with time frames, countries, and comparator type. |
| 12 | Critical appraisal of individual sources of evidence — if done, describe methods | Limitations section (index.html, line 560): "Consistent with scoping review methodology (Tricco et al., 2018; JBI Manual for Evidence Synthesis), no risk of bias or quality appraisal was performed. The objective is to map the extent and nature of available evidence, not to synthesize effect estimates." |
| **RESULTS** | | |
| 13 | Selection of sources of evidence — present a flow diagram and results of the search/selection process | PRISMA flow diagram rendered in dashboard (plotly_charts.js `renderPrismaFlow`). Shows CT.gov records identified, PubMed records identified, duplicates removed, and records included with hemodynamic mentions. Summary statistics in dashboard hero and insights page. |
| 14 | Characteristics of sources of evidence — present characteristics of each source | Dashboard charts: study status distribution, phase distribution, enrollment histogram, temporal trends (time series), geographic distribution (choropleth), intervention–outcome intersections (bubble matrix). All interactive with filtering. |
| 15 | Results of individual sources of evidence — present details of each source relevant to the review question | Per-keyword study counts, mention counts, and placebo coverage displayed in keyword signal bars chart (index.html, lines 219–228). Trial Coverage Matrix in insights.html shows per-keyword gaps. Individual trial details accessible via click-through. |
| 16 | Synthesis of results — summarize and/or present the main results as they relate to the review questions and objectives | Dashboard sections: hero summary statistics, keyword signal bars, bubble matrix, trial coverage matrix (insights.html), tier classification (Strong/Moderate/Weak based on placebo study count), temporal trends. All descriptive — no effect size synthesis. |
| **DISCUSSION** | | |
| 17 | Summary of evidence — summarize main findings, including an overview of concepts, themes, and types of evidence | Dashboard provides visual and interactive summary. Key finding categories: keyword coverage, placebo-arm gaps, temporal trends, geographic distribution. Insights page provides analytical interpretation with exploratory composite scores (clearly labeled as non-validated). |
| 18 | Limitations — discuss limitations of the scoping review process | "Limitations" section (index.html, lines 552–564): 10 specific limitations including registry bias (CT.gov only), keyword matching precision, composite score indices, geographic bias, no risk-of-bias assessment, no prospective registration, PRISMA adaptation, temporal bias from PubMed, dedup false merge risk. |
| 19 | Conclusions — provide a general interpretation of the results with respect to the review questions and objectives, including potential implications | Dashboard footer and hero text frame the map as a descriptive landscape of trial registrations. The scope is explicitly limited to characterizing registration patterns, not synthesizing evidence or making clinical recommendations. |
| **FUNDING** | | |
| 20 | Funding — describe sources of funding and role of funders | "Funding" section (index.html, line 579): "This research received no specific grant from any funding agency in the public, commercial, or not-for-profit sectors." |
| **OTHER** | | |
| 21 | Competing interests | "Competing interests" section (index.html, line 576): "The authors declare no competing interests." |
| 22 | Author contributions | "Author contributions (CRediT)" section (index.html, lines 581–586): Shahzaib Ahmad — Conceptualization, Data curation, Formal analysis, Methodology, Software, Validation, Visualization, Writing — original draft, Writing — review & editing. |

## Notes

- This checklist maps to the interactive dashboard (index.html and insights.html) which serves as both the research output and the reporting vehicle.
- A formal manuscript with structured Abstract, Introduction, and Discussion sections should accompany this dashboard for journal submission.
- The living review specification (index.html, lines 534–549) describes update frequency, stopping criteria, amendment policy, and version history per living systematic review guidelines.
- All source code, search strategies, and validation samples are provided as supplementary material for reproducibility.

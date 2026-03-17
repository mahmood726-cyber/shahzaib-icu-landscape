# PRISMA-ScR Checklist — Table S1

**Preferred Reporting Items for Systematic Reviews and Meta-Analyses extension for Scoping Reviews (PRISMA-ScR)**

Tricco AC, Lillie E, Zarin W, et al. PRISMA Extension for Scoping Reviews (PRISMA-ScR): Checklist and Explanation. *Ann Intern Med.* 2018;169(7):467–473. doi:10.7326/M18-0850

**Manuscript:** ICU Hemodynamic Trial Landscape: A Living Scoping Review of Registered Randomized Trials with Hemodynamic and Related Outcomes

| Item | PRISMA-ScR Checklist Item | Reported On |
|------|--------------------------|-------------|
| **TITLE** | | |
| 1 | Identify the report as a scoping review | Manuscript title: "ICU Hemodynamic Trial Landscape: A Living Scoping Review of Registered Randomized Trials with Hemodynamic and Related Outcomes." The term "living scoping review" identifies the report type. |
| **ABSTRACT** | | |
| 2 | Structured summary including background, objectives, eligibility criteria, sources of evidence, charting methods, results, and conclusions | Abstract section (260 words): structured with Background, Objectives, Methods, Results, and Conclusions sub-headings per PLOS ONE requirements. |
| **INTRODUCTION** | | |
| 3 | Rationale — describe the rationale for the review in the context of existing knowledge | Introduction, paragraphs 1–3: hemodynamic management in ICU (paragraph 1), gap in cross-cutting landscape mapping (paragraph 2), scoping review and living review methodology (paragraph 3). |
| 4 | Objectives — provide an explicit statement of the questions and objectives | Introduction, paragraph 4: four explicit objectives stated — (1) describe volume, trends, geography, and design; (2) classify outcomes into standardized categories; (3) quantify placebo-arm coverage; (4) identify evidence gaps. |
| **METHODS** | | |
| 5 | Protocol and registration — indicate whether a protocol exists; state registration ID if registered | Methods, "Study design and reporting" subsection: "This study was not prospectively registered; a full protocol describing the search strategy, classification rules, enrichment pipeline, and living update specification is provided as supplementary material." |
| 6 | Eligibility criteria — specify inclusion and exclusion criteria | Methods, "Eligibility criteria" subsection: Inclusion: interventional, randomized, CT.gov-registered, ICU population term + hemodynamic keyword. Exclusion: observational, non-randomized, no hemodynamic match. No date, language, or geographic restrictions. |
| 7 | Information sources — describe all information sources and date of search | Methods, "Information sources" subsection: Primary: ClinicalTrials.gov API v2. Supplementary: PubMed E-utilities. Search date: 14 February 2026. Seven enrichment adapters listed (not activated for current cycle). |
| 8 | Search — present the full search strategy for at least one database | Methods, "Search strategy" subsection: Full CT.gov query terms listed (API v2 `query.term` with AREA filters). PubMed search described. Recall validation: 21/21 reference trials (95% CI: 83.9%–100%). Machine-readable queries in S2 File. |
| 9 | Selection of sources of evidence — state the process for selecting sources | Methods, "Information sources" subsection: Automated retrieval from CT.gov API (all matching records, no manual screening). PubMed merged via NCT ID cross-reference and Levenshtein fuzzy title matching (threshold >= 0.85 with Jaccard pre-filter >= 0.50). Validation sample in S5 File. |
| 10 | Data charting process — describe methods of charting data and any processes for obtaining and confirming data | Methods, "Data charting" subsection: "Charting was fully automated from structured API fields; no manual data extraction was performed." |
| 11 | Data items — list and define all variables for which data were sought | Methods, "Data charting" subsection: NCT ID, title, conditions, interventions, study status, phase, enrollment, start date, completion date, allocation, masking, arm descriptions, primary/secondary/other outcome measures with time frames, countries, and comparator type. |
| 12 | Critical appraisal of individual sources of evidence — if done, describe methods | Methods, "Risk of bias assessment" subsection: "Consistent with scoping review methodology [13,15], no risk of bias or quality appraisal of individual studies was performed. The objective is to map the extent and nature of available evidence, not to synthesize effect estimates." |
| **RESULTS** | | |
| 13 | Selection of sources of evidence — present a flow diagram and results of the search/selection process | Results, "Study selection" subsection and Fig 1: Adapted PRISMA-ScR flow diagram showing CT.gov (22,054), PubMed (5,971), duplicates (527), total (27,498), hemodynamic (11,960), placebo (6,204), both (1,997). |
| 14 | Characteristics of sources of evidence — present characteristics of each source | Results, "Study characteristics" subsection and Table 1: Registration status, trial phase, masking, enrollment (median 100, IQR 50–247), primary purpose. Results, "Temporal trends" subsection and Fig 2: decade distribution. Results, "Geographic distribution" subsection and Table 2: 148 countries, top 15 listed. |
| 15 | Results of individual sources of evidence — present details of each source relevant to the review question | Results, "Hemodynamic outcome landscape" subsection and Table 3: Top 15 keywords by study count with mention counts and placebo coverage. Results, "Evidence gaps" subsection and Table 4: 18 parameters with <= 4 placebo studies. Normalized categories in S3 Table. |
| 16 | Synthesis of results — summarize and/or present the main results as they relate to the review questions and objectives | Results, "Hemodynamic outcome landscape" (outcome type distribution, normalized categories, co-occurrence), "Placebo-arm coverage," "Evidence gaps," and "Units of measurement" subsections. All descriptive — no effect size synthesis. Fig 4: keyword signal map. |
| **DISCUSSION** | | |
| 17 | Summary of evidence — summarize main findings, including an overview of concepts, themes, and types of evidence | Discussion, "Principal findings" subsection: three key findings (temporal acceleration, advanced parameter under-representation, low hemodynamic + placebo combination rate). |
| 18 | Limitations — discuss limitations of the scoping review process | Discussion, "Strengths and limitations" subsection: 9 specific limitations including registry bias (CT.gov only), keyword matching precision, SOFA composite counting, mention-level granularity, PubMed ascertainment differences, deduplication thresholds, no prospective registration, enrichment adapters not activated, registration vs. reporting gap. |
| 19 | Conclusions — provide a general interpretation of the results with respect to the review questions and objectives, including potential implications | Discussion, "Implications for research" and "Conclusions" subsections: evidence gap areas identified, interactive dashboard for dynamic exploration, scope limited to mapping trial registrations. |
| **FUNDING** | | |
| 20 | Funding — describe sources of funding and role of funders | Funding statement section: "The author received no specific funding for this work." |
| **OTHER** | | |
| 21 | Competing interests | Competing interests section: "The author declares no competing interests." |
| 22 | Author contributions | Author contributions (CRediT) section: Shahzaib Ahmad — Conceptualization, Data curation, Formal analysis, Methodology, Software, Validation, Visualization, Writing — original draft, Writing — review & editing. |

## Notes

- This checklist maps to the manuscript: "ICU Hemodynamic Trial Landscape: A Living Scoping Review of Registered Randomized Trials with Hemodynamic and Related Outcomes."
- The living review specification (Methods, "Living review specification" subsection) describes update frequency, stopping criteria, amendment policy, and version history per living systematic review guidelines [14].
- All source code, search strategies, and validation samples are provided as supplementary material (S2, S4, S5, S6 Files) for reproducibility.
- An interactive dashboard accompanies the manuscript for dynamic exploration of the trial landscape.

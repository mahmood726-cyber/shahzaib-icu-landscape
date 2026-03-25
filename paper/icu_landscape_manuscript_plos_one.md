# ICU Hemodynamic Trial Landscape: A Living Scoping Review of Registered Randomized Trials with Hemodynamic and Related Outcomes

**Shahzaib Ahmad**^1^

^1^ Royal Free Hospital, London, UK

**Corresponding author:** Shahzaib Ahmad, mahmood.ahmad2@nhs.net

ORCID: 0009-0003-7781-4478

---

## Abstract

**Background:** Hemodynamic monitoring and management are central to critical care, yet no comprehensive mapping of registered randomized controlled trials (RCTs) with hemodynamic outcomes exists. Understanding the breadth, gaps, and temporal trends in trial registrations is essential for identifying research priorities and avoiding redundant studies.

**Objectives:** To systematically map all registered ICU RCTs with hemodynamic and related outcomes on ClinicalTrials.gov, characterize their design features, and identify evidence gaps in placebo-controlled coverage.

**Methods:** This living scoping review followed the PRISMA-ScR guidelines. ClinicalTrials.gov API v2 and PubMed E-utilities were searched on 14 February 2026. Eligible studies were interventional, randomized, and registered with at least one ICU/critical care population term. Hemodynamic outcomes were classified into 35 normalized categories using keyword matching with negative-context filtering. Non-hemodynamic adjuncts (severity scores, ventilation duration) were reported separately.

**Results:** After deduplication, 27,498 ICU RCTs were identified (22,054 from ClinicalTrials.gov, 5,971 from PubMed; 527 duplicates removed). Of these, 11,960 (43.5%) registered at least one hemodynamic outcome and 6,204 (22.6%) included a placebo arm. Only 1,997 trials (7.3%) had both hemodynamic outcomes and placebo arms. The most frequently registered hemodynamic outcomes were heart rate (3,985 studies), blood pressure (3,920), and mean arterial pressure (1,542). Trials were registered across 148 countries, with the United States contributing 5,937 (21.6%). Nearly half of all registrations (49.1%) occurred in the 2020s. Several hemodynamic parameters had sparse placebo-controlled coverage, including cardiac power output (2 placebo studies), intrathoracic blood volume (0), and dP/dt (1).

**Conclusions:** This living landscape map reveals substantial hemodynamic trial activity but marked heterogeneity in placebo-arm coverage across outcome parameters. The interactive dashboard and structured dataset are provided to support evidence gap identification and trial planning.

---

## Introduction

Hemodynamic assessment and optimization remain fundamental to the management of critically ill patients in the intensive care unit (ICU) [1,2]. From basic vital signs such as heart rate and blood pressure to advanced parameters including cardiac output, stroke volume variation, and tissue perfusion markers, a broad spectrum of hemodynamic endpoints is used in clinical research and practice [3]. Over the past two decades, the number of registered randomized controlled trials (RCTs) in critical care has grown substantially, driven by increased regulatory requirements for trial registration and a growing emphasis on hemodynamic-guided resuscitation strategies [4,5].

Despite this growth, no systematic attempt has been made to map the full landscape of registered ICU RCTs with hemodynamic outcomes. Existing systematic reviews typically focus on specific conditions (e.g., septic shock [6], acute respiratory distress syndrome [ARDS] [7], cardiac arrest [8]) or specific interventions (e.g., vasopressors [9], fluid resuscitation [10]). While these reviews are valuable for synthesizing treatment effects, they do not provide a cross-cutting view of which hemodynamic parameters are well-represented in the trial registry and where evidence gaps persist.

Evidence gap maps and scoping reviews have emerged as methodological tools for mapping the extent and nature of available evidence in a given field [11,12]. Unlike systematic reviews, scoping reviews do not aim to synthesize effect estimates or assess risk of bias; instead, they characterize the breadth of evidence to inform research prioritization [13]. The living systematic review framework extends this approach by incorporating regular updates to maintain currency as new evidence accumulates [14].

This study presents a living scoping review that maps all registered ICU RCTs with hemodynamic and related outcomes from ClinicalTrials.gov and PubMed. The objectives are: (1) to describe the volume, temporal trends, geographic distribution, and design characteristics of registered hemodynamic ICU trials; (2) to classify registered outcomes into standardized hemodynamic categories; (3) to quantify placebo-arm coverage across outcome parameters; and (4) to identify evidence gaps where hemodynamic parameters lack placebo-controlled trial data. The study output includes both this manuscript and an interactive dashboard for dynamic exploration of the trial landscape.

## Methods

### Study design and reporting

This living scoping review was conducted and reported in accordance with the Preferred Reporting Items for Systematic Reviews and Meta-Analyses extension for Scoping Reviews (PRISMA-ScR) [13]. A completed PRISMA-ScR checklist is provided as supplementary material (S1 Table). This study was not prospectively registered; a full protocol describing the search strategy, classification rules, enrichment pipeline, and living update specification is provided as supplementary material (S2 File).

### Eligibility criteria

**Inclusion criteria:** Interventional, randomized studies registered on ClinicalTrials.gov with at least one ICU or critical care population term and at least one hemodynamic keyword in registered outcome measures (primary, secondary, or other).

**Exclusion criteria:** Observational studies, non-randomized designs, and trials without any hemodynamic keyword match in outcome measures. No date, language, or geographic restrictions were applied.

### Information sources

**Primary source:** ClinicalTrials.gov API v2 (all study statuses, no date restriction). The initial search was executed on 14 February 2026.

**Supplementary source:** PubMed E-utilities (esearch and efetch) for published RCTs that may lack ClinicalTrials.gov registration. PubMed results were deduplicated against ClinicalTrials.gov via NCT ID cross-referencing and Levenshtein fuzzy title matching (similarity threshold >= 0.85, with Jaccard word-overlap pre-filter >= 0.50). The 0.85 threshold was chosen to balance sensitivity against false merges for English-language clinical trial titles. A validation sample of 100 pairs (50 merged, 50 near-miss unmerged) is provided for independent assessment (S5 File).

The pipeline infrastructure includes 7 enrichment adapters (PubMed, OpenFDA/FAERS, OpenAlex, Crossref, Europe PMC, Unpaywall, OpenCitations) for augmenting trial records with publication metadata, safety signals, and citation data. These adapters were not activated for the current search cycle and are planned for future update cycles.

### Search strategy

Trials were retrieved from ClinicalTrials.gov using the API v2 `query.term` parameter filtered by `AREA[StudyType]INTERVENTIONAL AND AREA[DesignAllocation]RANDOMIZED`. ICU/critical care population terms included: intensive care, critical care, ICU, intensive therapy unit, high dependency unit, critical illness, mechanical ventilation, ventilator, septic shock, vasopressor, ARDS, acute respiratory distress, respiratory failure, cardiogenic shock, hemorrhagic shock, ECMO, extracorporeal membrane oxygenation, multi-organ failure, organ dysfunction, CCU, MICU, SICU, PICU, NICU, traumatic brain injury, TBI, cardiac arrest, post-cardiac arrest, targeted temperature management, therapeutic hypothermia, major burns, burn resuscitation, major trauma, pulmonary embolism, diabetic ketoacidosis, DKA, acute liver failure, and status epilepticus. The full machine-readable query is provided in the supplementary configuration file.

PubMed was searched using E-utilities with ICU terms harmonized to the ClinicalTrials.gov query, combined with hemodynamic outcome terms and filtered to the `Randomized Controlled Trial` publication type. PubMed-only studies were assigned `INFERRED_COMPLETED` status and `INFERRED_RANDOMIZED` allocation.

**Recall validation:** A reference standard of 21 landmark ICU RCTs spanning 11 clinical domains (septic shock, corticosteroids in sepsis, ARDS, ECMO, cardiac arrest/TTM, TBI, pulmonary embolism, burns, cardiogenic shock, hemorrhagic shock, and DKA) was assembled from published systematic reviews. All 21 trials were captured by the current search strategy (21/21 = 100% recall; 95% CI: 83.9%-100% by Clopper-Pearson). This small reference standard was author-assembled from published systematic reviews and is biased toward well-known landmark trials, which are easier to capture than smaller registrations. The reference standard does not yet include hepatorenal syndrome or acute pancreatitis sub-populations. Precision (false positive rate) of the search strategy was not formally assessed. NCT IDs and trial names are documented in the configuration file (S2 File).

### Hemodynamic outcome classification

Outcome measures, descriptions, and time frames were scanned for hemodynamic keywords using word-boundary matching. A total of 105 raw keywords were mapped to 35 normalized categories (e.g., "norepinephrine" to Vasopressor/Inotrope, "MAP" to Mean Arterial Pressure). Ambiguous abbreviations (HR, SV, PAP) were processed with negative-context filtering to exclude non-hemodynamic uses (e.g., "HR" as Hazard Ratio, "PAP" as Pap smear).

**Non-hemodynamic adjuncts** (ICU severity scores such as the Sequential Organ Failure Assessment [SOFA] and Acute Physiology and Chronic Health Evaluation [APACHE], ventilation duration, resuscitation endpoints, and vasopressor-free days) were included for clinical relevance but reported separately from core hemodynamic totals to avoid inflating evidence counts.

To enable independent assessment of classification accuracy, a stratified random sample of 200 mentions across all keyword categories was generated (S4 Table). The validation framework and unannotated sample are provided as supplementary material for independent human scoring of keyword classification precision. Formal sensitivity/specificity reporting requires this independent scoring step; the materials to facilitate it are provided.

### Data charting

Extracted data items per trial included: NCT ID, title, conditions, interventions, study status, phase, enrollment, start date, completion date, allocation, masking, arm descriptions, primary/secondary/other outcome measures with time frames, countries, and comparator type. Charting was fully automated from structured API fields; no manual data extraction was performed.

### Comparator arm classification

Placebo/sham comparators were classified as true inert comparators only. Usual care and standard care were classified separately as active comparators. The structured ClinicalTrials.gov `armGroupType` field was used when available; text-based classification was the fallback.

### Study status handling

All study statuses were included (recruiting, completed, withdrawn, terminated, suspended). Status stratification is provided in the summary dataset for downstream filtering.

### Living review specification

This landscape map is designed as a living scoping review [14], with the initial search cycle reported here. Monthly incremental updates are planned via the automated pipeline, which fetches new and updated trials from ClinicalTrials.gov and PubMed since the last successful run. Each update cycle is logged with timestamp, source counts, and a SHA-256 data integrity hash. Changes to the search strategy, classification rules, or enrichment sources are versioned in the configuration file and documented in the pipeline commit history. Stopping criteria: updates will continue as long as the ClinicalTrials.gov API remains available and the dashboard is actively maintained; cessation will be documented with a final update date and reason. Prior published versions will remain accessible via the Zenodo archive with versioned DOIs. Authorship for future update cycles will follow ICMJE criteria.

### Risk of bias assessment

Consistent with scoping review methodology [13,15], no risk of bias or quality appraisal of individual studies was performed. The objective is to map the extent and nature of available evidence, not to synthesize effect estimates. Masking and allocation data were extracted for descriptive purposes.

### Software and data availability

The pipeline was implemented in Python (version 3.13). Source code, configuration files, validation samples, and the interactive dashboard are provided as supplementary material (S6 File). All data were derived from publicly available sources (ClinicalTrials.gov, PubMed). The complete derived dataset is available in CSV and Parquet formats [ZENODO_DOI_PLACEHOLDER].

## Results

### Study selection

The adapted PRISMA-ScR flow diagram (Fig 1) summarizes the study identification process. ClinicalTrials.gov retrieval yielded 22,054 studies and PubMed retrieval yielded 5,971 studies. After removing 527 duplicates identified through NCT ID cross-referencing and fuzzy title matching, 27,498 unique ICU RCTs were included. Of these, 11,960 (43.5%) registered at least one hemodynamic outcome, 6,204 (22.6%) included a placebo or sham comparator arm, and 1,997 (7.3%) had both hemodynamic outcomes and placebo arms. A total of 15,538 studies were excluded from the hemodynamic subset due to absence of hemodynamic keyword matches in registered outcomes.

### Study characteristics

Table 1 presents the characteristics of the 27,498 included ICU RCTs. The majority had treatment as primary purpose (13,487; 49.0%), followed by prevention (3,875; 14.1%) and supportive care (1,953; 7.1%).

**Registration status.** Completed and inferred-completed studies accounted for the largest proportion (10,999 [40.0%] and 5,444 [19.8%], respectively). A total of 2,793 studies (10.2%) were actively recruiting, 1,224 (4.5%) were not yet recruiting, and 631 (2.3%) were active but not recruiting. Terminated and withdrawn studies accounted for 1,664 (6.1%) and 756 (2.7%), respectively. The status of 3,738 studies (13.6%) was unknown.

**Trial phase.** Among the 22,054 ClinicalTrials.gov-sourced studies, 9,653 (43.8%) reported a specific trial phase: Phase 3 (3,046; 31.6% of phased), Phase 4 (2,532; 26.2%), Phase 2 (2,321; 24.0%), combined Phase 2/3 (737; 7.6%), Phase 1 (414; 4.3%), combined Phase 1/2 (410; 4.2%), and Early Phase 1 (193; 2.0%). The remaining 12,396 (56.2%) were classified as "Not Applicable," predominantly reflecting studies of approved interventions or non-drug studies. Five studies (0.02%) had no phase data reported.

**Masking.** Among ClinicalTrials.gov-sourced studies, 8,117 (36.8%) were open-label (no masking), 4,534 (20.6%) used single masking, 3,704 (16.8%) double masking, 2,248 (10.2%) triple masking, and 3,401 (15.4%) quadruple masking.

**Enrollment.** Among 21,229 studies with reported enrollment, the median planned enrollment was 100 participants (interquartile range [IQR]: 50-247), with a total of 20,370,084 planned participants across all studies.

### Temporal trends

Fig 2 shows the temporal distribution of trial registrations by start date among the 22,016 studies with available start dates (ClinicalTrials.gov-sourced studies only; PubMed-inferred studies lack structured start dates). Trial registrations have increased markedly over time: 96 trials (0.4%) had start dates in the 1990s, 2,400 (10.9%) in the 2000s, 8,704 (39.5%) in the 2010s, and 10,802 (49.1%) in the 2020s (through February 2026). The earliest ClinicalTrials.gov-registered trial had a 1974 start date, while 14 trials had projected start dates in 2027-2029.

### Geographic distribution

Table 2 and Fig 3 present the geographic distribution of trial registration. Trials were registered across 148 countries. The United States contributed the most studies (5,937; 21.6%), followed by France (2,000; 7.3%), China (1,823; 6.6%), Canada (1,803; 6.6%), and Egypt (1,775; 6.5%). Other high-contributing countries included Germany (1,388; 5.0%), Spain (1,282; 4.7%), Italy (1,269; 4.6%), Turkey (1,147; 4.2%), and the United Kingdom (1,138; 4.1%).

### Hemodynamic outcome landscape

A total of 39,923 hemodynamic mentions were identified across the 11,960 studies with hemodynamic outcomes, comprising 37,168 core hemodynamic mentions and 2,755 non-hemodynamic adjunct mentions (severity scores, ventilation duration, resuscitation endpoints).

**Outcome type distribution.** Among the 39,923 hemodynamic mentions, 21,451 (53.7%) came from structured ClinicalTrials.gov outcome fields (4,981 primary, 14,993 secondary, 1,477 other/exploratory) across 5,989 unique studies. The remaining 18,472 mentions (46.3%) were inferred from PubMed-sourced studies (n = 5,971) whose hemodynamic outcomes were identified from title and abstract text rather than structured registration fields. This methodological distinction is important: ClinicalTrials.gov mentions are derived from investigator-registered outcome measures, while PubMed-inferred mentions are derived from publication text and may have different error profiles. Sensitivity analyses restricting to ClinicalTrials.gov-only studies are available in the interactive dashboard.

**Top hemodynamic keywords.** Table 3 presents the 15 most frequently registered hemodynamic outcome categories (by study count). Heart rate was the most common (3,985 studies; 4,525 mentions), followed by blood pressure (3,920 studies; 4,820 mentions), systolic blood pressure (2,217 studies; 2,747 mentions), mean arterial pressure (1,542 studies; 1,697 mentions), vasopressor use (1,370 studies; 1,670 mentions), lactate (1,318 studies; 1,497 mentions), and diastolic blood pressure (1,254 studies; 1,471 mentions).

**Normalized categories.** After normalization to 35 canonical categories, Blood Pressure (4,543 studies), Heart Rate (4,319 studies), Vasopressor/Inotrope (2,963 studies), and Hemodynamics (general) (2,922 studies) were the most prevalent.

**Keyword co-occurrence.** The most frequent co-occurring keyword pairs were Blood Pressure and Heart Rate (2,246 shared studies), Blood Pressure and Vasopressor/Inotrope (1,013), Heart Rate and MAP (1,009), Heart Rate and Hemodynamics (975), and Blood Pressure and Hemodynamics (974).

### Placebo-arm coverage

Of the 6,204 studies with placebo/sham arms, 1,997 (32.2%) registered at least one hemodynamic outcome measure, generating 7,201 placebo-associated hemodynamic mentions. Table 3 shows placebo study counts alongside total study counts for each keyword. Blood pressure had the highest absolute placebo coverage (744 placebo studies), followed by heart rate (543), SOFA score (320), diastolic blood pressure (308), and vasopressor use (258).

### Evidence gaps

Table 4 identifies hemodynamic parameters with the sparsest placebo-controlled evidence at the individual keyword level. Among core hemodynamic parameters (excluding adjuncts), several had zero or near-zero placebo-controlled studies: intrathoracic blood volume (ITBV; 0 studies), intrathoracic blood volume index (ITBVI; 0 studies), dP/dt (rate of left ventricular pressure rise; 1 study), fluid responsiveness (1 study), fluid challenge (0 studies), DO2I (indexed oxygen delivery; 1 study), and global end-diastolic volume (GEDV; 1 study). Note that some individual keywords map to broader normalized categories with higher aggregate counts (e.g., CVP abbreviation [12 placebo studies] plus "central venous pressure" [23 placebo] together yield 27 unique placebo studies in the normalized CVP category; see S3 Table for full normalized counts). Fig 4 plots total study count against placebo study count for each normalized category, highlighting parameters below the diagonal as evidence gaps. The evidence gap analysis at both the keyword and normalized category levels is available in the interactive dashboard.

### Units of measurement

Among the 39,923 hemodynamic mentions, 5,376 (13.5%) had unspecified measurement units, 4,171 (10.4%) were marked as not applicable, and 3,370 (8.4%) specified percentage (%). Other reported units included mmHg, L/min, L/min/m^2^, and mL/m^2^. The high proportion of unspecified units reflects the variable quality of outcome description in trial registrations.

## Discussion

### Principal findings

This living scoping review identified 27,498 registered ICU RCTs from ClinicalTrials.gov and PubMed, of which 11,960 (43.5%) included at least one hemodynamic outcome measure. The trial landscape reveals three key findings. First, hemodynamic trial registration has accelerated dramatically, with nearly half (49.1%) of all registrations occurring in the 2020s alone. Second, while basic hemodynamic parameters (heart rate, blood pressure, MAP) are extensively represented, advanced hemodynamic parameters (cardiac power output, global end-diastolic volume, intrathoracic blood volume) have minimal trial coverage and virtually no placebo-controlled evidence. Third, only 1,997 (7.3%) of all identified ICU RCTs combine hemodynamic outcomes with placebo or sham comparator arms, indicating that the vast majority of hemodynamic evidence in critical care comes from active-comparator or unblinded designs.

### Context within existing literature

Previous mapping efforts in critical care have typically focused on specific domains. Rhodes et al. [1] and the Surviving Sepsis Campaign provide guideline recommendations based on available evidence but do not map the registry landscape. Defined Critical Care Research Priorities initiatives [16] have identified knowledge gaps through expert consensus rather than systematic registry analysis. Evidence gap maps in other clinical areas [11] have demonstrated the value of visual, interactive approaches to identifying research priorities.

This appears to be the first comprehensive living landscape map of registered ICU hemodynamic trials. The dual-source approach (ClinicalTrials.gov and PubMed) and automated classification pipeline extend beyond manual search strategies used in traditional scoping reviews.

The finding that heart rate and blood pressure dominate the hemodynamic trial landscape is unsurprising, as these are universally monitored in ICU settings. However, the marked under-representation of advanced hemodynamic parameters — which are increasingly advocated for personalized hemodynamic management [3,17] — highlights a disconnect between clinical interest and registered trial evidence.

### Strengths and limitations

**Strengths** include the comprehensive, reproducible, automated pipeline; the dual-source search strategy with recall validation (21/21 landmark trials); the transparent hemodynamic classification with a provided validation sample; and the living review model for ongoing updates.

**Limitations** include: (1) ClinicalTrials.gov only — trials registered solely on other registries (EUCTR, ISRCTN, ANZCTR, ChiCTR) are not captured, introducing geographic bias toward US-centric and industry-sponsored trials; (2) keyword matching operates on outcome text — precision depends on outcome description quality, though a stratified validation sample (n = 200) is provided; (3) ICU severity scores (SOFA, APACHE) are composite indices where only the cardiovascular subscore is hemodynamic, yet they are counted as hemodynamic mentions (reported as adjuncts); (4) counts are mention-level by default, meaning one study with 3 MAP time points generates 3 mentions; (5) PubMed-sourced studies (46.3% of hemodynamic mentions) use a fundamentally different ascertainment method (title/abstract text) compared to ClinicalTrials.gov (structured outcome fields), which may have different error profiles; PubMed also introduces temporal bias toward published (completed) trials; (6) fuzzy title matching for deduplication (Levenshtein >= 0.85) may produce false merges; (7) the search was not prospectively registered, though the full protocol is provided (S2 File); (8) enrichment adapters were not activated for this search cycle; and (9) this study maps trial registrations, not published results or effect sizes — a registered hemodynamic outcome does not guarantee that the data were collected or reported.

### Implications for research

The evidence gap analysis identifies several areas where placebo-controlled trial data are sparse despite clinical relevance. Advanced hemodynamic monitoring parameters (cardiac power output, global end-diastolic volume, intrathoracic blood volume) represent potential targets for future trials. The low placebo-arm ratio for parameters such as CVP (7.1%) and cardiac index (7.8%) suggests that while these parameters are commonly measured, they are rarely evaluated in placebo-controlled designs.

The interactive dashboard accompanying this manuscript enables researchers to explore the landscape dynamically, filter by study status, phase, and country, and identify specific evidence gaps relevant to their research planning.

### Conclusions

This living scoping review maps 27,498 registered ICU RCTs with hemodynamic and related outcomes, revealing substantial trial activity but marked heterogeneity in evidence coverage. Basic vital sign parameters are extensively represented, while advanced hemodynamic endpoints have minimal placebo-controlled evidence. The structured dataset and interactive dashboard provide a resource for evidence gap identification and critical care trial planning.

---

## References

1. Rhodes A, Evans LE, Alhazzani W, Levy MM, Antonelli M, Ferrer R, et al. Surviving Sepsis Campaign: International Guidelines for Management of Sepsis and Septic Shock: 2016. Intensive Care Med. 2017;43(3):304-377. https://doi.org/10.1007/s00134-017-4683-6
2. Singer M, Deutschman CS, Seymour CW, Shankar-Hari M, Annane D, Bauer M, et al. The Third International Consensus Definitions for Sepsis and Septic Shock (Sepsis-3). JAMA. 2016;315(8):801-810. https://doi.org/10.1001/jama.2016.0287
3. Cecconi M, De Backer D, Antonelli M, Beale R, Bakker J, Hofer C, et al. Consensus on circulatory shock and hemodynamic monitoring. Task force of the European Society of Intensive Care Medicine. Intensive Care Med. 2014;40(12):1795-1815. https://doi.org/10.1007/s00134-014-3525-z
4. De Angelis C, Drazen JM, Frizelle FA, Haug C, Hoey J, Horton R, et al. Clinical trial registration: a statement from the International Committee of Medical Journal Editors. N Engl J Med. 2004;351(12):1250-1251. https://doi.org/10.1056/NEJMe048225
5. Rivers E, Nguyen B, Havstad S, Ressler J, Muzzin A, Knoblich B, et al. Early goal-directed therapy in the treatment of severe sepsis and septic shock. N Engl J Med. 2001;345(19):1368-1377. https://doi.org/10.1056/NEJMoa010307
6. Angus DC, van der Poll T. Severe sepsis and septic shock. N Engl J Med. 2013;369(9):840-851. https://doi.org/10.1056/NEJMra1208623
7. Fan E, Del Sorbo L, Goligher EC, Hodgson CL, Munshi L, Walkey AJ, et al. An Official American Thoracic Society/European Society of Intensive Care Medicine/Society of Critical Care Medicine Clinical Practice Guideline: Mechanical Ventilation in Adult Patients with Acute Respiratory Distress Syndrome. Am J Respir Crit Care Med. 2017;195(9):1253-1263. https://doi.org/10.1164/rccm.201703-0548ST
8. Nolan JP, Sandroni C, Böttiger BW, Cariou A, Cronberg T, Friberg H, et al. European Resuscitation Council and European Society of Intensive Care Medicine guidelines 2021: post-resuscitation care. Intensive Care Med. 2021;47(4):369-421. https://doi.org/10.1007/s00134-021-06368-4
9. De Backer D, Aldecoa C, Njimi H, Vincent JL. Dopamine versus norepinephrine in the treatment of septic shock: a meta-analysis. Crit Care Med. 2012;40(3):725-730. https://doi.org/10.1097/CCM.0b013e31823778ee
10. Finfer S, Myburgh J, Bellomo R. Intravenous fluid therapy in critically ill adults. Nat Rev Nephrol. 2018;14(9):541-557. https://doi.org/10.1038/s41581-018-0044-0
11. Snilstveit B, Vojtkova M, Bhavsar A, Stevenson J, Gaarder M. Evidence & Gap Maps: A tool for promoting evidence informed policy and strategic research agendas. J Clin Epidemiol. 2016;79:120-129. https://doi.org/10.1016/j.jclinepi.2016.05.015
12. Peters MDJ, Godfrey CM, Khalil H, McInerney P, Parker D, Soares CB. Guidance for conducting systematic scoping reviews. Int J Evid Based Healthc. 2015;13(3):141-146. https://doi.org/10.1097/XEB.0000000000000050
13. Tricco AC, Lillie E, Zarin W, O'Brien KK, Colquhoun H, Levac D, et al. PRISMA Extension for Scoping Reviews (PRISMA-ScR): Checklist and Explanation. Ann Intern Med. 2018;169(7):467-473. https://doi.org/10.7326/M18-0850
14. Elliott JH, Synnot A, Turner T, Simmonds M, Akl EA, McDonald S, et al. Living systematic review: 1. Introduction-the why, what, when, and how. J Clin Epidemiol. 2017;91:23-30. https://doi.org/10.1016/j.jclinepi.2017.08.010
15. Peters MDJ, Marnie C, Tricco AC, Pollock D, Munn Z, Alexander L, et al. Updated methodological guidance for the conduct of scoping reviews. JBI Evid Synth. 2020;18(10):2119-2126. https://doi.org/10.11124/JBIES-20-00167
16. De Backer D, Deutschman CS, Hellman J, Myatra SN, Ostermann M, Prescott HC, et al. Surviving Sepsis Campaign Research Priorities 2023. Crit Care Med. 2024;52(2):268-296. https://doi.org/10.1097/CCM.0000000000006135
17. Monnet X, Shi R, Teboul JL. Prediction of fluid responsiveness. What's new? Ann Intensive Care. 2022;12(1):46. https://doi.org/10.1186/s13613-022-01022-8

---

## Tables

### Table 1. Characteristics of 27,498 registered ICU randomized controlled trials.

| Characteristic | n (%) |
|---|---|
| **Total studies (after deduplication)** | 27,498 |
| **Source (pre-deduplication)** | |
| ClinicalTrials.gov | 22,054 |
| PubMed (supplementary) | 5,971 |
| Duplicates removed | 527 |
| **Unique contributions** | |
| ClinicalTrials.gov only | 22,054 (80.2%) |
| PubMed only (after dedup) | 5,444 (19.8%) |
| **Hemodynamic outcomes** | |
| Studies with hemodynamic mentions | 11,960 (43.5%) |
| Studies with placebo arm | 6,204 (22.6%) |
| Studies with hemodynamic + placebo | 1,997 (7.3%) |
| Total hemodynamic mentions | 39,923 |
| Core hemodynamic mentions | 37,168 (93.1%) |
| Adjunct mentions | 2,755 (6.9%) |
| **Registration status** | |
| Completed | 10,999 (40.0%) |
| Inferred completed (PubMed) | 5,444 (19.8%) |
| Recruiting | 2,793 (10.2%) |
| Unknown | 3,738 (13.6%) |
| Terminated | 1,664 (6.1%) |
| Not yet recruiting | 1,224 (4.5%) |
| Withdrawn | 756 (2.7%) |
| Active, not recruiting | 631 (2.3%) |
| Enrolling by invitation | 142 (0.5%) |
| Suspended | 107 (0.4%) |
| **Trial phase** (ClinicalTrials.gov, n = 22,054) | |
| Not applicable | 12,396 (56.2%) |
| Phase 3 | 3,046 (13.8%) |
| Phase 4 | 2,532 (11.5%) |
| Phase 2 | 2,321 (10.5%) |
| Phase 2/3 | 737 (3.3%) |
| Phase 1 | 414 (1.9%) |
| Phase 1/2 | 410 (1.9%) |
| Early Phase 1 | 193 (0.9%) |
| **Masking** (ClinicalTrials.gov, n = 22,054) | |
| None (open-label) | 8,117 (36.8%) |
| Single | 4,534 (20.6%) |
| Double | 3,704 (16.8%) |
| Quadruple | 3,401 (15.4%) |
| Triple | 2,248 (10.2%) |
| Not reported | 50 (0.2%) |
| **Primary purpose** | |
| Treatment | 13,487 (49.0%) |
| Prevention | 3,875 (14.1%) |
| Supportive care | 1,953 (7.1%) |
| Other | 1,033 (3.8%) |
| Health services research | 519 (1.9%) |
| Diagnostic | 535 (1.9%) |
| Basic science | 311 (1.1%) |
| Screening/other/not reported | 5,785 (21.0%) |
| **Enrollment** (n = 21,229 with data) | |
| Median (IQR) | 100 (50-247) |
| Total planned participants | 20,370,084 |

Note: Trial phase and masking percentages use the ClinicalTrials.gov subset (n = 22,054) as denominator, as PubMed-inferred studies lack structured phase and masking data. Primary purpose and registration status percentages use the full dataset (n = 27,498) as denominator.

### Table 2. Geographic distribution of registered ICU RCTs (top 15 countries).

| Rank | Country | Studies | % of total |
|---|---|---|---|
| 1 | United States | 5,937 | 21.6% |
| 2 | France | 2,000 | 7.3% |
| 3 | China | 1,823 | 6.6% |
| 4 | Canada | 1,803 | 6.6% |
| 5 | Egypt | 1,775 | 6.5% |
| 6 | Germany | 1,388 | 5.0% |
| 7 | Spain | 1,282 | 4.7% |
| 8 | Italy | 1,269 | 4.6% |
| 9 | Turkey | 1,147 | 4.2% |
| 10 | United Kingdom | 1,138 | 4.1% |
| 11 | Brazil | 999 | 3.6% |
| 12 | India | 935 | 3.4% |
| 13 | Belgium | 825 | 3.0% |
| 14 | Netherlands | 809 | 2.9% |
| 15 | South Korea | 788 | 2.9% |
| | Total countries | 148 | |

Note: Studies may be registered in multiple countries; percentages do not sum to 100%.

### Table 3. Top 15 hemodynamic outcome keywords by study count.

| Keyword | Study count | Mention count | Placebo studies | Placebo % |
|---|---|---|---|---|
| Heart rate | 3,985 | 4,525 | 543 | 13.6% |
| Blood pressure | 3,920 | 4,820 | 744 | 19.0% |
| Systolic | 2,217 | 2,747 | 462 | 20.8% |
| Mean arterial pressure | 1,542 | 1,697 | 166 | 10.8% |
| Vasopressor | 1,370 | 1,670 | 258 | 18.8% |
| Lactate | 1,318 | 1,497 | 212 | 16.1% |
| Diastolic | 1,254 | 1,471 | 308 | 24.6% |
| HR (abbreviation) | 1,021 | 1,221 | 149 | 14.6% |
| MAP (abbreviation) | 1,003 | 1,213 | 126 | 12.6% |
| SOFA | 917 | 1,100 | 320 | 34.9% |
| Cardiac output | 828 | 910 | 108 | 13.0% |
| Ejection fraction | 721 | 837 | 113 | 15.7% |
| Norepinephrine | 679 | 806 | 122 | 18.0% |
| Cardiac index | 667 | 712 | 52 | 7.8% |
| Inotropic | 554 | 616 | 105 | 19.0% |

Note: SOFA is an ICU severity score adjunct, not a core hemodynamic parameter; it is included here for completeness. Raw keywords are shown; see S3 Table for normalized categories.

### Table 4. Hemodynamic parameters with sparse placebo-controlled evidence.

| Parameter | Total studies | Placebo studies | Placebo % | Category |
|---|---|---|---|---|
| Intrathoracic blood volume (ITBV) | 6 | 0 | 0.0% | Volume |
| Intrathoracic blood volume index (ITBVI) | 9 | 0 | 0.0% | Volume |
| Fluid challenge | 33 | 0 | 0.0% | Fluid |
| dP/dt | 2 | 1 | 50.0% | Contractility |
| DO2I | 13 | 1 | 7.7% | Oxygen delivery |
| Fluid responsiveness | 49 | 1 | 2.0% | Fluid |
| GEDV | 2 | 1 | 50.0% | Volume |
| RVEF | 22 | 1 | 4.5% | Cardiac function |
| GEDVI | 8 | 1 | 12.5% | Volume |
| CPO | 7 | 2 | 28.6% | Cardiac function |
| EVLW | 27 | 2 | 7.4% | Lung water |
| Global end-diastolic volume | 18 | 2 | 11.1% | Volume |
| Cardiac power output | 12 | 2 | 16.7% | Cardiac function |
| Base deficit | 49 | 3 | 6.1% | Perfusion |
| DO2 | 38 | 3 | 7.9% | Oxygen delivery |
| StO2 | 21 | 3 | 14.3% | Tissue oxygenation |
| Capillary refill time | 30 | 3 | 10.0% | Perfusion |
| ScvO2 | 51 | 4 | 7.8% | Venous oxygenation |

Note: Individual keyword-level counts shown. Parameters with <= 4 placebo studies included. Core hemodynamic parameters only (adjuncts excluded). Some keywords (e.g., "CVP" and "central venous pressure") map to the same normalized category; see S3 Table for aggregated normalized counts that combine related keywords.

---

## Figures

### Fig 1. Adapted PRISMA-ScR flow diagram.

ClinicalTrials.gov records identified: 22,054 | PubMed records identified: 5,971 | Duplicates removed: 527 | Total after deduplication: 27,498 | With hemodynamic outcomes: 11,960 | With placebo arms: 6,204 | With hemodynamic outcomes AND placebo arms: 1,997 | Excluded (no hemodynamic match): 15,538.

*Note: This is an adapted PRISMA-ScR flow for automated trial landscape mapping, not a standard PRISMA 2020 flow diagram. A PRISMA-ScR checklist is provided as S1 Table.*

### Fig 2. Temporal distribution of ICU RCT registrations by decade of start date.

1990s: 96 (0.4%) | 2000s: 2,400 (10.9%) | 2010s: 8,704 (39.5%) | 2020s: 10,802 (49.1%).

*Note: Based on 22,016 studies with reported start dates. Decades prior to 1990 (n = 14) omitted for clarity. The 2020s include registrations through February 2026.*

### Fig 3. Geographic distribution of registered ICU RCTs (top 15 countries).

*Bar chart showing study counts by country. See Table 2 for exact values.*

### Fig 4. Hemodynamic keyword signal map.

*Scatter plot of total study count (x-axis) versus placebo study count (y-axis) for each normalized hemodynamic keyword category. Keywords below the diagonal represent evidence gaps where placebo coverage is low relative to total study volume. See the interactive dashboard for dynamic exploration.*

---

## Supporting information

**S1 Table.** PRISMA-ScR checklist. Completed checklist mapping manuscript sections to PRISMA-ScR items.

**S2 File.** Search strategy configuration file (`ctgov_icu_placebo_strategy.json`). Contains full search queries, recall reference standard (21 NCT IDs with trial names), and classification rules.

**S3 Table.** Full list of 35 normalized hemodynamic keyword categories with study counts, mention counts, and placebo study counts (`S3_normalized_keyword_categories.csv`).

**S4 Table.** Classification validation sample (n = 200 mentions). Stratified random sample for independent scoring of hemodynamic keyword classification accuracy.

**S5 File.** Deduplication validation sample (100 pairs: 50 merged, 50 near-miss unmerged). For independent assessment of fuzzy title matching accuracy.

**S6 File.** Pipeline source code and interactive dashboard. Complete Python pipeline, configuration files, and HTML/JS/CSS dashboard for dynamic exploration.

---

## Acknowledgments

The author thanks the ClinicalTrials.gov and PubMed teams for maintaining publicly accessible registries and APIs that made this work possible.

## Author contributions (CRediT)

**Shahzaib Ahmad:** Conceptualization, Data curation, Formal analysis, Methodology, Software, Validation, Visualization, Writing -- original draft, Writing -- review & editing.

## Funding statement

The author received no specific funding for this work.

## Competing interests

The author declares no competing interests.

## Ethics statement

This study uses only publicly available trial registration metadata from ClinicalTrials.gov and PubMed article metadata. No individual patient data, protected health information, or restricted-access datasets were used. Ethical approval was not required as no human subjects research was conducted.

## Data availability statement

All data underlying the findings of this study are publicly available. Primary data were obtained from ClinicalTrials.gov (https://clinicaltrials.gov/data-api/about-api) and PubMed (https://www.ncbi.nlm.nih.gov/books/NBK25501/), both freely accessible without authentication. The complete derived dataset (CSV, Parquet, and JSON formats), pipeline source code, interactive dashboard, and validation samples are available at [ZENODO_DOI_PLACEHOLDER].

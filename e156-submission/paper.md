Mahmood Ahmad
Tahir Heart Institute
author@example.com

ICU Hemodynamic Trial Landscape: A Living Evidence Map

Can a browser-based living evidence map provide reviewer-auditable trial landscape coverage for intensive care hemodynamic research? We built a pipeline that fetches ICU randomized controlled trials from ClinicalTrials.gov, enriches records via seven adapters including PubMed, OpenAlex, and FAERS, and renders two interactive dashboards with evidence-gap visualizations and PRISMA-style flow diagrams. The system uses keyword normalization, placebo-arm classification, deduplication validation, and incremental merge logic with a living update log recording every refresh cycle and its provenance metadata. Against a 21-trial reference standard for hemodynamic ICU interventions, the pipeline achieved sensitivity of 100 percent (95% CI 83.9-100) with all trials correctly classified. Stratified keyword-validation samples and deduplication checks confirmed consistent categorization across intervention classes, phases, and enrollment status. The platform serves as a descriptive evidence-mapping tool making registration coverage and signal gaps inspectable without requiring users to engage with code. However, the limitation of registry-only data means that unpublished results and non-registered trials remain invisible to this approach.

Outside Notes

Type: methods
Primary estimand: Sensitivity
App: ICU Trial Landscape v1.0
Data: ClinicalTrials.gov ICU RCTs, 21-trial reference standard
Code: https://github.com/mahmood726-cyber/shahzaib-icu-landscape
Version: 1.0
Validation: DRAFT

References

1. Page MJ, McKenzie JE, Bossuyt PM, et al. The PRISMA 2020 statement: an updated guideline for reporting systematic reviews. BMJ. 2021;372:n71.
2. Moher D, Liberati A, Tetzlaff J, Altman DG. Preferred reporting items for systematic reviews and meta-analyses: the PRISMA statement. PLoS Med. 2009;6(7):e1000097.
3. Borenstein M, Hedges LV, Higgins JPT, Rothstein HR. Introduction to Meta-Analysis. 2nd ed. Wiley; 2021.

AI Disclosure

This work represents a compiler-generated evidence micro-publication (i.e., a structured, pipeline-based synthesis output). AI (Claude, Anthropic) was used as a constrained synthesis engine operating on structured inputs and predefined rules for infrastructure generation, not as an autonomous author. The 156-word body was written and verified by the author, who takes full responsibility for the content. This disclosure follows ICMJE recommendations (2023) that AI tools do not meet authorship criteria, COPE guidance on transparency in AI-assisted research, and WAME recommendations requiring disclosure of AI use. All analysis code, data, and versioned evidence capsules (TruthCert) are archived for independent verification.

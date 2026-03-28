Mahmood Ahmad
Tahir Heart Institute
mahmood.ahmad2@nhs.net

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

This work represents a compiler-generated evidence micro-publication (i.e., a structured, pipeline-based synthesis output). AI is used as a constrained synthesis engine operating on structured inputs and predefined rules, rather than as an autonomous author. Deterministic components of the pipeline, together with versioned, reproducible evidence capsules (TruthCert), are designed to support transparent and auditable outputs. All results and text were reviewed and verified by the author, who takes full responsibility for the content. The workflow operationalises key transparency and reporting principles consistent with CONSORT-AI/SPIRIT-AI, including explicit input specification, predefined schemas, logged human-AI interaction, and reproducible outputs.

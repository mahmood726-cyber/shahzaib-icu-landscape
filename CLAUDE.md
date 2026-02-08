# CLAUDE.md — Shahzaib ICU Living Evidence Map

## Project Overview
CT.gov ICU RCT living evidence map: **fetch → enrich → build → dashboard** pipeline. Fetches clinical trials from ClinicalTrials.gov, enriches with PubMed/FAERS/OpenAlex data, builds a structured evidence map, and renders an interactive dashboard.

## Pipeline Steps
1. **Fetch**: CT.gov API search for ICU RCTs → raw JSON
2. **Enrich**: 8 sources (PubMed, FAERS, OpenAlex, etc.) → enriched records
3. **Build**: Aggregate, categorize, validate → structured evidence map
4. **Dashboard**: Interactive HTML with filters, bar charts, PRISMA flow

## Critical Warnings
- **PubMed efetch XML** contains `<!DOCTYPE PubmedArticleSet>` — never block it
- **`datetime.fromisoformat()`** on Python <3.11 cannot parse `+00:00` TZ suffix — strip it
- **Unicode apostrophes** (U+2019 RIGHT SINGLE QUOTATION) common in CT.gov — normalize before matching
- **FAERS delimiter collision**: use inner `::` / outer `;;` (NOT `|` for both)
- **`_csv_safe`** must NOT include `-` in medical data (corrupts "-0.5 mmHg" etc.)
- **`_csv_safe`**: early return must not skip newline check — use single-pass
- **`_pct_change(0, N)`** should be None/bootstrap, not 100% "major drift"
- **`MIN(fetched_utc)`** on append-only log = permanently anchored to oldest record
- **HR negative-context regex**: `0\.\d` → `\d+\.\d` (catches HR>=1.0)
- **NON_HEMODYNAMIC_ADJUNCTS**: severity scores, ventilation, metabolic must be separated from core hemo totals
- **`is_oa` CSV**: must output lowercase `true/false` (not Python `True/False`)
- **`normalize_keyword`**: must return "Unmapped" on no-match (not raw keyword)
- **Bar chart sort/display metric mismatch**: sort must use active barMetric

## Do NOT
- Block PubMed XML DOCTYPE declarations
- Use `|` as delimiter inside fields that may contain pipes
- Include `-` in CSV sanitization patterns (medical data contains negative values)
- Hardcode phase names (phase_1/phase_2) — iterate dynamically

## Workflow Rules (from usage insights)

### Data Integrity
Never fabricate or hallucinate identifiers (NCT IDs, DOIs, trial names, PMIDs). If you don't have the real identifier, say so and ask the user to provide it. Always verify identifiers against existing data files before using them in configs or gold standards.

### Multi-Persona Reviews
When running multi-persona reviews, run agents sequentially (not in parallel) to avoid rate limits and empty agent outputs. If an agent returns empty output, immediately retry it before moving on. Never launch more than 2 sub-agents simultaneously.

### Fix Completeness
When asked to "fix all issues", fix ALL identified issues in a single pass — do not stop partway. After applying fixes, re-run the relevant tests/validation before reporting completion. If fixes introduce new failures, fix those too before declaring done.

### Scope Discipline
Stay focused on the specific files and scope the user requests. Do not survey or analyze files outside the stated scope. When editing files, triple-check you are editing the correct file path — never edit a stale copy or wrong directory.

### Regression Prevention
Before applying optimization changes to extraction or analysis pipelines, save a snapshot of current accuracy metrics. After each change, compare against the snapshot. If any trial/metric regresses by more than 2%, immediately rollback and try a different approach. Never apply aggressive heuristics without isolated testing first.

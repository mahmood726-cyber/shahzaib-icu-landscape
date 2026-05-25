# ICU Hemodynamic Trial Landscape

A browser-based **living evidence map** for intensive-care hemodynamic research. Fetches RCTs from ClinicalTrials.gov, enriches via seven adapters (PubMed, OpenAlex, FAERS, and four others), and renders interactive dashboards with evidence-gap visualisations and PRISMA-style flow diagrams.

**Live dashboard:** <https://mahmood726-cyber.github.io/shahzaib-icu-landscape/>

## What it does

- Pulls ICU RCTs from CT.gov (AACT mirror).
- Enriches each trial with PubMed citations, OpenAlex bibliometric signal, FAERS adverse-event linkage.
- Normalises keywords, classifies placebo arms, deduplicates against the reference set, validates the merge incrementally.
- Maintains a **living update log** recording every refresh cycle's provenance metadata.
- Achieves 100% sensitivity (95% CI 83.9-100) against a 21-trial reference standard for hemodynamic ICU interventions.

## Install

```bash
pip install -r requirements.txt   # if present
```

The pipeline is mostly stdlib + `requests` + `pandas`. R is **not** required.

## Run the dashboard

Open `index.html` in any modern browser. The dashboard reads `data/living_map.json` (pre-computed).

For local development:

```bash
python -m http.server 8000
# then open http://localhost:8000/
```

## Rebuild the living map

```bash
python build_living_map.py
```

This fetches fresh CT.gov + enrichment data and writes `data/living_map.json` plus the update-log entry. Per `~/.claude/rules/lessons.md` "CT.gov / AACT Queries": the AACT snapshot may live on `C:`, `D:`, or `F:` — use config / candidate-root discovery, don't hardcode.

## Test

```bash
python -m pytest -q
```

The suite under `dashboard/tests/` and `tests/` validates:
- Keyword normalisation and placebo classification rules.
- Deduplication-invariant merge logic.
- Reference-set sensitivity (the 21-trial benchmark).
- Dashboard rendering against the pre-computed JSON.

## Repo layout

| Path | Purpose |
|---|---|
| `index.html` | landing page |
| `dashboard/` | the interactive dashboard |
| `build_living_map.py` | top-level pipeline orchestrator |
| `data/` | pre-computed JSON used by the dashboards |
| `tests/`, `dashboard/tests/` | pytest unit + integration tests |
| `F1000_Software_Tool_Article.md` | F1000 submission manuscript |
| `cover_letter_plos_one.md` | PLOS ONE cover letter (alt submission) |
| `E156-PROTOCOL.md` | project metadata (E156 entry #152) |

## Limitations

Registry-only coverage: unpublished results and non-registered trials remain invisible to this approach.

## License

See `LICENSE` (MIT).

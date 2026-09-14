# Banyan M&A Screening

Agentic market-research and target-screening pipeline for **Banyan Software**, a
buy-and-hold-forever acquirer of profitable, founder/family-owned vertical B2B
software companies. It discovers software companies, scores them against Banyan's
acquisition thesis (and a contrasting growth thesis), triangulates the candidate
universe across independent discovery passes, and produces analyst-ready
deliverables — all from **public web + official registries only (no paid data
providers)**.

## Repository layout

```
banyan-ma-research/
├── banyan_screen/        # Core scoring package (deterministic, LLM-separate)
│   ├── models.py          # Criterion/Tier enums, Company/ScoredCompany dataclasses
│   ├── config.py          # RubricConfig (weights, gates, thresholds) + from_yaml
│   ├── rubric_engine.py   # composite → confidence-discount → gates → tier
│   ├── ingest.py          # record → per-criterion CriterionScores (both rubrics)
│   ├── input_loader.py    # CSV/XLSX seed loader → records
│   ├── report.py          # HTML dashboard + CSV + JSON writer
│   ├── run.py             # CLI: score records under both rubrics, rank, curate
│   └── policy.py          # IAM enforcement layer (RBAC + field classification)
├── config.yaml            # Banyan buy-and-hold rubric  (loaded by relative path)
├── config.growth.yaml     # Growth/scaling rubric
├── tests/                 # pytest suite (47 tests)
├── data/
│   ├── records/           # Input company records (12 vertical JSON files, ~333 rows)
│   ├── screen/            # Screen outputs used as pipeline inputs (results.json, ranked.csv)
│   └── research/          # Curated lists, intermediate + raw research data
│       └── codex_research/  # Verbatim codex web-research per company (audit trail)
├── analysis/              # Research-pipeline scripts (post-processing / reporting)
│   ├── segment.py           # Roll 226 micro-verticals → 14 macro-segments
│   ├── build_market_report.py
│   ├── build_dossiers.py    # IAM-gated lead dossiers + pitches (fails closed on role)
│   ├── build_crossmatch.py  # 3-way discovery triangulation
│   ├── validate_grounding.py# Grounding check: deliverables vs raw codex research
│   ├── osint_wikidata.py    # OSINT firmographic enrichment (Wikidata)
│   ├── build_intelligence_hub.py    # One-stop hub (top-250 + dossiers + market + playbook)
│   ├── build_access_architecture.py # Layered IAM/data-access page (live role lens)
│   ├── templates/           # HTML templates the two builders inject data into
│   └── workflows/           # Multi-agent orchestration scripts (*.js, Claude Code Workflow tool)
├── reports/               # Self-contained HTML deliverables (open in a browser)
├── skills/                # banyan-sales-pitch (reusable Claude Code skill)
└── docs/                  # Design spec, implementation plan, HANDOFF.md
```

## Quick start

```bash
pip install -r requirements.txt

# Run the full test suite (47 tests)
python -m pytest -q

# Score the record set under both rubrics, curate to top 250, write deliverables
python -m banyan_screen.run data/records/*.json --top=250 --out=reports

# Regenerate the analysis deliverables (read data/, write reports/)
python analysis/segment.py
python analysis/build_market_report.py
python analysis/build_crossmatch.py
python analysis/build_dossiers.py                       # best-of-both dossiers
python analysis/build_dossiers.py data/research/raw_dossiers_banyan.json \
       data/research/top25_banyan.json reports/banyan_dossiers_pitches.html
python analysis/validate_grounding.py                   # faithfulness check
python analysis/build_intelligence_hub.py               # reports/intelligence_hub.html
python analysis/build_access_architecture.py            # reports/access_architecture.html
```

Scripts anchor on `ROOT = __file__.parent.parent`, so they must stay one level
below the project root (`analysis/`). `config.yaml`/`config.growth.yaml` are
loaded by **relative path** from `run.py` and the tests, so they stay at the root.

## Key deliverables (in `reports/`)

| File | What |
|------|------|
| `intelligence_hub.html` | **One-stop hub**: top-250 (both rubrics, per-criterion rationale, revenue/profitability signals), 25 dossiers + pitches, market map, outreach playbook, method & QC |
| `access_architecture.html` | Layered data-access architecture (identity → classification → PDP → enforcement → consumers → audit), role × tier matrix, live role lens from `policy.py`, Claude-user guidance |
| `dashboard.html` | Top-250 dual-rubric screen |
| `market_synthesis.html` | 14-segment market map, shortlist, whitespace, competing consolidators |
| `banyan_dossiers_pitches.html` | Banyan-rubric top-25 dossiers + outreach pitches (**18 SEND**) |
| `dossiers_pitches.html` | Best-of-both top-25 (contrast: 2 SEND) |
| `crossmatch.html` | 3-way discovery triangulation (602 union, 90 corroborated, 176 strong net-new) |
| `iam_hierarchy.html` | Conceptual IAM model (RBAC + ABAC + data classification) |

## Design notes

- **Deterministic core, separate from the LLM.** Extractors propose per-criterion
  scores *with confidence*; `rubric_engine` alone computes composite →
  confidence-discount → gates → tier. Every result carries an audit `rationale`.
- **Confidence discounting** caps private companies whose financials can't be
  verified from public web at tier C — so tier C ≠ bad fit.
- **IAM enforcement** (`policy.py`) filters output by consumer role: Data Science
  gets no PII/financials (aggregate-only), Finance gets financials but no PII,
  Sales/BD gets masked PII + pitches, Leadership sees deal-intent masked.
- **No paid data.** Discovery uses codex `web_search`; verification uses official
  registries (UK Companies House, EU registries, SEC EDGAR) and Wikidata.

See `docs/HANDOFF.md` for the full session narrative, decisions, validation
results, and next steps. See `docs/HLD.md` for the system-level architecture
(the idea, subsystems, data flow, execution model) and `docs/LLD.md` for
module-level design (algorithms, schemas, class/sequence diagrams). See
`docs/TOOLING_LOG.md` for exactly which skills, MCP servers, plugins, and
hooks were used to build this project.

# Banyan M&A Screening — Slice 1 Design Spec

**Date:** 2026-09-11
**Status:** Draft for review
**Author:** Claude (Opus 4.8) + pahmed
**Scope of this spec:** Slice 1 only — *enrich-and-score over an existing target list*. The full four-stage pipeline is described in "System context" for orientation; only Slice 1 is specified for implementation here. Later slices get their own spec → plan → build cycles.

---

## 1. Goal

Given a list of software companies the user already has, produce a **ranked, auditable pipeline** of how well each fits **Banyan Software's acquisition thesis**, using only public web + official registry data (no paid providers). Every score must be traceable to a source and carry a confidence level.

**Non-goals (Slice 1):** autonomous discovery of new companies (Slice 3), sector/landscape mapping (Slice 3), full diligence dossiers (Slice 2), interactive conversational layer (Slice 4).

---

## 2. System context (full pipeline — for orientation only)

Staged pipeline with a deterministic scoring core (Approach 1, approved):

```
S1 Landscape ─► S2 Sourcing ─► S3 Screening/Scoring ─► S4 Dossier
 (Slice 3)       (Slice 3       (Slice 1 = THIS SPEC)    (Slice 2)
                  discovery;
                  Slice 1 uses
                  list ingest
                  only)
```

Slice 1 exercises a **list-ingest subset of S2** + **all of S3** + **reporting**.

### The Banyan rubric (verified criteria — the scoring target)

From banyansoftware.com/faq + homepage (2026-09-11, self-reported; corroborate before production use):

| Criterion | Banyan requirement | Slice-1 weight (default, tunable) |
|-----------|--------------------|-----------------------------------|
| Recurring-revenue intensity | "high contribution of recurring revenue" | 0.25 |
| Profitability / positive cash flow | required; not a turnaround buyer | 0.20 (hard-fail gate on strong loss evidence) |
| Revenue ≥ $2M band | ">$2M annual revenue" | 0.10 (gate: below → deprioritize) |
| Vertical/enterprise B2B niche leadership | "lead a clearly defined niche" | 0.20 |
| Customer retention | "high customer retention" | 0.10 |
| Ownership fit | founder/family, "permanent home", not recently PE/VC-recapped | 0.10 |
| Team stability | "engaged team with low turnover" | 0.05 |

Weights live in `config.yaml`. They are defaults, explicitly presented as tunable and defensible, not ground truth.

---

## 3. Slice 1 architecture

### 3.1 Components (each a focused module)

| Module | Responsibility | Reuse |
|--------|----------------|-------|
| `config` (YAML + loader) | rubric weights, column mapping, thresholds, concurrency, cache/output dirs, Cosmos model id | new |
| `models.py` | `Company`, `Signal{value, source_url, method, confidence}`, `CriterionScore`, `Tier` | new |
| `input_loader.py` | read CSV/XLSX list → `Company` stubs; validate/normalize | reuse `merchant_analyzer/utils/file_handlers.py` |
| `domain_resolver.py` | fill missing domain via web_search + URL validation | reuse `merchant_analyzer/modules/url_validator.py` |
| `site_scraper.py` | fetch homepage / pricing / about / careers pages | reuse `merchant_analyzer/main.py` Playwright+aiohttp+BS4 scaffolding |
| `registry_client.py` | UK Companies House filed accounts (revenue/profit where filed) | new (SEC EDGAR optional, likely deferred) |
| `directory_client.py` | G2/Capterra category + review-volume/recency/rating signals | new |
| `extractors/` | one extractor per criterion signal (see 3.3) | partial reuse of `revenue_estimator.py`, `competitive_analysis.py` |
| `rubric_engine.py` | deterministic: signals → per-criterion 0–1 + confidence → gates → weighted composite → tier | new |
| `llm_client.py` | Cosmos.AI gateway wrapper; used only for extraction/classification | pattern from `gmah-agent` |
| `cache.py` | raw-fetch cache keyed by URL (avoid re-hitting sites; reproducibility) | new |
| `reporter.py` | ranked HTML dashboard + per-company JSON + CSV | reuse HTML-artifact patterns in `~/html-effectiveness/` |
| `orchestrator.py` / CLI | run batch or score-one; concurrency; per-company isolation | reuse async-batch pattern from `merchant_analyzer/main.py` |

### 3.2 Data flow

```
list.(csv|xlsx)
  └─► input_loader ──► [Company stub]…
        └─► domain_resolver (if domain missing)
              └─► site_scraper ──► cached raw pages
                    └─► registry_client (UK entities) ──► filed financials
                          └─► directory_client ──► review signals
                                └─► extractors ──► Signal{…, confidence, source_url}
                                      └─► rubric_engine ──► CriterionScore[], composite, Tier
                                            └─► reporter ──► dashboard.html + company_<id>.json + ranked.csv
```

### 3.3 Signal extractors (Slice 1)

Each returns a `Signal` with `value`, `source_url`, `method`, `confidence`. The LLM proposes; it never scores.

- **recurring_revenue_proxy** — from pricing page + product copy: subscription vs one-time, plan cadence, contract/renewal language. LLM extraction, confidence keyed to signal strength.
- **profitability_proxy** — UK: Companies House filed P&L (high confidence). Else: low-confidence inference from age/headcount/funding posture.
- **revenue_band_estimator** — Companies House turnover where filed; else heuristic band from headcount/traffic (reuse `revenue_estimator.py`), low-to-medium confidence.
- **vertical_niche_classifier** — LLM classifies vertical, B2B/enterprise flag, and niche-leadership signal from positioning + review categories.
- **retention_proxy** — review volume, recency cadence, rating trend as a retention proxy. **NOTE (verified 2026-09-11): direct G2 fetch returns HTTP 403 (anti-bot).** Source retention signals from web-search snippets / Capterra instead; keep confidence low. Do not attempt to scrape G2 directly.
- **ownership_detector** — founder/family-led vs recently PE/VC-recapped, from public about/news/funding-event snippets (LLM over search results).
- **team_stability_proxy** — LinkedIn public headcount trend + tenure. **Known-weak** (ToS + blocking); emit low confidence or `insufficient_data`.

### 3.4 Scoring (deterministic)

1. Each extractor → per-criterion score in [0,1] with confidence in [0,1].
2. **Gates:** strong evidence of losses → hard-fail (Tier D / rejected); revenue clearly < $2M → deprioritize.
3. **Composite** = Σ(weightᵢ × scoreᵢ), then **discounted by overall confidence** (mean signal confidence).
4. **Tier:** A / B / C thresholds + explicit **"insufficient data"** bucket when confidence coverage is too thin to rank honestly.
5. All inputs, weights, gates, and the arithmetic are logged per company for auditability.

---

## 4. Input contract (**needs your confirmation**)

Slice 1 reads a CSV or XLSX. Minimum viable schema:

| Column | Required | Notes |
|--------|----------|-------|
| `company_name` | yes | |
| `domain` / `website` | no | resolved via search if absent |
| `country` | no | drives registry choice (UK → Companies House) |
| `notes` / any extra | no | carried through to output |

Column names are mapped in `config.yaml`, so your real headers don't have to match. **Open input:** point me at the actual file (path + a header row) and confirm approximate row count, so I size concurrency/caching and confirm the mapping. Until then the spec assumes the schema above.

---

## 5. Outputs

- `dashboard.html` — ranked, sortable/filterable table (tier, composite, per-criterion, confidence), clean neutral theme (external subject — **not** PayPal-branded).
- `company_<id>.json` — full record incl. every signal with source_url + confidence.
- `ranked.csv` — flat export for CRM/handoff.
- (Markdown/HTML per-company dossiers = Slice 2.)

---

## 6. Error handling & reproducibility

- tenacity retries on fetch/registry; exponential backoff on rate limits.
- **Per-company isolation** — one failing target never aborts the batch; failures recorded with reason.
- Missing signal → lower confidence, not a crash.
- Raw-fetch cache → reproducible re-runs and cheap incremental updates.
- Every LLM call logged (prompt hash, model, response) for audit.

---

## 7. Testing

- **Rubric engine:** deterministic golden tests (fixed signal sets → expected tier/score). Highest priority — this is the defensible core.
- **Extractors:** fixture-HTML unit tests (saved pricing/about pages → expected signals).
- **Golden company set:** 5–10 known companies with expected tiers as a regression check.
- **Dry-run mode:** mocked LLM + cached fixtures, no network — for CI-style local runs.
- Tests run directly / via `pytest` inside this project's own `tests/` (workspace has no shared runner).

---

## 8. Runtime & environment

- **Language:** Python, standalone project at `~/banyan-ma-research/`.
- **LLM:** Cosmos.AI gateway (pattern from `gmah-agent`); model id in config.
- **CLI:** `python -m banyan_screen run --input <list> --config config.yaml --output out/`; `... score-one --company "<name>"`.

---

## 9. Risks / open questions

**Feasibility spike run 2026-09-11 (results folded in):**

1. **Network egress — VERIFIED OK:** banyansoftware.com HTTP 200, Companies House API HTTP 401 (reachable, needs free key), SEC EDGAR HTTP 200. Target-site scraping + registry access work through the sandbox proxy.
2. **G2 direct scraping — VERIFIED BLOCKED:** HTTP 403 (anti-bot). Retention proxy must use search snippets / Capterra and stay low-confidence. LinkedIn (team stability) likely the same → low-confidence or `insufficient_data`. Do not over-promise these two criteria.
3. **Cosmos gateway — VERIFIED READY:** `COSMOSAI_API_KEY` + `ANTHROPIC_BASE_URL` already set in env; reuse `gmah-agent/main.py` pattern. First live call still to be confirmed during build.
4. **Recurring-revenue proxy accuracy:** Banyan's hardest gate is the noisiest to infer from public pages — expect medium confidence at best without filed accounts.
5. **Companies House coverage:** UK only; US/EU private targets have far weaker financial signal. Requires a free CH API key (registration).
6. **Banyan figures** are self-reported (unverified this session) — fine for a rubric, flag before any external use.

---

## 10. Build order after this spec

**Reprioritized 2026-09-11 (user has no existing list → discovery-first):**

- **Build 1 — Scoring core (common to all paths):** `models.py`, `config.yaml`, `rubric_engine.py`, built test-first. List-independent; needed by both discovery and enrichment. **← starting here.**
- **Build 2 — Discovery + enrichment:** promote autonomous discovery (was Slice 3) ahead of list-ingest — S2 discovery queries + `site_scraper` + `registry_client` + extractors feeding the core. (List-ingest path remains available for later if a list appears.)
- **Build 3 — Dossiers (S4)** for top-tier candidates.
- **Build 4 — Landscape mapping (S1)** and the interactive re-run layer.

Each build gets its own implementation plan.

# HANDOFF — Banyan Software M&A Screening

**Repo:** `~/Market-Research-Intelligence/` (github.com/iam-pattan/Market-Research-Intelligence) · **Last updated:** 2026-09-14 · **Git:** committed on `main`; workspace policy = commit only when asked.
This is the authoritative session handoff. Deep chronological detail lives in the auto-memory `~/.claude/projects/-Users-pahmed/memory/project_banyan_ma_research.md`; the design/plan live in `docs/superpowers/`. **Architecture:** see `docs/HLD.md` (system-level) and `docs/LLD.md` (module-level). **Tooling used to build this:** see `docs/TOOLING_LOG.md`.

---

## 1. Objective

Build a working agentic market-research + target-screening solution for **Banyan Software** — a buy-and-hold-**forever** acquirer (founded 2016; self-reported "120+ acquired, 0 sold"; Constellation/Valsoft archetype) of **profitable, founder/family-owned, high-recurring-revenue vertical B2B software niche leaders (~$2M–$100M revenue)**. Discover companies, score them against Banyan's thesis, triangulate the universe, produce analyst-ready deliverables, and enforce role-based access on all output.

## 2. Hard constraints (carry these forward)

- **Public web + official registries only — NO paid data providers** (no PitchBook/Crunchbase/Grata). User has no existing list → discovery-first.
- **Private-company financials are mostly unverifiable from public web** → the screen confidence-discounts them (most genuine targets land at **tier C; C ≠ bad fit**). Only registries with *filed accounts* (UK Companies House, EU) give real private revenue.
- **Discovery engine = codex `web_search`** (model `gpt-5.6-sol`, ChatGPT-authed, no API key). Must run **FOREGROUND, sandbox OFF** (`dangerouslyDisableSandbox: true`). WebSearch/firecrawl/perplexity are all blocked/auth-walled here.
- **Sandbox gotchas:** `/tmp`→use `$TMPDIR`; GUI `open`, PyPI installs, and most `.claude/` writes need sandbox off; `config.yaml` is loaded by *relative path* (tests + `run.py`) so it must stay at repo root.

## 3. Architecture

Deterministic scoring core **separate from the LLM**: extractors propose per-criterion `CriterionScore`s *with confidence*; `rubric_engine` alone computes `composite → confidence-discount → gates → tier`. Confidence discount: `adjusted = composite × (floor + (1−floor)×overall_conf)`, floor 0.5. Gates: loss→REJECTED, rev<$2M→cap C, thin coverage→INSUFFICIENT_DATA. Dual rubric: `config.yaml` (Banyan) + `config.growth.yaml` (growth). Every score carries an audit `rationale`.

**IAM enforcement layer** (`banyan_screen/policy.py`) — a real filter on output, two layers:
- Field classification (`classify`): 5 tiers PUBLIC→INTERNAL→CONFIDENTIAL_FINANCIAL→RESTRICTED_PII→RESTRICTED_MNPI; unknown fields fail-closed to CONFIDENTIAL_FINANCIAL.
- `enforce`/`guard(role, payload)`: drops disallowed tiers, masks masked tiers; **Data Science = aggregate-only (per-record refused, never PII/financials)**; Finance = financials, no PII/MNPI; Sales/BD = masked PII + pitch; Leadership = MNPI, PII+financials masked.
- Coarse RBAC `pitch_visible(role)` (Sales/BD only) gates the outreach narrative; `build_dossiers.py` calls it and **fails closed** at build time.

## 4. What was built (the full arc)

1. **Screen** — 12 codex vertical-discovery batches → `data/records/*.json` (~333 rows). `banyan_screen.run` dual-scores + curates → top-250 (`data/screen/results.json`, `reports/dashboard.html`).
2. **IAM model** — conceptual RBAC/ABAC/classification (`reports/iam_hierarchy.html`) + the enforcing `policy.py` (10 tests).
3. **Pitch skill** — `skills/banyan-sales-pitch/` (thesis-branched, high-hit-rate rules, MNPI hygiene, Sales/BD access gate).
4. **Deep dossiers + pitches** — 50-agent workflow per list → structured dossier + thesis-appropriate pitch.
5. **Market synthesis** — 226 micro-verticals rolled to **14 macro-segments** (`analysis/segment.py`); 29-agent workflow → `reports/market_synthesis.html`.
6. **Triangulation** — three independent discovery passes (vertical / acquirer-adjacency / OSINT) cross-matched → `reports/crossmatch.html`.
7. **Validation** — two `/validation-loop:validate` QC rounds + a grounding check against raw codex research.

## 5. Key results & decisions

- **Rubric choice is decisive for outreach.** Top-25 by *best-of-both* rubrics = only **2 SEND** (dominated by VC-backed >$100M AI/infra non-targets). Top-25 by the **Banyan rubric = 18 SEND** — the actionable acquisition list (`reports/banyan_dossiers_pitches.html`). This confirmed a repeatedly-raised anti-sycophancy flag.
- **Best hunting grounds** (market synthesis): Education (K-12 SIS, highest verified fit density), Manufacturing/Industrial, Construction/Field-Service, Healthcare practice-mgmt, the *boring* Legal tail, Real Estate/Property.
- **Banyan's true competitors are permanent-hold consolidators** — Constellation (Volaris/Harris/Jonas/Vela/Topicus), Valsoft, Everfield/Main Capital — **not** mega-PE.
- **Triangulation:** 602-company union · **90 corroborated** (≥2 passes) · **176 strong net-new** (founder-owned or filed financials, non-PE/VC — e.g. Bromcom, CDL Group, Open Dental, Planning Center, GIRO, Maptek, EU registry names) · **11 false "founder-owned" caught & excluded** (Vagaro=PE, Agiloft=FTV, Tripleseat=Vista, + VC cluster).
- **OSINT gave real filed financials** for private EU/UK targets (Bromcom £38.15M/£4.3M PBT, CDL £66.8M/£10.3M, Eurécia €16.6M/€1.88M) — higher confidence than tier-C web estimates.

## 6. Validation results

- **QC round 1:** REVIEW 65.9 (GLM 74.6 / Kimi 57.2). **Round 2 (after fixes):** REVIEW 66.9 (GLM **81.0** / Kimi 52.8; judges diverged 28.2pts → low-confidence). Fixes: cross-match PE-in-strong bucket bug; classifier hardened to use authoritative `is_founder_owned`; runtime IAM gate added to `build_dossiers.py`; test-count wording (10 policy / 46 suite); ownership stat corrected. Pushed back with evidence on `gpt-5.6-sol` (verified working) and "tests unverified" (re-ran, 46 passed).
- **Grounding check** (`analysis/validate_grounding.py` → `data/research/grounding_validation.json`): **98.6% (409/415)** of Banyan-25 dossier facts appear in the paired raw codex research; all 6 flags were extractor false-positives, not hallucinations → synthesis is faithful. Caught one cross-pass name discrepancy (QT9 founder "Brant" grounded vs OSINT-pass "Brian Coleman" unreliable).
- **Reorg verification (this session):** after the cleanup below, `pytest` (46 passed) and every Python builder re-ran cleanly at the new paths.

## 7. Repository cleanup (this session)

Reorganized from a flat `leads/` grab-bag into an industry-standard layout (see `README.md`): `analysis/` (scripts) + `analysis/workflows/`, `data/{records,screen,research}`, `reports/` (all HTML), config at root. Removed junk (`__pycache__`, `.pytest_cache`, `.DS_Store`, `.firecrawl`, empty stray files). Rewrote the 6 pipeline scripts' hardcoded paths to centralized constants; added `requirements.txt`, proper `.gitignore`, updated `pyproject.toml` (added pandas/openpyxl) and `README.md`. The orphaned early hospitality-leads table was kept as `data/research/orphaned_hospitality_leads.md`.

## 7b. Consolidated deliverables (2026-09-14 session)

Two one-stop HTML pages, published as Claude artifacts and regenerable from `analysis/`:

- **`reports/intelligence_hub.html`** (`build_intelligence_hub.py` + `templates/intelligence_hub.html`) — top-250 in the curated best-of-both order (Banyan score sortable, per user decision), joined to the raw record the screen actually scored (`run.dedup()` rule), per-criterion rationale, revenue estimate + confidence, profitability *signal* (no margin/profit numbers exist for private targets — stated honestly), 25 dossiers + pitches, 14-segment market map, the pitch skill verbatim, method & QC. Full unfiltered data — Leadership/tech-lead audience; share accordingly.
- **`reports/access_architecture.html`** (`build_access_architecture.py` + template) — six-layer IAM design (identity → classification → PDP → PEP → consumers → audit), role × tier matrix and a **live role lens computed by the real `policy.py`** on a synthetic record, plus the answer to "what do Claude users need": SSO identity + an MCP/API enforcement point running `guard()` *before* data enters the model; nothing inside Claude.
- **QC:** `analysis/qc_consolidated_pages.py` (re-derives every figure on both pages from data/ and policy.py; exits non-zero on mismatch) + `validation-loop:qc-reviewer` second-model review (verdict REVIEW → all findings fixed: wrong duplicate-domain record join for 4 top-40 rows, overclaiming tier copy, tooltip HTML sink, hardcoded test counts). `validation-loop:validate` misfired (stale session marker) — run the reviewer agent directly instead.
- **Policy fix:** the lens exposed that `enforce()` filed pitch narrative under the Confidential default (shown to Finance, dropped for Sales — opposite of `pitch_visible()`). `policy.py` now gates `_PITCH_KEYS` through `pitch_visible()` inside `enforce()` (PII/MNPI patterns still win; narrative dicts keep copy but mask/drop contacts and deal state). A second `/validate` round also found `classify('recurring_revenue')` falling to Confidential because `revenue` matched first — fixed. Tests: `tests/test_policy.py` (13) + `tests/test_builders.py` (4); suite = 53.

## 8. Outstanding / next steps (none blocking)

1. **Score the 176 strong net-new** through `banyan_screen` — highest value. Convert `data/research/crossmatch.json` net-new entries into records and run `python -m banyan_screen.run`, merging them into the ranked universe. Pass 2/3 surfaced real founder-owned targets pass 1 missed.
2. Deeper QC: only the 10 policy tests were read line-by-line by the judge; the other 36 pass but weren't independently inspected.
3. Map the conceptual IAM model to real infrastructure (BQ RLS + policy tags / cloud IAM + IdP / OPA-Cedar) if this goes to production.
4. Optionally `git init` and commit (not done — workspace policy).

## 9. Suggested skills (Claude Code, call via the Skill tool)

- **`workflow-authoring`** — before resuming/authoring any multi-agent Workflow (scripts in `analysis/workflows/`).
- **`ai-hub-web-search:codex-websearch`** — the discovery engine, for more sourcing.
- **`banyan-sales-pitch`** — the project's own pitch skill (in `skills/`).
- **`validation-loop:validate`** — second-model QC after further changes.
- **`brainstorming` / `writing-plans`** — only if opening a new architectural workstream.

## 10. Caveats

Banyan's "120+ acquired / 0 sold" figures are self-reported (banyansoftware.com), not third-party audited — positioning, not fact. All discovery shares the public-web ceiling: the triangulation is a **coverage/consistency + ownership check, not independent financial verification** (registry filed accounts are the exception). Ownership names from single-pass OSINT are less reliable than grounded deep-research names — verify cap tables before outreach.

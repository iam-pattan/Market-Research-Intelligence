# Banyan Scoring Core — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deterministic, list-independent scoring core that turns per-criterion signals into an auditable Banyan-fit score and tier.

**Architecture:** Pure-Python core with three focused modules — `models.py` (typed data structures), `config.py` (YAML-backed rubric config with validation), `rubric_engine.py` (deterministic scoring: weighted composite → confidence discount → gates → tier). No network, no LLM, no I/O beyond reading a config file. This is the defensible heart both the discovery and enrichment paths depend on.

**Tech Stack:** Python 3.11+, `pyyaml`, `pytest`. Standard-library dataclasses/enums.

**Spec:** `docs/superpowers/specs/2026-09-11-banyan-ma-screening-slice1-design.md`

## Global Constraints

- Python 3.11+ (uses `X | None` unions and `from __future__ import annotations`).
- The scoring core is **pure** — no network, no LLM, no filesystem writes; the only I/O is reading `config.yaml`.
- Every score and confidence is a float clamped to `[0.0, 1.0]`; constructors raise `ValueError` on out-of-range input.
- Rubric weights (defaults, from spec §2): recurring_revenue 0.25, profitability 0.20, revenue_band 0.10, niche_leadership 0.20, retention 0.10, ownership_fit 0.10, team_stability 0.05 — must sum to 1.0 (± 0.001).
- Gates (spec §3.4): strong loss evidence → `Tier.REJECTED`; revenue clearly below `revenue_floor_usd` (default 2,000,000) → tier capped at `Tier.C`.
- The engine must emit an audit `rationale` (inputs, weights, arithmetic) on every result — nothing is a black box.
- **Git policy:** this is a new project under `~/banyan-ma-research/`. Per workspace policy, commits are local-only and the executor MUST confirm with the user before the first commit and before any push. Commit steps below are written assuming that confirmation was given.

---

### Task 1: Project scaffold + data models

**Files:**
- Create: `~/banyan-ma-research/pyproject.toml`
- Create: `~/banyan-ma-research/banyan_screen/__init__.py`
- Create: `~/banyan-ma-research/banyan_screen/models.py`
- Test: `~/banyan-ma-research/tests/test_models.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `class Criterion(str, Enum)` members: `RECURRING_REVENUE, PROFITABILITY, REVENUE_BAND, NICHE_LEADERSHIP, RETENTION, OWNERSHIP_FIT, TEAM_STABILITY` (values are the snake_case strings).
  - `class Tier(str, Enum)` members: `A, B, C, INSUFFICIENT_DATA, REJECTED`.
  - `Signal(name: str, value: Any, method: str, confidence: float, source_url: str | None = None)`.
  - `CriterionScore(criterion: Criterion, score: float, confidence: float, signals: list[Signal] = [], notes: str = "", loss_evidence: bool = False, revenue_below_floor: bool = False)`.
  - `Company(id: str, name: str, domain: str | None = None, country: str | None = None, extra: dict[str, Any] = {})`.
  - `ScoredCompany(company: Company, criterion_scores: dict[Criterion, CriterionScore], composite: float, adjusted_score: float, overall_confidence: float, tier: Tier, rationale: dict[str, Any])`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
import pytest
from banyan_screen.models import Criterion, Tier, Signal, CriterionScore, Company

def test_criterion_values_are_snake_case():
    assert Criterion.RECURRING_REVENUE.value == "recurring_revenue"
    assert len(list(Criterion)) == 7

def test_signal_rejects_out_of_range_confidence():
    with pytest.raises(ValueError):
        Signal(name="x", value=1, method="test", confidence=1.5)

def test_criterion_score_clamps_are_enforced():
    with pytest.raises(ValueError):
        CriterionScore(criterion=Criterion.RETENTION, score=-0.1, confidence=0.5)
    ok = CriterionScore(criterion=Criterion.RETENTION, score=0.4, confidence=0.9)
    assert ok.loss_evidence is False and ok.revenue_below_floor is False

def test_company_defaults():
    c = Company(id="acme", name="Acme")
    assert c.domain is None and c.extra == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/banyan-ma-research && python -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: banyan_screen`.

- [ ] **Step 3: Write minimal implementation**

Create `pyproject.toml`:
```toml
[project]
name = "banyan-screen"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pyyaml>=6.0"]

[project.optional-dependencies]
dev = ["pytest>=7.0"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

Create `banyan_screen/__init__.py` (empty).

Create `banyan_screen/models.py`:
```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Criterion(str, Enum):
    RECURRING_REVENUE = "recurring_revenue"
    PROFITABILITY = "profitability"
    REVENUE_BAND = "revenue_band"
    NICHE_LEADERSHIP = "niche_leadership"
    RETENTION = "retention"
    OWNERSHIP_FIT = "ownership_fit"
    TEAM_STABILITY = "team_stability"


class Tier(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    INSUFFICIENT_DATA = "insufficient_data"
    REJECTED = "rejected"


def _check_unit(name: str, v: float) -> None:
    if not 0.0 <= v <= 1.0:
        raise ValueError(f"{name} must be in [0.0, 1.0], got {v}")


@dataclass
class Signal:
    name: str
    value: Any
    method: str
    confidence: float
    source_url: str | None = None

    def __post_init__(self) -> None:
        _check_unit("confidence", self.confidence)


@dataclass
class CriterionScore:
    criterion: Criterion
    score: float
    confidence: float
    signals: list[Signal] = field(default_factory=list)
    notes: str = ""
    loss_evidence: bool = False
    revenue_below_floor: bool = False

    def __post_init__(self) -> None:
        _check_unit("score", self.score)
        _check_unit("confidence", self.confidence)


@dataclass
class Company:
    id: str
    name: str
    domain: str | None = None
    country: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScoredCompany:
    company: Company
    criterion_scores: dict[Criterion, CriterionScore]
    composite: float
    adjusted_score: float
    overall_confidence: float
    tier: Tier
    rationale: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/banyan-ma-research && python -m pytest tests/test_models.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit** (confirm with user first — see Global Constraints)

```bash
cd ~/banyan-ma-research && git init -q 2>/dev/null; \
printf "__pycache__/\n*.pyc\n.cache/\nout/\n.env\n" > .gitignore && \
git add pyproject.toml .gitignore banyan_screen/ tests/test_models.py && \
git commit -q -m "feat: scoring-core data models (Criterion, Tier, Signal, CriterionScore, Company)"
```

---

### Task 2: Rubric config loader

**Files:**
- Create: `~/banyan-ma-research/config.yaml`
- Create: `~/banyan-ma-research/banyan_screen/config.py`
- Test: `~/banyan-ma-research/tests/test_config.py`

**Interfaces:**
- Consumes: `Criterion`, `Tier` from `banyan_screen.models`.
- Produces:
  - `RubricConfig` dataclass with fields: `weights: dict[Criterion, float]`, `reject_on_loss_evidence: bool`, `revenue_floor_usd: float`, `revenue_below_floor_max_tier: Tier`, `min_confidence_floor: float`, `coverage_threshold: float`, `min_signal_confidence: float`, `a_threshold: float`, `b_threshold: float`.
  - classmethod `RubricConfig.from_yaml(path: str) -> RubricConfig`.
  - method `RubricConfig.validate() -> None` (raises `ValueError` if weights don't sum to 1.0 ± 0.001, or thresholds out of order).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import pytest
from banyan_screen.models import Criterion, Tier
from banyan_screen.config import RubricConfig

def test_loads_default_yaml_and_weights_sum_to_one():
    cfg = RubricConfig.from_yaml("config.yaml")
    assert abs(sum(cfg.weights.values()) - 1.0) < 1e-3
    assert set(cfg.weights) == set(Criterion)
    assert cfg.revenue_floor_usd == 2_000_000
    assert cfg.revenue_below_floor_max_tier == Tier.C

def test_validate_rejects_bad_weight_sum():
    cfg = RubricConfig.from_yaml("config.yaml")
    cfg.weights[Criterion.RETENTION] = 0.9
    with pytest.raises(ValueError):
        cfg.validate()

def test_validate_rejects_threshold_inversion():
    cfg = RubricConfig.from_yaml("config.yaml")
    cfg.a_threshold, cfg.b_threshold = 0.3, 0.8  # a must be >= b
    with pytest.raises(ValueError):
        cfg.validate()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/banyan-ma-research && python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: banyan_screen.config`.

- [ ] **Step 3: Write minimal implementation**

Create `config.yaml`:
```yaml
weights:
  recurring_revenue: 0.25
  profitability: 0.20
  revenue_band: 0.10
  niche_leadership: 0.20
  retention: 0.10
  ownership_fit: 0.10
  team_stability: 0.05
gates:
  reject_on_loss_evidence: true
  revenue_floor_usd: 2000000
  revenue_below_floor_max_tier: C
scoring:
  min_confidence_floor: 0.5     # confidence discount never drops below this fraction
  coverage_threshold: 0.5       # fraction of criteria needing adequate confidence to rank
  min_signal_confidence: 0.3    # a criterion "counts" toward coverage above this
tiers:
  a_threshold: 0.75
  b_threshold: 0.55
```

Create `banyan_screen/config.py`:
```python
from __future__ import annotations
from dataclasses import dataclass
import yaml
from banyan_screen.models import Criterion, Tier


@dataclass
class RubricConfig:
    weights: dict[Criterion, float]
    reject_on_loss_evidence: bool
    revenue_floor_usd: float
    revenue_below_floor_max_tier: Tier
    min_confidence_floor: float
    coverage_threshold: float
    min_signal_confidence: float
    a_threshold: float
    b_threshold: float

    @classmethod
    def from_yaml(cls, path: str) -> "RubricConfig":
        with open(path) as fh:
            raw = yaml.safe_load(fh)
        weights = {Criterion(k): float(v) for k, v in raw["weights"].items()}
        g, s, t = raw["gates"], raw["scoring"], raw["tiers"]
        cfg = cls(
            weights=weights,
            reject_on_loss_evidence=bool(g["reject_on_loss_evidence"]),
            revenue_floor_usd=float(g["revenue_floor_usd"]),
            revenue_below_floor_max_tier=Tier(g["revenue_below_floor_max_tier"]),
            min_confidence_floor=float(s["min_confidence_floor"]),
            coverage_threshold=float(s["coverage_threshold"]),
            min_signal_confidence=float(s["min_signal_confidence"]),
            a_threshold=float(t["a_threshold"]),
            b_threshold=float(t["b_threshold"]),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if set(self.weights) != set(Criterion):
            raise ValueError("weights must cover exactly the 7 criteria")
        if abs(sum(self.weights.values()) - 1.0) > 1e-3:
            raise ValueError(f"weights must sum to 1.0, got {sum(self.weights.values())}")
        if not self.a_threshold >= self.b_threshold:
            raise ValueError("a_threshold must be >= b_threshold")
        for name in ("min_confidence_floor", "coverage_threshold",
                     "min_signal_confidence", "a_threshold", "b_threshold"):
            v = getattr(self, name)
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"{name} must be in [0,1], got {v}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/banyan-ma-research && python -m pytest tests/test_config.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit** (confirm with user first)

```bash
cd ~/banyan-ma-research && git add config.yaml banyan_screen/config.py tests/test_config.py && \
git commit -q -m "feat: YAML-backed RubricConfig with validation"
```

---

### Task 3: Composite score + confidence discount

**Files:**
- Create: `~/banyan-ma-research/banyan_screen/rubric_engine.py`
- Test: `~/banyan-ma-research/tests/test_rubric_engine.py`

**Interfaces:**
- Consumes: `Company`, `Criterion`, `CriterionScore`, `Tier`, `ScoredCompany` from models; `RubricConfig` from config.
- Produces:
  - `score_company(company: Company, scores: dict[Criterion, CriterionScore], config: RubricConfig) -> ScoredCompany`.
  - Helper `_composite(scores, config) -> tuple[float, float]` returning `(composite, overall_confidence)`, where composite is the confidence-unaware weighted average over **present** criteria (weights renormalized over present set) and overall_confidence is the weighted mean of their confidences.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rubric_engine.py
from banyan_screen.models import Company, Criterion, CriterionScore, Tier
from banyan_screen.config import RubricConfig
from banyan_screen.rubric_engine import score_company

CFG = RubricConfig.from_yaml("config.yaml")
CO = Company(id="acme", name="Acme")

def _cs(crit, score, conf, **kw):
    return CriterionScore(criterion=crit, score=score, confidence=conf, **kw)

def _all(score, conf, **overrides):
    d = {c: _cs(c, score, conf) for c in Criterion}
    d.update(overrides)
    return d

def test_composite_of_all_perfect_high_conf_is_one():
    r = score_company(CO, _all(1.0, 1.0), CFG)
    assert abs(r.composite - 1.0) < 1e-9
    assert abs(r.overall_confidence - 1.0) < 1e-9
    assert abs(r.adjusted_score - 1.0) < 1e-9

def test_confidence_discount_lowers_adjusted_but_floors_at_min():
    # perfect scores, zero confidence -> adjusted = composite * min_confidence_floor (0.5)
    r = score_company(CO, _all(1.0, 0.0), CFG)
    assert abs(r.composite - 1.0) < 1e-9
    assert abs(r.adjusted_score - 0.5) < 1e-9

def test_composite_renormalizes_over_present_criteria():
    # only two criteria present, both 0.8 -> composite 0.8 regardless of their absolute weights
    scores = {Criterion.RECURRING_REVENUE: _cs(Criterion.RECURRING_REVENUE, 0.8, 1.0),
              Criterion.NICHE_LEADERSHIP: _cs(Criterion.NICHE_LEADERSHIP, 0.8, 1.0)}
    r = score_company(CO, scores, CFG)
    assert abs(r.composite - 0.8) < 1e-9

def test_rationale_is_populated():
    r = score_company(CO, _all(0.6, 0.7), CFG)
    assert "weighted_terms" in r.rationale and "composite" in r.rationale
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/banyan-ma-research && python -m pytest tests/test_rubric_engine.py -v`
Expected: FAIL — `ModuleNotFoundError: banyan_screen.rubric_engine`.

- [ ] **Step 3: Write minimal implementation**

Create `banyan_screen/rubric_engine.py`:
```python
from __future__ import annotations
from banyan_screen.models import (
    Company, Criterion, CriterionScore, Tier, ScoredCompany,
)
from banyan_screen.config import RubricConfig


def _composite(scores: dict[Criterion, CriterionScore],
               config: RubricConfig) -> tuple[float, float]:
    present = [(c, cs) for c, cs in scores.items()]
    total_w = sum(config.weights[c] for c, _ in present)
    if total_w == 0:
        return 0.0, 0.0
    composite = sum(config.weights[c] * cs.score for c, cs in present) / total_w
    overall_conf = sum(config.weights[c] * cs.confidence for c, cs in present) / total_w
    return composite, overall_conf


def score_company(company: Company,
                  scores: dict[Criterion, CriterionScore],
                  config: RubricConfig) -> ScoredCompany:
    composite, overall_conf = _composite(scores, config)
    floor = config.min_confidence_floor
    discount = floor + (1.0 - floor) * overall_conf
    adjusted = composite * discount
    rationale = {
        "weighted_terms": {c.value: {"score": cs.score,
                                     "confidence": cs.confidence,
                                     "weight": config.weights[c]}
                           for c, cs in scores.items()},
        "composite": composite,
        "overall_confidence": overall_conf,
        "confidence_discount": discount,
        "adjusted_score": adjusted,
    }
    return ScoredCompany(
        company=company,
        criterion_scores=scores,
        composite=composite,
        adjusted_score=adjusted,
        overall_confidence=overall_conf,
        tier=Tier.C,  # placeholder; tiering added in Task 5
        rationale=rationale,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/banyan-ma-research && python -m pytest tests/test_rubric_engine.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit** (confirm with user first)

```bash
cd ~/banyan-ma-research && git add banyan_screen/rubric_engine.py tests/test_rubric_engine.py && \
git commit -q -m "feat: composite score + confidence discount"
```

---

### Task 4: Hard-fail and revenue-floor gates

**Files:**
- Modify: `~/banyan-ma-research/banyan_screen/rubric_engine.py`
- Test: `~/banyan-ma-research/tests/test_rubric_engine.py` (append)

**Interfaces:**
- Consumes: Task 3 `score_company`, `RubricConfig` gate fields.
- Produces: internal `_gate_tier(scores, config) -> Tier | None` — returns `Tier.REJECTED` when any `CriterionScore.loss_evidence` is True and `config.reject_on_loss_evidence`; else a cap marker handled in tiering. Adds `gate` info to `rationale`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rubric_engine.py  (append)
def test_loss_evidence_rejects_regardless_of_score():
    scores = _all(1.0, 1.0,
                  **{Criterion.PROFITABILITY: _cs(Criterion.PROFITABILITY, 1.0, 1.0,
                                                  loss_evidence=True)})
    r = score_company(CO, scores, CFG)
    assert r.tier == Tier.REJECTED
    assert r.rationale["gate"]["rejected_on_loss"] is True

def test_revenue_below_floor_caps_tier_at_c():
    scores = _all(1.0, 1.0,
                  **{Criterion.REVENUE_BAND: _cs(Criterion.REVENUE_BAND, 1.0, 1.0,
                                                 revenue_below_floor=True)})
    r = score_company(CO, scores, CFG)
    assert r.tier == Tier.C  # would be A on score, capped by gate
    assert r.rationale["gate"]["revenue_capped"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/banyan-ma-research && python -m pytest tests/test_rubric_engine.py -k "loss_evidence or revenue_below_floor" -v`
Expected: FAIL — `KeyError: 'gate'` / wrong tier (tiering still placeholder).

- [ ] **Step 3: Write minimal implementation**

In `rubric_engine.py`, add above `score_company`:
```python
def _gate(scores: dict[Criterion, CriterionScore],
          config: RubricConfig) -> dict:
    rejected = config.reject_on_loss_evidence and any(
        cs.loss_evidence for cs in scores.values())
    capped = any(cs.revenue_below_floor for cs in scores.values())
    return {"rejected_on_loss": rejected,
            "revenue_capped": capped,
            "max_tier": config.revenue_below_floor_max_tier if capped else None}
```

In `score_company`, after computing `rationale` and before the `return`, replace the placeholder tier logic:
```python
    gate = _gate(scores, config)
    rationale["gate"] = gate
    if gate["rejected_on_loss"]:
        tier = Tier.REJECTED
    else:
        tier = Tier.C  # full tiering wired in Task 5; honor cap there
    return ScoredCompany(
        company=company, criterion_scores=scores, composite=composite,
        adjusted_score=adjusted, overall_confidence=overall_conf,
        tier=tier, rationale=rationale,
    )
```
(The revenue cap is asserted by Task 5's tiering; for now the placeholder `Tier.C` already satisfies the cap test. Task 5 replaces this block.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/banyan-ma-research && python -m pytest tests/test_rubric_engine.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit** (confirm with user first)

```bash
cd ~/banyan-ma-research && git add banyan_screen/rubric_engine.py tests/test_rubric_engine.py && \
git commit -q -m "feat: loss-evidence and revenue-floor gates"
```

---

### Task 5: Coverage check + tier assignment (final wiring)

**Files:**
- Modify: `~/banyan-ma-research/banyan_screen/rubric_engine.py`
- Test: `~/banyan-ma-research/tests/test_rubric_engine.py` (append)

**Interfaces:**
- Consumes: everything from Tasks 3–4.
- Produces: `_assign_tier(adjusted: float, coverage: float, gate: dict, config: RubricConfig) -> Tier` and final `score_company` that: (1) computes coverage = fraction of the 7 criteria whose confidence ≥ `min_signal_confidence`; (2) if coverage < `coverage_threshold` → `INSUFFICIENT_DATA`; (3) gate reject → `REJECTED`; (4) else tier from `adjusted` vs `a_threshold`/`b_threshold`, capped by `gate["max_tier"]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rubric_engine.py  (append)
def test_high_score_full_coverage_is_tier_a():
    r = score_company(CO, _all(0.9, 1.0), CFG)
    assert r.tier == Tier.A

def test_mid_score_is_tier_b():
    r = score_company(CO, _all(0.6, 1.0), CFG)  # adjusted 0.6 -> B (>=0.55, <0.75)
    assert r.tier == Tier.B

def test_thin_coverage_is_insufficient_data():
    # only 2 of 7 criteria have usable confidence -> coverage 2/7 < 0.5
    scores = {Criterion.RECURRING_REVENUE: _cs(Criterion.RECURRING_REVENUE, 1.0, 1.0),
              Criterion.NICHE_LEADERSHIP: _cs(Criterion.NICHE_LEADERSHIP, 1.0, 1.0)}
    r = score_company(CO, scores, CFG)
    assert r.tier == Tier.INSUFFICIENT_DATA

def test_revenue_cap_holds_even_with_tier_a_score():
    scores = _all(0.95, 1.0,
                  **{Criterion.REVENUE_BAND: _cs(Criterion.REVENUE_BAND, 0.95, 1.0,
                                                 revenue_below_floor=True)})
    r = score_company(CO, scores, CFG)
    assert r.tier == Tier.C
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/banyan-ma-research && python -m pytest tests/test_rubric_engine.py -k "tier_a or tier_b or insufficient or revenue_cap_holds" -v`
Expected: FAIL — placeholder returns `Tier.C` for the A/B cases.

- [ ] **Step 3: Write minimal implementation**

Add to `rubric_engine.py`:
```python
_TIER_ORDER = [Tier.C, Tier.B, Tier.A]  # ascending


def _cap(tier: Tier, max_tier: Tier | None) -> Tier:
    if max_tier is None:
        return tier
    if _TIER_ORDER.index(tier) > _TIER_ORDER.index(max_tier):
        return max_tier
    return tier


def _assign_tier(adjusted: float, coverage: float,
                 gate: dict, config: RubricConfig) -> Tier:
    if gate["rejected_on_loss"]:
        return Tier.REJECTED
    if coverage < config.coverage_threshold:
        return Tier.INSUFFICIENT_DATA
    if adjusted >= config.a_threshold:
        base = Tier.A
    elif adjusted >= config.b_threshold:
        base = Tier.B
    else:
        base = Tier.C
    return _cap(base, gate["max_tier"])
```

Replace the tier block in `score_company` (from Task 4) with:
```python
    gate = _gate(scores, config)
    rationale["gate"] = gate
    n_total = len(list(Criterion))
    n_usable = sum(1 for cs in scores.values()
                   if cs.confidence >= config.min_signal_confidence)
    coverage = n_usable / n_total
    rationale["coverage"] = coverage
    tier = _assign_tier(adjusted, coverage, gate, config)
    return ScoredCompany(
        company=company, criterion_scores=scores, composite=composite,
        adjusted_score=adjusted, overall_confidence=overall_conf,
        tier=tier, rationale=rationale,
    )
```

- [ ] **Step 4: Run the full suite to verify everything passes**

Run: `cd ~/banyan-ma-research && python -m pytest -v`
Expected: PASS (all tests across the three test files).

- [ ] **Step 5: Commit** (confirm with user first)

```bash
cd ~/banyan-ma-research && git add banyan_screen/rubric_engine.py tests/test_rubric_engine.py && \
git commit -q -m "feat: coverage check + tier assignment (scoring core complete)"
```

---

## Self-Review

**1. Spec coverage:** §2 rubric weights → config.yaml + Task 2. §3.4 scoring (composite, confidence discount, gates, coverage/INSUFFICIENT_DATA, tiers) → Tasks 3–5. §3.2 data model (`Signal{value,source_url,method,confidence}`) → Task 1. §6 audit rationale → Tasks 3–5 `rationale`. Out of scope here (extractors, scrapers, registry, reporter, orchestrator) belong to Build 2+ per spec §10 — correctly excluded.

**2. Placeholder scan:** Task 3/4 use an explicit, labeled placeholder tier that Task 5 replaces — each intermediate state has passing tests, no "TODO/TBD" left in final code. OK.

**3. Type consistency:** `score_company`, `_composite`, `_gate`, `_assign_tier`, `_cap` signatures and the `rationale` keys (`weighted_terms`, `composite`, `overall_confidence`, `confidence_discount`, `adjusted_score`, `gate`, `coverage`) are consistent across tasks. `Tier`/`Criterion` enum values match config.yaml strings. OK.

---

## Execution Handoff

Plan complete. Two execution options:
1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks.
2. **Inline Execution** — execute here with checkpoints.

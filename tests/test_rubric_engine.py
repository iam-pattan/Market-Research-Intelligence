from banyan_screen.models import Company, Criterion, CriterionScore, Tier
from banyan_screen.config import RubricConfig
from banyan_screen.rubric_engine import score_company

CFG = RubricConfig.from_yaml("config/banyan.yaml")
CO = Company(id="acme", name="Acme")


def _cs(crit, score, conf, **kw):
    return CriterionScore(criterion=crit, score=score, confidence=conf, **kw)


def _all(score, conf, **overrides):
    d = {c: _cs(c, score, conf) for c in CFG.weights}  # the Banyan rubric's criteria
    d.update(overrides)
    return d


# --- Task 3: composite + confidence discount ---

def test_composite_of_all_perfect_high_conf_is_one():
    r = score_company(CO, _all(1.0, 1.0), CFG)
    assert abs(r.composite - 1.0) < 1e-9
    assert abs(r.overall_confidence - 1.0) < 1e-9
    assert abs(r.adjusted_score - 1.0) < 1e-9


def test_confidence_discount_lowers_adjusted_but_floors_at_min():
    r = score_company(CO, _all(1.0, 0.0), CFG)
    assert abs(r.composite - 1.0) < 1e-9
    assert abs(r.adjusted_score - 0.5) < 1e-9


def test_composite_renormalizes_over_present_criteria():
    scores = {Criterion.RECURRING_REVENUE: _cs(Criterion.RECURRING_REVENUE, 0.8, 1.0),
              Criterion.NICHE_LEADERSHIP: _cs(Criterion.NICHE_LEADERSHIP, 0.8, 1.0)}
    r = score_company(CO, scores, CFG)
    assert abs(r.composite - 0.8) < 1e-9


def test_rationale_is_populated():
    r = score_company(CO, _all(0.6, 0.7), CFG)
    assert "weighted_terms" in r.rationale and "composite" in r.rationale


# --- Task 4: gates ---

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
    assert r.tier == Tier.C
    assert r.rationale["gate"]["revenue_capped"] is True


# --- Task 5: coverage + tiering ---

def test_high_score_full_coverage_is_tier_a():
    r = score_company(CO, _all(0.9, 1.0), CFG)
    assert r.tier == Tier.A


def test_mid_score_is_tier_b():
    r = score_company(CO, _all(0.6, 1.0), CFG)
    assert r.tier == Tier.B


def test_thin_coverage_is_insufficient_data():
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

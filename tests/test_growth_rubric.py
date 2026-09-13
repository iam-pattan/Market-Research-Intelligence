"""Tests for the GROWTH rubric and dual-rubric behavior.

Proves one engine serves two theses: the Banyan rubric hard-gates on losses and
a revenue floor; the growth rubric does neither and scores growth-momentum
criteria instead. Coverage is measured against each rubric's own criteria set.
"""
from banyan_screen.models import Company, Criterion, CriterionScore, Tier
from banyan_screen.config import RubricConfig
from banyan_screen.rubric_engine import score_company

BANYAN = RubricConfig.from_yaml("config.yaml")
GROWTH = RubricConfig.from_yaml("config.growth.yaml")
CO = Company(id="x", name="X")
C = Criterion

GROWTH_CRITERIA = [C.REVENUE_GROWTH, C.RECURRING_REVENUE, C.MARKET_SIZE,
                   C.FUNDING_MOMENTUM, C.HIRING_VELOCITY, C.NICHE_LEADERSHIP,
                   C.RETENTION]


def cs(cr, s, c, **kw):
    return CriterionScore(cr, s, c, **kw)


def growth_scores(s, conf):
    return {cr: cs(cr, s, conf) for cr in GROWTH_CRITERIA}


def test_growth_config_loads_and_has_no_profitability_gate():
    assert abs(sum(GROWTH.weights.values()) - 1.0) < 1e-3
    assert C.PROFITABILITY not in GROWTH.weights
    assert GROWTH.reject_on_loss_evidence is False
    assert GROWTH.revenue_below_floor_max_tier is None


def test_growth_high_signals_is_tier_a():
    r = score_company(CO, growth_scores(0.9, 1.0), GROWTH)
    assert r.tier == Tier.A


def test_loss_evidence_does_not_reject_under_growth():
    scores = growth_scores(0.8, 1.0)
    scores[C.RECURRING_REVENUE] = cs(C.RECURRING_REVENUE, 0.8, 1.0, loss_evidence=True)
    r = score_company(CO, scores, GROWTH)
    assert r.tier != Tier.REJECTED


def test_coverage_denominator_is_rubric_specific():
    scores = {C.REVENUE_GROWTH: cs(C.REVENUE_GROWTH, 0.9, 1.0),
              C.RECURRING_REVENUE: cs(C.RECURRING_REVENUE, 0.9, 1.0),
              C.MARKET_SIZE: cs(C.MARKET_SIZE, 0.9, 1.0),
              C.FUNDING_MOMENTUM: cs(C.FUNDING_MOMENTUM, 0.9, 1.0)}
    r = score_company(CO, scores, GROWTH)
    assert abs(r.rationale["coverage"] - 4 / 7) < 1e-9


def test_growth_ignores_criteria_it_does_not_weight():
    scores = growth_scores(0.9, 1.0)
    scores[C.PROFITABILITY] = cs(C.PROFITABILITY, 0.0, 1.0)  # not in growth weights
    r = score_company(CO, scores, GROWTH)
    assert r.tier == Tier.A  # profitability 0.0 is ignored, not averaged in


def test_same_company_differs_across_rubrics():
    # A loss-making but high-growth company: REJECTED by Banyan, viable under growth.
    banyan_scores = {c: cs(c, 0.8, 0.9) for c in [
        C.RECURRING_REVENUE, C.REVENUE_BAND, C.NICHE_LEADERSHIP,
        C.RETENTION, C.OWNERSHIP_FIT, C.TEAM_STABILITY]}
    banyan_scores[C.PROFITABILITY] = cs(C.PROFITABILITY, 0.2, 0.9, loss_evidence=True)
    rb = score_company(CO, banyan_scores, BANYAN)
    rg = score_company(CO, growth_scores(0.85, 0.9), GROWTH)
    assert rb.tier == Tier.REJECTED
    assert rg.tier in (Tier.A, Tier.B)

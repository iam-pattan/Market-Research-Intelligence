import pytest
from banyan_screen.models import Criterion, Tier
from banyan_screen.config import RubricConfig
from banyan_screen.ingest import company_from_record, banyan_scores, growth_scores
from banyan_screen.rubric_engine import score_company

BANYAN = RubricConfig.from_yaml("config/banyan.yaml")
GROWTH = RubricConfig.from_yaml("config/growth.yaml")


def _rec(**over):
    base = {
        "name": "Test Co", "domain": "test.example", "hq_region": "US",
        "vertical": "healthcare", "is_vertical_niche": 1.0,
        "already_acquired_or_public": False,
        "recurring_revenue": {"score": 0.9, "confidence": 0.7},
        "profitability": {"score": 0.8, "confidence": 0.6, "loss_evidence": False},
        "revenue_est_usd": {"value": 8_000_000, "below_2M": False, "above_100M": False, "confidence": 0.5},
        "niche_leadership": {"score": 0.9, "confidence": 0.6},
        "retention": {"score": 0.7, "confidence": 0.4},
        "ownership_fit": {"score": 0.8, "confidence": 0.5, "type": "founder"},
        "team_stability": {"score": 0.6, "confidence": 0.3},
        "revenue_growth": {"score": 0.5, "confidence": 0.4},
        "hiring_velocity": {"score": 0.5, "confidence": 0.3},
        "funding_momentum": {"score": 0.3, "confidence": 0.4},
        "market_size": {"score": 0.7, "confidence": 0.5},
        "notes": "",
    }
    base.update(over)
    return base


def test_company_from_record_carries_metadata():
    co = company_from_record(_rec())
    assert co.name == "Test Co" and co.domain == "test.example"
    assert co.extra["vertical"] == "healthcare"


def test_below_2m_sets_gate_flag_and_low_score():
    scores = banyan_scores(_rec(revenue_est_usd={"below_2M": True, "above_100M": False, "confidence": 0.6}))
    rb = scores[Criterion.REVENUE_BAND]
    assert rb.revenue_below_floor is True and rb.score < 0.2


def test_above_100m_is_damped_not_full():
    scores = banyan_scores(_rec(revenue_est_usd={"below_2M": False, "above_100M": True, "confidence": 0.6}))
    assert scores[Criterion.REVENUE_BAND].score == 0.5


def test_horizontal_niche_is_damped_for_banyan():
    vert = banyan_scores(_rec(is_vertical_niche=1.0))[Criterion.NICHE_LEADERSHIP].score
    horiz = banyan_scores(_rec(is_vertical_niche=0.0))[Criterion.NICHE_LEADERSHIP].score
    assert horiz < vert  # horizontal product penalized under Banyan


def test_growth_scores_have_growth_criteria_only():
    keys = set(growth_scores(_rec()))
    assert Criterion.REVENUE_GROWTH in keys and Criterion.PROFITABILITY not in keys


def test_missing_metric_defaults_to_low_confidence():
    rec = _rec()
    del rec["team_stability"]
    ts = banyan_scores(rec)[Criterion.TEAM_STABILITY]
    assert ts.confidence <= 0.1


def test_full_record_scores_under_both_rubrics():
    rec = _rec()
    co = company_from_record(rec)
    rb = score_company(co, banyan_scores(rec), BANYAN)
    rg = score_company(co, growth_scores(rec), GROWTH)
    assert rb.tier in set(Tier) and rg.tier in set(Tier)

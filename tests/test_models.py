import pytest
from banyan_screen.models import Criterion, Tier, Signal, CriterionScore, Company


def test_criterion_values_are_snake_case():
    assert Criterion.RECURRING_REVENUE.value == "recurring_revenue"
    assert Criterion.REVENUE_GROWTH.value == "revenue_growth"
    assert len(list(Criterion)) == 11  # 7 Banyan-fit + 4 growth-thesis


def test_tier_has_five_members():
    assert {t.value for t in Tier} == {"A", "B", "C", "insufficient_data", "rejected"}


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

import pytest
from banyan_screen.models import Criterion, Tier
from banyan_screen.config import RubricConfig


def test_loads_default_yaml_and_weights_sum_to_one():
    cfg = RubricConfig.from_yaml("config/banyan.yaml")
    assert abs(sum(cfg.weights.values()) - 1.0) < 1e-3
    assert set(cfg.weights).issubset(set(Criterion))
    assert len(cfg.weights) == 7  # Banyan uses 7 of the 11 available criteria
    assert cfg.revenue_floor_usd == 2_000_000
    assert cfg.revenue_below_floor_max_tier == Tier.C


def test_validate_rejects_bad_weight_sum():
    cfg = RubricConfig.from_yaml("config/banyan.yaml")
    cfg.weights[Criterion.RETENTION] = 0.9
    with pytest.raises(ValueError):
        cfg.validate()


def test_validate_rejects_threshold_inversion():
    cfg = RubricConfig.from_yaml("config/banyan.yaml")
    cfg.a_threshold, cfg.b_threshold = 0.3, 0.8  # a must be >= b
    with pytest.raises(ValueError):
        cfg.validate()

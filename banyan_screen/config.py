from __future__ import annotations
from dataclasses import dataclass
import yaml
from banyan_screen.models import Criterion, Tier


@dataclass
class RubricConfig:
    weights: dict[Criterion, float]
    reject_on_loss_evidence: bool
    revenue_floor_usd: float
    revenue_below_floor_max_tier: Tier | None
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
        mt = g.get("revenue_below_floor_max_tier")
        cfg = cls(
            weights=weights,
            reject_on_loss_evidence=bool(g["reject_on_loss_evidence"]),
            revenue_floor_usd=float(g.get("revenue_floor_usd", 0)),
            revenue_below_floor_max_tier=Tier(mt) if mt else None,
            min_confidence_floor=float(s["min_confidence_floor"]),
            coverage_threshold=float(s["coverage_threshold"]),
            min_signal_confidence=float(s["min_signal_confidence"]),
            a_threshold=float(t["a_threshold"]),
            b_threshold=float(t["b_threshold"]),
        )
        cfg.validate()
        return cfg

    def validate(self) -> None:
        if not self.weights:
            raise ValueError("weights must define at least one criterion")
        if not set(self.weights).issubset(set(Criterion)):
            raise ValueError("weights contain unknown criteria")
        total = sum(self.weights.values())
        if abs(total - 1.0) > 1e-3:
            raise ValueError(f"weights must sum to 1.0, got {total}")
        if not self.a_threshold >= self.b_threshold:
            raise ValueError("a_threshold must be >= b_threshold")
        for name in ("min_confidence_floor", "coverage_threshold",
                     "min_signal_confidence", "a_threshold", "b_threshold"):
            v = getattr(self, name)
            if not 0.0 <= v <= 1.0:
                raise ValueError(f"{name} must be in [0,1], got {v}")

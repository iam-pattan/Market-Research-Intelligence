from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Criterion(str, Enum):
    # --- Banyan-fit (permanent-hold, profitable) criteria ---
    RECURRING_REVENUE = "recurring_revenue"
    PROFITABILITY = "profitability"
    REVENUE_BAND = "revenue_band"
    NICHE_LEADERSHIP = "niche_leadership"
    RETENTION = "retention"
    OWNERSHIP_FIT = "ownership_fit"
    TEAM_STABILITY = "team_stability"
    # --- Growth-thesis criteria (scaling software/AI) ---
    REVENUE_GROWTH = "revenue_growth"
    HIRING_VELOCITY = "hiring_velocity"
    FUNDING_MOMENTUM = "funding_momentum"
    MARKET_SIZE = "market_size"


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
    """A single observed signal with provenance and confidence.

    Nothing in this system is a fact without a source: every Signal carries
    where it came from (source_url), how it was derived (method), and how much
    to trust it (confidence).
    """

    name: str
    value: Any
    method: str
    confidence: float
    source_url: str | None = None

    def __post_init__(self) -> None:
        _check_unit("confidence", self.confidence)


@dataclass
class CriterionScore:
    """A per-criterion score in [0,1] with confidence and the signals behind it.

    ``loss_evidence`` and ``revenue_below_floor`` are the two hard-gate flags the
    rubric engine acts on (see rubric_engine._gate).
    """

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

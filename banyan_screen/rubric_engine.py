"""Deterministic Banyan-fit scoring.

The LLM/extractors (Build 2+) propose per-criterion CriterionScores with
confidence; this module alone turns them into a composite score, applies the
hard gates, and assigns a tier. It is pure: no network, no LLM, no I/O. Every
result carries a ``rationale`` dict recording exactly how the number was formed.
"""
from __future__ import annotations
from banyan_screen.models import (
    Company, Criterion, CriterionScore, Tier, ScoredCompany,
)
from banyan_screen.config import RubricConfig

_TIER_ORDER = [Tier.C, Tier.B, Tier.A]  # ascending quality


def _composite(scores: dict[Criterion, CriterionScore],
               config: RubricConfig) -> tuple[float, float]:
    """Weighted average of scores and of confidences over the criteria that are
    BOTH present in ``scores`` AND part of this rubric (``config.weights``).

    Weights are renormalized over that present set so a missing criterion does
    not silently drag the composite toward zero, and a signal for a criterion
    this rubric doesn't use is ignored rather than crashing. Absence is handled
    by the coverage check, not by the composite.
    """
    present = [(c, cs) for c, cs in scores.items() if c in config.weights]
    total_w = sum(config.weights[c] for c, _ in present)
    if total_w == 0:
        return 0.0, 0.0
    composite = sum(config.weights[c] * cs.score for c, cs in present) / total_w
    overall_conf = sum(config.weights[c] * cs.confidence for c, cs in present) / total_w
    return composite, overall_conf


def _gate(scores: dict[Criterion, CriterionScore],
          config: RubricConfig) -> dict:
    rejected = config.reject_on_loss_evidence and any(
        cs.loss_evidence for cs in scores.values())
    capped = (config.revenue_below_floor_max_tier is not None
              and any(cs.revenue_below_floor for cs in scores.values()))
    return {
        "rejected_on_loss": rejected,
        "revenue_capped": capped,
        "max_tier": config.revenue_below_floor_max_tier if capped else None,
    }


def _cap(tier: Tier, max_tier: Tier | None) -> Tier:
    if max_tier is None or tier not in _TIER_ORDER:
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


def score_company(company: Company,
                  scores: dict[Criterion, CriterionScore],
                  config: RubricConfig) -> ScoredCompany:
    composite, overall_conf = _composite(scores, config)
    floor = config.min_confidence_floor
    discount = floor + (1.0 - floor) * overall_conf
    adjusted = composite * discount

    gate = _gate(scores, config)
    rubric_criteria = list(config.weights)
    n_total = len(rubric_criteria)
    n_usable = sum(1 for c in rubric_criteria
                   if c in scores and scores[c].confidence >= config.min_signal_confidence)
    coverage = n_usable / n_total if n_total else 0.0
    tier = _assign_tier(adjusted, coverage, gate, config)

    rationale = {
        "weighted_terms": {c.value: {"score": cs.score,
                                     "confidence": cs.confidence,
                                     "weight": config.weights[c]}
                           for c, cs in scores.items() if c in config.weights},
        "composite": composite,
        "overall_confidence": overall_conf,
        "confidence_discount": discount,
        "adjusted_score": adjusted,
        "coverage": coverage,
        "gate": gate,
    }
    return ScoredCompany(
        company=company,
        criterion_scores=scores,
        composite=composite,
        adjusted_score=adjusted,
        overall_confidence=overall_conf,
        tier=tier,
        rationale=rationale,
    )

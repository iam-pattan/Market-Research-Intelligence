"""Map an enrichment record (the subagent JSON schema) to CriterionScores for
both rubrics.

A record is one company as produced by the enrichment agents. Each metric is a
``{"score", "confidence", ...}`` object. This module is the single place where
raw enrichment turns into rubric inputs, so the mapping choices live here and
are unit-tested:

- Banyan REVENUE_BAND is derived from revenue flags: below $2M floor -> low score
  + ``revenue_below_floor`` gate flag; above $100M (over Banyan's sweet spot) ->
  damped to 0.5; otherwise 1.0. (The revenue-ceiling handling addresses the
  spike finding that a floor alone over-scored very large companies.)
- Banyan NICHE_LEADERSHIP is damped for horizontal products (Banyan wants
  vertical niches): factor 0.4 + 0.6 * is_vertical_niche.
- The growth rubric uses raw niche_leadership (horizontal is fine for growth) and
  ignores profitability/ownership entirely.
"""
from __future__ import annotations
from typing import Any
from banyan_screen.models import Company, Criterion, CriterionScore

C = Criterion


def _pair(rec: dict[str, Any], key: str) -> tuple[float, float]:
    m = rec.get(key) or {}
    return float(m.get("score", 0.5)), float(m.get("confidence", 0.1))


def company_from_record(rec: dict[str, Any]) -> Company:
    return Company(
        id=rec.get("domain") or rec["name"].lower().replace(" ", "-"),
        name=rec["name"],
        domain=rec.get("domain"),
        country=rec.get("hq_region"),
        extra={"vertical": rec.get("vertical"),
               "already_acquired_or_public": bool(rec.get("already_acquired_or_public", False)),
               "notes": rec.get("notes", "")},
    )


def _revenue_band_banyan(rec: dict[str, Any]) -> CriterionScore:
    r = rec.get("revenue_est_usd") or {}
    conf = float(r.get("confidence", 0.1))
    below = bool(r.get("below_2M", False))
    above = bool(r.get("above_100M", False))
    if below:
        score = 0.1
    elif above:
        score = 0.5  # above Banyan's typical sweet spot, not disqualifying
    else:
        score = 1.0
    return CriterionScore(C.REVENUE_BAND, score, conf, revenue_below_floor=below)


def banyan_scores(rec: dict[str, Any]) -> dict[Criterion, CriterionScore]:
    rr_s, rr_c = _pair(rec, "recurring_revenue")
    pr_s, pr_c = _pair(rec, "profitability")
    nl_s, nl_c = _pair(rec, "niche_leadership")
    rt_s, rt_c = _pair(rec, "retention")
    ow_s, ow_c = _pair(rec, "ownership_fit")
    tm_s, tm_c = _pair(rec, "team_stability")
    loss = bool((rec.get("profitability") or {}).get("loss_evidence", False))
    vert = float(rec.get("is_vertical_niche", 0.5))
    niche_damped = nl_s * (0.4 + 0.6 * vert)
    return {
        C.RECURRING_REVENUE: CriterionScore(C.RECURRING_REVENUE, rr_s, rr_c),
        C.PROFITABILITY: CriterionScore(C.PROFITABILITY, pr_s, pr_c, loss_evidence=loss),
        C.REVENUE_BAND: _revenue_band_banyan(rec),
        C.NICHE_LEADERSHIP: CriterionScore(C.NICHE_LEADERSHIP, niche_damped, nl_c),
        C.RETENTION: CriterionScore(C.RETENTION, rt_s, rt_c),
        C.OWNERSHIP_FIT: CriterionScore(C.OWNERSHIP_FIT, ow_s, ow_c),
        C.TEAM_STABILITY: CriterionScore(C.TEAM_STABILITY, tm_s, tm_c),
    }


def growth_scores(rec: dict[str, Any]) -> dict[Criterion, CriterionScore]:
    def cs(crit, key):
        s, c = _pair(rec, key)
        return CriterionScore(crit, s, c)
    return {
        C.REVENUE_GROWTH: cs(C.REVENUE_GROWTH, "revenue_growth"),
        C.RECURRING_REVENUE: cs(C.RECURRING_REVENUE, "recurring_revenue"),
        C.MARKET_SIZE: cs(C.MARKET_SIZE, "market_size"),
        C.FUNDING_MOMENTUM: cs(C.FUNDING_MOMENTUM, "funding_momentum"),
        C.HIRING_VELOCITY: cs(C.HIRING_VELOCITY, "hiring_velocity"),
        C.NICHE_LEADERSHIP: cs(C.NICHE_LEADERSHIP, "niche_leadership"),
        C.RETENTION: cs(C.RETENTION, "retention"),
    }

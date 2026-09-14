"""Org/role-based output enforcement layer.

This is the RUNTIME guard that implements the conceptual IAM model
(iam/iam_hierarchy.html) as an actual filter over data leaving the platform —
"a layer on Claude's output" so that a consumer only ever receives the
classification tiers its role is entitled to.

Core guarantee: `enforce(role, record)` returns a copy of `record` with every
field whose data-classification the role may NOT see removed, and every field
the role may see only in masked form redacted. Deny-by-default: an unknown role
gets nothing. Example the user called out explicitly: Data Science never
receives PII (contacts) or raw financials.

The model is field-classification-driven, so it degrades safely: a NEW field
whose name doesn't match a known-safe pattern is treated as its containing
domain's tier or, failing that, the conservative default — it is never leaked
just because the policy didn't anticipate it.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import IntEnum
from typing import Any


class Tier(IntEnum):
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL_FINANCIAL = 2   # SOX
    RESTRICTED_PII = 3           # GDPR/CCPA
    RESTRICTED_MNPI = 4          # securities / insider info


# Substring patterns (matched against the lowercased field key) -> tier.
# Order matters: MNPI and PII checked before financial before internal.
_PII_KEYS = ("contact", "relationship", "email", "phone", "person", "people",
             "decision_maker", "linkedin", "owner_name", "pii")
_MNPI_KEYS = ("deal", "pipeline", "mnpi", "stage", "deal_intent", "acquisition_intent")
_FIN_KEYS = ("revenue", "tpv", "margin", "financial", "profit", "ebitda",
             "arr", "cash_flow", "valuation")
_INTERNAL_SAFE = ("name", "domain", "vertical", "region", "hq", "country",
                  "is_vertical_niche", "niche", "retention", "market_size",
                  "recurring_revenue", "team_stability", "hiring", "notes",
                  "score", "confidence", "tier", "rank")

_DEFAULT_TIER = Tier.CONFIDENTIAL_FINANCIAL  # conservative: unknown fields are NOT free to leak
# Outreach narrative is Sales/BD-owned content, not a data tier: gated by
# pitch_visible() inside enforce(), before tier classification (see below).
_PITCH_KEYS = ("pitch", "outreach", "email_body", "cold_email")


def classify(key: str) -> Tier:
    k = str(key).lower()
    if any(p in k for p in _MNPI_KEYS):
        return Tier.RESTRICTED_MNPI
    if any(p in k for p in _PII_KEYS):
        return Tier.RESTRICTED_PII
    if any(p in k for p in _FIN_KEYS):
        return Tier.CONFIDENTIAL_FINANCIAL
    if any(p in k for p in _INTERNAL_SAFE):
        return Tier.INTERNAL
    return _DEFAULT_TIER


@dataclass(frozen=True)
class RolePolicy:
    allowed: frozenset          # tiers the role may see at all
    masked: frozenset           # of the allowed, which are shown only redacted
    aggregate_only: bool = False  # DS: individual records are not a valid output shape


def _p(allowed, masked=frozenset(), aggregate_only=False) -> RolePolicy:
    return RolePolicy(frozenset(allowed), frozenset(masked), aggregate_only)


# Role -> policy. Mirrors the finalized IAM access matrix.
ROLES: dict[str, RolePolicy] = {
    # Data Science: identity + non-financial signals ONLY. No PII, no financials,
    # no MNPI. aggregate_only flags that per-record output should be refused.
    "ds_analyst": _p({Tier.PUBLIC, Tier.INTERNAL}, aggregate_only=True),
    "ds_lead":    _p({Tier.PUBLIC, Tier.INTERNAL}, aggregate_only=True),
    # Sales: identity + signals + PII (masked). No financials, no MNPI.
    "sales_rep":     _p({Tier.PUBLIC, Tier.INTERNAL, Tier.RESTRICTED_PII}, masked={Tier.RESTRICTED_PII}),
    "sales_manager": _p({Tier.PUBLIC, Tier.INTERNAL, Tier.RESTRICTED_PII}, masked={Tier.RESTRICTED_PII}),
    # Finance: full financials. No PII contacts, no MNPI.
    "finance_analyst":  _p({Tier.PUBLIC, Tier.INTERNAL, Tier.CONFIDENTIAL_FINANCIAL}),
    "finance_editor":   _p({Tier.PUBLIC, Tier.INTERNAL, Tier.CONFIDENTIAL_FINANCIAL}),
    "finance_approver": _p({Tier.PUBLIC, Tier.INTERNAL, Tier.CONFIDENTIAL_FINANCIAL}),
    # Leadership: everything, but PII masked and financials as summary (masked).
    "c_suite_leadership": _p(
        {Tier.PUBLIC, Tier.INTERNAL, Tier.CONFIDENTIAL_FINANCIAL, Tier.RESTRICTED_PII, Tier.RESTRICTED_MNPI},
        masked={Tier.RESTRICTED_PII, Tier.CONFIDENTIAL_FINANCIAL}),
    # Governance / ops: not business-data consumers -> deny all content.
    "compliance_officer":      _p({Tier.PUBLIC}),
    "dpo_data_protection":     _p({Tier.PUBLIC}),
    "data_steward":            _p({Tier.PUBLIC}),
    "access_admin":            _p({Tier.PUBLIC}),
    "access_reviewer_auditor": _p({Tier.PUBLIC}),
    "platform_admin":          _p({Tier.PUBLIC}),
}

_REDACTED = {
    Tier.RESTRICTED_PII: "[REDACTED:PII]",
    Tier.CONFIDENTIAL_FINANCIAL: "[REDACTED:FINANCIAL]",
    Tier.RESTRICTED_MNPI: "[REDACTED:MNPI]",
}


def _mask_value(tier: Tier, value: Any) -> Any:
    # A light, useful mask where possible (email -> domain), else a tier label.
    if tier == Tier.RESTRICTED_PII and isinstance(value, str) and "@" in value:
        return "***@" + value.split("@", 1)[1]
    return _REDACTED.get(tier, "[REDACTED]")


def enforce(role: str, record: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of `record` filtered to what `role` may receive.

    Fields above the role's allowance are DROPPED; masked-tier fields are
    redacted in place. Unknown role -> {} (deny-by-default / fail-closed).
    """
    policy = ROLES.get(role)
    if policy is None:
        return {}
    out: dict[str, Any] = {}
    for key, value in record.items():
        if any(p in str(key).lower() for p in _PITCH_KEYS):
            # Narrative fields follow the coarse Sales/BD gate, not a tier —
            # so the field engine and pitch_visible() never disagree.
            if pitch_visible(role):
                out[key] = value
            continue
        tier = classify(key)
        if isinstance(value, dict):
            # Nested object: classify by the sub-keys too; keep the higher of the
            # container tier and any child tier by recursing, then gate the whole.
            if tier not in policy.allowed:
                continue
            nested = enforce(role, value)
            if tier in policy.masked:
                out[key] = _REDACTED.get(tier, "[REDACTED]")
            elif nested:
                out[key] = nested
            continue
        if tier not in policy.allowed:
            continue  # drop entirely
        out[key] = _mask_value(tier, value) if tier in policy.masked else value
    return out


def guard(role: str, payload: Any) -> Any:
    """Apply `enforce` across a payload that may be a record, a list of records,
    or a dict wrapping a 'companies'/'results'/'leads' list. aggregate_only roles
    (Data Science) are refused per-record leads output entirely."""
    policy = ROLES.get(role)
    if policy is None:
        return None
    if isinstance(payload, list):
        if policy.aggregate_only:
            return {"error": "role is aggregate_only; per-record output denied",
                    "role": role}
        return [enforce(role, r) for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for list_key in ("companies", "results", "leads", "records", "rows"):
            if list_key in payload and isinstance(payload[list_key], list):
                if policy.aggregate_only:
                    return {"error": "role is aggregate_only; per-record leads output denied",
                            "role": role}
                clone = dict(payload)
                clone[list_key] = [enforce(role, r) for r in payload[list_key]
                                   if isinstance(r, dict)]
                return clone
        return enforce(role, payload)
    return payload


# --- Artifact-level (coarse RBAC) gate -------------------------------------
# Field classification above governs the structured DATA record. Generated
# outreach NARRATIVE (pitch + dossier prose) is a different thing: it is
# Sales/BD-owned content, not a data tier. Industry-standard access control
# layers the two — coarse RBAC on whole artifacts, fine classification on
# fields within them. This is the coarse layer.
SALES_BD_ROLES = frozenset({"sales_rep", "sales_manager"})


def pitch_visible(role: str) -> bool:
    """True only for Sales/BD roles. Outreach pitch/dossier narrative is
    Sales-owned; Finance, Data Science, governance and even Leadership-ops
    never receive the raw pitch (Leadership sees deal *impact* as MNPI, not
    the sales copy). Deny-by-default for unknown roles."""
    return role in SALES_BD_ROLES

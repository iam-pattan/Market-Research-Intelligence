"""Build the Layered Data Access Architecture page (reports/access_architecture.html).

Embeds the REAL enforcement outputs of banyan_screen.policy (role matrix,
field classification, guard() applied to a synthetic record for every role)
so the page's interactive "role lens" is the actual policy, not a re-write.

Usage: python analysis/build_access_architecture.py
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from banyan_screen import policy  # noqa: E402

TEMPLATE = ROOT / "analysis" / "templates" / "access_architecture.html"
OUT = ROOT / "reports" / "access_architecture.html"

# Synthetic record — no real company or person. Field names are chosen to hit
# every classification tier so the lens shows each rule firing.
SAMPLE_RECORD = {
    "name": "Northwind Practice Systems (synthetic example)",
    "domain": "northwind-practice.example",
    "vertical": "Dental practice management",
    "region": "US",
    "rank": 41,
    "banyan_tier": "B",
    "banyan_score": 0.612,
    "notes": "Founder-owned since 2004; ~90 employees; subscription SaaS for multi-site dental groups.",
    "revenue_est_usd": 18_500_000,
    "ebitda_margin_est": 0.27,
    "contact_name": "A. Founder (synthetic)",
    "contact_email": "founder@northwind-practice.example",
    "deal_stage": "First call scheduled",
    "acquisition_intent": "Permanent-home pitch sent 2026-09-02",
    "pitch": "Hi A., you've built Northwind into the system of record for multi-site dental groups…",
}

ROLE_GROUPS = [
    ("Data Science", ["ds_analyst", "ds_lead"]),
    ("Sales / BD", ["sales_rep", "sales_manager"]),
    ("Finance", ["finance_analyst", "finance_editor", "finance_approver"]),
    ("Leadership", ["c_suite_leadership"]),
    ("Governance / platform", ["compliance_officer", "dpo_data_protection", "data_steward",
                               "access_admin", "access_reviewer_auditor", "platform_admin"]),
]

TIER_NAMES = {t: t.name for t in policy.Tier}


def count_tests(path: Path) -> int:
    files = [path] if path.is_file() else sorted(path.glob("test_*.py"))
    return sum(len(re.findall(r"^def test_", f.read_text(), re.M)) for f in files)


def role_matrix():
    out = []
    for group, roles in ROLE_GROUPS:
        for r in roles:
            p = policy.ROLES[r]
            out.append({
                "group": group,
                "role": r,
                "allowed": [TIER_NAMES[t] for t in sorted(p.allowed)],
                "masked": [TIER_NAMES[t] for t in sorted(p.masked)],
                "aggregate_only": p.aggregate_only,
                "pitch_visible": policy.pitch_visible(r),
            })
    return out


def lens():
    """Per-role outcome for every field of SAMPLE_RECORD, straight from enforce()."""
    fields = list(SAMPLE_RECORD.keys())
    classified = {k: ("SALES_NARRATIVE" if any(p in k for p in policy._PITCH_KEYS)
                      else TIER_NAMES[policy.classify(k)]) for k in fields}
    per_role = {}
    for _, roles in ROLE_GROUPS:
        for r in roles:
            p = policy.ROLES[r]
            enforced = policy.enforce(r, SAMPLE_RECORD)
            guarded_list = policy.guard(r, [SAMPLE_RECORD])
            rows = []
            for k in fields:
                if k not in enforced:
                    status = "dropped"
                elif enforced[k] != SAMPLE_RECORD[k]:
                    status = "masked"
                else:
                    status = "shown"
                rows.append({"field": k, "tier": classified[k], "status": status,
                             "value": enforced.get(k)})
            per_role[r] = {
                "fields": rows,
                "per_record_refused": isinstance(guarded_list, dict) and "error" in guarded_list,
                "pitch_visible": policy.pitch_visible(r),
                "aggregate_only": p.aggregate_only,
            }
    per_role["unknown_role"] = {
        "fields": [{"field": k, "tier": classified[k], "status": "dropped", "value": None} for k in fields],
        "per_record_refused": True, "pitch_visible": False, "aggregate_only": False,
        "note": "enforce() returns {} and guard() returns None for any role not in ROLES — deny-by-default.",
    }
    return {"record": SAMPLE_RECORD, "classified": classified, "per_role": per_role}


def main() -> None:
    payload = {
        "meta": {"built": date.today().isoformat(), "n_roles": len(policy.ROLES),
                 "policy_tests": count_tests(ROOT / "tests" / "test_policy.py"),
                 "suite_tests": count_tests(ROOT / "tests")},
        "tiers": [{"name": TIER_NAMES[t], "level": int(t)} for t in policy.Tier],
        "patterns": {
            "RESTRICTED_MNPI": list(policy._MNPI_KEYS),
            "RESTRICTED_PII": list(policy._PII_KEYS),
            "CONFIDENTIAL_FINANCIAL": list(policy._FIN_KEYS),
            "INTERNAL": list(policy._INTERNAL_SAFE),
            "default": TIER_NAMES[policy._DEFAULT_TIER],
        },
        "matrix": role_matrix(),
        "lens": lens(),
        "groups": [{"group": g, "roles": r} for g, r in ROLE_GROUPS],
    }
    html = TEMPLATE.read_text()
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    OUT.write_text(html.replace("/*__DATA__*/null", blob))
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB) — {len(payload['matrix'])} roles in lens")


if __name__ == "__main__":
    main()

from banyan_screen.policy import Tier, classify, enforce, guard, pitch_visible


SAMPLE = {
    "name": "Acme Health",
    "domain": "acme.example",
    "vertical": "Healthcare SaaS",
    "niche_leadership": 0.8,
    "revenue_est_usd": 8_000_000,
    "margin_pct": 22,
    "primary_contact_email": "jane@acme.example",
    "decision_makers": ["Jane Doe (CEO)"],
    "deal_stage": "diligence",
    "deal_intent_score": 0.91,
}


def test_classify():
    assert classify("name") == Tier.INTERNAL
    assert classify("revenue_est_usd") == Tier.CONFIDENTIAL_FINANCIAL
    assert classify("primary_contact_email") == Tier.RESTRICTED_PII
    assert classify("deal_stage") == Tier.RESTRICTED_MNPI
    # unknown field is conservative, never auto-Internal
    assert classify("some_unmapped_field") >= Tier.CONFIDENTIAL_FINANCIAL


def test_data_science_gets_no_pii_or_financials():
    out = enforce("ds_analyst", SAMPLE)
    assert "name" in out and "vertical" in out           # identity/signals OK
    assert "revenue_est_usd" not in out                  # financial dropped
    assert "margin_pct" not in out
    assert "primary_contact_email" not in out            # PII dropped
    assert "decision_makers" not in out
    assert "deal_stage" not in out and "deal_intent_score" not in out  # MNPI dropped


def test_finance_gets_financials_but_no_pii_or_mnpi():
    out = enforce("finance_analyst", SAMPLE)
    assert out["revenue_est_usd"] == 8_000_000
    assert "primary_contact_email" not in out
    assert "deal_stage" not in out


def test_sales_sees_masked_pii_no_financials():
    out = enforce("sales_rep", SAMPLE)
    assert out["primary_contact_email"].startswith("***@")   # masked, not raw
    assert "revenue_est_usd" not in out                       # no financials
    assert "deal_stage" not in out                            # no MNPI


def test_leadership_sees_mnpi_pii_masked_financial_masked():
    out = enforce("c_suite_leadership", SAMPLE)
    assert out["deal_stage"] == "diligence"                   # MNPI visible
    assert out["primary_contact_email"] == "[REDACTED:PII]" or out["primary_contact_email"].startswith("***@")
    assert out["revenue_est_usd"] == "[REDACTED:FINANCIAL]"   # financial as summary/masked


def test_platform_admin_gets_no_business_content():
    out = enforce("platform_admin", SAMPLE)
    assert "revenue_est_usd" not in out and "primary_contact_email" not in out
    assert "deal_stage" not in out


def test_unknown_role_denied_by_default():
    assert enforce("random_role", SAMPLE) == {}
    assert guard("random_role", [SAMPLE]) is None


def test_guard_over_list_and_aggregate_only():
    filtered = guard("sales_rep", [SAMPLE, SAMPLE])
    assert len(filtered) == 2 and "revenue_est_usd" not in filtered[0]
    # DS is aggregate-only: per-record leads output refused
    refused = guard("ds_analyst", [SAMPLE])
    assert isinstance(refused, dict) and "error" in refused


def test_guard_wraps_companies_key():
    out = guard("finance_analyst", {"companies": [SAMPLE], "meta": 1})
    assert out["meta"] == 1
    assert out["companies"][0]["revenue_est_usd"] == 8_000_000
    assert "primary_contact_email" not in out["companies"][0]


def test_pitch_narrative_is_sales_bd_only():
    # Coarse artifact-level gate: only Sales/BD get outreach narrative.
    assert pitch_visible("sales_rep")
    assert pitch_visible("sales_manager")
    # Everyone else — including Finance, DS, Leadership, governance — is denied.
    assert not pitch_visible("finance_analyst")
    assert not pitch_visible("ds_analyst")
    assert not pitch_visible("c_suite_leadership")
    assert not pitch_visible("platform_admin")
    assert not pitch_visible("unknown_role")


def test_enforce_agrees_with_pitch_gate_on_narrative_fields():
    # Field-level engine must give the same answer as the coarse gate: pitch
    # narrative reaches Sales/BD only, regardless of the tier a name-pattern
    # would otherwise assign (it used to fall to the CONFIDENTIAL default).
    rec = {"name": "Acme Health", "pitch": "Hi Jane…", "pitch_subject": "Your niche",
           "outreach_email": "…", "revenue_est_usd": 1}
    for role in ("sales_rep", "sales_manager"):
        out = enforce(role, rec)
        assert out["pitch"] == "Hi Jane…" and "pitch_subject" in out and "outreach_email" in out
    for role in ("finance_analyst", "c_suite_leadership", "ds_analyst", "platform_admin"):
        out = enforce(role, rec)
        assert "pitch" not in out and "pitch_subject" not in out and "outreach_email" not in out
    assert "pitch" not in enforce("unknown_role", rec)

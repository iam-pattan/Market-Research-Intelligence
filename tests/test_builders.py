import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "analysis" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


hub = _load("build_intelligence_hub")


def _screen_row(name, domain):
    terms = {k: {"score": 0.5, "confidence": 0.5, "weight": 0.1} for k in hub.BANYAN_CRITERIA}
    gterms = {k: {"score": 0.5, "confidence": 0.5, "weight": 0.1} for k in hub.GROWTH_CRITERIA}
    rat = lambda t: {"weighted_terms": t, "composite": 0.5, "overall_confidence": 0.5,
                     "confidence_discount": 0.75, "adjusted_score": 0.375, "coverage": 1.0,
                     "gate": {"rejected_on_loss": False, "revenue_capped": False, "max_tier": None}}
    return {"name": name, "domain": domain, "vertical": "V", "region": "US",
            "banyan": {"tier": "C", "adjusted": 0.375, "confidence": 0.5, "rationale": rat(terms)},
            "growth": {"tier": "C", "adjusted": 0.375, "confidence": 0.5, "rationale": rat(gterms)}}


def _record(name, domain, rev, loss, conf):
    return {"name": name, "domain": domain, "notes": f"{name} notes",
            "revenue_est_usd": {"value": rev, "confidence": conf},
            "profitability": {"score": 0.5, "confidence": conf, "loss_evidence": loss},
            "ownership_fit": {"type": "founder", "confidence": conf},
            "recurring_revenue": {"score": 0.9, "confidence": conf}}


def test_send_bucket_covers_every_recommendation_form():
    assert hub.send_bucket("send") == "send"
    assert hub.send_bucket("send — patient, values-led") == "send"
    assert hub.send_bucket("send (address to the President)") == "send"
    assert hub.send_bucket("route-to-growth-mandate") == "route-to-growth"
    assert hub.send_bucket("do-not-contact") == "do-not-contact"
    assert hub.send_bucket("do-not-contact (for acquisition outreach)") == "do-not-contact"


def test_join_uses_the_record_the_screen_scored_for_duplicate_domains():
    # Two records share a domain; run.dedup keeps the one with the higher summed
    # confidence. The hub must show THAT record's facts, not the first one seen.
    weak = _record("Acme", "acme.example", rev=1_000_000, loss=True, conf=0.2)
    strong = _record("Acme", "acme.example", rev=5_000_000, loss=False, conf=0.9)
    out = hub.build_companies([_screen_row("Acme", "acme.example")], [weak, strong], {}, set(), {})
    assert out[0]["revenue"]["value"] == 5_000_000
    assert out[0]["profit"]["loss"] is False
    assert out[0]["notes"] == "Acme notes"


def test_join_normalises_domain_like_the_screen():
    rec = _record("Acme", "https://www.acme.example/", rev=2_000_000, loss=False, conf=0.5)
    out = hub.build_companies([_screen_row("Acme", "acme.example")], [rec], {}, set(), {})
    assert out[0]["revenue"]["value"] == 2_000_000


def test_dossiers_must_align_with_top25_order():
    raw = [{"company": "HawkSoft (hawksoft.com)", "thesis": "", "fit_assessment": "", "dossier": {},
            "pitch": {"subject": "", "body": "", "personalization_note": "", "send_recommendation": "send"}}]
    top = [{"name": "HawkSoft", "domain": "hawksoft.com", "vertical": "", "region": "", "banyan_tier": "B",
            "banyan_adj": 0.6, "growth_adj": 0.4}]
    assert hub.build_dossiers(raw, top)[0]["pitch"]["bucket"] == "send"
    with pytest.raises(AssertionError):
        hub.build_dossiers(raw, [dict(top[0], name="Rentec Direct")])

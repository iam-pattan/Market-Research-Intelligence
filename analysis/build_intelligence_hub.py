"""Build the one-stop Banyan Target Intelligence hub (reports/intelligence_hub.html).

Consolidates every deliverable in data/ into a single self-contained HTML page:
top-250 screen (both rubrics, per-criterion rationale), joined raw-record
facts (revenue estimate, profitability signal, ownership, notes), macro
segments, the 25 Banyan dossiers + pitches, the market synthesis, the
triangulation summary, the outreach skill text and the rubric/validation
method. Data is embedded as JSON; the template in analysis/templates renders
it client-side.

Usage: python analysis/build_intelligence_hub.py
"""
from __future__ import annotations

import glob
import json
import re
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from banyan_screen.run import _norm_domain, dedup  # noqa: E402  (same collapse rule as the screen)
DATA = ROOT / "data"
TEMPLATE = ROOT / "analysis" / "templates" / "intelligence_hub.html"
OUT = ROOT / "reports" / "intelligence_hub.html"

BANYAN_CRITERIA = ["recurring_revenue", "profitability", "revenue_band", "niche_leadership",
                   "retention", "ownership_fit", "team_stability"]
GROWTH_CRITERIA = ["revenue_growth", "recurring_revenue", "market_size", "funding_momentum",
                   "hiring_velocity", "niche_leadership", "retention"]


def load_json(p: Path):
    with open(p) as f:
        return json.load(f)


def count_tests(path: Path) -> int:
    files = [path] if path.is_file() else sorted(path.glob("test_*.py"))
    return sum(len(re.findall(r"^def test_", f.read_text(), re.M)) for f in files)


def send_bucket(rec: str) -> str:
    r = rec.lower()
    if r.startswith("send"):
        return "send"
    if r.startswith("route"):
        return "route-to-growth"
    return "do-not-contact"


def build_companies(results, records, seg_by_domain, corroborated, dossier_idx_by_domain):
    # Same record the screen scored: run.dedup() keeps the best-sourced duplicate.
    by_domain = {_norm_domain(rec): rec for rec in dedup(records)}
    out = []
    for rank, r in enumerate(results, start=1):
        rec = by_domain[_norm_domain(r)]
        rev = rec.get("revenue_est_usd") or {}
        prof = rec.get("profitability") or {}
        own = rec.get("ownership_fit") or {}
        b, g = r["banyan"], r["growth"]
        bt, gt = b["rationale"]["weighted_terms"], g["rationale"]["weighted_terms"]
        out.append({
            "rank": rank,
            "name": r["name"],
            "domain": r["domain"],
            "vertical": r["vertical"],
            "segment": seg_by_domain.get(r["domain"].lower(), "Other Vertical SaaS"),
            "region": r["region"],
            "notes": rec.get("notes", ""),
            "ownership": own.get("type") or "unknown",
            "last_funding": own.get("last_funding"),
            "public_or_acquired": bool(rec.get("already_acquired_or_public")),
            "revenue": {"value": rev.get("value"), "conf": rev.get("confidence"),
                        "source": rev.get("source"), "below_2m": rev.get("below_2M"),
                        "above_100m": rev.get("above_100M")},
            "profit": {"score": prof.get("score"), "conf": prof.get("confidence"),
                       "loss": bool(prof.get("loss_evidence")), "source": prof.get("source")},
            "recurring_source": (rec.get("recurring_revenue") or {}).get("source"),
            "banyan": {"tier": b["tier"], "adj": round(b["adjusted"], 3),
                       "conf": round(b["confidence"], 3),
                       "composite": b["rationale"]["composite"],
                       "discount": round(b["rationale"]["confidence_discount"], 3),
                       "coverage": round(b["rationale"]["coverage"], 2),
                       "gate": b["rationale"]["gate"],
                       "criteria": [{"k": k, **bt[k]} for k in BANYAN_CRITERIA if k in bt]},
            "growth": {"tier": g["tier"], "adj": round(g["adjusted"], 3),
                       "conf": round(g["confidence"], 3),
                       "composite": g["rationale"]["composite"],
                       "discount": round(g["rationale"]["confidence_discount"], 3),
                       "coverage": round(g["rationale"]["coverage"], 2),
                       "gate": g["rationale"]["gate"],
                       "criteria": [{"k": k, **gt[k]} for k in GROWTH_CRITERIA if k in gt]},
            "corroborated": r["name"].lower() in corroborated,
            "dossier": dossier_idx_by_domain.get(r["domain"].lower()),
        })
    return out


def build_dossiers(raw, top25):
    out = []
    assert len(raw) == len(top25), "dossier/top25 length mismatch"
    for i, (d, t) in enumerate(zip(raw, top25)):
        head = t["name"].split()[0].lower()
        assert head in d["company"].lower(), f"dossier {i} ({d['company']!r}) != top25 {t['name']!r}"
        out.append({
            "idx": i,
            "name": t["name"],
            "domain": t["domain"],
            "vertical": t["vertical"],
            "region": t["region"],
            "banyan_tier": t["banyan_tier"],
            "banyan_adj": t["banyan_adj"],
            "growth_adj": t["growth_adj"],
            "company_label": d["company"],
            "thesis": d["thesis"],
            "fit_assessment": d["fit_assessment"],
            "dossier": d["dossier"],
            "pitch": {**d["pitch"], "bucket": send_bucket(d["pitch"]["send_recommendation"])},
        })
    return out


def main() -> None:
    results = load_json(DATA / "screen" / "results.json")
    records = []
    for f in sorted(glob.glob(str(DATA / "records" / "*.json"))):
        records += load_json(Path(f))
    segments = load_json(DATA / "research" / "segments.json")
    seg_by_domain = {c["domain"].lower(): s for s, v in segments.items() for c in v["companies"]}
    crossmatch = load_json(DATA / "research" / "crossmatch.json")
    corroborated = {c.lower() for c in crossmatch["corroborated"]}
    raw_dossiers = load_json(DATA / "research" / "raw_dossiers_banyan.json")
    top25 = load_json(DATA / "research" / "top25_banyan.json")
    synthesis = load_json(DATA / "research" / "market_synthesis.json")
    grounding = load_json(DATA / "research" / "grounding_validation.json")
    banyan_cfg = yaml.safe_load(open(ROOT / "config.yaml"))
    growth_cfg = yaml.safe_load(open(ROOT / "config.growth.yaml"))

    dossiers = build_dossiers(raw_dossiers, top25)
    dossier_idx_by_domain = {d["domain"].lower(): d["idx"] for d in dossiers}
    companies = build_companies(results, records, seg_by_domain, corroborated, dossier_idx_by_domain)

    seg_summary = [{
        "name": s,
        "n": v["n"],
        "fit_count": v["banyan_fit_count"],
        "fit_density": v["banyan_fit_density"],
        "regions": v["regions"],
    } for s, v in segments.items()]

    skill_dir = ROOT / "skills" / "banyan-sales-pitch"
    skill_md = (skill_dir / "SKILL.md").read_text()
    skill_md = re.sub(r"^---.*?---\s*", "", skill_md, count=1, flags=re.S)  # strip frontmatter

    payload = {
        "meta": {
            "built": date.today().isoformat(),
            "n_companies": len(companies),
            "n_records": len(records),
            "n_dossiers": len(dossiers),
            "send": sum(1 for d in dossiers if d["pitch"]["bucket"] == "send"),
            "route": sum(1 for d in dossiers if d["pitch"]["bucket"] == "route-to-growth"),
            "dnc": sum(1 for d in dossiers if d["pitch"]["bucket"] == "do-not-contact"),
            "n_segments": len(segments),
            "n_verticals": len({c["vertical"] for c in companies}),
            "banyan_tiers": {t: sum(1 for c in companies if c["banyan"]["tier"] == t)
                             for t in ["A", "B", "C", "insufficient_data", "rejected"]},
            "growth_tiers": {t: sum(1 for c in companies if c["growth"]["tier"] == t)
                             for t in ["A", "B", "C", "insufficient_data", "rejected"]},
            "crossmatch": crossmatch["summary"],
            "grounding": {"rate": grounding["overall_rate"], "total": grounding["total_facts"],
                          "grounded": grounding["grounded"]},
            # QC round scores are recorded in docs/HANDOFF.md §6 (not reproducible here).
            "qc": {"round1": {"review": 65.9, "glm": 74.6, "kimi": 57.2},
                   "round2": {"review": 66.9, "glm": 81.0, "kimi": 52.8},
                   "tests": count_tests(ROOT / "tests"),
                   "policy_tests": count_tests(ROOT / "tests" / "test_policy.py")},
        },
        "rubrics": {"banyan": banyan_cfg, "growth": growth_cfg},
        "companies": companies,
        "dossiers": dossiers,
        "segments": seg_summary,
        "market": synthesis["synthesis"],
        "briefs": synthesis["briefs"],
        "playbook": {
            "skill": skill_md,
            "templates": (skill_dir / "templates.md").read_text(),
            "playbook": (skill_dir / "banyan_playbook.md").read_text(),
        },
    }

    html = TEMPLATE.read_text()
    blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = html.replace("/*__DATA__*/null", blob)
    OUT.write_text(html)
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB) — {len(companies)} companies, "
          f"{len(dossiers)} dossiers, {payload['meta']['send']} SEND")


if __name__ == "__main__":
    main()

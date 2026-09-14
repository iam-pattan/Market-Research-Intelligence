"""Re-derive every figure shown on the consolidated pages from the source data.

Reads the JSON payload embedded in reports/intelligence_hub.html and
reports/access_architecture.html and checks it against data/, the
screen's own dedup rule and banyan_screen.policy. Exits non-zero on any
mismatch so it can run in CI after the builders.

Usage: python analysis/qc_consolidated_pages.py
"""
from __future__ import annotations

import collections
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from banyan_screen import policy  # noqa: E402
from banyan_screen.run import _norm_domain, dedup  # noqa: E402

DATA = ROOT / "data"
FAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


def payload(path: Path):
    html = path.read_text()
    m = re.search(r"const D = (\{.*?\});\nconst \$ ", html, re.S)
    return json.loads(m.group(1).replace("<\\/", "</")), html


def load(p):
    return json.load(open(p))


def qc_hub() -> None:
    P, H = payload(ROOT / "reports" / "intelligence_hub.html")
    res = load(DATA / "screen" / "results.json")
    recs = [r for f in sorted(glob.glob(str(DATA / "records" / "*.json"))) for r in load(f)]
    tiers = collections.Counter(r["banyan"]["tier"] for r in res)
    M = P["meta"]

    check("n companies", M["n_companies"] == len(res) == len(P["companies"]))
    check("n records", M["n_records"] == len(recs))
    for t in ("A", "B", "C", "rejected", "insufficient_data"):
        check(f"tier {t}", M["banyan_tiers"][t] == tiers.get(t, 0))
    check("tiers sum", sum(M["banyan_tiers"].values()) == len(res))
    check("n verticals", M["n_verticals"] == len({r["vertical"] for r in res}))

    d = load(DATA / "research" / "raw_dossiers_banyan.json")
    t25 = load(DATA / "research" / "top25_banyan.json")
    send = sum(1 for x in d if x["pitch"]["send_recommendation"].lower().startswith("send"))
    check("SEND count", M["send"] == send)
    check("send+route+dnc = dossiers", M["send"] + M["route"] + M["dnc"] == M["n_dossiers"] == len(d))
    check("dossiers aligned to top25", [x["name"] for x in P["dossiers"]] == [t["name"] for t in t25])
    check("pitch text verbatim", all(x["pitch"]["body"] == y["pitch"]["body"] and x["thesis"] == y["thesis"]
                                     for x, y in zip(P["dossiers"], d)))
    check("dossier links resolve to same domain",
          all(P["dossiers"][c["dossier"]]["domain"] == c["domain"] for c in P["companies"] if c["dossier"] is not None)
          and sum(1 for c in P["companies"] if c["dossier"] is not None) == len(d))

    cm = load(DATA / "research" / "crossmatch.json")
    corr = {c.lower() for c in cm["corroborated"]}
    check("corroborated flags", sum(1 for c in P["companies"] if c["corroborated"])
          == sum(1 for r in res if r["name"].lower() in corr))
    check("crossmatch summary passthrough", M["crossmatch"] == cm["summary"])

    seg = load(DATA / "research" / "segments.json")
    check("segments n sum", sum(s["n"] for s in P["segments"]) == sum(v["n"] for v in seg.values()) == len(res))
    check("segment fit_count sum == tier B", sum(s["fit_count"] for s in P["segments"]) == tiers["B"])

    # Per-row fidelity against the screen and the record the screen scored.
    best = {_norm_domain(r): r for r in dedup(recs)}
    bad = []
    for c, r in zip(P["companies"], res):
        rec = best[_norm_domain(r)]
        if c["name"] != r["name"] or c["banyan"]["tier"] != r["banyan"]["tier"] \
                or abs(c["banyan"]["adj"] - round(r["banyan"]["adjusted"], 3)) > 1e-9 \
                or c["growth"]["tier"] != r["growth"]["tier"]:
            bad.append("score:" + c["name"])
        if c["revenue"]["value"] != rec["revenue_est_usd"].get("value") \
                or c["profit"]["loss"] != bool(rec["profitability"].get("loss_evidence")) \
                or c["notes"] != rec.get("notes", ""):
            bad.append("record:" + c["name"])
        terms = r["banyan"]["rationale"]["weighted_terms"]
        for k in c["banyan"]["criteria"]:
            if k["score"] != terms[k["k"]]["score"] or k["weight"] != terms[k["k"]]["weight"]:
                bad.append("criteria:" + c["name"])
    check("per-row score/record/criteria fidelity", not bad, ", ".join(bad[:5]))
    check("no loss-evidence row outside 'rejected'",
          not [c for c in P["companies"] if c["profit"]["loss"] and c["banyan"]["tier"] != "rejected"])

    ms = load(DATA / "research" / "market_synthesis.json")
    check("market synthesis passthrough", P["market"] == ms["synthesis"] and P["briefs"] == ms["briefs"])
    g = load(DATA / "research" / "grounding_validation.json")
    check("grounding", M["grounding"]["rate"] == g["overall_rate"] and M["grounding"]["grounded"] == g["grounded"]
          and M["grounding"]["total"] == g["total_facts"])
    skill = ROOT / "skills" / "banyan-sales-pitch"
    check("templates verbatim", P["playbook"]["templates"] == (skill / "templates.md").read_text())
    check("playbook verbatim", P["playbook"]["playbook"] == (skill / "banyan_playbook.md").read_text())

    ids = re.findall(r'\bid="([^"]+)"', H)
    check("hub: no duplicate ids", len(ids) == len(set(ids)))
    check("hub: placeholder replaced", "/*__DATA__*/null" not in H)
    check("hub: under 16MB", len(H.encode()) < 16_000_000)
    hosts = set(re.findall(r'https?://([^/"\s]+)', H.split("<script>")[0]))
    check("hub: external hosts are fonts only", hosts <= {"fonts.googleapis.com"}, str(hosts))


def qc_access() -> None:
    A, HA = payload(ROOT / "reports" / "access_architecture.html")
    rec = A["lens"]["record"]
    check("matrix roles == policy.ROLES", {m["role"] for m in A["matrix"]} == set(policy.ROLES))
    check("n_roles", A["meta"]["n_roles"] == len(policy.ROLES))
    for role, pr in A["lens"]["per_role"].items():
        if role == "unknown_role":
            check("unknown role denied", policy.enforce("nobody", rec) == {} and policy.guard("nobody", [rec]) is None)
            continue
        enf = policy.enforce(role, rec)
        ok = True
        for f in pr["fields"]:
            k = f["field"]
            exp = "dropped" if k not in enf else ("masked" if enf[k] != rec[k] else "shown")
            if exp != f["status"] or (exp != "dropped" and enf[k] != f["value"]):
                ok = False
        ok = ok and pr["pitch_visible"] == policy.pitch_visible(role) \
            and pr["per_record_refused"] == isinstance(policy.guard(role, [rec]), dict)
        check(f"lens matches enforce(): {role}", ok)
    st = lambda role, k: next(f["status"] for f in A["lens"]["per_role"][role]["fields"] if f["field"] == k)
    check("DS: no revenue/contact/deal, per-record refused",
          all(st(r, k) == "dropped" for r in ("ds_analyst", "ds_lead") for k in ("revenue_est_usd", "contact_email", "deal_stage"))
          and all(A["lens"]["per_role"][r]["per_record_refused"] for r in ("ds_analyst", "ds_lead")))
    check("sales: contact masked, revenue dropped, deal dropped, pitch shown",
          st("sales_rep", "contact_email") == "masked" and st("sales_rep", "revenue_est_usd") == "dropped"
          and st("sales_rep", "deal_stage") == "dropped" and st("sales_rep", "pitch") == "shown")
    check("finance: revenue shown, contact dropped, deal dropped, pitch dropped",
          st("finance_analyst", "revenue_est_usd") == "shown" and st("finance_analyst", "contact_email") == "dropped"
          and st("finance_analyst", "deal_stage") == "dropped" and st("finance_analyst", "pitch") == "dropped")
    check("leadership: deal shown, revenue masked, contact masked, pitch dropped",
          st("c_suite_leadership", "deal_stage") == "shown" and st("c_suite_leadership", "revenue_est_usd") == "masked"
          and st("c_suite_leadership", "contact_email") == "masked" and st("c_suite_leadership", "pitch") == "dropped")
    check("pitch visible only for Sales/BD",
          {r for r, p in A["lens"]["per_role"].items() if p["pitch_visible"]} == set(policy.SALES_BD_ROLES))
    check("classification patterns match policy",
          A["patterns"]["RESTRICTED_PII"] == list(policy._PII_KEYS) and A["patterns"]["INTERNAL"] == list(policy._INTERNAL_SAFE)
          and all(policy.classify(p) == policy.Tier.INTERNAL for p in policy._INTERNAL_SAFE))
    ids = re.findall(r'\bid="([^"]+)"', HA)
    check("access: no duplicate ids", len(ids) == len(set(ids)))
    check("access: placeholder replaced", "/*__DATA__*/null" not in HA)


def main() -> int:
    qc_hub()
    qc_access()
    print(f"\n{'OK' if not FAILS else 'FAILED'} — {len(FAILS)} failing check(s)" + (": " + ", ".join(FAILS) if FAILS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())

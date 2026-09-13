#!/usr/bin/env python3
"""3-way cross-match: pass-1 (vertical screen) x pass-2 (acquirer-adjacency) x
pass-3 (OSINT), plus the OSINT ownership-verification overlay.

Buckets:
  - corroborated : found by >=2 independent passes  -> validates the screen
  - net_new      : found ONLY by pass-2 / pass-3     -> candidates we missed
  - ours_only    : pass-1 only                       -> (count only; the bulk)
Overlay: OSINT verification (is_founder_owned / flag) + filed financials.

Honest scope: coverage/consistency + ownership check. Not independent financial
verification (all passes share the public-web + registries ceiling).
"""
from __future__ import annotations
import glob
import html
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
RESEARCH = ROOT / "data" / "research"
REPORTS = ROOT / "reports"
E = lambda s: html.escape(str(s if s is not None else ""))

_SUFFIX = re.compile(
    r"\b(inc|llc|ltd|limited|plc|corp|corporation|gmbh|pty|oy|ab|srl|s\.?a|co|company|"
    r"software|systems|technologies|technology|group|holdings|solutions|labs|inc\.)\b", re.I)


def norm_name(n: str) -> str:
    n = (n or "").lower()
    n = re.sub(r"\(.*?\)", " ", n)          # drop parentheticals "(formerly …)"
    n = n.split(" — ")[0].split(" - ")[0]   # drop trailing descriptors
    n = _SUFFIX.sub(" ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def reg_domain(d: str) -> str:
    if not d:
        return ""
    d = d.strip().lower().split("//")[-1].split("/")[0].removeprefix("www.")
    return d


# ---- load pass 1 (discovery universe + scored) ----
p1 = {}   # key -> {name, domain, vertical, region}
scored = {}
for fp in glob.glob(str(ROOT / "data" / "records" / "*.json")):
    for r in json.load(open(fp)):
        dom = reg_domain(r.get("domain", ""))
        key = dom or norm_name(r["name"])
        p1[key] = {"name": r["name"], "domain": dom,
                   "vertical": r.get("vertical", ""), "region": r.get("hq_region", "")}
for r in json.load(open(ROOT / "data" / "screen" / "results.json")):
    key = reg_domain(r.get("domain", "")) or norm_name(r["name"])
    scored[key] = {"banyan": r["banyan"]["adjusted"], "banyan_tier": r["banyan"]["tier"],
                   "growth": r["growth"]["adjusted"]}

P1_NAMEIDX = {norm_name(v["name"]): k for k, v in p1.items()}


def in_p1(name: str, domain: str) -> bool:
    dom = reg_domain(domain)
    if dom and dom in p1:
        return True
    nn = norm_name(name)
    return nn in P1_NAMEIDX or nn in p1


# ---- load pass 2 (acquirer-adjacency) ----
p2_raw = []
for a in json.load(open(RESEARCH / "independent_results.json"))["angles"]:
    for c in a["companies"]:
        c = dict(c); c["_angle"] = a["angle"]; p2_raw.append(c)

# ---- load pass 3 (OSINT) ----
osint = json.load(open(RESEARCH / "osint_results.json"))
p3_raw = []
for a in osint["discovery"]:
    for c in a["companies"]:
        c = dict(c); c["_angle"] = a["angle"]; p3_raw.append(c)
verifications = osint.get("verification", [])
VER = {norm_name(v["company"]): v for v in verifications}


def key_of(c) -> str:
    return reg_domain(c.get("domain", "")) or norm_name(c["name"])


# ---- build master union ----
master = {}   # key -> record with pass flags
def add(c, passname):
    k = key_of(c)
    m = master.setdefault(k, {"name": c["name"], "domain": reg_domain(c.get("domain", "")),
                              "vertical": c.get("vertical", ""), "region": c.get("region", ""),
                              "passes": set(), "ownership": "", "filed_financials": "",
                              "size_signal": "", "fit_note": "", "angles": set()})
    m["passes"].add(passname)
    if c.get("_angle"):
        m["angles"].add(c["_angle"])
    for src, dst in [("ownership", "ownership"), ("filed_financials", "filed_financials"),
                     ("size_signal", "size_signal"), ("banyan_fit_note", "fit_note")]:
        if c.get(src) and not m[dst]:
            m[dst] = c[src]
    if not m["vertical"] and c.get("vertical"):
        m["vertical"] = c["vertical"]

for k, v in p1.items():
    master[k] = {"name": v["name"], "domain": v["domain"], "vertical": v["vertical"],
                 "region": v["region"], "passes": {"p1"}, "ownership": "",
                 "filed_financials": "", "size_signal": "", "fit_note": "", "angles": set()}
for c in p2_raw:
    add(c, "p2")
for c in p3_raw:
    add(c, "p3")

# attach verification overlay
for m in master.values():
    v = VER.get(norm_name(m["name"]))
    if v:
        m["verified_owner"] = v.get("verified_owner_type", "")
        m["is_founder_owned"] = v.get("is_founder_owned")
        m["flag"] = v.get("flag", "")
        if v.get("filed_or_reported_financials") and not m["filed_financials"]:
            m["filed_financials"] = v["filed_or_reported_financials"]

# ---- buckets ----
def npasses(m): return len(m["passes"])
corroborated = [m for m in master.values() if npasses(m) >= 2]
net_new = [m for m in master.values() if "p1" not in m["passes"]]
ours_only = [m for m in master.values() if m["passes"] == {"p1"}]

# net_new confidence ranking: filed financials > founder/family ownership > has-domain
def own_class(m):
    # Authoritative signal FIRST: the OSINT verification boolean, where present.
    if m.get("is_founder_owned") is True:
        return ("founder", "founder/family (verified)")
    if m.get("is_founder_owned") is False:
        fl = (m.get("flag", "") or "").lower()
        return ("vc", "VC-backed — exclude") if "vc" in fl else ("pe", "PE/growth-held — exclude")
    # Fallback substring heuristic for UN-verified names. PE/VC take precedence,
    # and bare "privately held"/"private" do NOT imply founder-ownership (a PE
    # portfolio company is also privately held) — require explicit founder words.
    o = (m.get("ownership", "") + " " + str(m.get("verified_owner", ""))).lower()
    fl = (m.get("flag", "") or "").lower()
    if "vc" in fl or "venture" in o or "vc-backed" in o:
        return ("vc", "VC-backed — exclude")
    if ("pe" in fl or "private equity" in o or "pe-" in o or "growth-equity" in o
            or "growth equity" in o or "recapitaliz" in o):
        return ("pe", "PE/growth-held — secondary")
    if any(w in o for w in ("founder", "family", "bootstrap", "employee-owned", "closely held")):
        return ("founder", "founder/family/bootstrapped")
    return ("unknown", "unverified")

for m in net_new:
    m["_own"] = own_class(m)
    m["_conf"] = (2 if m["filed_financials"] else 0) + (1 if m["_own"][0] == "founder" else 0)
net_new.sort(key=lambda m: (-m["_conf"], m["_own"][0] != "founder", m["name"].lower()))

# net-new that are strong: founder/family owned, OR filed financials from a
# NON-PE/VC company (PE/VC with filed financials must NOT count as a strong
# permanent-home candidate — QC catch).
strong_new = [m for m in net_new
              if m["_own"][0] == "founder"
              or (m["filed_financials"] and m["_own"][0] not in ("vc", "pe"))]

# ownership overlay: PE/VC caught among names anywhere in our union
mislabeled = [m for m in master.values()
              if m.get("is_founder_owned") is False]

summary = {
    "p1_universe": len(p1), "p2_candidates": len(p2_raw), "p3_candidates": len(p3_raw),
    "union_total": len(master), "corroborated": len(corroborated),
    "net_new": len(net_new), "strong_net_new": len(strong_new),
    "ours_only": len(ours_only), "verifications": len(verifications),
    "pe_vc_caught": len(mislabeled),
}
json.dump({"summary": summary,
           "net_new": [{k: (list(v) if isinstance(v, set) else v) for k, v in m.items()} for m in net_new],
           "corroborated": [m["name"] for m in corroborated]},
          open(RESEARCH / "crossmatch.json", "w"), indent=1, default=str)


# ---------- render ----------
def passchips(m):
    order = [("p1", "screen"), ("p2", "adjacency"), ("p3", "OSINT")]
    return "".join(f'<span class="pc {p}">{lbl}</span>' for p, lbl in order if p in m["passes"])

def own_badge(cls):
    k, lbl = cls
    return f'<span class="ob {k}">{E(lbl)}</span>'

def new_rows(rows):
    out = []
    for m in rows:
        fin = E(m["filed_financials"][:90]) if m["filed_financials"] else '<span class="dim">—</span>'
        out.append(
            f'<tr><td class="co">{E(m["name"])}{("<br><span class=dim>"+E(m["domain"])+"</span>") if m["domain"] else ""}</td>'
            f'<td>{E(m["vertical"][:46])}</td><td>{E(m["region"][:22])}</td>'
            f'<td>{own_badge(m["_own"])}</td><td class="fin">{fin}</td>'
            f'<td>{passchips(m)}</td></tr>')
    return "".join(out)

def corr_rows():
    rows = sorted(corroborated, key=lambda m: (-npasses(m), m["name"].lower()))
    out = []
    for m in rows:
        sc = scored.get(reg_domain(m["domain"]) or norm_name(m["name"]))
        sctxt = f'{sc["banyan"]:.3f}/{sc["banyan_tier"]}' if sc else "—"
        vo = ""
        if m.get("is_founder_owned") is True:
            vo = '<span class="ob founder">founder ✓</span>'
        elif m.get("is_founder_owned") is False:
            vo = '<span class="ob vc">not founder ✗</span>'
        out.append(
            f'<tr><td class="co">{E(m["name"])}</td><td>{E(m["vertical"][:42])}</td>'
            f'<td class="num">{npasses(m)}×</td><td>{passchips(m)}</td>'
            f'<td class="num">{sctxt}</td><td>{vo}</td></tr>')
    return "".join(out)

def ver_rows():
    out = []
    for v in sorted(verifications, key=lambda v: (v.get("is_founder_owned") is not False)):
        fo = v.get("is_founder_owned")
        cls = "founder" if fo is True else ("vc" if fo is False else "unknown")
        badge = "founder-owned ✓" if fo is True else ("NOT founder — exclude ✗" if fo is False else "uncertain")
        fin = E((v.get("filed_or_reported_financials") or "")[:80]) or '<span class="dim">—</span>'
        out.append(
            f'<tr class="{cls}"><td class="co">{E(v["company"])}</td>'
            f'<td><span class="ob {cls}">{badge}</span></td>'
            f'<td>{E(v.get("verified_owner_type","")[:60])}</td>'
            f'<td>{E((v.get("latest_investor_or_acquirer") or "")[:40])}</td>'
            f'<td class="fin">{fin}</td></tr>')
    return "".join(out)

s = summary
HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Banyan — 3-Way Cross-Match</title>
<style>
:root{{--ink:#0f1a2b;--mut:#5b6b82;--line:#e3e8ef;--bg:#f5f7fa;--card:#fff;--brand:#0b4f6c;
--ok:#12805c;--okbg:#e7f6ef;--warn:#9a6b00;--warnbg:#fef6e3;--bad:#a02533;--badbg:#fbeaec;}}
*{{box-sizing:border-box}}body{{margin:0;font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}}
.wrap{{max-width:1180px;margin:0 auto;padding:28px 20px 90px}}
header.top{{border-bottom:3px solid var(--brand);padding-bottom:14px}} header.top h1{{margin:0 0 4px;font-size:26px;color:var(--brand)}}
.sub{{color:var(--mut);font-size:14px}}
.cards{{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:12px 16px;min-width:120px}}
.kpi b{{font-size:24px;display:block;color:var(--brand)}} .kpi span{{font-size:12px;color:var(--mut)}}
.kpi.good b{{color:var(--ok)}} .kpi.bad b{{color:var(--bad)}}
h2.sec{{margin:30px 0 8px;font-size:19px;border-bottom:2px solid var(--line);padding-bottom:6px}}
p.note{{color:var(--mut);font-size:13px;margin:4px 0 10px}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:13px}}
th{{background:#0e1c2b;color:#fff;text-align:left;padding:8px 10px;font-size:12px}} td{{padding:7px 10px;border-top:1px solid var(--line);vertical-align:top}}
td.co{{font-weight:700;width:180px}} td.num{{text-align:center;width:60px;font-variant-numeric:tabular-nums}} td.fin{{font-size:12px;color:#33465e}}
.dim{{color:#9aa7b6}}
.pc{{font-size:10.5px;font-weight:700;border-radius:5px;padding:1px 6px;margin-right:3px}}
.pc.p1{{background:#eef2f7;color:#4a5a70}} .pc.p2{{background:#e7eef9;color:#2b5aa8}} .pc.p3{{background:var(--okbg);color:var(--ok)}}
.ob{{font-size:11px;font-weight:700;border-radius:12px;padding:2px 9px;white-space:nowrap}}
.ob.founder{{background:var(--okbg);color:var(--ok)}} .ob.pe{{background:var(--warnbg);color:var(--warn)}} .ob.vc{{background:var(--badbg);color:var(--bad)}} .ob.unknown{{background:#eef2f7;color:#667}}
tr.vc td.co,tr.pe td.co{{color:var(--bad)}}
.banner{{border-radius:10px;padding:14px 18px;margin:14px 0;font-size:13.5px}}
.banner.ok{{background:var(--okbg);border:1px solid #bfe6d5}} .banner.warn{{background:var(--warnbg);border:1px solid #f0deb0}}
footer{{margin-top:36px;color:var(--mut);font-size:12px;border-top:1px solid var(--line);padding-top:14px}}
@media(max-width:720px){{td.co{{width:auto}}}}
</style></head><body><div class="wrap">
<header class="top"><h1>3-Way Discovery Cross-Match</h1>
<div class="sub">Independent triangulation for Banyan M&amp;A: pass-1 vertical screen × pass-2 acquirer-adjacency × pass-3 OSINT (+ ownership verification)</div></header>

<div class="cards">
  <div class="kpi"><b>{s['p1_universe']}</b><span>pass-1 universe</span></div>
  <div class="kpi"><b>{s['p2_candidates']}</b><span>pass-2 (adjacency)</span></div>
  <div class="kpi"><b>{s['p3_candidates']}</b><span>pass-3 (OSINT)</span></div>
  <div class="kpi good"><b>{s['corroborated']}</b><span>corroborated (≥2 passes)</span></div>
  <div class="kpi good"><b>{s['strong_net_new']}</b><span>strong net-new</span></div>
  <div class="kpi"><b>{s['net_new']}</b><span>net-new total</span></div>
  <div class="kpi bad"><b>{s['pe_vc_caught']}</b><span>false "founder-owned" caught</span></div>
</div>

<div class="banner ok"><b>How to read this:</b> pass-2 and pass-3 used deliberately DIFFERENT sourcing than pass-1 (acquirer-portfolio adjacency; OSINT registries), so heavy overlap was never the goal — <b>corroboration validates the names it hits, and net-new is the payoff</b> (companies our vertical screen missed). Low overlap + high net-new = the independent passes expanded coverage rather than echoing pass-1.</div>

<h2 class="sec">① Strong net-new candidates <span class="sub">— not in pass-1; founder/family-owned or with filed financials</span></h2>
<p class="note">The actionable output: run these through <code>banyan_screen</code> to slot into the ranking. Ordered by confidence (real filed financials first, then verified founder/family ownership). VC/PE names are excluded from this table.</p>
<table><thead><tr><th>Company</th><th>Vertical</th><th>Region</th><th>Ownership</th><th>Filed / reported financials</th><th>Found by</th></tr></thead>
<tbody>{new_rows(strong_new)}</tbody></table>

<h2 class="sec">② Corroborated — found independently by ≥2 passes <span class="sub">({s['corroborated']})</span></h2>
<p class="note">Independent re-discovery = a confidence signal for the screen. Score shown is pass-1's confidence-discounted banyan_adj/tier where available; ✓/✗ = OSINT ownership verification.</p>
<table><thead><tr><th>Company</th><th>Vertical</th><th>Passes</th><th>Found by</th><th>Banyan score</th><th>Ownership check</th></tr></thead>
<tbody>{corr_rows()}</tbody></table>

<h2 class="sec">③ Ownership-verification overlay <span class="sub">— OSINT truth on {s['verifications']} known names</span></h2>
<div class="banner warn"><b>{s['pe_vc_caught']} names that look independent are NOT</b> — caught by OSINT (registries, cap-table, M&amp;A news). These must be excluded from permanent-home outreach even though they scored as fits. Vagaro (PE recap), Agiloft (FTV), Tripleseat (Vista) and the VC-backed cluster are confirmed here.</div>
<table><thead><tr><th>Company</th><th>Verdict</th><th>Verified owner</th><th>Investor / acquirer</th><th>Filed / reported financials</th></tr></thead>
<tbody>{ver_rows()}</tbody></table>

<footer>
Union of {s['union_total']} distinct companies across three passes; {s['ours_only']} are pass-1-only (the bulk — not listed).
Matched on registrable domain (primary) + normalized name. <b>Honest scope:</b> all passes share the public-web + registries ceiling (no paid data) — this is a coverage / consistency + ownership check, <b>not</b> independent financial verification. OSINT filed financials (UK Companies House / EU registries) are the exception and carry real numbers. Data: data/research/{{independent_results,osint_results,crossmatch}}.json.
</footer>
</div></body></html>"""

(REPORTS / "crossmatch.html").write_text(HTML, encoding="utf-8")
print("=== CROSS-MATCH SUMMARY ===")
for k, v in summary.items():
    print(f"  {k:16s}: {v}")
print(f"\nstrong net-new (sample): " + ", ".join(m['name'] for m in strong_new[:12]))
print(f"PE/VC caught: " + ", ".join(m['name'] for m in mislabeled))
print(f"\nwrote reports/crossmatch.html + data/research/crossmatch.json")

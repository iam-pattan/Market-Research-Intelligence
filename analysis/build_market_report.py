#!/usr/bin/env python3
"""Assemble the 250-wide market synthesis into a self-contained HTML report."""
from __future__ import annotations
import html
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
SYN = json.load(open(ROOT / "data" / "research" / "market_synthesis.json"))
SEGS = json.load(open(ROOT / "data" / "research" / "segments.json"))
S = SYN["synthesis"]
BRIEFS = {b["segment"]: b for b in SYN["briefs"]}

E = lambda s: html.escape(str(s if s is not None else ""))
def nl2br(s): return E(s).replace("\n", "<br>")


def band(attr: str) -> str:
    a = (attr or "").lower()
    if "high" in a and "medium" not in a:
        return "hi"
    if "medium" in a:
        return "med"
    if "low" in a or "off" in a or "band 3" in a:
        return "lo"
    return "med"


def density_for(seg_name: str):
    # segments.json keys are the macro-segment names; ranked names may be embellished.
    for k, v in SEGS.items():
        key = k.split(" (")[0].lower()
        if key in seg_name.lower() or seg_name.lower()[:12] in k.lower():
            return v
    return None


def ranked_rows() -> str:
    out = []
    for i, r in enumerate(S["segments_ranked"], 1):
        seg = r["segment"]
        d = density_for(seg)
        b = band(r.get("attractiveness", ""))
        n = d["n"] if d else "—"
        fit = d["banyan_fit_count"] if d else "—"
        dens = d["banyan_fit_density"] if d else "—"
        out.append(
            f'<tr class="{b}"><td class="rk">{i}</td>'
            f'<td class="sg">{E(seg)}</td>'
            f'<td class="at"><span class="pill {b}">{E(r.get("attractiveness","—"))}</span></td>'
            f'<td class="num">{n}</td><td class="num">{fit}</td><td class="num">{dens}</td>'
            f'<td class="ra">{E(r["rationale"])}</td></tr>'
        )
    return "".join(out)


def shortlist_rows() -> str:
    out = []
    for i, t in enumerate(S["prioritized_shortlist"], 1):
        out.append(
            f'<tr><td class="rk">{i}</td><td class="co">{E(t["company"])}</td>'
            f'<td class="sg">{E(t.get("segment",""))}</td><td class="why">{E(t["why"])}</td></tr>'
        )
    return "".join(out)


def li(items): return "".join(f"<li>{nl2br(x)}</li>" for x in items)


def brief_cards() -> str:
    cards = []
    # order briefs by the ranked-segment order
    order = [r["segment"] for r in S["segments_ranked"]]
    seen = set()
    ordered = []
    for name in order:
        for bs, b in BRIEFS.items():
            if bs not in seen and (bs.lower()[:12] in name.lower() or name.lower()[:12] in bs.lower()):
                ordered.append(b); seen.add(bs); break
    for b in BRIEFS.values():
        if b["segment"] not in seen:
            ordered.append(b); seen.add(b["segment"])

    for b in ordered:
        d = density_for(b["segment"])
        chips = ""
        if d:
            chips = (f'<span class="chip">n={d["n"]}</span>'
                     f'<span class="chip">B-fit {d["banyan_fit_count"]}</span>'
                     f'<span class="chip">density {d["banyan_fit_density"]}</span>')
        targets = "".join(
            f'<li><b>{E(t["name"])}</b> — {E(t["why"])}</li>' for t in (b.get("top_targets") or [])
        )
        acq = ", ".join(E(a) for a in (b.get("competing_acquirers") or []))
        srcs = " · ".join(
            f'<a href="{E(u)}" target="_blank" rel="noopener">{E(u.split("//")[-1].split("/")[0])}</a>'
            for u in (b.get("sources") or [])[:8]
        )
        cards.append(f"""
        <details class="brief">
          <summary><span class="bt">{E(b['segment'])}</span>{chips}</summary>
          <div class="bbody">
            <div class="bblk"><h4>Market overview</h4><p>{nl2br(b['market_overview'])}</p></div>
            <div class="bblk"><h4>Consolidation state</h4><p>{nl2br(b['consolidation_state'])}</p></div>
            <div class="bblk"><h4>Banyan-fit read</h4><p>{nl2br(b['banyan_fit_read'])}</p></div>
            <div class="bblk"><h4>Top targets (our cohort)</h4><ul>{targets}</ul></div>
            <div class="bblk"><h4>Whitespace</h4><p>{nl2br(b.get('whitespace',''))}</p></div>
            <div class="bblk"><h4>Precedent M&amp;A / comps</h4><p>{nl2br(b.get('precedent_ma',''))}</p></div>
            <div class="bblk"><h4>Competing acquirers</h4><p>{acq}</p></div>
            <div class="bblk"><h4>Risks</h4><p>{nl2br(b.get('risks',''))}</p></div>
            {'<div class="bblk src"><h4>Sources</h4><p>'+srcs+'</p></div>' if srcs else ''}
          </div>
        </details>""")
    return "".join(cards)


HTML = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Banyan — 250-Company Market Synthesis</title>
<style>
:root{{--ink:#0f1a2b;--mut:#5b6b82;--line:#e3e8ef;--bg:#f5f7fa;--card:#fff;--brand:#0b4f6c;
--hi:#12805c;--hibg:#e7f6ef;--med:#9a6b00;--medbg:#fef6e3;--lo:#a02533;--lobg:#fbeaec;}}
*{{box-sizing:border-box}}body{{margin:0;font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}}
.wrap{{max-width:1180px;margin:0 auto;padding:28px 20px 90px}}
header.top{{border-bottom:3px solid var(--brand);padding-bottom:16px}}
header.top h1{{margin:0 0 4px;font-size:27px;color:var(--brand)}}
.sub{{color:var(--mut);font-size:14px}}
h2.sec{{margin:34px 0 10px;font-size:20px;border-bottom:2px solid var(--line);padding-bottom:6px}}
.exec{{background:var(--card);border:1px solid var(--line);border-left:5px solid var(--brand);border-radius:12px;padding:18px 22px;margin:18px 0;font-size:14.5px;line-height:1.65}}
table{{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;font-size:13px}}
th{{background:#0e1c2b;color:#fff;text-align:left;padding:9px 10px;font-size:12px;font-weight:600}}
td{{padding:8px 10px;border-top:1px solid var(--line);vertical-align:top}}
td.rk{{color:var(--mut);font-weight:700;width:28px}} td.num{{text-align:center;width:52px;font-variant-numeric:tabular-nums}}
td.sg{{font-weight:600;width:210px}} td.co{{font-weight:700;width:170px}} td.ra,td.why{{color:#2b3a4f}}
tr.hi td.sg{{border-left:3px solid var(--hi)}} tr.med td.sg{{border-left:3px solid var(--med)}} tr.lo td.sg{{border-left:3px solid var(--lo)}}
.pill{{font-size:11px;font-weight:700;border-radius:20px;padding:2px 9px;white-space:nowrap}}
.pill.hi{{background:var(--hibg);color:var(--hi)}} .pill.med{{background:var(--medbg);color:var(--med)}} .pill.lo{{background:var(--lobg);color:var(--lo)}}
ul.themes{{margin:6px 0;padding-left:20px}} ul.themes li{{margin-bottom:9px;font-size:14px}}
ul.ws{{columns:2;column-gap:26px;padding-left:20px}} ul.ws li{{margin-bottom:8px;font-size:13.5px;break-inside:avoid}}
.cons{{display:flex;flex-wrap:wrap;gap:8px;margin:8px 0}} .cons span{{background:#eef2f7;border:1px solid var(--line);border-radius:8px;padding:5px 11px;font-size:13px;font-weight:600;color:#33465e}}
.caveats{{background:var(--lobg);border:1px solid #eecdd2;border-radius:10px;padding:14px 18px;margin:12px 0}} .caveats li{{font-size:13px;margin-bottom:6px;color:#7a2531}}
details.brief{{background:var(--card);border:1px solid var(--line);border-radius:10px;margin:9px 0;overflow:hidden}}
details.brief summary{{cursor:pointer;padding:12px 16px;font-weight:700;display:flex;align-items:center;gap:10px;flex-wrap:wrap;list-style:none}}
details.brief summary::-webkit-details-marker{{display:none}}
details.brief summary:before{{content:"▸";color:var(--brand);font-weight:700}} details.brief[open] summary:before{{content:"▾"}}
.bt{{color:var(--brand);font-size:15px}} .chip{{font-size:11px;font-weight:600;background:#eef2f7;color:#4a5a70;border-radius:6px;padding:2px 8px}}
.bbody{{padding:4px 18px 16px;display:grid;grid-template-columns:1fr 1fr;gap:6px 26px}}
.bblk h4{{margin:10px 0 2px;font-size:11.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--brand)}}
.bblk p{{margin:0;font-size:13px;color:#2b3a4f}} .bblk ul{{margin:2px 0;padding-left:18px;font-size:13px}}
.bblk.src{{grid-column:1/-1}} .bblk.src a{{color:var(--brand);margin-right:2px}}
footer{{margin-top:40px;color:var(--mut);font-size:12px;border-top:1px solid var(--line);padding-top:14px}}
@media(max-width:820px){{.bbody{{grid-template-columns:1fr}} ul.ws{{columns:1}}}}
</style></head><body><div class="wrap">

<header class="top">
  <h1>250-Company Market Synthesis</h1>
  <div class="sub">Banyan Software M&amp;A · 14 macro-segments × deep codex market/M&amp;A research → cross-segment thesis · 29-agent workflow</div>
</header>

<h2 class="sec">Executive summary</h2>
<div class="exec">{nl2br(S['executive_summary'])}</div>

<h2 class="sec">Segments ranked for Banyan's thesis</h2>
<p class="sub">Attractiveness = fit to the buy-and-hold thesis (profitable, founder-owned niche leaders — not VC growth). N / B-fit / density are from the deterministic screen; <b>tier C ≠ bad fit</b> (private financials unverifiable), so density understates the true target pool everywhere except the AI-native segments where density 0 is literally true.</p>
<table><thead><tr><th>#</th><th>Segment</th><th>Attractiveness</th><th>N</th><th>B-fit</th><th>Density</th><th>Rationale</th></tr></thead>
<tbody>{ranked_rows()}</tbody></table>

<h2 class="sec">Prioritized shortlist — {len(S['prioritized_shortlist'])} genuine Banyan candidates</h2>
<table><thead><tr><th>#</th><th>Company</th><th>Segment</th><th>Why</th></tr></thead>
<tbody>{shortlist_rows()}</tbody></table>

<h2 class="sec">Cross-segment themes</h2>
<ul class="themes">{li(S['cross_segment_themes'])}</ul>

<h2 class="sec">Whitespace — thickest, least-contested consolidation opportunity</h2>
<ul class="ws">{li(S['whitespace_ranked'])}</ul>

<h2 class="sec">Competing consolidators — who Banyan bids against</h2>
<div class="cons">{''.join(f'<span>{E(c)}</span>' for c in S['competing_consolidators'])}</div>

<h2 class="sec">Caveats</h2>
<div class="caveats"><ul>{li(S['caveats'])}</ul></div>

<h2 class="sec">Segment briefs (detailed)</h2>
{brief_cards()}

<footer>
  Generated from a 29-agent workflow (14 segments × [codex deep market/M&amp;A research → structured brief] + cross-segment synthesis).
  Research is public web (cited per brief). Scores are the deterministic screen's confidence-discounted <code>banyan_adj</code>.
  Banyan self-reported figures are positioning, not audited. Names may bleed across segments (keyword roll-up) — de-contaminate before outreach.
</footer>
</div></body></html>"""

if __name__ == "__main__":
    out = ROOT / "reports" / "market_synthesis.html"
    out.write_text(HTML, encoding="utf-8")
    print(f"wrote {out}  ({out.stat().st_size:,} bytes)")

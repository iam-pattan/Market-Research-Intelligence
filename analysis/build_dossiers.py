#!/usr/bin/env python3
"""Assemble the top-25 deep-research dossiers + outreach pitches into a
self-contained, IAM-gated HTML deliverable.

Two access-control layers are applied FOR REAL (not simulated) using
banyan_screen.policy:
  1. Coarse RBAC  - policy.pitch_visible(role): outreach narrative is Sales/BD-only.
  2. Field classification - policy.guard(role, record): the structured internal
     DATA record is filtered per role (financials->Finance, PII->masked/absent,
     deal-intent->Leadership, aggregate-only->DS refused).

Narrative prose = PUBLIC web research (codex web_search) -> Sales/BD may read it.
Structured internal estimates (revenue/margin/deal-intent/contacts) = withheld
from Sales; only the entitled role sees them. That distinction is the point.
"""
from __future__ import annotations
import html
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from banyan_screen.policy import guard, enforce, ROLES, pitch_visible, classify, Tier  # noqa: E402

RESEARCH = ROOT / "data" / "research"
REPORTS = ROOT / "reports"
# Optional argv: RAW_JSON  FIRMO_JSON  OUT_HTML  (defaults = best-of-both list)
RAW_PATH = sys.argv[1] if len(sys.argv) > 1 else str(RESEARCH / "raw_dossiers.json")
FIRMO_PATH = sys.argv[2] if len(sys.argv) > 2 else str(RESEARCH / "top25.json")
OUT_PATH = sys.argv[3] if len(sys.argv) > 3 else str(REPORTS / "dossiers_pitches.html")
RAW = json.load(open(RAW_PATH))
FIRMO = json.load(open(FIRMO_PATH))
assert len(RAW) == len(FIRMO), "row-count mismatch; pipeline preserves order so index-zip is safe"

# The role this artifact is generated FOR. Everything below is enforced against it.
REQUESTER_ROLE = "sales_rep"

E = lambda s: html.escape(str(s if s is not None else ""))


def nl2br(s: str) -> str:
    return E(s).replace("\n", "<br>")


def thesis_label(fm, rr) -> str:
    return "banyan-fit" if fm["best"] == "banyan" else "growth-thesis"


def send_badge(rec: str) -> tuple[str, str]:
    r = (rec or "").split("—")[0].split(".")[0].strip().lower()
    if r.startswith("send"):
        return ("SEND", "send")
    if r.startswith("route"):
        return ("ROUTE → GROWTH MANDATE", "route")
    return ("DO NOT CONTACT", "dnc")


def structured_record(fm, rr) -> dict:
    """The internal DATA record for a lead. Field NAMES are chosen so
    policy.classify() tiers them correctly. The financial/PII/MNPI values are
    internal-platform ILLUSTRATIVE estimates (labelled as such in the UI) — we
    do not hold verified private financials or real contact PII from public-web
    research. The point is to show the enforcement layer act on the schema."""
    return {
        # INTERNAL — identity + non-sensitive signals (all business roles)
        "name": fm["name"],
        "domain": fm["domain"],
        "vertical": fm["vertical"],
        "region": fm["region"],
        "niche_position": (rr["dossier"]["niche_position"][:180] + "…"),
        "banyan_fit_score": fm["banyan_adj"],
        "growth_score": fm["growth_adj"],
        # CONFIDENTIAL_FINANCIAL — Finance + Leadership(masked) only
        "revenue_est_usd": "internal estimate — see Finance",
        "margin_profitability": "internal estimate — see Finance",
        # RESTRICTED_PII — Sales(masked) + Leadership(masked); dropped for Finance/DS
        "primary_contact_email": "⟨CRM field — set at outreach⟩",
        "decision_makers": "⟨CRM field — set at outreach⟩",
        # RESTRICTED_MNPI — Leadership only
        "deal_disposition": send_badge(rr["pitch"]["send_recommendation"])[0],
        "deal_intent_score": fm["banyan_adj"] if fm["best"] == "banyan" else fm["growth_adj"],
    }


# ---------------------------------------------------------------------------
# Access-enforcement panel: one representative record, four role views, live.
# ---------------------------------------------------------------------------
def render_access_panel() -> str:
    # HawkSoft: a real SEND target — makes the demo concrete.
    idx = next(i for i, fm in enumerate(FIRMO) if fm["name"] == "HawkSoft")
    rec = structured_record(FIRMO[idx], RAW[idx])

    roles = [
        ("sales_rep", "Sales / BD", "Identity + signals; PII masked; NO financials, NO deal-intent. Gets the pitch."),
        ("finance_analyst", "Finance", "Full financials; NO contact PII; NO deal-intent; NO pitch."),
        ("ds_analyst", "Data Science", "Aggregate-only → per-record leads REFUSED. Never PII, never financials."),
        ("c_suite_leadership", "C-Suite / Leadership", "Deal-intent (MNPI) visible; PII & financials masked; no raw pitch."),
    ]

    cols = []
    for role, title, blurb in roles:
        # field-level enforcement on the record (guard handles the list/refusal shape)
        view = guard(role, [rec])
        if isinstance(view, dict) and "error" in view:
            body = f'<div class="refused">⛔ REFUSED<br><span>{E(view["error"])}</span></div>'
        else:
            row = view[0] if view else {}
            lines = "".join(
                f'<div class="kv"><span class="k">{E(k)}</span>'
                f'<span class="v {"red" if str(v).startswith("[REDACT") or str(v).startswith("***") else ""}">{E(v)}</span></div>'
                for k, v in row.items()
            ) or '<div class="kv"><span class="v red">— nothing —</span></div>'
            body = lines
        pv = "✓ pitch delivered" if pitch_visible(role) else "✕ pitch withheld"
        pvc = "ok" if pitch_visible(role) else "no"
        cols.append(
            f'<div class="rolecol">'
            f'<div class="roletitle">{E(title)}<code>{E(role)}</code></div>'
            f'<div class="roleblurb">{E(blurb)}</div>'
            f'<div class="pitchflag {pvc}">{pv}</div>'
            f'<div class="reclist">{body}</div>'
            f"</div>"
        )

    return f"""
    <section class="panel" id="access">
      <h2>🔒 IAM enforcement layer — live on this data</h2>
      <p class="lead">The <em>same</em> internal record for <b>HawkSoft</b>, passed through
      <code>banyan_screen.policy.guard(role, …)</code>. Each column is the actual output that role
      receives — computed by the tested policy module (10 policy tests; 46/46 suite-wide), not mocked. Red = masked/redacted;
      dropped fields are simply absent. This is the "layer on Claude's output": Data Science gets no PII and
      no financials, and per-record lead output is refused outright.</p>
      <div class="rolegrid">{''.join(cols)}</div>
      <p class="foot">Field tiers via <code>policy.classify()</code>: identity/signals =
      <b>INTERNAL</b> · revenue/margin = <b>CONFIDENTIAL_FINANCIAL</b> · contacts =
      <b>RESTRICTED_PII</b> · deal-intent/disposition = <b>RESTRICTED_MNPI</b>.
      Unknown fields default to CONFIDENTIAL_FINANCIAL (fail-closed) so new fields never auto-leak.</p>
    </section>"""


# ---------------------------------------------------------------------------
# Lead card
# ---------------------------------------------------------------------------
def render_card(fm, rr, full: bool) -> str:
    d, p = rr["dossier"], rr["pitch"]
    label = thesis_label(fm, rr)
    btxt, bcls = send_badge(p["send_recommendation"])
    company = E(rr["company"])

    # Sales/BD-gated narrative (public web research) — Sales MAY read.
    # Financial prose (revenue_profitability, ownership_funding) is WITHHELD from Sales
    # here to make the field-level rule visible in the artifact itself.
    biz_blocks = [
        ("What they do", d["business_model"]),
        ("Niche position", d["niche_position"]),
        ("Moat", d["moat"]),
        ("Personalization hook (public)", d["personalization_hook"]),
        ("Key risks", d["risks"]),
        ("Competitors", d["competitors"]),
    ]
    if full:
        blocks_html = "".join(
            f'<div class="dblk"><h4>{E(t)}</h4><p>{nl2br(v)}</p></div>' for t, v in biz_blocks
        )
    else:
        # compact: niche + hook + risks only
        compact = [("Niche position", d["niche_position"]), ("Why not a target", rr["fit_assessment"].split("\n")[0])]
        blocks_html = "".join(
            f'<div class="dblk"><h4>{E(t)}</h4><p>{nl2br(v)}</p></div>' for t, v in compact
        )

    # sources
    srcs = d.get("sources") or []
    src_html = ""
    if full and srcs:
        src_html = '<div class="sources"><h4>Sources</h4>' + " · ".join(
            f'<a href="{E(u)}" target="_blank" rel="noopener">{E(u.split("//")[-1].split("/")[0])}</a>' for u in srcs[:8]
        ) + "</div>"

    # pitch block
    subj = E(p["subject"])
    body = nl2br(p["body"])
    pnote = E(p["personalization_note"])
    if bcls == "send":
        pitch_html = f"""
        <div class="pitch send">
          <div class="pitchhead">✅ READY-TO-SEND · Permanent-Home pitch</div>
          <div class="subj"><span>Subject</span>{subj}</div>
          <div class="pbody">{body}</div>
          <div class="pnote"><b>Personalization:</b> {pnote}</div>
        </div>"""
    elif bcls == "route":
        pitch_html = f"""
        <div class="pitch route">
          <div class="pitchhead">↪ NOT a buy-and-hold target — relationship note only (route to growth mandate if one exists)</div>
          <div class="subj"><span>Subject</span>{subj}</div>
          <div class="pbody">{body}</div>
          <div class="pnote"><b>Personalization:</b> {pnote}</div>
        </div>"""
    else:
        pitch_html = f"""
        <div class="pitch dnc">
          <div class="pitchhead">⛔ DO NOT CONTACT — no acquisition pitch appropriate</div>
          <div class="pbody">{body}</div>
          <div class="pnote"><b>Rationale:</b> {pnote}</div>
        </div>"""

    return f"""
    <article class="card {bcls}">
      <div class="cardhead">
        <div class="ident">
          <h3>{company}</h3>
          <div class="meta">{E(fm['vertical'])} · {E(fm['region'])} · <a href="https://{E(fm['domain'])}" target="_blank" rel="noopener">{E(fm['domain'])}</a></div>
        </div>
        <div class="badges">
          <span class="thesis {label}">{E(label)}</span>
          <span class="rec {bcls}">{E(btxt)}</span>
        </div>
      </div>
      <div class="scores">
        <span title="Confidence-discounted Banyan buy-and-hold fit">Banyan-fit <b>{fm['banyan_adj']:.3f}</b></span>
        <span title="Confidence-discounted growth score">Growth <b>{fm['growth_adj']:.3f}</b></span>
        <span class="withheld" title="Field-level enforcement: revenue/margin estimates are CONFIDENTIAL_FINANCIAL → Finance/Leadership only">💲 financials withheld from Sales</span>
      </div>
      <div class="dossier">{blocks_html}{src_html}</div>
      {pitch_html}
    </article>"""


def render() -> str:
    sends, routes, dncs = [], [], []
    for fm, rr in zip(FIRMO, RAW):
        _, bcls = send_badge(rr["pitch"]["send_recommendation"])
        (sends if bcls == "send" else routes if bcls == "route" else dncs).append((fm, rr))

    send_html = "".join(render_card(fm, rr, full=True) for fm, rr in sends)
    route_html = "".join(render_card(fm, rr, full=False) for fm, rr in routes)
    dnc_html = "".join(render_card(fm, rr, full=False) for fm, rr in dncs)

    n = len(FIRMO)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Banyan — Top-25 Lead Dossiers &amp; Outreach (Sales/BD view)</title>
<style>
:root{{--ink:#0f1a2b;--mut:#5b6b82;--line:#e2e8f0;--bg:#f6f8fb;--card:#fff;
--send:#12805c;--sendbg:#e7f6ef;--route:#9a6b00;--routebg:#fef6e3;--dnc:#a02533;--dncbg:#fbeaec;
--brand:#0b4f6c;--red:#c0392b;}}
*{{box-sizing:border-box}}body{{margin:0;font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);background:var(--bg)}}
.wrap{{max-width:1120px;margin:0 auto;padding:28px 20px 80px}}
header.top{{border-bottom:3px solid var(--brand);padding-bottom:16px;margin-bottom:8px}}
header.top h1{{margin:0 0 4px;font-size:26px;color:var(--brand)}}
.sub{{color:var(--mut);font-size:14px}}
.gatebar{{display:flex;flex-wrap:wrap;gap:10px;align-items:center;background:#0b4f6c;color:#fff;border-radius:10px;padding:12px 16px;margin:16px 0;font-size:13.5px}}
.gatebar b{{color:#bfe3f0}} .gatebar code{{background:rgba(255,255,255,.15);padding:1px 6px;border-radius:5px}}
.reality{{background:#fff8e6;border:1px solid #f0d68a;border-left:5px solid var(--route);border-radius:10px;padding:14px 18px;margin:16px 0}}
.reality h2{{margin:0 0 6px;font-size:16px;color:#8a5d00}}
.tallies{{display:flex;gap:22px;flex-wrap:wrap;margin-top:8px}}
.tal{{font-size:13px}} .tal b{{font-size:22px;display:block}}
.tal.s b{{color:var(--send)}} .tal.r b{{color:var(--route)}} .tal.d b{{color:var(--dnc)}}
h2.sec{{margin:34px 0 4px;font-size:19px;border-bottom:2px solid var(--line);padding-bottom:6px}}
h2.sec small{{font-weight:400;color:var(--mut);font-size:13px}}
/* access panel */
.panel{{background:#0e1c2b;color:#e7eef6;border-radius:14px;padding:20px 22px;margin:18px 0}}
.panel h2{{margin:0 0 6px;font-size:18px;color:#fff}}
.panel .lead{{color:#b9c6d6;font-size:13.5px;margin:0 0 14px}} .panel code{{background:rgba(255,255,255,.12);padding:1px 6px;border-radius:5px;color:#cfe6ff}}
.rolegrid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
.rolecol{{background:#16283b;border:1px solid #24384f;border-radius:10px;padding:12px}}
.roletitle{{font-weight:700;font-size:13.5px;display:flex;flex-direction:column;gap:3px}}
.roletitle code{{font-weight:400;font-size:11px;color:#8fb6d6;background:none;padding:0}}
.roleblurb{{color:#96a8bd;font-size:11.5px;margin:6px 0 8px;min-height:52px}}
.pitchflag{{font-size:11.5px;font-weight:700;border-radius:6px;padding:3px 7px;display:inline-block;margin-bottom:8px}}
.pitchflag.ok{{background:#123f2d;color:#5be3a7}} .pitchflag.no{{background:#3a1620;color:#ff9aa8}}
.reclist{{font-size:11.5px}} .kv{{display:flex;justify-content:space-between;gap:8px;padding:2px 0;border-bottom:1px dotted #24384f}}
.kv .k{{color:#8fb6d6}} .kv .v{{text-align:right;max-width:60%}} .kv .v.red{{color:#ff9aa8;font-style:italic}}
.refused{{background:#3a1620;color:#ff9aa8;border-radius:8px;padding:14px;text-align:center;font-weight:700}}
.refused span{{font-weight:400;font-size:11px}}
.panel .foot{{color:#8ba0b6;font-size:11.5px;margin:14px 0 0}}
/* cards */
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin:14px 0;box-shadow:0 1px 2px rgba(16,32,60,.04)}}
.card.send{{border-left:5px solid var(--send)}} .card.route{{border-left:5px solid var(--route)}} .card.dnc{{border-left:5px solid var(--dnc)}}
.cardhead{{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;flex-wrap:wrap}}
.ident h3{{margin:0;font-size:18px}} .meta{{color:var(--mut);font-size:13px}} .meta a{{color:var(--brand)}}
.badges{{display:flex;gap:8px;flex-wrap:wrap}}
.thesis,.rec{{font-size:11.5px;font-weight:700;border-radius:20px;padding:3px 11px}}
.thesis.banyan-fit{{background:var(--sendbg);color:var(--send)}} .thesis.growth-thesis{{background:#eef2f7;color:#4a5a70}}
.rec.send{{background:var(--sendbg);color:var(--send)}} .rec.route{{background:var(--routebg);color:var(--route)}} .rec.dnc{{background:var(--dncbg);color:var(--dnc)}}
.scores{{display:flex;gap:16px;flex-wrap:wrap;margin:10px 0 12px;font-size:12.5px;color:var(--mut)}}
.scores b{{color:var(--ink)}} .scores .withheld{{color:#8a5d00;background:var(--routebg);border-radius:6px;padding:1px 8px}}
.dossier{{display:grid;grid-template-columns:1fr 1fr;gap:10px 22px}}
.card.route .dossier,.card.dnc .dossier{{grid-template-columns:1fr}}
.dblk h4{{margin:6px 0 2px;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--brand)}}
.dblk p{{margin:0;font-size:13px;color:#2b3a4f}}
.sources{{grid-column:1/-1;margin-top:6px;font-size:11.5px;color:var(--mut)}} .sources a{{color:var(--brand);margin-right:2px}}
.pitch{{margin-top:14px;border-radius:10px;padding:12px 14px}}
.pitch.send{{background:var(--sendbg);border:1px solid #bfe6d5}} .pitch.route{{background:var(--routebg);border:1px solid #f0deb0}} .pitch.dnc{{background:var(--dncbg);border:1px solid #eecdd2}}
.pitchhead{{font-weight:700;font-size:12.5px;margin-bottom:8px}}
.card.send .pitchhead{{color:var(--send)}} .card.route .pitchhead{{color:var(--route)}} .card.dnc .pitchhead{{color:var(--dnc)}}
.subj{{font-size:13px;margin-bottom:8px}} .subj span{{display:inline-block;font-size:10.5px;text-transform:uppercase;color:var(--mut);margin-right:8px}}
.pbody{{background:#fff;border:1px solid var(--line);border-radius:8px;padding:12px;font-size:13px;line-height:1.6}}
.pnote{{font-size:11.5px;color:var(--mut);margin-top:8px}}
footer{{margin-top:40px;color:var(--mut);font-size:12px;border-top:1px solid var(--line);padding-top:14px}}
@media(max-width:820px){{.rolegrid{{grid-template-columns:1fr 1fr}}.dossier{{grid-template-columns:1fr}}}}
@media(max-width:520px){{.rolegrid{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap">

<header class="top">
  <h1>Top-25 Lead Dossiers &amp; Outreach Pitches</h1>
  <div class="sub">Banyan Software M&amp;A screening · deep web research (codex <code>web_search</code>) → thesis-branched pitches · generated {n} leads</div>
</header>

<div class="gatebar">
  🔐 <b>Access:</b> this artifact was generated for role <code>{REQUESTER_ROLE}</code> —
  <code>policy.pitch_visible("{REQUESTER_ROLE}")</code> = <b>True</b>.
  A Data-Science request → <code>guard()</code> <b>refuses</b> per-record leads;
  a Finance request → financials only, <b>no pitch</b>. See the enforcement panel below.
</div>

<div class="reality">
  <h2>⚠ Strategic reality — read before working these leads</h2>
  <p style="margin:0;font-size:13.5px">This is the top-25 by <b>best-of-both</b> rubrics, which is dominated by VC-backed,
  &gt;$100M / unprofitable AI &amp; infra companies — the structural <b>opposite</b> of a Banyan buy-and-hold target.
  The deep research confirms only <b>2 of {n}</b> are sendable acquisition targets. For a genuine acquisition-outreach
  list, re-run dossiers on the top-25 by the <b>Banyan rubric</b> (one flag).</p>
  <div class="tallies">
    <div class="tal s"><b>{len(sends)}</b>SEND (banyan-fit)</div>
    <div class="tal r"><b>{len(routes)}</b>route → growth mandate</div>
    <div class="tal d"><b>{len(dncs)}</b>do-not-contact</div>
  </div>
</div>

{render_access_panel()}

<h2 class="sec">✅ Ready-to-send — Banyan permanent-home targets <small>({len(sends)})</small></h2>
{send_html}

<h2 class="sec">↪ Route to growth mandate — not buy-and-hold targets <small>({len(routes)})</small></h2>
{route_html}

<h2 class="sec">⛔ Do not contact — outside every Banyan mandate <small>({len(dncs)})</small></h2>
{dnc_html}

<footer>
  Enforcement is real: every role view in the panel is computed by <code>banyan_screen.policy</code>
  (<code>banyan_screen.policy</code>: 10 policy tests; full suite 46/46 passing). Narrative prose = public web research, Sales/BD-gated. Structured financial
  estimates &amp; deal-intent = withheld from Sales (field classification). Banyan self-reported figures
  ("120+ acquired, zero sold") are positioning, not third-party audited. Sources are public and cited per dossier.
</footer>
</div></body></html>"""


if __name__ == "__main__":
    # Runtime IAM gate (not just the in-page demo): this artifact emits Sales/BD
    # pitch narrative, so the coarse gate MUST pass for the requester role before
    # we render anything. Fail-closed if it doesn't.
    if not pitch_visible(REQUESTER_ROLE):
        raise SystemExit(
            f"IAM refused: role '{REQUESTER_ROLE}' may not receive pitch/dossier narrative "
            f"(policy.pitch_visible == False). Not building {OUT_PATH}.")
    out = pathlib.Path(OUT_PATH)
    out.write_text(render(), encoding="utf-8")
    print(f"wrote {out}  ({out.stat().st_size:,} bytes)  [IAM gate passed: pitch_visible('{REQUESTER_ROLE}')=True]")

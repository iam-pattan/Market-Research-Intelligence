"""Render dual-rubric screening results to a self-contained HTML dashboard, plus
CSV and JSON exports. Neutral theme (external subject, not PayPal-branded)."""
from __future__ import annotations
import csv
import html
import json
import os
from typing import Any

_TIER_COLOR = {
    "A": "#1a7f37", "B": "#9a6700", "C": "#8250df",
    "insufficient_data": "#6e7781", "rejected": "#cf222e",
}


def _badge(tier: str) -> str:
    return (f'<span style="background:{_TIER_COLOR.get(tier, "#6e7781")};color:#fff;'
            f'padding:2px 8px;border-radius:10px;font-size:12px;font-weight:600">{html.escape(tier)}</span>')


def _rows(scored: list[dict[str, Any]]) -> str:
    out = []
    for i, r in enumerate(scored, 1):
        co = r["company"]
        b, g = r["banyan"], r["growth"]
        if b.adjusted_score >= g.adjusted_score:
            best_lbl, bt = "Banyan", b
        else:
            best_lbl, bt = "Growth", g
        best_cell = f"{best_lbl} {_badge(bt.tier.value)} {bt.adjusted_score:.3f}"
        acq = co.extra.get("already_acquired_or_public")
        out.append(
            "<tr>"
            f'<td data-sort="{i}">{i}</td>'
            f'<td data-sort="{bt.adjusted_score:.4f}">{best_cell}</td>'
            f"<td>{html.escape(co.name)}"
            + (' <span title="already acquired or public" style="color:#cf222e">⚑</span>' if acq else "")
            + f'<br><span style="color:#6e7781;font-size:12px">{html.escape(co.domain or "")}</span></td>'
            f"<td>{html.escape(str(co.extra.get('vertical') or ''))}</td>"
            f"<td>{html.escape(co.country or '')}</td>"
            f"<td>{_badge(b.tier.value)}</td>"
            f'<td data-sort="{b.adjusted_score:.4f}">{b.adjusted_score:.3f}</td>'
            f'<td data-sort="{b.overall_confidence:.4f}">{b.overall_confidence:.2f}</td>'
            f"<td>{_badge(g.tier.value)}</td>"
            f'<td data-sort="{g.adjusted_score:.4f}">{g.adjusted_score:.3f}</td>'
            f'<td data-sort="{g.overall_confidence:.4f}">{g.overall_confidence:.2f}</td>'
            f'<td style="max-width:320px;font-size:12px;color:#57606a">{html.escape((co.extra.get("notes") or "")[:240])}</td>'
            "</tr>"
        )
    return "\n".join(out)


def render_html(scored: list[dict[str, Any]]) -> str:
    return f"""<!doctype html><html lang=en><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Banyan M&A Screening</title>
<style>
 body{{font:14px -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:0;background:#f6f8fa;color:#1f2328}}
 .wrap{{max-width:1200px;margin:0 auto;padding:24px 16px}}
 h1{{font-size:22px;margin:0 0 4px}} .sub{{color:#57606a;margin:0 0 16px}}
 table{{border-collapse:collapse;width:100%;background:#fff;border:1px solid #d0d7de;border-radius:8px;overflow:hidden}}
 th,td{{padding:8px 10px;border-bottom:1px solid #eaeef2;text-align:left;vertical-align:top}}
 th{{background:#f6f8fa;cursor:pointer;user-select:none;font-size:12px;text-transform:uppercase;letter-spacing:.03em;color:#57606a}}
 tr:hover td{{background:#f6f8fa}}
 .legend{{margin:12px 0;font-size:12px;color:#57606a}}
</style>
<div class=wrap>
<h1>Banyan M&A — dual-rubric candidate screening</h1>
<p class=sub>{len(scored)} companies · scored under the Banyan-fit and Growth rubrics · click a header to sort · ⚑ = already acquired/public</p>
<p class=legend>Tiers: {_badge('A')} {_badge('B')} {_badge('C')} {_badge('insufficient_data')} {_badge('rejected')} &nbsp; Every score is confidence-discounted; low confidence = thinly sourced.</p>
<table id=t>
<thead><tr>
<th>#</th><th>Best fit</th><th>Company</th><th>Vertical</th><th>Region</th>
<th>Banyan tier</th><th>Banyan adj</th><th>Banyan conf</th>
<th>Growth tier</th><th>Growth adj</th><th>Growth conf</th><th>Notes</th>
</tr></thead>
<tbody>
{_rows(scored)}
</tbody></table>
</div>
<script>
const t=document.getElementById('t');
t.querySelectorAll('th').forEach((th,i)=>th.onclick=()=>{{
 const rows=[...t.tBodies[0].rows];
 const asc=th.dataset.asc=th.dataset.asc==='1'?'':'1';
 rows.sort((a,b)=>{{
  const x=a.cells[i].dataset.sort??a.cells[i].innerText, y=b.cells[i].dataset.sort??b.cells[i].innerText;
  const nx=parseFloat(x),ny=parseFloat(y);
  const c=(!isNaN(nx)&&!isNaN(ny))?nx-ny:String(x).localeCompare(String(y));
  return asc?c:-c;
 }});
 rows.forEach(r=>t.tBodies[0].appendChild(r));
}});
</script>
</html>"""


def write_outputs(scored: list[dict[str, Any]], out_dir: str) -> dict[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    html_path = os.path.join(out_dir, "dashboard.html")
    csv_path = os.path.join(out_dir, "ranked.csv")
    json_path = os.path.join(out_dir, "results.json")

    with open(html_path, "w") as fh:
        fh.write(render_html(scored))

    with open(csv_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["rank", "best_thesis", "best_adj", "name", "domain", "vertical", "region",
                    "banyan_tier", "banyan_adj", "banyan_conf",
                    "growth_tier", "growth_adj", "growth_conf", "already_acquired_or_public"])
        for i, r in enumerate(scored, 1):
            co, b, g = r["company"], r["banyan"], r["growth"]
            best_thesis = "banyan" if b.adjusted_score >= g.adjusted_score else "growth"
            best_adj = max(b.adjusted_score, g.adjusted_score)
            w.writerow([i, best_thesis, f"{best_adj:.3f}", co.name, co.domain,
                        co.extra.get("vertical"), co.country,
                        b.tier.value, f"{b.adjusted_score:.3f}", f"{b.overall_confidence:.3f}",
                        g.tier.value, f"{g.adjusted_score:.3f}", f"{g.overall_confidence:.3f}",
                        co.extra.get("already_acquired_or_public")])

    with open(json_path, "w") as fh:
        json.dump([{
            "name": r["company"].name, "domain": r["company"].domain,
            "vertical": r["company"].extra.get("vertical"), "region": r["company"].country,
            "banyan": {"tier": r["banyan"].tier.value, "adjusted": r["banyan"].adjusted_score,
                       "confidence": r["banyan"].overall_confidence, "rationale": r["banyan"].rationale},
            "growth": {"tier": r["growth"].tier.value, "adjusted": r["growth"].adjusted_score,
                       "confidence": r["growth"].overall_confidence, "rationale": r["growth"].rationale},
        } for r in scored], fh, indent=2)

    return {"html": html_path, "csv": csv_path, "json": json_path}

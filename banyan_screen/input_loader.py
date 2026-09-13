"""Load a user-supplied seed list (CSV/XLSX of ~500 companies) into records.

Columns are auto-mapped by header heuristics (override with an explicit mapping).
Any firmographic the export PROVIDES becomes a high-confidence ("seed_list")
signal; anything absent is left at low confidence and flagged for web enrichment,
so the scoring core naturally discounts un-provided criteria until they are filled.

Caveat: revenue parsing normalizes magnitudes ($/£/€, k/m/b) but does NOT convert
currencies — a value in GBP is treated as its numeric USD-equivalent magnitude.
Flag currency in the seed if it matters.
"""
from __future__ import annotations
import re
from typing import Any

import pandas as pd

_ALIASES = {
    "name": ["name", "company", "company_name", "company name", "organization",
             "organisation", "account name", "account_name"],
    "domain": ["domain", "website", "url", "web", "site", "homepage", "web site"],
    "country": ["country", "hq", "hq_region", "region", "location", "headquarters", "geo"],
    "vertical": ["vertical", "industry", "sector", "category", "niche", "market"],
    "revenue": ["revenue", "annual_revenue", "annual revenue", "arr", "revenue_usd",
                "turnover", "est_revenue", "estimated revenue"],
    "employees": ["employees", "headcount", "employee_count", "staff", "team_size",
                  "size", "num_employees", "# employees"],
    "ownership": ["ownership", "owner", "investor", "investors", "funding",
                  "ownership_type", "backing", "owner_type"],
    "founded": ["founded", "founded_year", "year_founded", "incorporated", "founding year"],
    "description": ["description", "notes", "about", "summary", "desc"],
}

_MULT = {"k": 1e3, "m": 1e6, "mm": 1e6, "b": 1e9, "bn": 1e9,
         "thousand": 1e3, "million": 1e6, "billion": 1e9}


def _canon_columns(cols) -> dict[str, str]:
    """Map canonical field -> actual column name present in the sheet."""
    lower = {str(c).strip().lower(): c for c in cols}
    out: dict[str, str] = {}
    for field, aliases in _ALIASES.items():
        for a in aliases:
            if a in lower:
                out[field] = lower[a]
                break
    return out


def parse_money(x: Any) -> float | None:
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip().lower().replace(",", "").replace("$", "").replace("£", "").replace("€", "")
    if not s:
        return None
    m = re.match(r"^([0-9]*\.?[0-9]+)\s*([a-z]+)?$", s)
    if not m:
        return None
    val = float(m.group(1))
    suffix = (m.group(2) or "").strip()
    return val * _MULT.get(suffix, 1.0)


def _revenue_signal(raw: Any) -> dict[str, Any]:
    f = parse_money(raw)
    if f is None:
        return {"value": None, "below_2M": False, "above_100M": False,
                "confidence": 0.1, "source": None}
    return {"value": f, "below_2M": f < 2_000_000, "above_100M": f > 100_000_000,
            "confidence": 0.85, "source": "seed_list"}


def _ownership_signal(raw: Any) -> dict[str, Any]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return {"score": 0.5, "confidence": 0.1, "type": "unknown"}
    t = str(raw).lower()
    if any(k in t for k in ("founder", "family", "bootstrap", "owner-operated", "independent")):
        return {"score": 0.9, "confidence": 0.8, "type": "founder/family"}
    if any(k in t for k in ("vc", "venture", "private equity", "pe-", "pe ", "backed", "series ")):
        return {"score": 0.3, "confidence": 0.75, "type": "VC/PE"}
    return {"score": 0.5, "confidence": 0.2, "type": "unknown"}


def _default_metric() -> dict[str, Any]:
    return {"score": 0.5, "confidence": 0.1}


def _cell(row, canon, field):
    col = canon.get(field)
    if col is None:
        return None
    v = row[col]
    if isinstance(v, float) and pd.isna(v):
        return None
    return v


def row_to_record(row, canon: dict[str, str]) -> dict[str, Any]:
    name = _cell(row, canon, "name")
    rec: dict[str, Any] = {
        "name": str(name) if name is not None else "(unnamed)",
        "domain": (str(_cell(row, canon, "domain")) if _cell(row, canon, "domain") else None),
        "hq_region": (str(_cell(row, canon, "country")) if _cell(row, canon, "country") else None),
        "vertical": (str(_cell(row, canon, "vertical")) if _cell(row, canon, "vertical") else None),
        "is_vertical_niche": 0.5,  # unknown until enriched
        "already_acquired_or_public": False,
        "recurring_revenue": _default_metric(),
        "profitability": {**_default_metric(), "loss_evidence": False},
        "revenue_est_usd": _revenue_signal(_cell(row, canon, "revenue")),
        "niche_leadership": _default_metric(),
        "retention": _default_metric(),
        "ownership_fit": _ownership_signal(_cell(row, canon, "ownership")),
        "team_stability": _default_metric(),
        "revenue_growth": _default_metric(),
        "hiring_velocity": _default_metric(),
        "funding_momentum": _default_metric(),
        "market_size": _default_metric(),
        "notes": (str(_cell(row, canon, "description")) or "") if _cell(row, canon, "description") else "",
    }
    emp = _cell(row, canon, "employees")
    if emp is not None:
        rec["notes"] = (f"employees={emp}. " + rec["notes"]).strip()
    # Record which criteria came from the seed (high conf) vs need enrichment.
    provided = [k for k in ("revenue_est_usd", "ownership_fit")
                if rec[k].get("confidence", 0) >= 0.7]
    rec["_provided"] = provided
    rec["_needs_enrichment"] = [k for k in
                                ("recurring_revenue", "profitability", "niche_leadership",
                                 "retention", "team_stability", "revenue_growth",
                                 "hiring_velocity", "funding_momentum", "market_size")
                                if rec[k]["confidence"] < 0.3]
    return rec


def load_seed(path: str, mapping: dict[str, str] | None = None) -> list[dict[str, Any]]:
    if path.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(path)
    else:
        df = pd.read_csv(path)
    canon = mapping or _canon_columns(df.columns)
    if "name" not in canon:
        raise ValueError(
            f"could not find a company-name column in {list(df.columns)}; "
            "pass an explicit mapping like {'name': 'YourHeader'}")
    return [row_to_record(row, canon) for _, row in df.iterrows()]

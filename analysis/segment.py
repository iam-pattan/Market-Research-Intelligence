#!/usr/bin/env python3
"""Roll the 250 screened companies' 226 micro-verticals into ~12 macro-segments
and normalize regions. Deterministic + reproducible; feeds the market-synthesis
workflow. Writes data/research/segments.json (grouped) and prints the distribution.
"""
from __future__ import annotations
import collections
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROWS = json.load(open(ROOT / "data" / "screen" / "results.json"))

# Ordered rules: first matching keyword set wins. Order resolves overlaps
# (e.g. "legal AI" -> Legal before AI-infra; "construction permitting" ->
# Construction before Government).
SEGMENT_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Healthcare & Life Sciences",
     ("health", "clinical", "medical", "ehr", "dental", "veterinar", "vet ",
      "behavioral", "wellness", "nutrition", "radiolog", "scribe", "patient",
      "mental health", "allied-health", "medspa", "aesthetic", "practice management",
      "hippocratic", "abridge", "ambience", "tennr")),
    ("Legal, Risk & Compliance",
     ("legal", "law ", "law-", "law/", "litigation", "e-discovery", "ediscovery",
      "legal hold", "patent", " ip ", "/ip", "ip ai", "clm", "contract", "grc",
      "compliance", "regulator", "aml", "financial crime", "e-discovery")),
    ("Construction & Field Service",
     ("construction", "contractor", "field service", "field-service", "fsm",
      "trades", "roofing", "plumb", "hvac", "electrical", "jobsite", "takeoff",
      "estimating", "reality capture", "field reporting", "home services")),
    ("Manufacturing & Industrial",
     ("manufactur", "erp", "mrp", "mes", "qms", "mom", "oee", "machine monitoring",
      "industrial iot", "plm", "factory", "production", "job shop", "precision",
      "cmms", "eam", "ehsq", "make-to-order", "engineer-to-order", "eto", "mto", "pim")),
    ("Logistics & Supply Chain",
     ("tms", "wms", "oms", "fleet", "delivery", "last-mile", "last mile", "drayage",
      "dispatch", "route", "carrier", "shipper", "yard", "dock", "3pl", "telematics",
      "inventory", "warehouse", "logistics", "ltl", "fulfillment", "distribut")),
    ("Real Estate & Property",
     ("property", "real estate", "real-estate", "hoa", "community management",
      "condo", "lease", "brokerage", "cre ", "commercial real estate", "mortgage",
      " los", "rental", "pms")),  # PMS here = property mgmt; hotel PMS caught earlier? no
    ("Hospitality, Restaurant & Personal Services",
     ("hotel", "restaurant", "hospitality", "catering", "event", "venue", "salon",
      "spa", "beauty", "booking", "pos")),
    ("Government & Public Sector",
     ("government", "public sector", "public-sector", "civic", "311", "municipal",
      "local government", "utility billing", "public records", "citizen", "permitting",
      "licensing", "gis")),
    ("Education",
     ("k-12", "k12", "sis", "lms", "higher-ed", "higher ed", "school", "student",
      "rostering", "district", "education", "college", "campus", "independent-school")),
    ("Fintech & Financial Infrastructure",
     ("fintech", "banking", "payment", "lending", "loan", "credit", "card issuing",
      "baas", "banking-as-a-service", "wealth", "ria", "advisor", "portfolio",
      "investment compliance", "core banking", "money movement", "debt", "underwriting")),
    ("Security",
     ("security", "siem", "soar", "sast", "sca", "appsec", "supply-chain security",
      "supply chain security", "email & cloud", "detection", "static analysis")),
    ("Dev Tools, Data & AI Infrastructure",
     ("data infrastructure", "database", "vector", "olap", "observability", "monitoring",
      "developer", "dev tools", "workflow orchestration", "paas", "serverless", "compute",
      "orchestration", "api", "webhook", "llm", "ml infrastructure", "ai/ml", "auth",
      "identity", "containers", "background jobs", "durable", "elt", "data integration",
      "graphql", "hosting", "data layer", "telemetry", "data pipeline")),
]

# AI-native horizontal apps that don't sit in one end-market
HORIZONTAL_AI = ("gtm / sales", "sales data", "sales agents", "sdr",
                 "customer service ai", "customer support ai", "market intelligence",
                 "ai agents")


def macro_segment(vertical: str) -> str:
    v = vertical.lower()
    if any(k in v for k in HORIZONTAL_AI):
        return "Horizontal AI Applications"
    for seg, keys in SEGMENT_RULES:
        if any(k in v for k in keys):
            return seg
    return "Other Vertical SaaS"


REGION_MAP = {
    "usa": "US", "united states": "US", "u.s.": "US", "us": "US",
    "uk": "UK", "united kingdom": "UK",
}


def norm_region(r: str) -> str:
    return REGION_MAP.get(str(r).strip().lower(), str(r).strip())


def main() -> None:
    groups: dict[str, list[dict]] = collections.defaultdict(list)
    for row in ROWS:
        seg = macro_segment(row["vertical"])
        b, g = row["banyan"], row["growth"]
        item = {
            "name": row["name"], "domain": row["domain"],
            "vertical": row["vertical"], "region": norm_region(row["region"]),
            "banyan_tier": b.get("tier"), "banyan_adj": round(b.get("adjusted", 0), 3),
            "banyan_conf": round(b.get("confidence", 0), 3),
            "growth_tier": g.get("tier"), "growth_adj": round(g.get("adjusted", 0), 3),
        }
        groups[seg].append(item)

    # sort each segment by banyan_adj desc; sort segments by size desc
    out = {}
    for seg in sorted(groups, key=lambda s: -len(groups[s])):
        rows = sorted(groups[seg], key=lambda x: -x["banyan_adj"])
        banyan_fit = sum(1 for x in rows if x["banyan_tier"] in ("A", "B"))
        out[seg] = {
            "n": len(rows),
            "banyan_fit_count": banyan_fit,
            "banyan_fit_density": round(banyan_fit / len(rows), 2),
            "regions": dict(collections.Counter(x["region"] for x in rows).most_common(5)),
            "top_by_banyan": [f"{x['name']} ({x['banyan_adj']}, {x['banyan_tier']})" for x in rows[:6]],
            "companies": rows,
        }

    (ROOT / "data" / "research" / "segments.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    total = sum(v["n"] for v in out.values())
    print(f"{len(out)} macro-segments, {total} companies\n")
    print(f"{'SEGMENT':<44}{'N':>4}{'B-fit':>7}{'density':>9}")
    for seg, v in out.items():
        print(f"{seg:<44}{v['n']:>4}{v['banyan_fit_count']:>7}{v['banyan_fit_density']:>9}")


if __name__ == "__main__":
    main()

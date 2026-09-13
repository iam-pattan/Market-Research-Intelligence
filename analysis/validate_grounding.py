#!/usr/bin/env python3
"""Extract the raw codex research from workflow journals (the real 'datapull'),
persist it, then GROUNDING-VALIDATE the Banyan-25 dossiers against it:
for each dossier, are its checkable facts (founder/person names, years, and
currency figures) actually present in the paired codex research text, or were
they introduced by the synthesis step (potential hallucination)?

Only the 2-stage workflows (dossiers, discovery, synthesis) separately capture
raw research; OSINT/Wikidata were single-stage/direct and can't be grounded here.
"""
from __future__ import annotations
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
JROOT = pathlib.Path.home() / ".claude/projects/-Users-pahmed/8b7ea042-6048-49c4-825c-e57087597417/subagents/workflows"
OUT = ROOT / "data" / "research" / "codex_research"
OUT.mkdir(exist_ok=True)


def load_journal(run: str) -> dict:
    """Return {label: result_string} joined by key across task+result lines."""
    f = JROOT / run / "journal.jsonl"
    if not f.exists():
        return {}
    label_by_key, result_by_key = {}, {}
    for line in open(f):
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        k = o.get("key")
        if o.get("label"):
            label_by_key[k] = o["label"]
        if o.get("type") == "result":
            r = o.get("result")
            result_by_key[k] = r if isinstance(r, str) else json.dumps(r, ensure_ascii=False)
    return {label_by_key.get(k, k): v for k, v in result_by_key.items()}


# ---- 1. extract + persist raw research from all 2-stage workflows ----
RUNS = {
    "banyan25-dossiers": "wf_7ecee39a-5af",
    "bestofboth-dossiers": "wf_65d57250-698",
    "market-synthesis": "wf_ecccb68b-f72",
    "independent-discovery": "wf_00afa4c4-c5a",
}
research = {}   # run -> {name: research_text}
for name, run in RUNS.items():
    j = load_journal(run)
    rmap = {lbl.split("research:", 1)[1]: txt for lbl, txt in j.items()
            if isinstance(lbl, str) and lbl.startswith("research:")}
    research[name] = rmap
    d = OUT / name
    d.mkdir(exist_ok=True)
    for who, txt in rmap.items():
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", who)[:80]
        (d / f"{safe}.md").write_text(txt or "", encoding="utf-8")
    print(f"  {name:22s}: {len(rmap)} research docs -> data/research/codex_research/{name}/")

# ---- 2. grounding-validate Banyan-25 dossiers against paired research ----
dossiers = json.load(open(ROOT / "data" / "research" / "raw_dossiers_banyan.json"))
firmo = json.load(open(ROOT / "data" / "research" / "top25_banyan.json"))
rmap = research["banyan25-dossiers"]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower())


NAME_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b")
STOP = {"North America", "United States", "New York", "San Francisco", "Los Angeles",
        "Am Law", "The Company", "Our Story", "Series A", "Series B", "Series C",
        "Series D", "Series E", "Machine Learning", "Artificial Intelligence"}
YEAR_RE = re.compile(r"\b(19[6-9]\d|20[0-2]\d)\b")
MONEY_RE = re.compile(r"[£$€]\s?\d[\d.,]*\s?(?:[MBK]|million|billion|bn|m|k)?", re.I)


def checkable_facts(dossier: dict) -> dict:
    d = dossier["dossier"]
    hook = " ".join([d.get("personalization_hook", ""), d.get("ownership_funding", ""),
                     d.get("business_model", "")])
    names = {n for n in NAME_RE.findall(hook) if n not in STOP and len(n) > 6}
    fin = " ".join([d.get("revenue_profitability", ""), d.get("ownership_funding", "")])
    years = set(YEAR_RE.findall(fin + " " + hook))
    monies = {re.sub(r"\s", "", m) for m in MONEY_RE.findall(fin)}
    return {"names": names, "years": years, "monies": monies}


def grounded(token: str, research_text: str) -> bool:
    rt = norm(research_text)
    t = norm(token)
    if not t:
        return True
    # for money, compare digit core
    digits = re.sub(r"[^\d]", "", t)
    if digits and digits in re.sub(r"[^\d]", "", rt):
        return True
    return t in rt


rows, tot_facts, tot_grounded = [], 0, 0
for i, dossier in enumerate(dossiers):
    name = firmo[i]["name"]
    rtext = rmap.get(name, "")
    facts = checkable_facts(dossier)
    checks, ok, missing = 0, 0, []
    for cat in ("names", "years", "monies"):
        for tok in facts[cat]:
            checks += 1
            if not rtext:
                missing.append(f"{cat}:{tok} (NO RESEARCH)")
            elif grounded(tok, rtext):
                ok += 1
            else:
                missing.append(f"{cat}:{tok}")
    tot_facts += checks
    tot_grounded += ok
    rate = (ok / checks) if checks else 1.0
    rows.append({"name": name, "checks": checks, "grounded": ok,
                 "rate": round(rate, 2), "has_research": bool(rtext),
                 "missing": missing[:8]})

rows.sort(key=lambda r: r["rate"])
print("\n=== GROUNDING VALIDATION: Banyan-25 dossiers vs raw codex research ===")
print(f"{'company':26s}{'facts':>6}{'grounded':>9}{'rate':>7}  flags")
for r in rows:
    flag = "" if r["rate"] >= 0.8 else "  ⚠ REVIEW"
    miss = ("  missing: " + "; ".join(r["missing"][:4])) if r["missing"] else ""
    print(f"  {r['name'][:24]:24s}{r['checks']:>6}{r['grounded']:>9}{r['rate']:>7.0%}{flag}{miss}")
overall = (tot_grounded / tot_facts) if tot_facts else 1.0
no_research = sum(1 for r in rows if not r["has_research"])
print(f"\nOverall grounding: {tot_grounded}/{tot_facts} = {overall:.0%} of checkable facts appear in the paired codex research")
print(f"Dossiers with paired research: {len(rows)-no_research}/{len(rows)}")
json.dump({"overall_rate": round(overall, 3), "total_facts": tot_facts,
           "grounded": tot_grounded, "per_lead": rows},
          open(ROOT / "data" / "research" / "grounding_validation.json", "w"), indent=1)
print("wrote data/research/grounding_validation.json + persisted raw research under data/research/codex_research/")

"""Score a set of enrichment records under both rubrics, rank, and write outputs.

Usage:
    python -m banyan_screen.run records/*.json --out=out
"""
from __future__ import annotations
import glob
import json
import re
import sys

from banyan_screen.config import RubricConfig
from banyan_screen.ingest import company_from_record, banyan_scores, growth_scores
from banyan_screen.rubric_engine import score_company
from banyan_screen.report import write_outputs


def _norm_domain(rec: dict) -> str:
    d = str(rec.get("domain") or rec.get("name") or "").lower().strip()
    d = re.sub(r"^https?://", "", d)
    d = re.sub(r"^www\.", "", d)
    return d.rstrip("/")


def dedup(recs: list[dict]) -> list[dict]:
    """Collapse duplicate companies by normalized domain, keeping the record with
    the most total confidence (best-sourced wins)."""
    best: dict[str, tuple[float, dict]] = {}
    for r in recs:
        k = _norm_domain(r)
        conf = sum(v.get("confidence", 0) for v in r.values() if isinstance(v, dict))
        if k not in best or conf > best[k][0]:
            best[k] = (conf, r)
    return [v[1] for v in best.values()]


def load_records(paths: list[str]) -> list[dict]:
    recs: list[dict] = []
    for p in paths:
        with open(p) as fh:
            data = json.load(fh)
        recs.extend(data if isinstance(data, list) else [data])
    return recs


def _best_adjusted(r: dict) -> float:
    return max(r["banyan"].adjusted_score, r["growth"].adjusted_score)


def _best_tier(r: dict):
    b, g = r["banyan"], r["growth"]
    return b.tier if b.adjusted_score >= g.adjusted_score else g.tier


def score_records(recs, banyan_cfg, growth_cfg) -> list[dict]:
    scored = []
    for rec in recs:
        co = company_from_record(rec)
        scored.append({
            "company": co,
            "banyan": score_company(co, banyan_scores(rec), banyan_cfg),
            "growth": score_company(co, growth_scores(rec), growth_cfg),
            "record": rec,
        })
    # Rank by each company's BEST score across the two theses.
    scored.sort(key=lambda r: -_best_adjusted(r))
    return scored


def curate(scored: list[dict], top: int | None) -> tuple[list[dict], dict]:
    """Drop companies whose best-of-both tier is rejected/insufficient_data, then
    cap to the top N by best-of-both adjusted score. Returns (kept, stats)."""
    before = len(scored)
    kept = [r for r in scored
            if _best_tier(r).value not in ("rejected", "insufficient_data")]
    dropped_bad = before - len(kept)
    kept.sort(key=lambda r: -_best_adjusted(r))
    capped = kept[:top] if top else kept
    stats = {"before": before, "dropped_rejected_insufficient": dropped_bad,
             "after_filter": len(kept), "final": len(capped)}
    return capped, stats


def main(argv: list[str]) -> int:
    paths: list[str] = []
    seed: str | None = None
    out = "out"
    top: int | None = None
    for a in argv:
        if a.startswith("--out="):
            out = a.split("=", 1)[1]
        elif a.startswith("--seed="):
            seed = a.split("=", 1)[1]
        elif a.startswith("--top="):
            top = int(a.split("=", 1)[1])
        else:
            paths.extend(glob.glob(a))
    if not paths and not seed:
        print("usage: python -m banyan_screen.run <records.json ...> [--top=N] [--out=DIR]")
        print("   or: python -m banyan_screen.run --seed=list.csv [--top=N] [--out=DIR]")
        return 1
    banyan = RubricConfig.from_yaml("config.yaml")
    growth = RubricConfig.from_yaml("config.growth.yaml")
    if seed:
        from banyan_screen.input_loader import load_seed
        recs = load_seed(seed)
        print(f"loaded {len(recs)} companies from seed {seed}")
    else:
        recs = load_records(paths)
    before = len(recs)
    recs = dedup(recs)
    if len(recs) < before:
        print(f"deduped {before} -> {len(recs)} unique companies")
    scored = score_records(recs, banyan, growth)
    if top is not None:
        scored, stats = curate(scored, top)
        print(f"curated: {stats['before']} scored -> dropped "
              f"{stats['dropped_rejected_insufficient']} rejected/insufficient -> "
              f"{stats['after_filter']} qualified -> top {stats['final']}")
    files = write_outputs(scored, out)
    print(f"wrote {len(scored)} companies -> {files['html']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""OSINT firmographic enrichment of the Banyan top-25 via Wikidata (public, no key).
Best-effort: many small private vendors have NO Wikidata entity — absence is itself a
signal. Where present, pulls real founding date / HQ country / employees / ownership.
"""
from __future__ import annotations
import json
import pathlib
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOP = json.load(open(ROOT / "data" / "research" / "top25_banyan.json"))
API = "https://www.wikidata.org/w/api.php"
UA = {"User-Agent": "banyan-ma-research/1.0 (OSINT enrichment; contact via project)"}


def _get(params: dict) -> dict:
    url = API + "?" + urllib.parse.urlencode(params)
    for attempt in range(5):
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 4:
                time.sleep(2.0 * (attempt + 1))  # backoff (background: sleep allowed)
                continue
            raise
    return {}


def reg_domain(url: str) -> str:
    if not url:
        return ""
    d = url.split("//")[-1].split("/")[0].lower().removeprefix("www.")
    return d


def claim_ids(claims: dict, prop: str) -> list[str]:
    out = []
    for c in claims.get(prop, []):
        try:
            dv = c["mainsnak"]["datavalue"]["value"]
            if isinstance(dv, dict) and "id" in dv:
                out.append(dv["id"])
        except (KeyError, TypeError):
            pass
    return out


def claim_time(claims: dict, prop: str) -> str:
    for c in claims.get(prop, []):
        try:
            t = c["mainsnak"]["datavalue"]["value"]["time"]  # +2011-00-00T00:00:00Z
            return t.lstrip("+")[:4]
        except (KeyError, TypeError):
            pass
    return ""


def claim_qty(claims: dict, prop: str) -> str:
    for c in claims.get(prop, []):
        try:
            return c["mainsnak"]["datavalue"]["value"]["amount"].lstrip("+")
        except (KeyError, TypeError):
            pass
    return ""


def claim_str(claims: dict, prop: str) -> str:
    for c in claims.get(prop, []):
        try:
            return c["mainsnak"]["datavalue"]["value"]
        except (KeyError, TypeError):
            pass
    return ""


def labels_for(ids: list[str]) -> dict[str, str]:
    ids = [i for i in ids if i]
    if not ids:
        return {}
    d = _get({"action": "wbgetentities", "ids": "|".join(ids[:40]),
              "props": "labels", "languages": "en", "format": "json"})
    return {k: v.get("labels", {}).get("en", {}).get("value", k)
            for k, v in d.get("entities", {}).items()}


def enrich(name: str, domain: str) -> dict:
    try:
        s = _get({"action": "wbsearchentities", "search": name, "language": "en",
                  "type": "item", "limit": 5, "format": "json"})
    except Exception as e:
        return {"status": f"search-error: {e}"}
    hits = s.get("search", [])
    if not hits:
        return {"status": "no-wikidata-entity"}
    ids = [h["id"] for h in hits]
    try:
        ent = _get({"action": "wbgetentities", "ids": "|".join(ids),
                    "props": "claims|descriptions|labels", "languages": "en", "format": "json"})
    except Exception as e:
        return {"status": f"entity-error: {e}"}
    entities = ent.get("entities", {})

    # pick best hit: official-website domain match > description mentions software/company > first
    chosen, why = None, ""
    for hid in ids:
        cl = entities.get(hid, {}).get("claims", {})
        site = reg_domain(claim_str(cl, "P856"))
        if site and domain and (site == domain or site.endswith("." + domain) or domain.endswith("." + site)):
            chosen, why = hid, "website-match"
            break
    if not chosen:
        for hid in ids:
            desc = entities.get(hid, {}).get("descriptions", {}).get("en", {}).get("value", "").lower()
            if any(k in desc for k in ("software", "company", "saas", "technology")):
                chosen, why = hid, "desc-match"
                break
    if not chosen:
        chosen, why = ids[0], "first-hit"

    cl = entities.get(chosen, {}).get("claims", {})
    desc = entities.get(chosen, {}).get("descriptions", {}).get("en", {}).get("value", "")
    owner_ids = claim_ids(cl, "P127") + claim_ids(cl, "P749")   # owned by / parent org
    country_ids = claim_ids(cl, "P17")
    industry_ids = claim_ids(cl, "P452")
    lab = labels_for(owner_ids + country_ids + industry_ids)
    return {
        "status": "found",
        "qid": chosen,
        "match": why,
        "description": desc,
        "founded": claim_time(cl, "P571"),
        "country": ", ".join(lab.get(i, i) for i in country_ids),
        "employees": claim_qty(cl, "P1128"),
        "owned_by": ", ".join(lab.get(i, i) for i in owner_ids),
        "industry": ", ".join(lab.get(i, i) for i in industry_ids),
        "official_site": reg_domain(claim_str(cl, "P856")),
    }


def main() -> None:
    rows = []
    for c in TOP:
        e = enrich(c["name"], c["domain"])
        e["name"], e["domain"] = c["name"], c["domain"]
        rows.append(e)
        time.sleep(1.2)  # be polite to Wikidata (background process: sleep allowed)
        found = e["status"] == "found"
        extra = ""
        if found:
            bits = [b for b in [
                f"founded {e['founded']}" if e["founded"] else "",
                f"HQ {e['country']}" if e["country"] else "",
                f"{e['employees']} staff" if e["employees"] else "",
                f"owned_by {e['owned_by']}" if e["owned_by"] else "",
            ] if b]
            extra = " | ".join(bits) or "(entity, no firmographic claims)"
        print(f"  {c['name']:26s} {'OK ' if found else '-- '} {e['status'] if not found else extra}")
    json.dump(rows, open(ROOT / "data" / "research" / "osint_wikidata_top25.json", "w"), indent=1)
    n_found = sum(1 for r in rows if r["status"] == "found")
    n_owned = sum(1 for r in rows if r.get("owned_by"))
    print(f"\nWikidata coverage: {n_found}/{len(rows)} have an entity; {n_owned} disclose an owner/parent.")
    print("wrote data/research/osint_wikidata_top25.json")


if __name__ == "__main__":
    main()

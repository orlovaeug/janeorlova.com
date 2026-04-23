#!/usr/bin/env python3
# Amsterdam Motions Tracker - scraper
# Uses the Open Raadsinformatie Elasticsearch API (public, no auth)
# Endpoint: https://api.openraadsinformatie.nl/v1/elastic/
import json, time, logging, re
from datetime import date, datetime
from pathlib import Path
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ORI_BASE = "https://api.openraadsinformatie.nl/v1/elastic"
START_DATE = date(2025, 6, 1)
OUTPUT_FILE = Path(__file__).parent / "motions.json"
DELAY = 0.5
PAGE_SIZE = 100

S = requests.Session()
S.headers.update({
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "AmsterdamMotionsTracker/1.0 (civic project)",
})


def post(url, body, retries=3):
    for attempt in range(1, retries + 1):
        try:
            r = S.post(url, json=body, timeout=30)
            log.info("POST %s -> %d", url, r.status_code)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            log.warning("Attempt %d failed: %s", attempt, exc)
            if attempt < retries:
                time.sleep(3 * attempt)
    return None


def get(url, retries=3):
    for attempt in range(1, retries + 1):
        try:
            r = S.get(url, timeout=30)
            log.info("GET %s -> %d", url, r.status_code)
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            log.warning("Attempt %d failed: %s", attempt, exc)
            if attempt < retries:
                time.sleep(3 * attempt)
    return None


def clean(t):
    if not t: return ""
    return " ".join(str(t).split())


def map_status(raw):
    s = str(raw).lower()
    if any(k in s for k in ("aangenomen","passed","approved","aanvaard")): return "Aangenomen"
    if any(k in s for k in ("verworpen","rejected","afgekeurd")): return "Verworpen"
    if any(k in s for k in ("aangehouden","ingetrokken","withdrawn","pending")): return "Aangehouden"
    if any(k in s for k in ("geamendeerd","amended","gewijzigd")): return "Geamendeerd"
    return "Onbekend"


def infer_topic(text):
    t = text.lower()
    rules = [
        ("Housing",     ["wonen","huur","woningbouw","airbnb","woonruimte"]),
        ("Mobility",    ["fiets","verkeer","metro","tram","parkeer"]),
        ("Climate",     ["klimaat","groen","duurzaam","energie","aardgas","co2"]),
        ("Safety",      ["veiligheid","politie","camera","handhaving","overlast"]),
        ("Social",      ["zorg","armoed","daklozen","welzijn","jeugd"]),
        ("Education",   ["school","integratie","discriminatie","onderwijs"]),
        ("PublicSpace", ["openbare ruimte","park","plein","markt","toilet"]),
        ("Finance",     ["begroting","subsidie","budget","financ"]),
        ("Governance",  ["democratie","bestuur","raad","motie"]),
    ]
    for topic, kws in rules:
        if any(k in t for k in kws): return topic
    return "Other"


def parse_date(raw):
    if not raw: return None
    for fmt in ("%Y-%m-%dT%H:%M:%S","%Y-%m-%d %H:%M:%S","%Y-%m-%d"):
        try: return datetime.strptime(str(raw)[:19], fmt).date().isoformat()
        except ValueError: continue
    return str(raw)[:10] if len(str(raw)) >= 10 else None


def discover_amsterdam_index():
    """Find the Amsterdam index name in ORI elastic."""
    data = get(ORI_BASE + "/_cat/indices?format=json&h=index")
    if not data:
        log.warning("Could not list indices")
        return None
    log.info("Available indices: %s", [d.get("index") for d in data])
    # Look for amsterdam index
    for item in data:
        idx = item.get("index", "")
        if "amsterdam" in idx.lower() or "ori_ams" in idx.lower():
            log.info("Found Amsterdam index: %s", idx)
            return idx
    # Fallback: try known pattern
    for item in data:
        idx = item.get("index", "")
        if idx.startswith("ori_"):
            log.info("Candidate index: %s", idx)
    return None


def fetch_motions_from_index(index):
    """Query ORI elastic for motions in the Amsterdam index."""
    results = []
    page_from = 0
    url = ORI_BASE + "/" + index + "/_search"
    while True:
        body = {
            "from": page_from,
            "size": PAGE_SIZE,
            "sort": [{"startDate": {"order": "desc"}}],
            "query": {
                "bool": {
                    "must": [
                        {"terms": {"types": ["Motie","Motion","motie","motion"]}}
                    ],
                    "filter": [
                        {"range": {"startDate": {"gte": START_DATE.isoformat()}}}
                    ]
                }
            }
        }
        data = post(url, body)
        if not data:
            log.error("No response from ORI elastic")
            break
        hits = data.get("hits", {}).get("hits", [])
        total = data.get("hits", {}).get("total", {})
        total_n = total.get("value", 0) if isinstance(total, dict) else int(total or 0)
        log.info("Page from=%d: got %d hits (total=%d)", page_from, len(hits), total_n)
        if not hits: break
        for hit in hits:
            src = hit.get("_source", {})
            motion = parse_ori_hit(src, hit.get("_id",""))
            if motion:
                results.append(motion)
        page_from += PAGE_SIZE
        if page_from >= total_n: break
        time.sleep(DELAY)
    return results


def fetch_motions_global():
    """Query across all ORI indices filtering by Amsterdam."""
    results = []
    page_from = 0
    # Try searching all indices with Amsterdam filter
    url = ORI_BASE + "/_search"
    while True:
        body = {
            "from": page_from,
            "size": PAGE_SIZE,
            "sort": [{"startDate": {"order": "desc"}}],
            "query": {
                "bool": {
                    "must": [
                        {"terms": {"types": ["Motie","Motion","motie","motion"]}}
                    ],
                    "filter": [
                        {"range": {"startDate": {"gte": START_DATE.isoformat()}}},
                        {"multi_match": {
                            "query": "Amsterdam",
                            "fields": ["organization","municipality","sources.description"]
                        }}
                    ]
                }
            }
        }
        data = post(url, body)
        if not data:
            log.warning("Global search failed, trying match_all")
            break
        hits = data.get("hits", {}).get("hits", [])
        total = data.get("hits", {}).get("total", {})
        total_n = total.get("value", 0) if isinstance(total, dict) else int(total or 0)
        log.info("Global page from=%d: %d hits (total=%d)", page_from, len(hits), total_n)
        if not hits: break
        for hit in hits:
            src = hit.get("_source", {})
            motion = parse_ori_hit(src, hit.get("_id",""))
            if motion:
                results.append(motion)
        page_from += PAGE_SIZE
        if page_from >= total_n or page_from > 2000: break
        time.sleep(DELAY)
    return results


def parse_ori_hit(src, hit_id):
    """Convert an ORI elasticsearch hit into our schema."""
    date_str = parse_date(src.get("startDate") or src.get("date") or src.get("modified"))
    if not date_str:
        return None
    if date_str < START_DATE.isoformat():
        return None
    motion_id = str(src.get("id") or src.get("@id") or hit_id or "")
    title = clean(src.get("name") or src.get("title") or src.get("description","")[:120])
    summary = clean(src.get("description") or src.get("text") or "")
    # Parties / indieners
    parties = []
    for p in (src.get("submitter") or src.get("creator") or []):
        if isinstance(p, dict):
            parties.append(clean(p.get("name","")))
        elif isinstance(p, str):
            parties.append(clean(p))
    # Status / result
    status_raw = clean(src.get("result") or src.get("outcome") or src.get("status") or "")
    status = map_status(status_raw) if status_raw else "Onbekend"
    # Votes
    votes = src.get("votes") or src.get("voteEvent") or {}
    if isinstance(votes, list) and votes:
        votes = votes[0]
    v_for = int(votes.get("for", votes.get("voors", 0)) or 0) if isinstance(votes, dict) else 0
    v_against = int(votes.get("against", votes.get("tegens", 0)) or 0) if isinstance(votes, dict) else 0
    v_abstain = int(votes.get("abstain", votes.get("onthoudingen", 0)) or 0) if isinstance(votes, dict) else 0
    # Link
    sources = src.get("sources") or []
    link = ""
    if sources and isinstance(sources, list):
        link = sources[0].get("url","") if isinstance(sources[0], dict) else ""
    link = link or src.get("url") or "https://amsterdam.raadsinformatie.nl"
    topic = infer_topic(title + " " + summary)
    if not title:
        return None
    log.debug("Motion %s: %s | %s | %s", motion_id, date_str, status, title[:60])
    return {
        "id": motion_id,
        "title": title,
        "date": date_str,
        "party": parties[0] if parties else "",
        "parties": parties,
        "topic": topic,
        "status": status,
        "status_raw": status_raw,
        "for": v_for,
        "against": v_against,
        "abstain": v_abstain,
        "summary": summary[:500],
        "link": link,
    }


def load_existing():
    if OUTPUT_FILE.exists():
        try:
            return json.loads(OUTPUT_FILE.read_text(encoding="utf-8")).get("motions",[])
        except Exception: pass
    return []


def merge(existing, fresh):
    by_id = {m["id"]: m for m in existing}
    added = updated = 0
    for m in fresh:
        mid = m["id"]
        if mid not in by_id:
            by_id[mid] = m; added += 1
        else:
            by_id[mid].update({k: m[k] for k in ("status","status_raw","for","against","abstain")})
            updated += 1
    log.info("Merge: +%d new, ~%d updated, %d total", added, updated, len(by_id))
    return sorted(by_id.values(), key=lambda m: m["date"], reverse=True)


def main():
    log.info("Scraper starting, coverage from %s", START_DATE)
    fresh = []
    # Step 1: find Amsterdam-specific index
    idx = discover_amsterdam_index()
    if idx:
        fresh = fetch_motions_from_index(idx)
        log.info("Index search returned %d motions", len(fresh))
    # Step 2: global search across all indices
    if not fresh:
        log.info("Trying global ORI search...")
        fresh = fetch_motions_global()
        log.info("Global search returned %d motions", len(fresh))
    if not fresh:
        log.warning("No motions found from ORI API. Check logs for index list.")
    existing = load_existing()
    merged = merge(existing, fresh)
    meta = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "total": len(merged),
        "start_date": START_DATE.isoformat(),
        "source": "api.openraadsinformatie.nl",
    }
    OUTPUT_FILE.write_text(
        json.dumps({"meta": meta, "motions": merged}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("Written %d motions to %s", len(merged), OUTPUT_FILE)


if __name__ == "__main__":
    main()

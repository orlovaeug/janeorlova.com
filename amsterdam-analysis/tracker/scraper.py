#!/usr/bin/env python3
import json, time, logging
from datetime import date, datetime
from pathlib import Path
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ORI = "https://api.openraadsinformatie.nl/v1/elastic"
# Main Amsterdam city council index
MAIN_INDEX = "ori_amsterdam_20250317151602"
# All Amsterdam indices to search
ALL_INDICES = [
    "ori_amsterdam_20250317151602",
    "ori_amsterdam_centrum_20250326114002",
    "ori_amsterdam_noord_20250327160013",
    "ori_amsterdam_oost_20250328191204",
    "ori_amsterdam_west_20250329060605",
    "ori_amsterdam_zuid_20250330113603",
    "ori_amsterdam_zuidoost_20250330224604",
    "ori_amsterdam_nieuw-west_20250327080802",
]
START_DATE = date(2026, 1, 1)
OUTPUT_FILE = Path(__file__).parent / "motions.json"
DELAY = 0.4
PAGE = 100

S = requests.Session()
S.headers.update({"Content-Type": "application/json", "Accept": "application/json",
                  "User-Agent": "AmsterdamMotionsTracker/1.0"})


def post(url, body):
    try:
        r = S.post(url, json=body, timeout=30)
        if not r.ok:
            log.error("POST %s -> %d: %s", url, r.status_code, r.text[:300])
            return None
        return r.json()
    except Exception as exc:
        log.error("POST failed %s: %s", url, exc)
        return None


def clean(t):
    return " ".join(str(t).split()) if t else ""


def map_status(raw):
    s = str(raw).lower()
    if any(k in s for k in ("aangenomen","passed","approved","aanvaard")): return "Aangenomen"
    if any(k in s for k in ("verworpen","rejected","afgekeurd")): return "Verworpen"
    if any(k in s for k in ("aangehouden","ingetrokken","withdrawn")): return "Aangehouden"
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
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try: return datetime.strptime(str(raw)[:19], fmt).date().isoformat()
        except ValueError: continue
    return str(raw)[:10] if len(str(raw)) >= 10 else None


def log_sample(index):
    """Fetch one doc and log ALL its fields so we can see the real structure."""
    data = post(ORI + "/" + index + "/_search", {"size": 1, "query": {"match_all": {}}})
    if not data: return
    hits = data.get("hits", {}).get("hits", [])
    total = data.get("hits", {}).get("total", {})
    n = total.get("value", 0) if isinstance(total, dict) else int(total or 0)
    log.info("Index %s total docs: %d", index, n)
    if not hits: return
    src = hits[0].get("_source", {})
    log.info("SAMPLE DOC FIELDS: %s", list(src.keys()))
    for k, v in src.items():
        log.info("  FIELD %s = %s", k, str(v)[:150])


def fetch_index(index):
    """Fetch all docs from one index, no type filtering - return everything."""
    results = []
    from_ = 0
    url = ORI + "/" + index + "/_search"
    while True:
        body = {
            "from": from_,
            "size": PAGE,
            "sort": [{"startDate": {"order": "desc", "unmapped_type": "date"}}],
            "query": {"match_all": {}},
        }
        data = post(url, body)
        if not data: break
        hits = data.get("hits", {}).get("hits", [])
        total = data.get("hits", {}).get("total", {})
        total_n = total.get("value", 0) if isinstance(total, dict) else int(total or 0)
        if not hits: break
        for hit in hits:
            src = hit.get("_source", {})
            m = parse_doc(src, hit.get("_id", ""))
            if m:
                results.append(m)
        from_ += PAGE
        if from_ >= total_n: break
        time.sleep(DELAY)
    return results


def is_motion(src):
    """Check if a document is a motion/amendement based on all possible type fields."""
    motion_keywords = ("motie", "motion", "amendement", "amendment")
    # Check every field that might indicate type
    for field in ("@type", "type", "types", "classification", "documentType",
                  "document_type", "vergadertype", "soort", "category"):
        val = src.get(field, "")
        if not val: continue
        if isinstance(val, list):
            val = " ".join(str(v) for v in val)
        if any(k in str(val).lower() for k in motion_keywords):
            return True
    # Also check title/name for motion keywords as fallback
    title = str(src.get("name", "") or src.get("title", "")).lower()
    if any(k in title for k in ("motie", "amendement")):
        return True
    return False


def parse_doc(src, hit_id):
    """Convert a raw doc to our motion schema, returns None if not a motion."""
    if not is_motion(src):
        return None
    date_str = parse_date(
        src.get("startDate") or src.get("date") or src.get("modified") or src.get("created")
    )
    if not date_str: return None
    if date_str < START_DATE.isoformat(): return None
    motion_id = str(src.get("id") or src.get("@id") or hit_id or "")
    title = clean(src.get("name") or src.get("title") or "")
    if not title: return None
    summary = clean(src.get("description") or src.get("text") or "")
    parties = []
    for p in (src.get("submitter") or src.get("creator") or
              src.get("submitters") or src.get("initiators") or []):
        name = p.get("name", "") if isinstance(p, dict) else str(p)
        if clean(name): parties.append(clean(name))
    status_raw = clean(
        src.get("result") or src.get("outcome") or src.get("status") or""
    )
    status = map_status(status_raw) if status_raw else "Onbekend"
    sources = src.get("sources") or []
    link = ""
    if isinstance(sources, list) and sources:
        link = sources[0].get("url", "") if isinstance(sources[0], dict) else ""
    link = link or src.get("url") or "https://amsterdam.raadsinformatie.nl"
    log.info("MOTION: %s | %s | %s | %s", motion_id, date_str, status, title[:70])
    return {
        "id": motion_id,
        "title": title,
        "date": date_str,
        "party": parties[0] if parties else "",
        "parties": parties,
        "topic": infer_topic(title + " " + summary),
        "status": status,
        "status_raw": status_raw,
        "for": 0, "against": 0, "abstain": 0,
        "summary": summary[:500],
        "link": link,
    }


def load_existing():
    if OUTPUT_FILE.exists():
        try: return json.loads(OUTPUT_FILE.read_text(encoding="utf-8")).get("motions", [])
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
    # Log one sample doc so we can see real field names in Actions log
    log.info("=== PROBING INDEX STRUCTURE ===")
    log_sample(MAIN_INDEX)
    fresh = []
    seen = set()
    for index in ALL_INDICES:
        log.info("Fetching index: %s", index)
        motions = fetch_index(index)
        for m in motions:
            if m["id"] not in seen:
                seen.add(m["id"])
                fresh.append(m)
        log.info("After %s: %d total motions", index, len(fresh))
    log.info("Total motions found: %d", len(fresh))
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

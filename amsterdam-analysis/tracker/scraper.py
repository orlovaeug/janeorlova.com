#!/usr/bin/env python3
import json, time, logging
from datetime import date, datetime
from pathlib import Path
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

ORI = "https://api.openraadsinformatie.nl/v1/elastic"
# The main Amsterdam index (city council, not districts)
# Confirmed from index list: ori_amsterdam_20250317151602
# Also need to search district indices for full coverage
AMS_INDICES = [
    "ori_amsterdam_20250317151602",
    "ori_amsterdam_centrum_20250326114002",
    "ori_amsterdam_noord_20250327160013",
    "ori_amsterdam_oost_20250328191204",
    "ori_amsterdam_west_20250329060605",
    "ori_amsterdam_zuid_20250330113603",
    "ori_amsterdam_zuidoost_20250330224604",
    "ori_amsterdam_nieuw-west_20250327080802",
]
START_DATE = date(2025, 6, 1)
OUTPUT_FILE = Path(__file__).parent / "motions.json"
DELAY = 0.5
PAGE = 100

S = requests.Session()
S.headers.update({"Content-Type": "application/json", "Accept": "application/json",
                  "User-Agent": "AmsterdamMotionsTracker/1.0"})


def post(url, body, retries=3):
    for attempt in range(1, retries + 1):
        try:
            r = S.post(url, json=body, timeout=30)
            if r.status_code == 400:
                log.error("400 Bad Request for %s: %s", url, r.text[:500])
                return None
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            log.warning("Attempt %d failed: %s", attempt, exc)
            if attempt < retries:
                time.sleep(3 * attempt)
    return None


def clean(t):
    return " ".join(str(t).split()) if t else ""


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


def probe_index_mapping(index):
    """Check what fields and type values exist in this index."""
    try:
        r = S.get(ORI + "/" + index + "/_mapping", timeout=20)
        mapping = r.json()
        # Also get a sample document to see field names
        sample_url = ORI + "/" + index + "/_search"
        sample = post(sample_url, {"size": 1, "query": {"match_all": {}}})
        if sample:
            hits = sample.get("hits",{}).get("hits",[])
            if hits:
                src = hits[0].get("_source",{})
                log.info("Sample doc keys: %s", list(src.keys()))
                log.info("Sample doc type fields: %s", {
                    k: src[k] for k in src if "type" in k.lower()[:10]
                })
                log.info("Sample startDate: %s", src.get("startDate") or src.get("date"))
        return mapping
    except Exception as e:
        log.error("Probe failed: %s", e)
        return {}


def search_index(index, from_=0):
    """Search one index for motions, using a simple match_all first to understand structure."""
    url = ORI + "/" + index + "/_search"
    # Try match_all first to understand what is in this index
    body = {
        "from": from_,
        "size": PAGE,
        "sort": [{"startDate": {"order": "desc", "unmapped_type": "date"}}],
        "query": {"match_all": {}},
    }
    return post(url, body)


def parse_hit(src, hit_id):
    """Parse a raw ES hit into our motion schema."""
    # Check if this is actually a motion type
    type_val = (src.get("@type") or src.get("type") or
                src.get("types") or src.get("classification") or "")
    if isinstance(type_val, list):
        type_str = " ".join(str(v) for v in type_val).lower()
    else:
        type_str = str(type_val).lower()
    # Only keep motions (skip agendas, minutes, etc)
    is_motion = any(k in type_str for k in ("motie","motion","amendement","amendment"))
    if not is_motion:
        return None
    date_str = parse_date(src.get("startDate") or src.get("date") or src.get("modified"))
    if not date_str or date_str < START_DATE.isoformat():
        return None
    motion_id = str(src.get("id") or src.get("@id") or hit_id or "")
    title = clean(src.get("name") or src.get("title") or "")
    if not title: return None
    summary = clean(src.get("description") or src.get("text") or "")
    parties = []
    for p in (src.get("submitter") or src.get("creator") or
              src.get("submitters") or src.get("initiators") or []):
        name = p.get("name","") if isinstance(p, dict) else str(p)
        if name: parties.append(clean(name))
    status_raw = clean(src.get("result") or src.get("outcome") or src.get("status") or "")
    status = map_status(status_raw) if status_raw else "Onbekend"
    sources = src.get("sources") or []
    link = ""
    if isinstance(sources, list) and sources:
        link = sources[0].get("url","") if isinstance(sources[0], dict) else ""
    link = link or src.get("url") or "https://amsterdam.raadsinformatie.nl"
    return {
        "id": motion_id,
        "title": title,
        "date": date_str,
        "party": parties[0] if parties else "",
        "parties": parties,
        "topic": infer_topic(title + " " + summary),
        "status": status,
        "status_raw": status_raw,
        "for": 0,
        "against": 0,
        "abstain": 0,
        "summary": summary[:500],
        "link": link,
    }


def fetch_all_motions():
    results = []
    seen = set()
    for index in AMS_INDICES:
        log.info("=== Scanning index: %s ===", index)
        # Probe first index only to understand structure
        if index == AMS_INDICES[0]:
            probe_index_mapping(index)
        from_ = 0
        while True:
            data = search_index(index, from_=from_)
            if not data:
                log.warning("No data from index %s at from=%d", index, from_)
                break
            hits = data.get("hits",{}).get("hits",[])
            total = data.get("hits",{}).get("total",{})
            total_n = total.get("value",0) if isinstance(total,dict) else int(total or 0)
            log.info("Index %s from=%d: %d hits (total=%d)", index, from_, len(hits), total_n)
            if not hits: break
            for hit in hits:
                mid = hit.get("_id","")
                if mid in seen: continue
                seen.add(mid)
                m = parse_hit(hit.get("_source",{}), mid)
                if m:
                    results.append(m)
                    log.info("Motion: %s | %s | %s", m["date"], m["status"], m["title"][:60])
            from_ += PAGE
            if from_ >= total_n: break
            time.sleep(DELAY)
        log.info("Running total after %s: %d motions", index, len(results))
    return results


def load_existing():
    if OUTPUT_FILE.exists():
        try: return json.loads(OUTPUT_FILE.read_text(encoding="utf-8")).get("motions",[])
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
    fresh = fetch_all_motions()
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

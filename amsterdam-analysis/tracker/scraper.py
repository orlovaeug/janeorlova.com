#!/usr/bin/env python3
import json, re, time, logging
from datetime import date, datetime
from pathlib import Path
import requests

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BASE_URL = "https://api.notubiz.nl"
ORG_SLUG = "gemeente-amsterdam"
START_DATE = date(2025, 6, 1)
OUTPUT_FILE = Path(__file__).parent / "motions.json"
REQUEST_DELAY = 0.4
MAX_PAGES = 60

SESSION = requests.Session()
SESSION.headers.update({"Accept": "application/json", "User-Agent": "AmsterdamTracker/1.0"})


def get_json(url, params=None, retries=3):
    for attempt in range(1, retries + 1):
        try:
            resp = SESSION.get(url, params=params, timeout=20)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as exc:
            log.warning("Attempt %d/%d failed: %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(2 ** attempt)
    return {}


def parse_date(raw):
    if not raw:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(raw)[:19], fmt).date().isoformat()
        except ValueError:
            continue
    return str(raw)[:10] if len(str(raw)) >= 10 else None


def clean_text(text):
    if not text:
        return ""
    return " ".join(str(text).split())


def map_status(raw):
    if not raw:
        return "Onbekend"
    s = str(raw).lower().strip()
    if any(k in s for k in ("aangenomen", "passed", "approved")):
        return "Aangenomen"
    if any(k in s for k in ("verworpen", "rejected", "afgekeurd")):
        return "Verworpen"
    if any(k in s for k in ("aangehouden", "ingetrokken", "pending", "withdrawn")):
        return "Aangehouden"
    if any(k in s for k in ("geamendeerd", "amended")):
        return "Geamendeerd"
    return "Onbekend"


def infer_topic(title, summary):
    text = (title + " " + summary).lower()
    rules = [
        ("Housing",     ["wonen", "huur", "woningbouw", "airbnb"]),
        ("Mobility",    ["fiets", "verkeer", "metro", "tram", "parkeer"]),
        ("Climate",     ["klimaat", "groen", "duurzaam", "energie", "aardgas"]),
        ("Safety",      ["veiligheid", "politie", "camera", "handhaving"]),
        ("Social",      ["zorg", "armoed", "daklozen", "welzijn"]),
        ("Education",   ["school", "integratie", "onderwijs"]),
        ("PublicSpace", ["openbare ruimte", "park", "plein", "markt"]),
        ("Finance",     ["begroting", "subsidie", "budget"]),
        ("Governance",  ["democratie", "bestuur", "raad"]),
    ]
    for topic, keywords in rules:
        if any(k in text for k in keywords):
            return topic
    return "Other"


def fetch_organisation_id():
    data = get_json(BASE_URL + "/organisations", params={"slug": ORG_SLUG})
    for org in data.get("items", data.get("results", [])):
        if org.get("slug") == ORG_SLUG:
            return org.get("id")
    data2 = get_json(BASE_URL + "/organisations")
    for org in data2.get("items", data2.get("results", [])):
        name = str(org.get("name", "")).lower()
        if "amsterdam" in name and "gemeente" in name:
            return org.get("id")
    return None


def fetch_motions_page(org_id, page=1, per_page=50):
    params = {"organisation_id": org_id, "page": page, "per_page": per_page, "sort": "date", "order": "desc"}
    data = get_json(BASE_URL + "/events/motions", params=params)
    if not data or ("items" not in data and "results" not in data):
        params["type"] = "Motie"
        data = get_json(BASE_URL + "/documents", params=params)
    return data


def parse_motion(raw):
    date_str = parse_date(raw.get("date") or raw.get("meeting_date") or raw.get("created_at"))
    if not date_str or date_str < START_DATE.isoformat():
        return None
    motion_id = str(raw.get("id", ""))
    title = clean_text(raw.get("title") or raw.get("name") or "")
    summary = clean_text(raw.get("summary") or raw.get("description") or raw.get("text") or "")
    parties_raw = raw.get("parties") or raw.get("submitters") or raw.get("initiators") or []
    if isinstance(parties_raw, list):
        parties = [clean_text(p.get("name", p) if isinstance(p, dict) else str(p)) for p in parties_raw]
    else:
        parties = []
    lead_party = parties[0] if parties else str(raw.get("party", ""))
    status_raw = raw.get("result") or raw.get("status") or raw.get("decision") or ""
    status = map_status(status_raw)
    votes = raw.get("votes") or raw.get("vote_counts") or {}
    v_for     = int(votes.get("for",     votes.get("voors",  votes.get("pro",    0))) or 0)
    v_against = int(votes.get("against", votes.get("tegens", votes.get("contra", 0))) or 0)
    v_abstain = int(votes.get("abstain", votes.get("onthoudingen", 0)) or 0)
    topic_raw = clean_text(raw.get("topic") or raw.get("category") or "")
    topic = topic_raw if topic_raw else infer_topic(title, summary)
    link = raw.get("url") or raw.get("link") or "https://amsterdam.raadsinformatie.nl"
    return {
        "id": motion_id, "title": title, "date": date_str,
        "party": lead_party, "parties": parties, "topic": topic,
        "status": status, "status_raw": clean_text(str(status_raw)),
        "for": v_for, "against": v_against, "abstain": v_abstain,
        "summary": summary[:500], "link": link,
    }


def fetch_via_ori(org_id):
    results = []
    params = {"@type": "Motion", "organization.name": "Gemeente Amsterdam", "size": 100, "from": 0}
    page = 0
    while page < MAX_PAGES:
        params["from"] = page * 100
        data = get_json("https://id.openraadsinformatie.nl/search", params=params)
        hits = data.get("hits", {}).get("hits", data.get("results", []))
        if not hits:
            break
        for hit in hits:
            src = hit.get("_source", hit)
            date_str = parse_date(src.get("startDate") or src.get("date"))
            if not date_str or date_str < START_DATE.isoformat():
                continue
            title   = clean_text(src.get("name") or src.get("title") or "")
            summary = clean_text(src.get("description") or src.get("text") or "")
            results.append({
                "id": str(src.get("id", "ORI-" + str(len(results)))),
                "title": title, "date": date_str, "party": "", "parties": [],
                "topic": infer_topic(title, summary),
                "status": map_status(src.get("result") or ""),
                "status_raw": "", "for": 0, "against": 0, "abstain": 0,
                "summary": summary[:500],
                "link": src.get("url") or "https://amsterdam.raadsinformatie.nl",
            })
        page += 1
        time.sleep(REQUEST_DELAY)
    return results


def load_existing():
    if OUTPUT_FILE.exists():
        try:
            return json.loads(OUTPUT_FILE.read_text(encoding="utf-8")).get("motions", [])
        except (json.JSONDecodeError, KeyError):
            pass
    return []


def merge(existing, fresh):
    by_id = {m["id"]: m for m in existing}
    added = updated = 0
    for motion in fresh:
        mid = motion["id"]
        if mid not in by_id:
            by_id[mid] = motion
            added += 1
        else:
            for field in ("status", "status_raw", "for", "against", "abstain"):
                by_id[mid][field] = motion[field]
            updated += 1
    log.info("Merge: %d added, %d updated, %d total", added, updated, len(by_id))
    return sorted(by_id.values(), key=lambda m: m["date"], reverse=True)


def main():
    log.info("Scraper started from %s", START_DATE.isoformat())
    fresh = []
    org_id = fetch_organisation_id()
    if not org_id:
        log.warning("Could not resolve org ID")
    else:
        page = 1
        stop = False
        while page <= MAX_PAGES and not stop:
            data = fetch_motions_page(org_id, page=page)
            items = data.get("items", data.get("results", []))
            if not items:
                break
            for raw in items:
                motion = parse_motion(raw)
                if motion is None:
                    stop = True
                    break
                fresh.append(motion)
            total_pages = data.get("meta", {}).get("total_pages", data.get("total_pages", page))
            if page >= total_pages:
                break
            page += 1
            time.sleep(REQUEST_DELAY)
        log.info("Fetched %d motions", len(fresh))
    if not fresh:
        fresh = fetch_via_ori(org_id or 0)
    existing = load_existing()
    merged = merge(existing, fresh)
    meta = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "total": len(merged),
        "start_date": START_DATE.isoformat(),
        "source": "api.notubiz.nl",
    }
    OUTPUT_FILE.write_text(
        json.dumps({"meta": meta, "motions": merged}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("Written %d motions to %s", len(merged), OUTPUT_FILE)


if __name__ == "__main__":
    main()

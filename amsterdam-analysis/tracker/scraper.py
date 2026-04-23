#!/usr/bin/env python3
import json, time, logging, re
from datetime import date, datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BASE = "https://amsterdam.raadsinformatie.nl"
START_DATE = date(2025, 6, 1)
OUTPUT_FILE = Path(__file__).parent / "motions.json"
DELAY = 1.0

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 AmsterdamMotionsTracker/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
})


def get(url, params=None, retries=3):
    for attempt in range(1, retries + 1):
        try:
            r = SESSION.get(url, params=params, timeout=20)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            log.warning("Attempt %d failed: %s", attempt, e)
            if attempt < retries:
                time.sleep(3 * attempt)
    return None


def clean(text):
    if not text:
        return ""
    return " ".join(str(text).split())


def map_status(raw):
    s = str(raw).lower()
    if any(k in s for k in ("aangenomen", "passed", "approved")):
        return "Aangenomen"
    if any(k in s for k in ("verworpen", "rejected")):
        return "Verworpen"
    if any(k in s for k in ("aangehouden", "ingetrokken", "withdrawn")):
        return "Aangehouden"
    if any(k in s for k in ("geamendeerd", "amended")):
        return "Geamendeerd"
    return "Onbekend"


def infer_topic(text):
    t = text.lower()
    rules = [
        ("Housing",     ["wonen", "huur", "woningbouw", "airbnb", "woonruimte"]),
        ("Mobility",    ["fiets", "verkeer", "metro", "tram", "parkeer"]),
        ("Climate",     ["klimaat", "groen", "duurzaam", "energie", "aardgas", "co2"]),
        ("Safety",      ["veiligheid", "politie", "camera", "handhaving"]),
        ("Social",      ["zorg", "armoed", "daklozen", "welzijn"]),
        ("Education",   ["school", "integratie", "onderwijs"]),
        ("PublicSpace", ["openbare ruimte", "park", "plein", "markt"]),
        ("Finance",     ["begroting", "subsidie", "budget"]),
        ("Governance",  ["democratie", "bestuur", "raad"]),
    ]
    for topic, kws in rules:
        if any(k in t for k in kws):
            return topic
    return "Other"


def fetch_motion_detail(url):
    r = get(url)
    if not r:
        return {}, "", ""
    soup = BeautifulSoup(r.text, "html.parser")
    detail = {}
    summary = ""
    parties = ""
    # Try to get summary from description paragraphs
    body = soup.find("div", class_="document-body") or soup.find("div", class_="motie-body")
    if body:
        paras = [clean(p.get_text()) for p in body.find_all("p") if p.get_text().strip()]
        summary = " ".join(paras[:3])[:500]
    # Try to get party/indiener info from metadata
    for dt in soup.find_all("dt"):
        label = clean(dt.get_text()).lower()
        dd = dt.find_next_sibling("dd")
        if not dd:
            continue
        val = clean(dd.get_text())
        if "indiener" in label or "partij" in label or "fractie" in label:
            parties = val
        if "besluit" in label or "uitslag" in label or "resultaat" in label:
            detail["status_raw"] = val
    return detail, summary, parties


def scrape_list_page(page_num):
    url = BASE + "/modules/6/moties/view"
    params = {"ContentType": "Motie", "page": page_num}
    r = get(url, params=params)
    if not r:
        return [], False
    soup = BeautifulSoup(r.text, "html.parser")
    motions = []
    rows = soup.select("table tbody tr") or soup.select(".module-item") or soup.select(".list-item")
    if not rows:
        # Try any link containing /moties/ with an ID
        links = soup.find_all("a", href=True)
        rows = [l for l in links if "/moties/" in l["href"] and l["href"].split("/")[-1].isdigit()]
    for row in rows:
        motions.append(row)
    has_next = bool(soup.find("a", string=lambda s: s and "volgende" in s.lower()))
    return motions, has_next


def scrape_motions_module():
    log.info("Scraping amsterdam.raadsinformatie.nl moties module")
    results = []
    url = BASE + "/modules/6/moties/view"
    r = get(url)
    if not r:
        log.error("Could not reach raadsinformatie.nl")
        return results
    soup = BeautifulSoup(r.text, "html.parser")
    # Find all motion links
    all_links = soup.find_all("a", href=True)
    motion_links = []
    for a in all_links:
        href = a["href"]
        if "/moties/" in href:
            parts = href.rstrip("/").split("/")
            if parts[-1].isdigit():
                full = BASE + href if href.startswith("/") else href
                motion_links.append((parts[-1], full, clean(a.get_text())))
    log.info("Found %d motion links on listing page", len(motion_links))
    seen = set()
    for mid, link, title_text in motion_links:
        if mid in seen:
            continue
        seen.add(mid)
        log.info("Fetching motion %s", mid)
        detail, summary, parties_str = fetch_motion_detail(link)
        status_raw = detail.get("status_raw", "")
        status = map_status(status_raw) if status_raw else "Onbekend"
        title = title_text or "Motie " + mid
        results.append({
            "id": mid,
            "title": title,
            "date": datetime.utcnow().date().isoformat(),
            "party": parties_str,
            "parties": [parties_str] if parties_str else [],
            "topic": infer_topic(title + " " + summary),
            "status": status,
            "status_raw": status_raw,
            "for": 0,
            "against": 0,
            "abstain": 0,
            "summary": summary,
            "link": link,
        })
        time.sleep(DELAY)
    return results


def try_notubiz_api():
    log.info("Trying notubiz API")
    results = []
    # Amsterdam organisation ID on notubiz is 281
    # Confirmed from raadzaam.amsterdam.nl referencing api.notubiz.nl documents
    ORG_ID = 281
    base = "https://api.notubiz.nl"
    page = 1
    while page <= 60:
        try:
            r = SESSION.get(
                base + "/events/motions",
                params={
                    "organisation_id": ORG_ID,
                    "page": page,
                    "per_page": 50,
                    "sort": "date",
                    "order": "desc",
                },
                timeout=20,
            )
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            log.warning("Notubiz API error: %s", e)
            break
        items = data.get("items", data.get("results", []))
        if not items:
            break
        stop = False
        for raw in items:
            date_str = _parse_date(raw.get("date") or raw.get("meeting_date"))
            if not date_str:
                continue
            if date_str < START_DATE.isoformat():
                stop = True
                break
            parties_raw = raw.get("parties") or raw.get("submitters") or []
            if isinstance(parties_raw, list):
                parties = [clean(p.get("name", p) if isinstance(p, dict) else str(p)) for p in parties_raw]
            else:
                parties = []
            title = clean(raw.get("title") or raw.get("name") or "")
            summary = clean(raw.get("summary") or raw.get("description") or "")
            status_raw = raw.get("result") or raw.get("status") or ""
            results.append({
                "id": str(raw.get("id", "")),
                "title": title,
                "date": date_str,
                "party": parties[0] if parties else "",
                "parties": parties,
                "topic": infer_topic(title + " " + summary),
                "status": map_status(status_raw),
                "status_raw": clean(str(status_raw)),
                "for": 0,
                "against": 0,
                "abstain": 0,
                "summary": summary[:500],
                "link": raw.get("url") or "https://amsterdam.raadsinformatie.nl",
            })
        total_pages = data.get("meta", {}).get("total_pages", page)
        if stop or page >= total_pages:
            break
        page += 1
        time.sleep(DELAY)
    log.info("Notubiz API returned %d motions", len(results))
    return results


def _parse_date(raw):
    if not raw:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(raw)[:19], fmt).date().isoformat()
        except ValueError:
            continue
    return None


def load_existing():
    if OUTPUT_FILE.exists():
        try:
            return json.loads(OUTPUT_FILE.read_text(encoding="utf-8")).get("motions", [])
        except Exception:
            pass
    return []


def merge(existing, fresh):
    by_id = {m["id"]: m for m in existing}
    added = updated = 0
    for m in fresh:
        mid = m["id"]
        if mid not in by_id:
            by_id[mid] = m
            added += 1
        else:
            by_id[mid].update({k: m[k] for k in ("status", "status_raw", "for", "against", "abstain")})
            updated += 1
    log.info("Merge: +%d new, ~%d updated, %d total", added, updated, len(by_id))
    return sorted(by_id.values(), key=lambda m: m["date"], reverse=True)


def main():
    log.info("Scraper starting, coverage from %s", START_DATE)
    # Try notubiz API first (fastest)
    fresh = try_notubiz_api()
    # If that gave nothing, scrape the portal directly
    if not fresh:
        log.info("API empty, scraping portal")
        fresh = scrape_motions_module()
    log.info("Total fresh: %d", len(fresh))
    existing = load_existing()
    merged = merge(existing, fresh)
    meta = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "total": len(merged),
        "start_date": START_DATE.isoformat(),
        "source": "amsterdam.raadsinformatie.nl",
    }
    OUTPUT_FILE.write_text(
        json.dumps({"meta": meta, "motions": merged}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    log.info("Written %d motions to %s", len(merged), OUTPUT_FILE)


if __name__ == "__main__":
    main()

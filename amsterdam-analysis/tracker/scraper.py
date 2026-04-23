#!/usr/bin/env python3
# Amsterdam Motions Tracker
# Scrapes council meeting pages which are publicly accessible (unlike the listing page)
# Meeting pages contain motions with title, date, party, status
# Strategy: fetch known recent meeting IDs, parse motions from each page

import json, time, logging, re
from datetime import date, datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE = "https://amsterdam.raadsinformatie.nl"
START_DATE = date(2026, 1, 1)
OUTPUT_FILE = Path(__file__).parent / "motions.json"
DELAY = 1.5

# Known recent RAAD (city council, not committee) meeting IDs from search results
# Format: (meeting_id, meeting_date_approx)
# The scraper will also discover new meetings from the calendar
KNOWN_MEETINGS = [
    1483059,  # TAR 15-04-2026
    1475000,  # approx
    1470000,  # approx
    1465452,  # RAAD 18-02-2026
    1461820,  # commissie 12-02-2026
    1460000,  # approx
    1455000,  # approx
    1450000,  # approx
]

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
})


def get_html(url):
    try:
        r = S.get(url, timeout=20)
        log.info("GET %s -> %d", url, r.status_code)
        if r.status_code == 200:
            return r.text
        return None
    except Exception as e:
        log.warning("Failed %s: %s", url, e)
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


def parse_date_dutch(text):
    months = {"jan":1,"feb":2,"mrt":3,"maa":3,"apr":4,"mei":5,"jun":6,
              "jul":7,"aug":8,"sep":9,"okt":10,"nov":11,"dec":12}
    text = clean(text).lower()
    m = re.search(r"(\d{1,2})[\s\-](\w{3})[\w]*[\s\-](\d{4})", text)
    if m:
        mo = months.get(m.group(2)[:3])
        if mo:
            try: return date(int(m.group(3)), mo, int(m.group(1))).isoformat()
            except: pass
    m2 = re.search(r"(\d{2})-(\d{2})-(\d{4})", text)
    if m2:
        try: return date(int(m2.group(3)), int(m2.group(2)), int(m2.group(1))).isoformat()
        except: pass
    m3 = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m3:
        return m3.group(0)
    return None


def fetch_calendar_meeting_ids():
    """Fetch the calendar page to discover recent RAAD meeting IDs."""
    meeting_ids = []
    html = get_html(BASE + "/kalender")
    if not html:
        return meeting_ids
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        m = re.search(r"/vergadering/(\d+)", a["href"])
        if m:
            mid = int(m.group(1))
            text = clean(a.get_text()).upper()
            if "RAAD" in text and mid not in meeting_ids:
                meeting_ids.append(mid)
    log.info("Calendar: found %d RAAD meeting IDs", len(meeting_ids))
    return meeting_ids


def scrape_meeting(meeting_id):
    """Scrape motions from a single meeting page."""
    url = BASE + "/vergadering/" + str(meeting_id)
    html = get_html(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text()

    # Extract meeting date from page title or header
    meeting_date = None
    title_el = soup.find("h1") or soup.find("title")
    if title_el:
        meeting_date = parse_date_dutch(title_el.get_text())
    if not meeting_date:
        # Try any date pattern on the page
        m = re.search(r"(\d{2})-(\d{2})-(\d{4})", page_text)
        if m:
            try: meeting_date = date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
            except: pass

    if not meeting_date or meeting_date < START_DATE.isoformat():
        log.info("Meeting %d: date %s before cutoff, skipping", meeting_id, meeting_date)
        return []

    log.info("Meeting %d: date=%s, parsing motions...", meeting_id, meeting_date)
    motions = []

    # Find all motion/amendment links and text blocks
    # Pattern: links containing /modules/6/moties/ or text mentioning Motie NNN
    seen_ids = set()

    # Method 1: find explicit motion links
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/modules/6/moties/" in href or "/modules/7/" in href:
            m = re.search(r"/(\d+)$", href.rstrip("/"))
            if not m: continue
            doc_id = m.group(1)
            if doc_id in seen_ids: continue
            seen_ids.add(doc_id)
            title = clean(a.get_text())
            if not title or len(title) < 5: continue
            # Look for status near this element
            parent = a.find_parent(["li","div","tr","section"])
            context = clean(parent.get_text()) if parent else ""
            status_raw = ""
            for word in ("aangenomen","verworpen","aangehouden","geamendeerd","ingetrokken"):
                if word in context.lower():
                    status_raw = word
                    break
            # Extract party from context (look for known parties)
            party = extract_party(context)
            motions.append({
                "id": "AMS-" + doc_id,
                "title": title,
                "date": meeting_date,
                "party": party,
                "parties": [party] if party else [],
                "topic": infer_topic(title),
                "status": map_status(status_raw),
                "status_raw": status_raw,
                "for": 0, "against": 0, "abstain": 0,
                "summary": "",
                "link": BASE + "/vergadering/" + str(meeting_id),
            })

    # Method 2: find motion text patterns like "Motie 044 van het lid X inzake Y"
    # when not captured by links
    for m in re.finditer(r"(Motie|Amendement)\s+(\d+)\s+van\s+([^\n]{10,120})", page_text):
        doc_type = m.group(1)
        num = m.group(2)
        rest = clean(m.group(3))
        full_title = doc_type + " " + num + " van " + rest
        mid = "AMS-TXT-" + num + "-" + meeting_date.replace("-","")
        if mid in seen_ids: continue
        # Skip if we already have this motion number from a link
        already = any(num in existing["id"] for existing in motions)
        if already: continue
        seen_ids.add(mid)
        # Look for status in surrounding text
        start = m.start()
        context = page_text[max(0,start-100):start+300].lower()
        status_raw = ""
        for word in ("aangenomen","verworpen","aangehouden","geamendeerd","ingetrokken"):
            if word in context:
                status_raw = word
                break
        motions.append({
            "id": mid,
            "title": full_title[:200],
            "date": meeting_date,
            "party": "",
            "parties": [],
            "topic": infer_topic(full_title),
            "status": map_status(status_raw),
            "status_raw": status_raw,
            "for": 0, "against": 0, "abstain": 0,
            "summary": "",
            "link": BASE + "/vergadering/" + str(meeting_id),
        })

    log.info("Meeting %d: found %d motions", meeting_id, len(motions))
    return motions


def extract_party(text):
    parties = ["GroenLinks","PvdA","D66","VVD","CDA","SP","PvdD","BIJ1","DENK",
               "JA21","FvD","ChristenUnie","SGP","Volt","PRO","De Vonk",
               "Kune Burgers","Daan Wijnants","Havelaar","Kreuger","Van Berkel",
               "Von Gerhardt","Van Schijndel","Moeskops","IJmker","Belkasmi"]
    for p in parties:
        if p.lower() in text.lower():
            return p
    return ""


def discover_meeting_ids():
    """Build list of meeting IDs to scrape."""
    ids = set(KNOWN_MEETINGS)
    # Try calendar
    cal_ids = fetch_calendar_meeting_ids()
    ids.update(cal_ids)
    # Also probe a range around known IDs to find unlisted ones
    # Recent meetings are in range 1440000-1490000 based on search results
    probe_ids = list(range(1440000, 1490001, 1000))
    ids.update(probe_ids)
    return sorted(ids, reverse=True)


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
            by_id[mid].update({k: m[k] for k in ("status","status_raw")})
            updated += 1
    log.info("Merge: +%d new, ~%d updated, %d total", added, updated, len(by_id))
    return sorted(by_id.values(), key=lambda m: m["date"], reverse=True)


def main():
    log.info("Scraper starting, from %s", START_DATE)
    meeting_ids = discover_meeting_ids()
    log.info("Will probe %d meeting IDs", len(meeting_ids))
    fresh = []
    seen_motions = set()
    for mid in meeting_ids:
        motions = scrape_meeting(mid)
        for m in motions:
            if m["id"] not in seen_motions:
                seen_motions.add(m["id"])
                fresh.append(m)
        time.sleep(DELAY)
    log.info("Total fresh motions: %d", len(fresh))
    existing = load_existing()
    merged = merge(existing, fresh)
    meta = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "total": len(merged),
        "start_date": START_DATE.isoformat(),
        "source": "amsterdam.raadsinformatie.nl (meeting pages)",
    }
    OUTPUT_FILE.write_text(
        json.dumps({"meta": meta, "motions": merged}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    log.info("Written %d motions to %s", len(merged), OUTPUT_FILE)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
import json, time, logging, re
from datetime import date, datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

BASE = "https://amsterdam.raadsinformatie.nl"
START_DATE = date(2025, 6, 1)
OUTPUT_FILE = Path(__file__).parent / "motions.json"
DELAY = 1.5

S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; AmsterdamMotionsTracker/1.0)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
})


def fetch(url, params=None):
    try:
        r = S.get(url, params=params, timeout=30)
        log.info("GET %s -> %d (%d bytes)", url, r.status_code, len(r.content))
        r.raise_for_status()
        return r
    except Exception as exc:
        log.error("fetch failed %s: %s", url, exc)
        return None


def clean(t):
    if not t: return ""
    return " ".join(str(t).split())


def parse_dutch_date(text):
    months = {"januari":1,"februari":2,"maart":3,"april":4,"mei":5,"juni":6,
              "juli":7,"augustus":8,"september":9,"oktober":10,"november":11,"december":12}
    text = clean(text).lower()
    m = re.search(r"(\d{1,2})\s+(\w+)\s+(\d{4})", text)
    if m:
        day, mon, yr = m.group(1), m.group(2), m.group(3)
        mo = months.get(mon)
        if mo:
            try: return date(int(yr), mo, int(day)).isoformat()
            except: pass
    m2 = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m2:
        return m2.group(0)
    return None


def map_status(raw):
    s = str(raw).lower()
    if any(k in s for k in ("aangenomen", "passed", "approved", "aanvaard")): return "Aangenomen"
    if any(k in s for k in ("verworpen", "rejected", "afgekeurd")): return "Verworpen"
    if any(k in s for k in ("aangehouden", "ingetrokken", "withdrawn", "pending")): return "Aangehouden"
    if any(k in s for k in ("geamendeerd", "amended", "gewijzigd")): return "Geamendeerd"
    return "Onbekend"


def infer_topic(text):
    t = text.lower()
    rules = [
        ("Housing",     ["wonen","huur","woningbouw","airbnb","woonruimte","sociale huur"]),
        ("Mobility",    ["fiets","verkeer","metro","tram","parkeer","bereikbaar"]),
        ("Climate",     ["klimaat","groen","duurzaam","energie","aardgas","co2","plastic"]),
        ("Safety",      ["veiligheid","politie","camera","criminaliteit","handhaving","overlast"]),
        ("Social",      ["zorg","armoed","daklozen","welzijn","jeugd","schulden"]),
        ("Education",   ["school","integratie","discriminatie","onderwijs"]),
        ("PublicSpace", ["openbare ruimte","park","plein","markt","toilet"]),
        ("Finance",     ["begroting","subsidie","budget","financ"]),
        ("Governance",  ["democratie","bestuur","raad","motie"]),
    ]
    for topic, kws in rules:
        if any(k in t for k in kws): return topic
    return "Other"


def scrape_motions():
    results = []
    # Fetch the moties listing page
    url = BASE + "/modules/6/moties/view"
    r = fetch(url)
    if not r:
        log.error("Cannot reach moties listing page")
        return results

    soup = BeautifulSoup(r.text, "html.parser")

    # Debug: show page title
    title = soup.find("title")
    log.info("Page title: %s", title.get_text() if title else "none")

    # Find all links to individual motions
    # Pattern: /modules/6/moties/NNNNNN
    found_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = re.search(r"/modules/6/moties/(\d+)", href)
        if m:
            mid = m.group(1)
            full_url = BASE + "/modules/6/moties/" + mid
            label = clean(a.get_text())
            if mid not in [x[0] for x in found_links]:
                found_links.append((mid, full_url, label))

    log.info("Found %d motion links on listing page", len(found_links))

    # Also try to find table rows with dates
    rows = soup.select("table tr") or soup.select(".list-item") or soup.select("li")
    log.info("Found %d table/list rows", len(rows))

    # Debug: log raw HTML snippet (first 2000 chars) to understand structure
    log.info("HTML snippet: %s", r.text[:2000].replace("\n", " "))

    for mid, link, label in found_links:
        time.sleep(DELAY)
        dr = fetch(link)
        if not dr:
            continue
        dsoup = BeautifulSoup(dr.text, "html.parser")

        # Extract title
        h1 = dsoup.find("h1") or dsoup.find("h2")
        title_text = clean(h1.get_text()) if h1 else label

        # Extract date from meta or content
        date_str = None
        for el in dsoup.find_all(["td","dd","span","div","p"])[:30]:
            d = parse_dutch_date(el.get_text())
            if d:
                date_str = d
                break
        if not date_str:
            date_str = datetime.utcnow().date().isoformat()

        # Skip if before start date
        if date_str < START_DATE.isoformat():
            log.info("Skipping %s (date %s before cutoff)", mid, date_str)
            continue

        # Extract status
        status_raw = ""
        status = "Onbekend"
        for dt in dsoup.find_all("dt"):
            lbl = clean(dt.get_text()).lower()
            dd = dt.find_next_sibling("dd")
            if not dd: continue
            val = clean(dd.get_text())
            if any(k in lbl for k in ("besluit","uitslag","resultaat","status","beslissing")):
                status_raw = val
                status = map_status(val)
        # Also check page text for common status words
        page_text = clean(dsoup.get_text()[:3000]).lower()
        if not status_raw:
            for word in ("aangenomen","verworpen","aangehouden","geamendeerd"):
                if word in page_text:
                    status = map_status(word)
                    status_raw = word
                    break

        # Extract parties
        parties = []
        for dt in dsoup.find_all("dt"):
            lbl = clean(dt.get_text()).lower()
            dd = dt.find_next_sibling("dd")
            if not dd: continue
            if any(k in lbl for k in ("indiener","partij","fractie","penvoerder")):
                val = clean(dd.get_text())
                if val:
                    parties = [p.strip() for p in re.split(r"[,;/]", val) if p.strip()]

        # Extract summary
        summary = ""
        body = dsoup.find("div", class_=re.compile(r"body|content|tekst|motie", re.I))
        if body:
            paras = [clean(p.get_text()) for p in body.find_all("p") if p.get_text().strip()]
            summary = " ".join(paras[:3])[:500]

        results.append({
            "id": mid,
            "title": title_text,
            "date": date_str,
            "party": parties[0] if parties else "",
            "parties": parties,
            "topic": infer_topic(title_text + " " + summary),
            "status": status,
            "status_raw": status_raw,
            "for": 0,
            "against": 0,
            "abstain": 0,
            "summary": summary,
            "link": link,
        })
        log.info("Scraped: %s | %s | %s | %s", mid, date_str, status, title_text[:60])

    log.info("Total scraped: %d motions", len(results))
    return results


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
            by_id[mid] = m; added += 1
        else:
            by_id[mid].update({k: m[k] for k in ("status","status_raw","for","against","abstain")})
            updated += 1
    log.info("Merge: +%d new, ~%d updated, %d total", added, updated, len(by_id))
    return sorted(by_id.values(), key=lambda m: m["date"], reverse=True)


def main():
    log.info("Scraper starting, coverage from %s", START_DATE)
    fresh = scrape_motions()
    if not fresh:
        log.warning("No motions found. Check the HTML snippet above in the logs.")
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

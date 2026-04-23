#!/usr/bin/env python3
# Amsterdam Motions Tracker - hybrid scraper
# Strategy 1: Notubiz API (api.notubiz.nl) - tries Amsterdam org directly
# Strategy 2: Excel fallback - reads moties.xlsx if present
#
# To update manually:
#   1. Download Excel from amsterdam.raadsinformatie.nl/modules/6/moties/view
#   2. Save as amsterdam-analysis/tracker/moties.xlsx and commit

import json, logging, sys, re, time
from datetime import date, datetime
from pathlib import Path
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

START_DATE = date(2026, 1, 1)
OUTPUT_FILE = Path(__file__).parent / "motions.json"
XLSX_FILE   = Path(__file__).parent / "moties.xlsx"

S = requests.Session()
S.headers.update({"Accept": "application/json", "User-Agent": "AmsterdamMotionsTracker/1.0"})


def clean(v):
    return " ".join(str(v).split()) if v else ""


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


def parse_date(v):
    if not v: return None
    if hasattr(v, "strftime"): return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
        try: return datetime.strptime(s[:len(fmt)], fmt).date().isoformat()
        except: continue
    return None


# ---- Strategy 1: Notubiz API ----

def try_notubiz_api():
    """Try to fetch motions from api.notubiz.nl with Amsterdam org IDs."""
    # Amsterdam has multiple possible org IDs in Notubiz.
    # We try a range of plausible IDs and see which one returns motions.
    # Confirmed from raadzaam.amsterdam.nl that they use api.notubiz.nl
    results = []
    base = "https://api.notubiz.nl"

    # First: list all organisations and find Amsterdam
    try:
        r = S.get(base + "/organisations", timeout=15)
        log.info("Notubiz /organisations -> %d", r.status_code)
        if r.ok:
            orgs = r.json()
            items = orgs.get("items", orgs.get("results", orgs if isinstance(orgs, list) else []))
            for org in items:
                name = str(org.get("name","")).lower()
                if "amsterdam" in name:
                    log.info("Found org: %s id=%s", org.get("name"), org.get("id"))
    except Exception as e:
        log.warning("Notubiz orgs failed: %s", e)

    # Try known Amsterdam organisation IDs
    # amsterdam.notubiz.nl -> typical ID range for large cities is 1-500
    for org_id in [281, 280, 479, 478, 1, 2, 3, 4, 5, 10, 20, 50, 100]:
        try:
            r = S.get(base + "/events/meetings",
                      params={"organisation_id": org_id, "page": 1, "per_page": 5},
                      timeout=15)
            if r.ok:
                data = r.json()
                items = data.get("items", data.get("results", []))
                if items:
                    # Check if this looks like Amsterdam
                    sample = str(items[0]).lower()
                    if "amsterdam" in sample or len(items) > 0:
                        log.info("Org %d: found %d meetings - trying motions", org_id, len(items))
                        motions = fetch_notubiz_motions(base, org_id)
                        if motions:
                            log.info("Org %d: found %d motions!", org_id, len(motions))
                            return motions
        except Exception as e:
            log.debug("Org %d failed: %s", org_id, e)
        time.sleep(0.2)
    return results


def fetch_notubiz_motions(base, org_id):
    results = []
    page = 1
    while page <= 50:
        try:
            r = S.get(base + "/events/motions",
                      params={"organisation_id": org_id, "page": page,
                              "per_page": 50, "sort": "date", "order": "desc"},
                      timeout=20)
            if not r.ok: break
            data = r.json()
            items = data.get("items", data.get("results", []))
            if not items: break
            for raw in items:
                d = parse_date(raw.get("date") or raw.get("meeting_date"))
                if not d: continue
                if d < START_DATE.isoformat(): return results
                title = clean(raw.get("title") or raw.get("name") or "")
                if not title: continue
                parties_raw = raw.get("parties") or raw.get("submitters") or []
                parties = [clean(p.get("name",p) if isinstance(p,dict) else p) for p in parties_raw]
                status_raw = clean(raw.get("result") or raw.get("status") or "")
                results.append({
                    "id": str(raw.get("id","")),
                    "title": title,
                    "date": d,
                    "party": parties[0] if parties else "",
                    "parties": parties,
                    "topic": infer_topic(title),
                    "status": map_status(status_raw),
                    "status_raw": status_raw,
                    "for": 0, "against": 0, "abstain": 0,
                    "summary": clean(raw.get("summary") or raw.get("description") or ""),
                    "link": raw.get("url") or "https://amsterdam.raadsinformatie.nl",
                })
            total_pages = data.get("meta",{}).get("total_pages", page)
            if page >= total_pages: break
            page += 1
            time.sleep(0.3)
        except Exception as e:
            log.warning("Page %d error: %s", page, e)
            break
    return results


# ---- Strategy 2: Excel fallback ----

def try_excel():
    if not XLSX_FILE.exists():
        log.info("No Excel file found at %s", XLSX_FILE)
        return []
    try:
        import openpyxl
    except ImportError:
        log.error("pip install openpyxl needed for Excel fallback")
        return []

    log.info("Reading Excel: %s", XLSX_FILE)
    wb = openpyxl.load_workbook(XLSX_FILE, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    # Find header row
    header_idx = None
    for i, row in enumerate(rows):
        if any("titel" in str(c).lower() for c in row if c):
            header_idx = i; break
    if header_idx is None:
        log.error("No TITEL column found in Excel")
        return []

    headers = [str(c).lower().strip() if c else "" for c in rows[header_idx]]
    log.info("Excel headers: %s", list(rows[header_idx]))

    def col(*names):
        for name in names:
            for i, h in enumerate(headers):
                if name in h or h in name:
                    return i
        return None

    c_title  = col("titel", "title")
    c_date   = col("datum indiening", "indiening", "datum")
    c_party  = col("fractie", "indiener", "partij")
    c_status = col("uitslag", "besluit", "resultaat")
    c_event  = col("gekoppeld evenement", "evenement")
    c_settled= col("datum afdoening", "afdoening")

    motions = []
    for i, row in enumerate(rows[header_idx+1:], start=header_idx+2):
        def cell(c):
            if c is None or c >= len(row): return ""
            return clean(row[c])
        title = cell(c_title)
        if not title: continue
        raw_date = row[c_date] if c_date is not None and c_date < len(row) else None
        if not raw_date and c_settled is not None:
            raw_date = row[c_settled] if c_settled < len(row) else None
        d = parse_date(raw_date)
        if not d or d < START_DATE.isoformat(): continue
        party_raw = cell(c_party)
        parties = [p.strip() for p in re.split(r"[,;/]", party_raw) if p.strip()]
        status_raw = cell(c_status)
        num = (re.search(r"\b(\d{3})\b", title) or re.search(r"\b(\d+)\b", title))
        num = num.group(1) if num else str(i)
        motion_id = "M" + d[:4] + "-" + num
        motions.append({
            "id": motion_id,
            "title": title,
            "date": d,
            "party": parties[0] if parties else "",
            "parties": parties,
            "topic": infer_topic(title),
            "status": map_status(status_raw),
            "status_raw": status_raw,
            "for": 0, "against": 0, "abstain": 0,
            "summary": cell(c_event),
            "link": "https://amsterdam.raadsinformatie.nl/modules/6/moties/view",
        })
        log.info("  %s | %s | %s | %s", motion_id, d, map_status(status_raw), title[:60])
    log.info("Excel: loaded %d motions", len(motions))
    return motions


def main():
    log.info("Scraper starting from %s", START_DATE)

    # Try Notubiz API first
    motions = try_notubiz_api()

    # Fall back to Excel if API gave nothing
    if not motions:
        log.info("API returned nothing, trying Excel fallback")
        motions = try_excel()

    if not motions:
        log.warning("No motions found from any source.")
        log.warning("To populate data manually:")
        log.warning("  1. Go to amsterdam.raadsinformatie.nl/modules/6/moties/view")
        log.warning("  2. Export to Excel")
        log.warning("  3. Save as amsterdam-analysis/tracker/moties.xlsx and commit")

    motions.sort(key=lambda m: m["date"], reverse=True)
    meta = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "total": len(motions),
        "start_date": START_DATE.isoformat(),
        "source": "api.notubiz.nl or manual Excel upload",
    }
    OUTPUT_FILE.write_text(
        json.dumps({"meta": meta, "motions": motions}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    log.info("Written %d motions to %s", len(motions), OUTPUT_FILE)


if __name__ == "__main__":
    main()

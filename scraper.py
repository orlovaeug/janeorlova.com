#!/usr/bin/env python3
import json, logging, re
from datetime import date, datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

START_DATE  = date(2026, 1, 1)
_xlsx = Path(__file__).parent / "moties.xlsx"
_xls  = Path(__file__).parent / "moties.xls"
XLSX_FILE   = _xlsx if _xlsx.exists() else _xls
OUTPUT_FILE = Path(__file__).parent / "motions.json"


def map_status(raw):
    s = str(raw).lower()
    if any(k in s for k in ("aangenomen","passed","approved","aanvaard")): return "Aangenomen"
    if any(k in s for k in ("verworpen","rejected","afgekeurd","niet aangenomen")): return "Verworpen"
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
        ("Social",      ["zorg","armoed","daklozen","welzijn","jeugd","opvang"]),
        ("Education",   ["school","integratie","discriminatie","onderwijs"]),
        ("PublicSpace", ["openbare ruimte","park","plein","markt","toilet","evenement"]),
        ("Finance",     ["begroting","subsidie","budget","financ","belasting"]),
        ("Governance",  ["democratie","bestuur","raad","motie","college","wethouder"]),
    ]
    for topic, kws in rules:
        if any(k in t for k in kws): return topic
    return "Other"


def parse_date(v):
    if not v: return None
    if hasattr(v, "strftime"): return v.strftime("%Y-%m-%d")
    s = str(v).strip()
    if not s or s.lower() in ("none","nan",""): return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"):
        try: return datetime.strptime(s[:len(fmt)], fmt).date().isoformat()
        except: continue
    return None


def clean(v):
    return " ".join(str(v).split()) if v else ""


def col_idx(headers, *names):
    h = [str(x).lower().strip() if x else "" for x in headers]
    for name in names:
        n = name.lower()
        for i, hdr in enumerate(h):
            if n == hdr or n in hdr or hdr in n:
                return i
    return None


def load_xlsx():
    import openpyxl
    wb = openpyxl.load_workbook(XLSX_FILE, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    # Find header row
    hdr_idx = None
    for i, row in enumerate(rows):
        if any("titel" in str(c).lower() for c in row if c):
            hdr_idx = i
            break
    if hdr_idx is None:
        log.error("No TITEL column found. First rows: %s", rows[:3])
        return []

    hdrs = rows[hdr_idx]
    log.info("Headers: %s", [str(c) for c in hdrs if c])

    c_title   = col_idx(hdrs, "titel")
    c_date    = col_idx(hdrs, "datum indiening", "indiening")
    c_party   = col_idx(hdrs, "fractie", "indiener")
    c_status  = col_idx(hdrs, "uitslag")
    c_event   = col_idx(hdrs, "gekoppeld evenement", "evenement")
    c_toelichting = col_idx(hdrs, "toelichting afdoening", "toelichting")

    log.info("Columns: title=%s date=%s party=%s status=%s", c_title, c_date, c_party, c_status)

    # Log first 3 data rows in full to see raw values
    for i, row in enumerate(rows[hdr_idx+1:hdr_idx+4], start=hdr_idx+2):
        log.info("DATA ROW %d raw: %s", i, list(row[:10]))
        if c_date is not None and c_date < len(row):
            log.info("  date cell raw value: %r type: %s", row[c_date], type(row[c_date]).__name__)

    motions = []
    last_date = None

    for i, row in enumerate(rows[hdr_idx+1:], start=hdr_idx+2):
        def cell(c):
            if c is None or c >= len(row): return ""
            return clean(row[c])

        # Always try to update last_date from this row regardless of title
        if c_date is not None and c_date < len(row):
            d_try = parse_date(row[c_date])
            if d_try:
                last_date = d_try

        title = cell(c_title)
        if not title: continue

        d = last_date
        if not d:
            log.warning("Row %d: no date yet, skipping: %s", i, title[:60])
            continue
        if d < START_DATE.isoformat():
            continue

        party_raw = cell(c_party)
        parties = [p.strip() for p in re.split(r"[,;/\n]", party_raw) if p.strip()]

        status_raw = cell(c_status)
        status = map_status(status_raw)

        num_m = re.search(r"\b(\d{3})\b", title)
        num = num_m.group(1) if num_m else str(i)
        motion_id = "M" + d[:4] + "-" + num

        event = cell(c_event)
        toelichting = cell(c_toelichting) if c_toelichting is not None else ""
        summary = toelichting or event

        motions.append({
            "id":         motion_id,
            "title":      title,
            "date":       d,
            "party":      parties[0] if parties else "",
            "parties":    parties,
            "topic":      infer_topic(title),
            "status":     status,
            "status_raw": status_raw,
            "for":        0,
            "against":    0,
            "abstain":    0,
            "summary":    summary[:400],
            "link":       "https://amsterdam.raadsinformatie.nl/modules/6/moties/view",
        })
        log.info("OK %s | %s | %s | %s", motion_id, d, status, title[:60])

    log.info("Loaded %d motions", len(motions))
    return motions


def main():
    log.info("Converting %s -> motions.json", XLSX_FILE.name)
    if not XLSX_FILE.exists():
        log.error("File not found. Upload moties.xlsx to amsterdam-analysis/tracker/")
        meta = {"last_updated": datetime.utcnow().isoformat()+"Z","total":0,
                "start_date": START_DATE.isoformat(),"source":"excel"}
        OUTPUT_FILE.write_text(json.dumps({"meta":meta,"motions":[]},indent=2),encoding="utf-8")
        return

    motions = load_xlsx()
    motions.sort(key=lambda m: m["date"], reverse=True)
    meta = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "total":        len(motions),
        "start_date":   START_DATE.isoformat(),
        "source":       "amsterdam.raadsinformatie.nl (Excel)",
    }
    OUTPUT_FILE.write_text(
        json.dumps({"meta": meta, "motions": motions}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    log.info("Written %d motions to %s", len(motions), OUTPUT_FILE)


if __name__ == "__main__":
    main()

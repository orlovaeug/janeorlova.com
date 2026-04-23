#!/usr/bin/env python3
# Amsterdam Motions Tracker - Excel converter
# 1. Download Excel from amsterdam.raadsinformatie.nl/modules/6/moties/view
# 2. Save as amsterdam-analysis/tracker/moties.xlsx
# 3. Commit and push - this script runs automatically via GitHub Actions

import json, logging, re
from datetime import date, datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

START_DATE  = date(2026, 1, 1)
# Accept both .xlsx and .xls formats
_xlsx = Path(__file__).parent / "moties.xlsx"
_xls  = Path(__file__).parent / "moties.xls"
XLSX_FILE = _xlsx if _xlsx.exists() else _xls
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
        ("Housing",     ["wonen","huur","woningbouw","airbnb","woonruimte","sociale huur"]),
        ("Mobility",    ["fiets","verkeer","metro","tram","parkeer","bereikbaar"]),
        ("Climate",     ["klimaat","groen","duurzaam","energie","aardgas","co2","plastic"]),
        ("Safety",      ["veiligheid","politie","camera","handhaving","overlast","criminaliteit"]),
        ("Social",      ["zorg","armoed","daklozen","welzijn","jeugd","schulden","opvang"]),
        ("Education",   ["school","integratie","discriminatie","onderwijs","antisemit"]),
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
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
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
    if XLSX_FILE.suffix.lower() == ".xls":
        log.error("File is .xls (old format). Please re-save as .xlsx in Excel/Numbers and re-upload.")
        log.error("Or rename: git mv amsterdam-analysis/tracker/moties.xls amsterdam-analysis/tracker/moties.xlsx")
        return []
    wb = openpyxl.load_workbook(XLSX_FILE, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    # Find header row - look for TITEL
    hdr_idx = None
    for i, row in enumerate(rows):
        if any("titel" in str(c).lower() for c in row if c):
            hdr_idx = i
            break
    if hdr_idx is None:
        log.error("Cannot find header row. Columns found: %s", [str(c) for c in rows[0] if c])
        return []

    hdrs = rows[hdr_idx]
    log.info("All rows preview:")
    for preview_i, preview_row in enumerate(rows[:5]):
        log.info("  Row %d: %s", preview_i, [str(c)[:30] for c in preview_row if c])
    log.info("Header row index: %d", hdr_idx)
    log.info("Headers: %s", [str(c) for c in hdrs if c])

    # Map exact Amsterdam Excel columns
    c_title   = col_idx(hdrs, "titel")
    c_date    = col_idx(hdrs, "datum indiening", "indiening")
    c_party   = col_idx(hdrs, "fractie", "indiener")
    c_status  = col_idx(hdrs, "uitslag")
    c_type    = col_idx(hdrs, "type")
    c_event   = col_idx(hdrs, "gekoppeld evenement", "evenement")
    c_settled = col_idx(hdrs, "datum afdoening", "afdoening")

    log.info("Column mapping: title=%s date=%s party=%s status=%s event=%s",
             c_title, c_date, c_party, c_status, c_event)

    motions = []
    last_date = None  # carry forward date across grouped rows
    for i, row in enumerate(rows[hdr_idx + 1:], start=hdr_idx + 2):
        def cell(c):
            if c is None or c >= len(row): return ""
            return clean(row[c])

        title = cell(c_title)
        if not title: continue

        # Date may only appear on first row of a grouped motion - carry it forward
        raw_date = (row[c_date] if c_date is not None and c_date < len(row) else None)
        if not raw_date and c_settled is not None:
            raw_date = row[c_settled] if c_settled < len(row) else None
        d = parse_date(raw_date)
        if d:
            last_date = d  # update carried date whenever we see a new one
        else:
            d = last_date  # use last known date
        if not d:
            log.warning("Row %d: no date at all, skipping: %s", i, title[:50])
            continue
        if d < START_DATE.isoformat():
            continue

        # Extract motion number for stable ID
        num_match = re.search(r"\b(\d{3})\b", title)
        num = num_match.group(1) if num_match else str(i)
        motion_id = "M" + d[:4] + "-" + num

        party_raw = cell(c_party)
        parties = [p.strip() for p in re.split(r"[,;\n/]", party_raw) if p.strip()]

        status_raw = cell(c_status)
        status = map_status(status_raw)

        doc_type = cell(c_type)
        event    = cell(c_event)

        motions.append({
            "id":         motion_id,
            "title":      title,
            "date":       d,
            "party":      parties[0] if parties else "",
            "parties":    parties,
            "topic":      infer_topic(title),
            "status":     status,
            "status_raw": status_raw,
            "type":       doc_type,
            "for":        0,
            "against":    0,
            "abstain":    0,
            "summary":    event,
            "link":       "https://amsterdam.raadsinformatie.nl/modules/6/moties/view",
        })
        log.info("  %s | %s | %-12s | %s", motion_id, d, status, title[:60])

    log.info("Loaded %d motions from %s onwards", len(motions), START_DATE)
    return motions


def main():
    log.info("Converting moties.xlsx to motions.json")
    if not XLSX_FILE.exists():
        log.error("Excel file missing. Looked for moties.xlsx and moties.xls")
        log.error("Download from: https://amsterdam.raadsinformatie.nl/modules/6/moties/view")
        log.error("Save as amsterdam-analysis/tracker/moties.xlsx and commit to repo")
        # Write empty JSON so site does not break
        meta = {"last_updated": datetime.utcnow().isoformat() + "Z",
                "total": 0, "start_date": START_DATE.isoformat(),
                "source": "amsterdam.raadsinformatie.nl (Excel export)"}
        OUTPUT_FILE.write_text(
            json.dumps({"meta": meta, "motions": []}, ensure_ascii=False, indent=2),
            encoding="utf-8")
        return

    motions = load_xlsx()
    motions.sort(key=lambda m: m["date"], reverse=True)

    meta = {
        "last_updated": datetime.utcnow().isoformat() + "Z",
        "total":        len(motions),
        "start_date":   START_DATE.isoformat(),
        "source":       "amsterdam.raadsinformatie.nl (Excel export)",
    }
    OUTPUT_FILE.write_text(
        json.dumps({"meta": meta, "motions": motions}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    log.info("Done: %d motions written to %s", len(motions), OUTPUT_FILE)


if __name__ == "__main__":
    main()

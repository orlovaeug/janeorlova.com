#!/usr/bin/env python3
import json
import re
import sys
import argparse
import datetime
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    sys.exit("Missing deps. Run: pip install requests beautifulsoup4")

WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/Next_Dutch_general_election"

# Columns as they appear on this specific page
SEAT_COLUMNS = [
    "D66", "PVV", "VVD", "GL-PvdA", "CDA", "JA21",
    "FvD", "BBB", "Denk", "SGP", "PvdD", "CU", "SP", "50+", "Volt",
]

# Map GL-PvdA (Wikipedia) -> GL/PvdA (our display name)
PARTY_NAME_MAP = {
    "GL-PvdA": "GL/PvdA",
}

FIRM_MAP = {
    "ipsos i&o": "Ipsos I&O",
    "ipsos":     "Ipsos I&O",
    "i&o research": "Ipsos I&O",
    "peil.nl":   "Peil.nl",
    "peil":      "Peil.nl",
    "verian":    "Verian",
    "eenvandaag": "EenVandaag",
    "kantar":    "Kantar",
}

EVENTS = [
    {"date": "2025-06-15", "text": "PVV withdraws from Schoof coalition over migration policy, triggering snap election."},
    {"date": "2025-08-01", "text": "NSC leaves caretaker Schoof cabinet, leaving only VVD and BBB as remaining partners."},
    {"date": "2025-10-29", "text": "General election: D66 and PVV tie at 26 seats. D66 achieves best-ever result. NSC collapses."},
    {"date": "2025-11-03", "text": "Jesse Klaver succeeds Frans Timmermans as leader of GL-PvdA."},
    {"date": "2026-01-20", "text": "Seven MPs leave the PVV to form the Markuszower Group, weakening Wilders bloc."},
    {"date": "2026-02-20", "text": "Caroline van der Plas hands over leadership of BBB to Henk Vermeer."},
    {"date": "2026-02-23", "text": "The Jetten cabinet (D66-VVD-CDA-GL/PvdA) is sworn in."},
    {"date": "2026-03-18", "text": "Dutch municipal elections held. D66 gains; VVD loses significantly in major cities."},
]

ELECTION_RESULT = {
    "date": "2025-10-29",
    "firm": "Election Result",
    "data": {
        "D66": 26, "PVV": 26, "GL/PvdA": 20, "VVD": 22, "CDA": 14,
        "JA21": 9, "FvD": 7, "BBB": 4, "NSC": 3, "SP": 5,
        "PvdD": 3, "SGP": 3, "CU": 3, "Volt": 1, "50+": 2, "Denk": 3,
    }
}


def fetch_page(url):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; DutchPollTracker/1.0)"}
    resp = requests.get(url, headers=headers, timeout=20)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def normalise_firm(raw):
    key = raw.strip().lower()
    for pattern, name in FIRM_MAP.items():
        if pattern in key:
            return name
    return raw.strip().title()


def parse_date(raw):
    raw = re.sub(r'\[.*?\]', '', raw).strip()
    # Split on en-dash or hyphen, take the end date of the range
    parts = re.split(r'\s*[\u2013\-]\s*', raw)
    for part in reversed(parts):
        part = part.strip()
        # If bare day number, grab month+year from the original string
        if re.match(r'^\d{1,2}$', part):
            my = re.search(r'[A-Za-z]+ \d{4}', raw)
            if my:
                part = part + ' ' + my.group(0)
        for fmt in ("%d %b %Y", "%d %B %Y"):
            try:
                return datetime.datetime.strptime(part.strip(), fmt).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return None


def scrape_polls(soup):
    polls = []
    tables = soup.find_all("table", class_="wikitable")

    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 3:
            continue

        # Find the header row that contains party columns
        header_texts = []
        for row in rows[:3]:
            texts = [c.get_text(strip=True) for c in row.find_all(["th", "td"])]
            if sum(1 for t in texts if t in SEAT_COLUMNS) >= 5:
                header_texts = texts
                break

        if not header_texts:
            continue

        # Skip percentage tables
        if any('%' in h for h in header_texts):
            continue

        # Build column index
        col_index = {}
        for i, h in enumerate(header_texts):
            if h in SEAT_COLUMNS:
                col_index[h] = i

        firm_col = next(
            (i for i, h in enumerate(header_texts)
             if any(k in h.lower() for k in ["polling", "firm", "pollster"])),
            0
        )
        date_col = next(
            (i for i, h in enumerate(header_texts)
             if any(k in h.lower() for k in ["fieldwork", "date"])),
            1
        )

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 5:
                continue

            raw_firm = cells[firm_col].get_text(strip=True) if firm_col < len(cells) else ""
            raw_date = cells[date_col].get_text(strip=True) if date_col < len(cells) else ""

            if not raw_firm:
                continue
            low = raw_firm.lower()
            if any(k in low for k in ["election", "result", "average"]):
                continue

            firm = normalise_firm(raw_firm)
            date = parse_date(raw_date)
            if not date:
                continue

            data = {}
            for wiki_name, idx in col_index.items():
                if idx >= len(cells):
                    continue
                val = re.sub(r'\[.*?\]', '', cells[idx].get_text(strip=True)).strip()
                val = val.replace('\u2013', '').replace('-', '').strip()
                if val.isdigit():
                    display_name = PARTY_NAME_MAP.get(wiki_name, wiki_name)
                    data[display_name] = int(val)

            if len(data) < 3:
                continue

            polls.append({"date": date, "firm": firm, "data": data})

    # Deduplicate
    seen = set()
    unique = []
    for p in polls:
        key = p["date"] + "|" + p["firm"]
        if key not in seen:
            seen.add(key)
            unique.append(p)

    unique.sort(key=lambda p: p["date"], reverse=True)
    return unique


def build_output(polls):
    all_polls = polls + [ELECTION_RESULT]
    all_polls.sort(key=lambda p: p["date"], reverse=True)
    return {
        "updated": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": "Wikipedia - Next Dutch general election",
        "polls": all_polls,
        "events": sorted(EVENTS, key=lambda e: e["date"]),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("Fetching Wikipedia page...", file=sys.stderr)
    try:
        soup = fetch_page(WIKIPEDIA_URL)
    except Exception as e:
        sys.exit("Failed to fetch Wikipedia: " + str(e))

    print("Parsing poll tables...", file=sys.stderr)
    polls = scrape_polls(soup)

    if not polls:
        sys.exit("No polls found - Wikipedia table structure may have changed.")

    print("Found " + str(len(polls)) + " polls.", file=sys.stderr)
    output = build_output(polls)
    json_str = json.dumps(output, ensure_ascii=False, indent=2)

    if args.dry_run:
        print(json_str)
        return

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = Path(__file__).parent.parent / "data" / "polls.json"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json_str, encoding="utf-8")
    print("Written to " + str(out_path), file=sys.stderr)
    print("Latest poll: " + polls[0]["date"] + " by " + polls[0]["firm"], file=sys.stderr)


if __name__ == "__main__":
    main()

import requests
from bs4 import BeautifulSoup
import json
import re
import os
from datetime import datetime

WIKI_URL = "https://en.wikipedia.org/wiki/Next_Dutch_general_election"

PARTIES = ["D66", "PVV", "VVD", "GL-PvdA", "CDA", "JA21", "FvD", "BBB", "Denk", "SGP", "PvdD", "CU", "SP", "50+", "Volt"]

KEY_EVENTS = [
    {"date": "2025-10-29", "text": "2025 election: D66 and PVV tie at 26 seats each"},
    {"date": "2025-11-03", "text": "Jesse Klaver succeeds Timmermans as GL-PvdA leader"},
    {"date": "2026-01-20", "text": "Seven MPs leave PVV to form the Markuszower Group"},
    {"date": "2026-02-20", "text": "Van der Plas hands BBB leadership to Henk Vermeer"},
    {"date": "2026-02-23", "text": "The Jetten cabinet is sworn in"},
]

def clean(text):
    return re.sub(r"[\[\]daggers*]|\(\d+\)", "", text).strip()

def parse_seats(text):
    text = clean(text)
    m = re.search(r"\d+", text)
    return int(m.group()) if m else None

def parse_date(text):
    text = clean(text)
    months = {"Jan":1,"Feb":2,"Mar":3,"Apr":4,"May":5,"Jun":6,
               "Jul":7,"Aug":8,"Sep":9,"Oct":10,"Nov":11,"Dec":12}
    m = re.findall(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", text)
    if m:
        day, mon, year = m[-1]
        mon_num = months.get(mon[:3].capitalize())
        if mon_num:
            return f"{year}-{mon_num:02d}-{int(day):02d}"
    return None

def scrape():
    print(f"Fetching {WIKI_URL} ...")
    r = requests.get(WIKI_URL, headers={"User-Agent": "janeorlova-poll-tracker/1.0"}, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    polls = []
    tables = soup.find_all("table", class_=re.compile("wikitable"))

    for table in tables:
        rows = table.find_all("tr")
        if not rows:
            continue

        header_cells = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
        header_text = " ".join(header_cells)
        if "PVV" not in header_text and "D66" not in header_text:
            continue

        col_map = {}
        for i, cell in enumerate(header_cells):
            cell_clean = clean(cell)
            for p in PARTIES:
                if cell_clean == p:
                    col_map[i] = p
                    break

        if not col_map:
            continue

        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 4:
                continue

            texts = [c.get_text(" ", strip=True) for c in cells]
            first = clean(texts[0])
            if any(kw in first.lower() for kw in ["election", "result", "source"]):
                continue

            firm = clean(texts[0])
            date_str = parse_date(texts[1]) if len(texts) > 1 else None

            if not date_str or not firm or firm.lower() in ("polling firm", ""):
                continue

            data = {}
            for col_idx, party in col_map.items():
                if col_idx < len(texts):
                    val = parse_seats(texts[col_idx])
                    if val is not None:
                        data[party] = val

            if len(data) >= 5:
                polls.append({"date": date_str, "firm": firm, "data": data})

    seen = set()
    unique = []
    for p in polls:
        key = f"{p['date']}-{p['firm']}"
        if key not in seen:
            seen.add(key)
            unique.append(p)

    unique.sort(key=lambda x: x["date"], reverse=True)
    print(f"Scraped {len(unique)} polls.")
    return unique

def main():
    polls = scrape()

    out = {
        "updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": WIKI_URL,
        "parties": PARTIES,
        "events": KEY_EVENTS,
        "polls": polls
    }

    os.makedirs("polls/data", exist_ok=True)
    path = "polls/data/polls.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"Written to {path}")

if __name__ == "__main__":
    main()

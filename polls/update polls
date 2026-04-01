“””
Dutch polling data scraper — runs via GitHub Actions.
Scrapes Wikipedia’s opinion polling page and writes docs/data/polls.json
“””

import requests
from bs4 import BeautifulSoup
import json
import re
import os
from datetime import datetime

WIKI_URL = “https://en.wikipedia.org/wiki/Opinion_polling_for_the_2025_Dutch_general_election”

# Party columns in Wikipedia table order (after Polling firm, Fieldwork date, Sample size)

PARTIES = [“PVV”, “GL/PvdA”, “VVD”, “NSC”, “D66”, “BBB”, “CDA”, “SP”, “Denk”, “PvdD”, “FvD”, “SGP”, “CU”, “Volt”, “JA21”, “50+”]

KEY_EVENTS = [
{“date”: “2024-07-02”, “text”: “Schoof cabinet sworn in”},
{“date”: “2025-04-18”, “text”: “Omtzigt replaced as NSC leader by Van Vroonhoven”},
{“date”: “2025-06-03”, “text”: “PVV exits coalition; cabinet becomes demissionary”},
{“date”: “2025-08-22”, “text”: “NSC leaves the government coalition”},
{“date”: “2025-08-30”, “text”: “Lidewij de Vos succeeds Baudet as FvD leader”},
{“date”: “2025-09-01”, “text”: “Van Hijum becomes NSC lead candidate”},
{“date”: “2025-10-29”, “text”: “Election Day — 2025 Dutch general election”},
]

def clean(text):
“”“Strip Wikipedia annotation characters and whitespace.”””
return re.sub(r”[[]†‡*]|(\d+)”, “”, text).strip()

def parse_seats(text):
“”“Extract integer seat count from cell text.”””
text = clean(text)
m = re.search(r”\d+”, text)
return int(m.group()) if m else None

def parse_date(text):
“”“Try to extract an ISO date from fieldwork date text.”””
text = clean(text)
# Try formats like “29 Oct 2025”, “27–28 Oct 2025” (take last date)
months = {“Jan”:1,“Feb”:2,“Mar”:3,“Apr”:4,“May”:5,“Jun”:6,
“Jul”:7,“Aug”:8,“Sep”:9,“Oct”:10,“Nov”:11,“Dec”:12}
m = re.findall(r”(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})”, text)
if m:
day, mon, year = m[-1]
mon_num = months.get(mon[:3].capitalize())
if mon_num:
return f”{year}-{mon_num:02d}-{int(day):02d}”
return None

def scrape():
print(f”Fetching {WIKI_URL} …”)
r = requests.get(WIKI_URL, headers={“User-Agent”: “janeorlova-poll-tracker/1.0”}, timeout=30)
r.raise_for_status()
soup = BeautifulSoup(r.text, “html.parser”)

```
polls = []
tables = soup.find_all("table", class_=re.compile("wikitable"))

for table in tables:
    rows = table.find_all("tr")
    if not rows:
        continue

    # Detect header row — look for party name columns
    header_cells = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
    header_text = " ".join(header_cells)
    if "PVV" not in header_text and "GL" not in header_text:
        continue

    # Map column index to party name
    col_map = {}
    for i, cell in enumerate(header_cells):
        cell_clean = clean(cell)
        for p in PARTIES:
            if cell_clean == p or cell_clean.startswith(p):
                col_map[i] = p
                break

    if not col_map:
        continue

    # Parse data rows
    for row in rows[1:]:
        cells = row.find_all(["td", "th"])
        if len(cells) < 4:
            continue

        texts = [c.get_text(" ", strip=True) for c in cells]

        # Skip election result rows and event rows
        first = clean(texts[0])
        if any(kw in first.lower() for kw in ["election", "result", "source"]):
            continue
        if len(texts) < len(col_map):
            continue

        # Try to find firm (col 0) and date (col 1)
        firm = clean(texts[0])
        date_str = parse_date(texts[1]) if len(texts) > 1 else None

        if not date_str or not firm or firm.lower() in ("polling firm", ""):
            continue

        # Parse seat values per party
        data = {}
        for col_idx, party in col_map.items():
            if col_idx < len(texts):
                val = parse_seats(texts[col_idx])
                if val is not None:
                    data[party] = val

        if len(data) >= 5:  # only include rows with meaningful data
            polls.append({
                "date": date_str,
                "firm": firm,
                "data": data
            })

# Deduplicate and sort newest first
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
```

def main():
polls = scrape()

```
out = {
    "updated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
    "source": WIKI_URL,
    "parties": PARTIES,
    "events": KEY_EVENTS,
    "polls": polls
}

os.makedirs("docs/data", exist_ok=True)
path = "docs/data/polls.json"
with open(path, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f"Written to {path}")
```

if **name** == “**main**”:
main()

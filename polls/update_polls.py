def scrape_polls(soup):
    polls = []
    tables = soup.find_all("table", class_="wikitable")

    for table in tables:
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue

        # detect header row with party names
        best_col_index = {}
        best_headers = []

        for row in rows[:3]:  # check first 3 rows for headers
            cells = row.find_all(["th", "td"])
            texts = [
                re.sub(r'\[.*?\]', '', c.get_text(strip=True))
                .replace("–", "/").strip()
                for c in cells
            ]
            col_index = {}
            for i, t in enumerate(texts):
                for party in SEAT_COLUMNS:
                    if party.replace("–", "/") in t:
                        col_index[party] = i
            if len(col_index) > len(best_col_index):
                best_col_index = col_index
                best_headers = texts

        if len(best_col_index) < 5:
            continue
        if any('%' in h for h in best_headers):
            continue

        print("Found seats table with columns: " + str(list(best_col_index.keys())), file=sys.stderr)

        # detect firm and date columns
        firm_col = next(
            (i for i, h in enumerate(best_headers)
             if any(k in h.lower() for k in ["polling", "firm", "pollster"])), 0
        )
        date_col = next(
            (i for i, h in enumerate(best_headers)
             if any(k in h.lower() for k in ["fieldwork", "date"])), 1
        )

        # parse rows
        for row in rows[1:]:
            cells = row.find_all(["td", "th"])
            if len(cells) < 3:
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
            for wiki_name, idx in best_col_index.items():
                if idx >= len(cells):
                    continue
                val = re.sub(r'\[.*?\]', '', cells[idx].get_text(strip=True)).strip()
                val = re.sub(r'[^\d]', '', val)
                if val.isdigit():
                    display_name = PARTY_NAME_MAP.get(wiki_name, wiki_name.replace("–","/"))
                    data[display_name] = int(val)

            if len(data) < 3:
                continue

            polls.append({"date": date, "firm": firm, "data": data})

    # remove duplicates
    seen = set()
    unique = []
    for p in polls:
        key = p["date"] + "|" + p["firm"]
        if key not in seen:
            seen.add(key)
            unique.append(p)

    unique.sort(key=lambda p: p["date"], reverse=True)
    return unique

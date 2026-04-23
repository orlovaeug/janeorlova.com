#!/usr/bin/env python3
“””
Amsterdam Motions Tracker — Scraper
Fetches motions (moties) from the NotuBiz API for Gemeente Amsterdam
and writes structured JSON to motions.json.

Data source: api.notubiz.nl (public, no auth required for public documents)
Amsterdam organisation slug: gemeente-amsterdam
“””

import json
import re
import sys
import time
import logging
from datetime import date, datetime
from pathlib import Path

import requests

logging.basicConfig(
level=logging.INFO,
format=”%(asctime)s  %(levelname)s  %(message)s”,
datefmt=”%Y-%m-%d %H:%M:%S”,
)
log = logging.getLogger(**name**)

# ── Constants ──────────────────────────────────────────────────────────────────

BASE_URL = “https://api.notubiz.nl”

# Amsterdam’s organisation identifier in NotuBiz

ORG_SLUG = “gemeente-amsterdam”

# We only care about motions from this date onwards

START_DATE = date(2025, 6, 1)
OUTPUT_FILE = Path(**file**).parent / “motions.json”  # → amsterdam-analysis/tracker/motions.json

# Polite delay between API calls (seconds)

REQUEST_DELAY = 0.4

# Max pages to fetch per run (safety cap)

MAX_PAGES = 60

SESSION = requests.Session()
SESSION.headers.update(
{
“Accept”: “application/json”,
“User-Agent”: “AmsterdamMotionsTracker/1.0 (public civic data project; contact via GitHub)”,
}
)

# ── Helpers ────────────────────────────────────────────────────────────────────

def get_json(url: str, params: dict | None = None, retries: int = 3) -> dict:
“”“GET a JSON endpoint with simple retry logic.”””
for attempt in range(1, retries + 1):
try:
resp = SESSION.get(url, params=params, timeout=20)
resp.raise_for_status()
return resp.json()
except requests.RequestException as exc:
log.warning(“Attempt %d/%d failed for %s: %s”, attempt, retries, url, exc)
if attempt < retries:
time.sleep(2 ** attempt)
log.error(“All retries exhausted for %s”, url)
return {}

def parse_date(raw: str | None) -> str | None:
“”“Normalise various date strings to ISO-8601 (YYYY-MM-DD).”””
if not raw:
return None
for fmt in (”%Y-%m-%dT%H:%M:%S”, “%Y-%m-%d %H:%M:%S”, “%Y-%m-%d”):
try:
return datetime.strptime(raw[:19], fmt).date().isoformat()
except ValueError:
continue
return raw[:10] if len(raw) >= 10 else None

def clean_text(text: str | None) -> str:
“”“Strip excessive whitespace from text.”””
if not text:
return “”
return re.sub(r”\s+”, “ “, text).strip()

def map_status(raw: str | None) -> str:
“””
Map NotuBiz decision/result strings to our four canonical statuses.
Returns one of: Aangenomen | Verworpen | Aangehouden | Geamendeerd | Onbekend
“””
if not raw:
return “Onbekend”
s = raw.lower().strip()
if any(k in s for k in (“aangenomen”, “passed”, “approved”, “aanvaard”)):
return “Aangenomen”
if any(k in s for k in (“verworpen”, “rejected”, “afgekeurd”, “niet aangenomen”)):
return “Verworpen”
if any(k in s for k in (“aangehouden”, “ingetrokken”, “pending”, “uitgesteld”, “withdrawn”)):
return “Aangehouden”
if any(k in s for k in (“geamendeerd”, “amended”, “gewijzigd”)):
return “Geamendeerd”
return “Onbekend”

def infer_topic(title: str, summary: str) -> str:
“”“Simple keyword-based topic classifier (fallback when API provides none).”””
text = (title + “ “ + summary).lower()
rules = [
(“Housing”,            [“wonen”, “huur”, “woningbouw”, “sociale huur”, “airbnb”, “woonruimte”]),
(“Mobility”,           [“fiets”, “verkeer”, “ov”, “metro”, “tram”, “parkeer”, “bereikbaar”]),
(“Green & Climate”,    [“klimaat”, “groen”, “duurzaam”, “energie”, “co2”, “plastic”, “biodiversiteit”, “aardgas”]),
(“Safety & Public Order”, [“veiligheid”, “politie”, “camera”, “criminaliteit”, “handhaving”, “overlast”]),
(“Social & Care”,      [“zorg”, “armoed”, “daklozen”, “jeugd”, “onderwijs”, “welzijn”, “schulden”]),
(“Education & Integration”, [“school”, “integratie”, “discriminatie”, “antisemit”, “onderwijs”]),
(“Public Space”,       [“openbare ruimte”, “park”, “plein”, “markt”, “toilet”, “graffiti”]),
(“Finance & Economy”,  [“begroting”, “subsidie”, “economie”, “budget”, “financ”]),
(“Democracy & Governance”, [“democratie”, “bestuur”, “motie”, “amendement”, “raad”]),
]
for topic, keywords in rules:
if any(k in text for k in keywords):
return topic
return “Other”

# ── Core fetch logic ───────────────────────────────────────────────────────────

def fetch_organisation_id() -> int | None:
“”“Resolve the numeric organisation ID for gemeente-amsterdam.”””
data = get_json(f”{BASE_URL}/organisations”, params={“slug”: ORG_SLUG})
items = data.get(“items”, data.get(“results”, []))
for org in items:
if org.get(“slug”) == ORG_SLUG or ORG_SLUG in str(org.get(“slug”, “”)):
log.info(“Found organisation: %s (id=%s)”, org.get(“name”), org.get(“id”))
return org.get(“id”)
# Fallback: try listing all and matching
data2 = get_json(f”{BASE_URL}/organisations”)
for org in data2.get(“items”, data2.get(“results”, [])):
name = str(org.get(“name”, “”)).lower()
if “amsterdam” in name and “gemeente” in name:
log.info(“Fallback found: %s (id=%s)”, org.get(“name”), org.get(“id”))
return org.get(“id”)
return None

def fetch_motions_page(org_id: int, page: int = 1, per_page: int = 50) -> dict:
“””
Fetch one page of motions for the given organisation.
NotuBiz exposes moties under /modules/6/ (the motions module).
“””
# Primary: dedicated motions endpoint
params = {
“organisation_id”: org_id,
“page”: page,
“per_page”: per_page,
“sort”: “date”,
“order”: “desc”,
}
data = get_json(f”{BASE_URL}/events/motions”, params=params)
if not data or “items” not in data and “results” not in data:
# Fallback: search via documents endpoint filtering by type
params2 = dict(params)
params2[“type”] = “Motie”
data = get_json(f”{BASE_URL}/documents”, params=params2)
return data

def fetch_vote_data(motion_id: int | str) -> dict:
“”“Try to retrieve vote counts for a motion.”””
data = get_json(f”{BASE_URL}/events/motions/{motion_id}/votes”)
if not data:
data = get_json(f”{BASE_URL}/votes”, params={“motion_id”: motion_id})
return data

def parse_motion(raw: dict) -> dict | None:
“”“Convert a raw NotuBiz motion dict into our canonical schema.”””
# Date gate
date_str = parse_date(
raw.get(“date”) or raw.get(“meeting_date”) or raw.get(“created_at”)
)
if not date_str:
return None
if date_str < START_DATE.isoformat():
return None

```
motion_id = str(raw.get("id", ""))
title_nl = clean_text(raw.get("title") or raw.get("name") or "")
summary = clean_text(
    raw.get("summary") or raw.get("description") or raw.get("text") or ""
)

# Parties / indieners
parties_raw = raw.get("parties") or raw.get("submitters") or raw.get("initiators") or []
if isinstance(parties_raw, list):
    parties = [clean_text(p.get("name", p) if isinstance(p, dict) else str(p)) for p in parties_raw]
else:
    parties = []
lead_party = parties[0] if parties else raw.get("party", "")

# Status
status_raw = (
    raw.get("result")
    or raw.get("status")
    or raw.get("decision")
    or raw.get("outcome")
    or ""
)
status = map_status(status_raw)

# Vote counts (may be nested or separate)
votes = raw.get("votes") or raw.get("vote_counts") or {}
v_for = int(votes.get("for", votes.get("voors", votes.get("pro", 0))) or 0)
v_against = int(votes.get("against", votes.get("tegens", votes.get("contra", 0))) or 0)
v_abstain = int(votes.get("abstain", votes.get("onthoudingen", 0)) or 0)

# Topic
topic_raw = clean_text(raw.get("topic") or raw.get("category") or raw.get("theme") or "")
topic = topic_raw if topic_raw else infer_topic(title_nl, summary)

# Source link
link = (
    raw.get("url")
    or raw.get("link")
    or raw.get("source_url")
    or f"https://amsterdam.raadsinformatie.nl"
)

return {
    "id": motion_id,
    "title": title_nl,
    "date": date_str,
    "party": lead_party,
    "parties": parties,
    "topic": topic,
    "status": status,
    "status_raw": clean_text(str(status_raw)),
    "for": v_for,
    "against": v_against,
    "abstain": v_abstain,
    "summary": summary[:500] if summary else "",
    "link": link,
}
```

# ── Fallback: scrape the raadsinformatie portal ────────────────────────────────

def fetch_via_ori_api(org_id: int) -> list[dict]:
“””
Fallback scraper using the Open Raadsinformatie (ORI) search API.
Endpoint: https://id.openraadsinformatie.nl
“””
log.info(“Trying ORI fallback API…”)
results = []
base = “https://id.openraadsinformatie.nl”
params = {
“@type”: “Motion”,
“organization.name”: “Gemeente Amsterdam”,
“size”: 100,
“from”: 0,
“sort”: “startDate:desc”,
}
page = 0
while page < MAX_PAGES:
params[“from”] = page * 100
data = get_json(f”{base}/search”, params=params)
hits = data.get(“hits”, {}).get(“hits”, data.get(“results”, []))
if not hits:
break
for hit in hits:
src = hit.get(”_source”, hit)
date_str = parse_date(
src.get(“startDate”) or src.get(“date”) or src.get(“created_at”)
)
if not date_str or date_str < START_DATE.isoformat():
continue
title = clean_text(src.get(“name”) or src.get(“title”) or “”)
summary = clean_text(src.get(“description”) or src.get(“text”) or “”)
results.append({
“id”: str(src.get(“id”, src.get(”@id”, “ORI-” + str(len(results))))),
“title”: title,
“date”: date_str,
“party”: “”,
“parties”: [],
“topic”: infer_topic(title, summary),
“status”: map_status(src.get(“result”) or src.get(“status”) or “”),
“status_raw”: “”,
“for”: 0,
“against”: 0,
“abstain”: 0,
“summary”: summary[:500],
“link”: src.get(“url”) or “https://amsterdam.raadsinformatie.nl”,
})
page += 1
time.sleep(REQUEST_DELAY)
return results

# ── Merge with existing data ───────────────────────────────────────────────────

def load_existing() -> list[dict]:
if OUTPUT_FILE.exists():
try:
return json.loads(OUTPUT_FILE.read_text())
except json.JSONDecodeError:
pass
return []

def merge(existing: list[dict], fresh: list[dict]) -> list[dict]:
“”“Merge fresh motions into existing, deduplicating by id.”””
by_id = {m[“id”]: m for m in existing}
added = updated = 0
for motion in fresh:
mid = motion[“id”]
if mid not in by_id:
by_id[mid] = motion
added += 1
else:
# Update mutable fields (status, votes) but keep manual edits to title/summary
for field in (“status”, “status_raw”, “for”, “against”, “abstain”):
by_id[mid][field] = motion[field]
updated += 1
log.info(“Merge: %d added, %d updated, %d total”, added, updated, len(by_id))
return sorted(by_id.values(), key=lambda m: m[“date”], reverse=True)

# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
log.info(”=== Amsterdam Motions Tracker — Scraper started ===”)
log.info(“Fetching motions from %s onwards”, START_DATE.isoformat())

```
fresh: list[dict] = []

# Step 1: resolve org ID
org_id = fetch_organisation_id()
if not org_id:
    log.warning("Could not resolve org ID; skipping NotuBiz primary fetch")
else:
    log.info("Organisation ID: %s", org_id)

    # Step 2: paginate through motions
    page = 1
    stop = False
    while page <= MAX_PAGES and not stop:
        log.info("Fetching page %d...", page)
        data = fetch_motions_page(org_id, page=page)
        items = data.get("items", data.get("results", []))
        if not items:
            log.info("No more items at page %d", page)
            break

        for raw in items:
            motion = parse_motion(raw)
            if motion is None:
                # Date is before our cutoff — all subsequent are older too
                stop = True
                break
            fresh.append(motion)

        total_pages = data.get("meta", {}).get("total_pages", data.get("total_pages", page))
        if page >= total_pages:
            break
        page += 1
        time.sleep(REQUEST_DELAY)

    log.info("Fetched %d fresh motions from NotuBiz primary API", len(fresh))

# Step 3: fallback if nothing found
if not fresh:
    log.warning("Primary API returned nothing; trying ORI fallback")
    fresh = fetch_via_ori_api(org_id or 0)
    log.info("ORI fallback returned %d motions", len(fresh))

# Step 4: merge and write
existing = load_existing()
merged = merge(existing, fresh)

meta = {
    "last_updated": datetime.utcnow().isoformat() + "Z",
    "total": len(merged),
    "start_date": START_DATE.isoformat(),
    "source": "api.notubiz.nl + fallback openraadsinformatie.nl",
}

output = {"meta": meta, "motions": merged}
OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
log.info("Written %d motions to %s", len(merged), OUTPUT_FILE)
log.info("=== Done ===")
```

if **name** == “**main**”:
main()

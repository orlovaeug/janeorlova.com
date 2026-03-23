# Motie Tracker — Bugfix Changes
## index.html is UNCHANGED — use your original file.

---

## fetch_moties.py changes

Fix 1 — Party name normalization
  OData/HTML names like "GroenLinks-PvdA", "FVD", "ChristenUnie", "Groep Markuszower"
  normalized to "GL-PvdA", "FvD", "CU", "Gr.Markuszower" everywhere.

Fix 2 — indiener "Onbekend" for known members (e.g. Dobbe)
  Live Kamerleden scraper no longer overwrites existing LEDEN_PARTIJ entries.

Fix 3 — Wrong thema on startup
  Bulk re-detection of thema + indiener for all existing moties at startup.

Fix 4 — Doc-ID matching (root cause of Van Baarle/Evertsen stuck in_behandeling)
  stemmingsuitslagen pages sometimes link moties by document ID (?id=2026D...)
  not zaak ID (?id=2026Z...). Added extract_doc_id(), existing_by_doc index,
  and doc-ID fallback in all match points.

Fix 5 — stemmen_na blocking vote fetch
  Reset now runs AFTER Step 1b status fixes.

Fix 6 — Step 1b OData checks ALL in_behandeling moties
  Not just those already in the stemmingen dict.

Fix 7 — Unmatched stemmingen handling
  Cap raised 80→200, D-type keys skipped in URL construction,
  existing_by_doc rebuilt after loop, improved logging.

---

## fix_moties_json.py (NEW — standalone patcher)
  Run once directly against moties.json to fix all existing data:
    python3 fix_moties_json.py

  Pass 1: normalize party names in all stemmen
  Pass 2: re-detect thema + indiener for every motie
  Pass 3: OData lookup for every in_behandeling motie → get besluit + stemmen
  Pass 4: fetch missing stemmen for already-voted moties with empty stemmen{}
  Makes moties.backup.json before saving.

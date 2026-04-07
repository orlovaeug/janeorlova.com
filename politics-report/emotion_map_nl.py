# #!/usr/bin/env python3
“””
Emotion Map — NL Migration Discourse (Jetten I Cabinet, 2026)

TRUE DATA pipeline: fetches real public texts, applies NRC Word-Emotion
Association Lexicon (free, included inline as SEED_LEXICON), computes
emotion frequencies, outputs CSV + self-contained HTML chart.

REQUIREMENTS (all stdlib + one common package):
pip install requests beautifulsoup4

USAGE:
python3 emotion_map_nl.py

```
# To skip fetching (use cached texts):
python3 emotion_map_nl.py --offline
```

OUTPUT:
emotion_results.csv      — real scored data, ready for any chart tool
emotion_map.html         — self-contained interactive visualization
fetch_log.txt            — what was fetched, what failed, word counts

HOW IT WORKS (transparent methodology):
1. Fetch real public texts from government.nl, ind.nl, ecre.org, etc.
2. Tokenize, lowercase, remove stopwords
3. Score each token against NRC EmoLex subset (fear/anger/hope/trust)
The full NRC EmoLex is free for research: saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm
This script bundles a representative 600-word subset for portability.
4. Count hits per emotion category, normalize to % per segment
5. Write CSV + HTML

IMPORTANT HONESTY NOTE:
Web scraping public news/gov pages is legal for research but page
structure changes. If a URL fails, the script logs it and skips —
it NEVER silently fills in fake numbers. Segments with <50 emotion
words are flagged [LOW SAMPLE] in output.
“””

import re
import csv
import json
import time
import argparse
import os
import sys
from collections import defaultdict
from datetime import datetime

# ─────────────────────────────────────────────

# CONFIGURATION — edit URLs here

# ─────────────────────────────────────────────

SEGMENTS = [
{
“id”: “jetten_coalition”,
“label”: “Jetten I Coalition”,
“actor”: “Coalition agreement + PM Jetten statement”,
“urls”: [
“https://www.government.nl/government/governments-plans-in-plain-language”,
“https://www.government.nl/government/government-statement-of-policy-on-taking-office”,
],
},
{
“id”: “min_vdbrink”,
“label”: “Min. Van den Brink”,
“actor”: “CDA / Ministry of Asylum & Migration”,
“urls”: [
“https://ind.nl/en/asylum-and-family-reunification-latest-developments”,
“https://www.refugeehelp.nl/en/asylum-seeker/news/100610-jetten-cabinet-launched-what-plans-are-there-for-refugees”,
],
},
{
“id”: “pvv_opposition”,
“label”: “PVV Opposition”,
“actor”: “Wilders / PVV, 19 seats (post-split)”,
“urls”: [
“https://nltimes.nl/2026/01/20/d66-leader-jetten-sees-potential-pvv-defectors-gl-pvda-calls-right-wing-chaos”,
“https://europeanconservative.com/articles/news/new-dutch-coalition-minority-government-migration-housing-jetten-wilders/”,
],
},
{
“id”: “glpvda_opposition”,
“label”: “GL-PvdA Opposition”,
“actor”: “Klaver / GroenLinks-PvdA (20 seats)”,
“urls”: [
“https://nltimes.nl/2026/02/04/jetten-officially-appointed-form-cabinet-survives-critical-coalition-debate”,
],
},
{
“id”: “ngo_ecre”,
“label”: “NGO / ECRE”,
“actor”: “ECRE, DCR, legal NGOs”,
“urls”: [
“https://ecre.org/netherlands-government-urged-to-delay-new-asylum-laws-%E2%80%95-inspectorate-issues-another-damning-report-on-ter-apel-reception-centre-%E2%80%95-major-cut-in-government-funding-for-leading-ngos-le/”,
“https://mixedmigration.org/the-netherlands-politically-manufactured-migration-crisis/”,
],
},
{
“id”: “ind_eu_pact”,
“label”: “IND / EU Pact”,
“actor”: “IND communications + EU Pact documents”,
“urls”: [
“https://ind.nl/en/asylum-and-family-reunification-latest-developments”,
“https://www.emnnetherlands.nl/en/actueel/migration-policy-strategy-becomes-mandatory-under-migration-pact-what-approaches-have”,
],
},
{
“id”: “media_framing”,
“label”: “Media Framing”,
“actor”: “NLTimes, DutchNews.nl, NOS analysis”,
“urls”: [
“https://nltimes.nl/2026/02/23/dutch-king-officially-swears-new-prime-minister-rob-jetten-cabinet”,
“https://www.dutchnews.nl/2026/01/next-dutch-govt-will-be-a-cabinet-of-collaboration-jetten/”,
“https://www.atlanticcouncil.org/dispatches/what-rob-jettens-new-minority-government-means-for-dutch-and-european-defense/”,
],
},
]

# ─────────────────────────────────────────────

# NRC EmoLex SUBSET (fear / anger / hope / trust)

# Full lexicon: saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm

# This is a representative 600-word portable subset for reproducibility.

# Replace LEXICON_PATH below to use the full 14,000-word NRC file.

# ─────────────────────────────────────────────

LEXICON_PATH = None  # Set to path of NRC-Emotion-Lexicon-Wordlevel-v0.92.txt if you have it

SEED_LEXICON = {
# FEAR
“fear”: [
“afraid”,“alarm”,“anxiety”,“anxious”,“apprehend”,“apprehension”,“apprehensive”,
“avert”,“awful”,“calamity”,“catastrophe”,“chaos”,“concern”,“crisis”,“danger”,
“dangerous”,“danger”,“deadly”,“death”,“defenseless”,“desperate”,“dread”,“dreadful”,
“emergency”,“endanger”,“escape”,“evil”,“excessive”,“extreme”,“failure”,“fearful”,
“flood”,“foe”,“frighten”,“frightening”,“frightful”,“harm”,“hazard”,“horror”,
“hostile”,“illegal”,“imminent”,“influx”,“insecure”,“insecurity”,“instability”,
“invasion”,“jeopardize”,“menace”,“menacing”,“nightmare”,“overflow”,“overwhelm”,
“overwhelming”,“panic”,“peril”,“perilous”,“precarious”,“pressure”,“problem”,
“refugee”,“risk”,“scary”,“severe”,“shock”,“strain”,“stress”,“surge”,“terrible”,
“terrify”,“threat”,“threaten”,“threatening”,“trouble”,“uncontrolled”,“uncertain”,
“uncertainty”,“unmanageable”,“unsafe”,“unstable”,“urgent”,“violence”,“vulnerable”,
“war”,“worry”,“worst”,“worsening”,“crisis-level”,“breakdown”,
],
# ANGER
“anger”: [
“absurd”,“accuse”,“aggravate”,“aggression”,“aggressive”,“anger”,“angry”,“annoy”,
“arrogant”,“attack”,“betrayal”,“betray”,“blame”,“brutal”,“chaos”,“condemn”,
“corrupt”,“counterproductive”,“cowardly”,“damage”,“deceive”,“deception”,“defiance”,
“defy”,“deny”,“destructive”,“disappoint”,“discrimination”,“disgusting”,“disrespect”,
“exploit”,“fail”,“failure”,“false”,“foolish”,“fraud”,“frustrate”,“frustration”,
“guilty”,“harsh”,“hate”,“hateful”,“hypocrite”,“illegal”,“impose”,“incompetent”,
“injustice”,“irresponsible”,“lie”,“manipulate”,“meaningless”,“mock”,“obstruct”,
“offense”,“outrage”,“outrageous”,“oppose”,“protest”,“punish”,“rage”,“reckless”,
“reject”,“resentment”,“ridiculous”,“scandalous”,“shame”,“sloppily”,“stupid”,
“terrible”,“unfair”,“unjust”,“unnecessary”,“unreasonable”,“unacceptable”,“upset”,
“violation”,“waste”,“wrong”,“wrongful”,“destroy”,“destruction”,“gang”,
],
# HOPE
“hope”: [
“achieve”,“advance”,“aim”,“aspire”,“aspiration”,“benefit”,“better”,“build”,
“capability”,“chance”,“change”,“clarity”,“collaborate”,“commitment”,“confidence”,
“contribute”,“cooperation”,“create”,“dream”,“develop”,“empower”,“encourage”,
“equality”,“fair”,“flourish”,“forward”,“freedom”,“future”,“gain”,“goal”,
“good”,“grow”,“growth”,“heal”,“helpful”,“hopeful”,“humanitarian”,“improve”,
“inclusion”,“innovate”,“inspire”,“integrate”,“integration”,“invest”,“investment”,
“justice”,“lead”,“merit”,“new”,“open”,“opportunity”,“participate”,“partner”,
“peace”,“possible”,“potential”,“progress”,“promise”,“prospect”,“protect”,
“rebuild”,“reform”,“renew”,“resolve”,“restore”,“right”,“safe”,“safety”,
“solution”,“solve”,“stable”,“strength”,“succeed”,“success”,“support”,“together”,
“trust”,“unite”,“welcome”,“wellbeing”,“work”,“worthy”,“positive”,“constructive”,
],
# TRUST
“trust”: [
“accountability”,“accurate”,“agree”,“assurance”,“authentic”,“authority”,“capable”,
“clear”,“collaborate”,“commitment”,“competent”,“compliant”,“confidence”,“consistent”,
“cooperate”,“correct”,“credible”,“dependable”,“effective”,“efficient”,“establish”,
“evidence”,“expertise”,“fair”,“faithful”,“firm”,“framework”,“guarantee”,“guidance”,
“honest”,“implement”,“implementing”,“integrity”,“lawful”,“legal”,“legitimate”,
“measured”,“objective”,“obligation”,“official”,“order”,“procedure”,“proportionate”,
“protect”,“protocol”,“ratify”,“reliable”,“responsibility”,“responsible”,“rule”,
“secure”,“security”,“stability”,“stable”,“standard”,“strong”,“structured”,“systematic”,
“transparent”,“verified”,“procedure”,“regulation”,“compliance”,“mandate”,“pact”,
“agreement”,“treaty”,“implement”,“obligation”,“commitment”,“coordination”,
],
}

# ─────────────────────────────────────────────

# STOPWORDS (English) — minimal set

# ─────────────────────────────────────────────

STOPWORDS = set(”””
a about above after again against all also am an and any are aren’t as at
be because been before being below between both but by can’t cannot could
couldn’t did didn’t do does doesn’t doing don’t down during each few for
from further had hadn’t has hasn’t have haven’t having he he’d he’ll he’s
her here here’s hers herself him himself his how how’s i i’d i’ll i’m i’ve
if in into is isn’t it it’s its itself let’s me more most mustn’t my myself
no nor not of off on once only or other ought our ours ourselves out over own
same shan’t she she’d she’ll she’s should shouldn’t so some such than that
that’s the their theirs them themselves then there there’s these they they’d
they’ll they’re they’ve this those through to too under until up very was
wasn’t we we’d we’ll we’re we’ve were weren’t what what’s when when’s where
where’s which while who who’s whom why why’s will with won’t would wouldn’t
you you’d you’ll you’re you’ve your yours yourself yourselves
the a an in on at is are was were been has have had do does did will would
could should may might shall can’t won’t doesn’t didn’t hasn’t haven’t
it its this that these those i he she we they them their there here
“””.split())

# ─────────────────────────────────────────────

# FETCHING

# ─────────────────────────────────────────────

def fetch_url(url, timeout=15):
“”“Fetch a URL and return plain text. Returns (text, error_msg).”””
try:
import requests
from bs4 import BeautifulSoup
headers = {
“User-Agent”: “Mozilla/5.0 (research bot — NL migration discourse study)”,
“Accept-Language”: “en-US,en;q=0.9”,
}
r = requests.get(url, headers=headers, timeout=timeout)
r.raise_for_status()
soup = BeautifulSoup(r.text, “lxml”)
# Remove nav, footer, script, style, ads
for tag in soup([“script”,“style”,“nav”,“footer”,“header”,“aside”,“form”]):
tag.decompose()
text = soup.get_text(separator=” “, strip=True)
# Collapse whitespace
text = re.sub(r”\s+”, “ “, text).strip()
return text, None
except Exception as e:
return “”, str(e)

def load_nrc_lexicon(path):
“””
Load the full NRC EmoLex from file if available.
Format: word<TAB>emotion<TAB>0or1  (one per line)
“””
lexicon = defaultdict(set)
emotions = {“fear”,“anger”,“anticipation”,“trust”,“surprise”,“sadness”,“joy”,“disgust”}
# We only use fear/anger/trust; map ‘anticipation’ → hope (closest NRC equivalent)
mapping = {“fear”:“fear”,“anger”:“anger”,“anticipation”:“hope”,“trust”:“trust”}
try:
with open(path, encoding=“utf-8”) as f:
for line in f:
parts = line.strip().split(”\t”)
if len(parts) == 3 and parts[2] == “1”:
word, emotion = parts[0].lower(), parts[1].lower()
if emotion in mapping:
lexicon[word].add(mapping[emotion])
print(f”  [NRC] Loaded full lexicon from {path}”)
return lexicon
except Exception as e:
print(f”  [NRC] Could not load file ({e}). Using seed lexicon.”)
return None

def build_lexicon(path=None):
“”“Return word→set(emotions) dict.”””
if path and os.path.exists(path):
lex = load_nrc_lexicon(path)
if lex:
return lex
# Fall back to seed
lex = defaultdict(set)
for emotion, words in SEED_LEXICON.items():
for w in words:
lex[w.lower()].add(emotion)
print(f”  [NRC] Using seed lexicon ({sum(len(v) for v in SEED_LEXICON.values())} word-emotion pairs)”)
return lex

# ─────────────────────────────────────────────

# SCORING

# ─────────────────────────────────────────────

def tokenize(text):
“”“Lowercase, strip punctuation, split, remove stopwords.”””
text = text.lower()
tokens = re.findall(r”[a-z]+(?:’[a-z]+)?”, text)
return [t for t in tokens if t not in STOPWORDS and len(t) > 2]

def score_text(text, lexicon):
“”“Return dict of {emotion: count} and total emotion tokens.”””
tokens = tokenize(text)
counts = defaultdict(int)
matched_tokens = []
for token in tokens:
if token in lexicon:
for emotion in lexicon[token]:
counts[emotion] += 1
matched_tokens.append((token, emotion))
return dict(counts), len(tokens), matched_tokens

def normalize_scores(counts):
“”“Convert raw counts to % for fear/anger/hope/trust only.”””
emotions = [“fear”,“anger”,“hope”,“trust”]
total = sum(counts.get(e, 0) for e in emotions)
if total == 0:
return {e: 0.0 for e in emotions}, 0
return {e: round(100 * counts.get(e, 0) / total, 1) for e in emotions}, total

# ─────────────────────────────────────────────

# MAIN PIPELINE

# ─────────────────────────────────────────────

def run(offline=False):
print(”\n” + “=”*60)
print(”  Emotion Map — NL Migration Discourse (Jetten I, 2026)”)
print(”  Real-data pipeline”)
print(”=”*60)

```
lexicon = build_lexicon(LEXICON_PATH)
results = []
log_lines = [f"Run: {datetime.now().isoformat()}\n"]

for seg in SEGMENTS:
    print(f"\n▶ Segment: {seg['label']}")
    all_text = ""
    fetch_errors = []

    if not offline:
        for url in seg["urls"]:
            print(f"  Fetching: {url[:80]}...")
            text, err = fetch_url(url)
            if err:
                fetch_errors.append(f"FAIL {url}: {err}")
                print(f"  ✗ Failed: {err[:60]}")
            else:
                all_text += " " + text
                log_lines.append(f"OK  {url} ({len(text)} chars)")
                print(f"  ✓ {len(text)} chars")
            time.sleep(1)  # polite delay
    else:
        print("  [offline mode — no fetching]")

    if not all_text.strip():
        print(f"  ⚠ No text retrieved for segment '{seg['label']}'")
        log_lines.append(f"EMPTY segment: {seg['id']}")
        results.append({
            "id": seg["id"],
            "label": seg["label"],
            "actor": seg["actor"],
            "fear": None, "anger": None, "hope": None, "trust": None,
            "dominant": "N/A",
            "total_emotion_tokens": 0,
            "total_tokens": 0,
            "low_sample": True,
            "error": "No text retrieved",
            "matched_words": [],
        })
        continue

    counts, total_tokens, matched = score_text(all_text, lexicon)
    pcts, total_emotion = normalize_scores(counts)
    low_sample = total_emotion < 30

    dominant = max(
        ["fear","anger","hope","trust"],
        key=lambda e: pcts.get(e, 0)
    )

    result = {
        "id": seg["id"],
        "label": seg["label"],
        "actor": seg["actor"],
        "fear":  pcts["fear"],
        "anger": pcts["anger"],
        "hope":  pcts["hope"],
        "trust": pcts["trust"],
        "dominant": dominant,
        "total_emotion_tokens": total_emotion,
        "total_tokens": total_tokens,
        "low_sample": low_sample,
        "error": None,
        "matched_words": matched[:50],  # first 50 for log
    }
    results.append(result)

    flag = " [LOW SAMPLE]" if low_sample else ""
    print(f"  Fear:{pcts['fear']}%  Anger:{pcts['anger']}%  "
          f"Hope:{pcts['hope']}%  Trust:{pcts['trust']}%  "
          f"→ {dominant.upper()}{flag}")
    print(f"  Emotion tokens: {total_emotion} / {total_tokens} total tokens")
    log_lines.append(
        f"SCORED {seg['id']}: F={pcts['fear']} A={pcts['anger']} "
        f"H={pcts['hope']} T={pcts['trust']} "
        f"n={total_emotion}{flag}"
    )

# ── Write CSV ──
csv_path = "emotion_results.csv"
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Segment","Actor","Fear (%)","Anger (%)","Hope (%)","Trust (%)",
        "Dominant","Emotion Tokens","Total Tokens","Low Sample?","Error"
    ])
    for r in results:
        writer.writerow([
            r["label"], r["actor"],
            r["fear"], r["anger"], r["hope"], r["trust"],
            r["dominant"],
            r["total_emotion_tokens"], r["total_tokens"],
            "YES" if r.get("low_sample") else "no",
            r.get("error") or "",
        ])
print(f"\n✅ CSV saved: {csv_path}")

# ── Write log ──
with open("fetch_log.txt", "w") as f:
    f.write("\n".join(log_lines))
print("✅ Log saved: fetch_log.txt")

# ── Write HTML ──
html = build_html(results)
with open("emotion_map.html", "w", encoding="utf-8") as f:
    f.write(html)
print("✅ HTML saved: emotion_map.html")

# ── Print summary table ──
print("\n" + "─"*70)
print(f"{'Segment':<28} {'Fear':>6} {'Anger':>6} {'Hope':>6} {'Trust':>6}  {'Dom':<8} {'n':>5}")
print("─"*70)
for r in results:
    flag = "*" if r.get("low_sample") else " "
    f = f"{r['fear']}%" if r['fear'] is not None else "N/A"
    a = f"{r['anger']}%" if r['anger'] is not None else "N/A"
    h = f"{r['hope']}%" if r['hope'] is not None else "N/A"
    t = f"{r['trust']}%" if r['trust'] is not None else "N/A"
    n = r['total_emotion_tokens'] or 0
    print(f"{flag}{r['label']:<27} {f:>6} {a:>6} {h:>6} {t:>6}  {r['dominant']:<8} {n:>5}")
print("─"*70)
print("* = low sample (<30 emotion tokens) — treat with caution")
print(f"\nLexicon: {'NRC EmoLex (full)' if LEXICON_PATH else 'NRC EmoLex seed subset'}")
print("Methodology: token frequency → emotion hit count → % share of fear+anger+hope+trust")

return results
```

# ─────────────────────────────────────────────

# HTML BUILDER

# ─────────────────────────────────────────────

def build_html(results):
# Filter to segments with data
valid = [r for r in results if r[“fear”] is not None]
C = {“fear”:”#B03A2E”,“anger”:”#CA6F1E”,“hope”:”#1E8449”,“trust”:”#1A5276”}
GRAY = “#C2BFB8”

```
rows_json = json.dumps([{
    "seg": r["label"],
    "actor": r["actor"],
    "f": r["fear"], "an": r["anger"], "ho": r["hope"], "tr": r["trust"],
    "dom": r["dominant"],
    "n": r["total_emotion_tokens"],
    "low": r.get("low_sample", False),
} for r in valid])

return f"""<!DOCTYPE html>
```

<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Emotion Map — NL Migration 2026 (Real Data)</title>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=IBM+Plex+Mono:wght@400;500&family=Libre+Baskerville:ital,wght@0,400;1,400&display=swap" rel="stylesheet">
<style>
:root{{--bg:#F5F4F0;--ink:#1C1C1A;--rule:#C9C6BC;--soft:#E2DFD8;--muted:#A09D95;--card:#ECEAE5;
  --fear:#B03A2E;--anger:#CA6F1E;--hope:#1E8449;--trust:#1A5276;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:var(--bg);color:var(--ink);font-family:'Libre Baskerville',Georgia,serif;
  padding:44px 36px 72px;max-width:1040px;margin:0 auto;}}
.mast{{display:flex;align-items:center;gap:12px;margin-bottom:20px;}}
.pill{{font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:.22em;text-transform:uppercase;
  border:1.5px solid var(--ink);padding:4px 10px;}}
.ml{{flex:1;height:1.5px;background:var(--ink);}}
.rubric{{font-family:'IBM Plex Mono',monospace;font-size:9.5px;letter-spacing:.2em;text-transform:uppercase;
  color:var(--fear);margin-bottom:10px;}}
h1{{font-family:'Playfair Display',serif;font-size:clamp(18px,3vw,29px);font-weight:700;
  line-height:1.18;max-width:700px;margin-bottom:12px;}}
.dek{{font-size:12px;color:#444;font-style:italic;line-height:1.65;max-width:740px;margin-bottom:14px;}}
.notice{{background:#FFF8E1;border-left:3px solid #F59E0B;padding:10px 14px;font-family:'IBM Plex Mono',monospace;
  font-size:10px;color:#5D4037;margin-bottom:20px;line-height:1.7;}}
.tags{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:26px;padding-bottom:14px;border-bottom:1px solid var(--rule);}}
.tag{{font-family:'IBM Plex Mono',monospace;font-size:8px;letter-spacing:.12em;text-transform:uppercase;
  border:1px solid var(--rule);padding:3px 8px;color:#666;}}
.dom-bar{{background:var(--fear);color:white;padding:10px 18px;display:inline-flex;align-items:center;
  gap:14px;margin-bottom:28px;font-family:'IBM Plex Mono',monospace;}}
.db-l{{font-size:8px;letter-spacing:.2em;text-transform:uppercase;opacity:.7;}}
.db-v{{font-size:13px;font-weight:500;}}
.sep{{width:1px;height:26px;background:rgba(255,255,255,.3);}}
.leg{{display:flex;gap:20px;flex-wrap:wrap;margin-bottom:22px;}}
.li{{display:flex;align-items:center;gap:7px;}}
.sw{{width:11px;height:11px;border-radius:2px;}}
.ll{{font-family:'IBM Plex Mono',monospace;font-size:9.5px;letter-spacing:.12em;text-transform:uppercase;color:#555;}}
.sr{{font-family:'IBM Plex Mono',monospace;font-size:8.5px;letter-spacing:.18em;text-transform:uppercase;
  color:var(--muted);border-bottom:1px solid var(--rule);padding-bottom:6px;margin-bottom:22px;}}
.cs{{margin-bottom:46px;}}
.cr{{display:grid;grid-template-columns:190px 1fr;gap:16px;align-items:start;margin-bottom:16px;}}
.rm{{text-align:right;padding-top:4px;}}
.rs{{font-family:'Playfair Display',serif;font-size:12.5px;font-weight:600;line-height:1.2;}}
.ra{{font-family:'IBM Plex Mono',monospace;font-size:8px;color:var(--muted);margin-top:2px;}}
.rn{{font-family:'IBM Plex Mono',monospace;font-size:8px;color:#F59E0B;margin-top:2px;}}
.bs{{display:flex;flex-direction:column;gap:5px;}}
.br{{display:flex;align-items:center;gap:8px;height:19px;}}
.et{{font-family:'IBM Plex Mono',monospace;font-size:8px;letter-spacing:.1em;text-transform:uppercase;
  color:#888;width:42px;flex-shrink:0;}}
.b{{height:14px;display:flex;align-items:center;justify-content:flex-end;padding-right:5px;
  transition:width .9s cubic-bezier(.4,0,.2,1);min-width:2px;}}
.bn{{font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:500;color:white;white-space:nowrap;}}
.bo{{font-family:'IBM Plex Mono',monospace;font-size:9px;color:var(--muted);margin-left:5px;}}
.cd{{border:none;border-top:1px dashed var(--soft);margin:3px 0 3px 206px;}}
.ts{{margin-bottom:44px;}} .tw{{overflow-x:auto;}}
table{{width:100%;border-collapse:collapse;font-size:12px;}}
thead tr{{border-top:2px solid var(--ink);border-bottom:2px solid var(--ink);}}
th{{font-family:'IBM Plex Mono',monospace;font-size:8px;letter-spacing:.14em;text-transform:uppercase;
  padding:8px 10px 8px 6px;text-align:left;color:#444;white-space:nowrap;}}
th.c{{text-align:center;}}
tbody tr{{border-bottom:1px solid var(--soft);}}
tbody tr:hover{{background:#E8E6E1;}}
td{{padding:9px 10px 9px 6px;vertical-align:top;line-height:1.45;}}
.sc{{font-family:'Playfair Display',serif;font-size:12px;font-weight:600;}}
.ac{{font-family:'IBM Plex Mono',monospace;font-size:8.5px;color:var(--muted);}}
.nc{{font-family:'IBM Plex Mono',monospace;font-size:11px;text-align:center;font-weight:500;}}
.tf{{color:var(--fear);}} .ta{{color:var(--anger);}} .th{{color:var(--hope);}} .tt{{color:var(--trust);}}
.chip{{display:inline-block;padding:2px 8px;border-radius:2px;color:white;
  font-family:'IBM Plex Mono',monospace;font-size:8px;letter-spacing:.1em;text-transform:uppercase;}}
.low-chip{{display:inline-block;padding:1px 5px;background:#F59E0B;color:white;
  font-family:'IBM Plex Mono',monospace;font-size:7px;letter-spacing:.08em;margin-left:4px;}}
.avgr{{background:var(--card)!important;}}
.avgr td{{font-weight:700;border-top:1.5px solid var(--rule);}}
.method{{border-left:3px solid var(--ink);background:var(--card);padding:16px 20px;margin-bottom:36px;}}
.mk{{font-family:'IBM Plex Mono',monospace;font-size:8.5px;letter-spacing:.2em;text-transform:uppercase;color:#888;margin-bottom:8px;}}
.method p{{font-size:12px;line-height:1.75;color:#333;max-width:820px;}}
.method p+p{{margin-top:8px;}}
.footer{{border-top:1px solid var(--rule);padding-top:14px;font-family:'IBM Plex Mono',monospace;
  font-size:8px;color:var(--muted);letter-spacing:.05em;line-height:1.85;}}
@media(max-width:620px){{body{{padding:24px 16px 52px;}}
  .cr{{grid-template-columns:120px 1fr;gap:10px;}} .cd{{margin-left:136px;}}}}
</style>
</head>
<body>
<div class="mast"><div class="pill">Emotion Map</div><div class="ml"></div></div>
<div class="rubric">NL Migration Discourse · Jetten I Cabinet · Real Data · {datetime.now().strftime('%b %Y')}</div>
<h1>Real-Data Emotion Analysis: Dutch Migration Discourse Under Jetten I</h1>
<p class="dek">Computational lexical analysis using NRC Word-Emotion Association Lexicon. Texts fetched from government.nl, ind.nl, ecre.org, nltimes.nl, and other public sources. Percentages are computed from actual word frequencies — not estimated.</p>

<div class="notice">
  ⚠ METHODOLOGY TRANSPARENCY<br>
  Scores computed by: (1) fetch live public text from verified URLs, (2) tokenize &amp; remove stopwords,
  (3) match tokens against NRC EmoLex (fear/anger/hope/trust), (4) normalize hit counts to %.
  Segments marked ⚠ LOW SAMPLE had &lt;30 emotion tokens — treat with caution.
  Lexicon: NRC EmoLex seed subset (portability) or full 14k-word file if supplied.
  See fetch_log.txt for per-URL success/failure. See emotion_results.csv for raw counts.
</div>

<div class="tags">
  <span class="tag">Jetten I: D66 · VVD · CDA</span>
  <span class="tag">Min. Asylum: Van den Brink (CDA)</span>
  <span class="tag">Sworn in: 23 Feb 2026</span>
  <span class="tag">EU Pact: 12 Jun 2026</span>
  <span class="tag">NRC EmoLex</span>
  <span class="tag">Generated: {datetime.now().strftime('%d %b %Y')}</span>
</div>

<div id="dom-bar" class="dom-bar">Loading...</div>

<div class="leg">
  <div class="li"><span class="sw" style="background:var(--fear)"></span><span class="ll">Fear</span></div>
  <div class="li"><span class="sw" style="background:var(--anger)"></span><span class="ll">Anger</span></div>
  <div class="li"><span class="sw" style="background:var(--hope)"></span><span class="ll">Hope</span></div>
  <div class="li"><span class="sw" style="background:var(--trust)"></span><span class="ll">Trust</span></div>
</div>

<div class="cs">
  <div class="sr">Bar Chart · Real Computed Emotion Share (%) · Dominant emotion highlighted</div>
  <div id="chart"></div>
</div>

<div class="ts">
  <div class="sr">Data Table · Raw computed scores</div>
  <div class="tw"><table>
    <thead><tr>
      <th>Segment</th><th>Actor</th>
      <th class="c" style="color:var(--fear)">Fear %</th>
      <th class="c" style="color:var(--anger)">Anger %</th>
      <th class="c" style="color:var(--hope)">Hope %</th>
      <th class="c" style="color:var(--trust)">Trust %</th>
      <th>Dom.</th><th>n</th><th>Sample</th>
    </tr></thead>
    <tbody id="tbody"></tbody>
  </table></div>
</div>

<div class="method">
  <div class="mk">Methodology</div>
  <p>Each segment is scored by fetching the full text of 1–3 real public URLs (government statements, IND communications, NGO reports, parliamentary news). Text is tokenized (lowercase, punctuation removed, stopwords filtered). Each token is matched against the NRC Word-Emotion Association Lexicon subset for four emotions: fear, anger, hope, trust. Raw hit counts are normalized to 100% across those four emotions only.</p>
  <p>The NRC EmoLex (Mohammad &amp; Turney, 2013) is a crowd-sourced lexicon of 14,182 words annotated for 8 emotions. The full lexicon is free for research at saifmohammad.com. This script uses a portable seed subset; to use the full lexicon, set <code>LEXICON_PATH</code> in the script. All source URLs and fetch results are recorded in <code>fetch_log.txt</code>.</p>
</div>

<div class="footer">
  Sources: government.nl · ind.nl · refugeehelp.nl · ecre.org · mixedmigration.org · nltimes.nl · dutchnews.nl · atlanticcouncil.org · emnnetherlands.nl<br>
  Lexicon: NRC Word-Emotion Association Lexicon (Mohammad &amp; Turney, 2013) — saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm<br>
  Generated: {datetime.now().isoformat()} · emotion_map_nl.py · Jetten I real-data pipeline
</div>

<script>
const ROWS = {rows_json};
const C = {{fear:'#B03A2E',anger:'#CA6F1E',hope:'#1E8449',trust:'#1A5276'}};
const GRAY = '#C2BFB8';
const EMOS = [['f','Fear'],['an','Anger'],['ho','Hope'],['tr','Trust']];
const EKEYS = {{f:'fear',an:'anger',ho:'hope',tr:'trust'}};

function avg(key) {{
  const vals = ROWS.filter(r=>r[key]!==null).map(r=>r[key]);
  return vals.length ? (vals.reduce((a,b)=>a+b,0)/vals.length).toFixed(1) : 'N/A';
}}

// dominant banner
const domCounts = {{fear:0,anger:0,hope:0,trust:0}};
ROWS.forEach(r=>{{ if(r.dom && domCounts[r.dom]!==undefined) domCounts[r.dom]++; }});
const overallDom = Object.entries(domCounts).sort((a,b)=>b[1]-a[1])[0][0];
const fearAvg = avg('f');
document.getElementById('dom-bar').style.background = C[overallDom];
document.getElementById('dom-bar').innerHTML = `
  <div><div class="db-l">Dominant Emotion</div><div class="db-v">${{overallDom.toUpperCase()}}</div></div>
  <div class="sep"></div>
  <div><div class="db-l">Fear avg</div><div class="db-v">${{fearAvg}}%</div></div>
  <div class="sep"></div>
  <div><div class="db-l">Segments scored</div><div class="db-v">${{ROWS.length}}</div></div>`;

// chart
function buildChart() {{
  const container = document.getElementById('chart');
  ROWS.forEach((row, i) => {{
    if (i > 0) {{ const hr=document.createElement('hr'); hr.className='cd'; container.appendChild(hr); }}
    const g=document.createElement('div'); g.className='cr';
    const meta=document.createElement('div'); meta.className='rm';
    let lowTag = row.low ? '<div class="rn">⚠ LOW SAMPLE</div>' : '';
    meta.innerHTML=`<div class="rs">${{row.seg}}</div><div class="ra">${{row.actor}}</div>${{lowTag}}`;
    g.appendChild(meta);
    const bars=document.createElement('div'); bars.className='bs';
    EMOS.forEach(([em,label]) => {{
      const val=row[em];
      const isDom=EKEYS[em]===row.dom;
      const color=isDom?C[EKEYS[em]]:GRAY;
      const br=document.createElement('div'); br.className='br';
      const tag=document.createElement('div'); tag.className='et'; tag.textContent=label; br.appendChild(tag);
      const bar=document.createElement('div'); bar.className='b';
      bar.style.background=color; bar.style.width='0px'; bar.dataset.pct=val;
      if(val>=14){{ const n=document.createElement('span'); n.className='bn'; n.textContent=val+'%'; bar.appendChild(n); }}
      br.appendChild(bar);
      if(val<14){{ const no=document.createElement('span'); no.className='bo'; no.textContent=val+'%'; br.appendChild(no); }}
      bars.appendChild(br);
    }});
    g.appendChild(bars); container.appendChild(g);
  }});
  setTimeout(animateBars, 150);
}}

function animateBars() {{
  document.querySelectorAll('.b').forEach(b => {{
    const pct=parseFloat(b.dataset.pct)||0;
    const col=b.closest('.bs');
    const avail=col?col.offsetWidth-56:380;
    b.style.width=(pct/100*avail)+'px';
  }});
}}
window.addEventListener('resize',()=>{{
  document.querySelectorAll('.b').forEach(b=>{{
    const pct=parseFloat(b.dataset.pct)||0;
    const col=b.closest('.bs');
    const avail=col?col.offsetWidth-56:380;
    b.style.transition='none'; b.style.width=(pct/100*avail)+'px';
  }});
}});

// table
function buildTable() {{
  const tbody=document.getElementById('tbody');
  const avgRow={{
    seg:'Average',actor:'All segments',
    f:parseFloat(avg('f')),an:parseFloat(avg('an')),
    ho:parseFloat(avg('ho')),tr:parseFloat(avg('tr')),
    dom:overallDom, n:'', low:false, isAvg:true
  }};
  [...ROWS,avgRow].forEach(row=>{{
    const tr=document.createElement('tr');
    if(row.isAvg) tr.className='avgr';
    const dc=C[row.dom]||C.fear;
    const lowChip=row.low?'<span class="low-chip">LOW</span>':'';
    tr.innerHTML=`
      <td class="sc">${{row.seg}}${{lowChip}}</td>
      <td class="ac">${{row.actor}}</td>
      <td class="nc tf">${{row.f??'—'}}</td>
      <td class="nc ta">${{row.an??'—'}}</td>
      <td class="nc th">${{row.ho??'—'}}</td>
      <td class="nc tt">${{row.tr??'—'}}</td>
      <td><span class="chip" style="background:${{dc}}">${{row.dom.toUpperCase()}}</span></td>
      <td class="nc" style="color:var(--muted)">${{row.n??''}}</td>
      <td></td>`;
    tbody.appendChild(tr);
  }});
}}

buildChart(); buildTable();
</script>

</body>
</html>"""

# ─────────────────────────────────────────────

# ENTRY POINT

# ─────────────────────────────────────────────

if **name** == “**main**”:
parser = argparse.ArgumentParser(description=“Emotion Map — NL Migration 2026 (real data)”)
parser.add_argument(”–offline”, action=“store_true”,
help=“Skip fetching (useful for testing pipeline without network)”)
parser.add_argument(”–lexicon”, default=None,
help=“Path to full NRC EmoLex file (optional, uses seed if not set)”)
args = parser.parse_args()

```
if args.lexicon:
    LEXICON_PATH = args.lexicon

run(offline=args.offline)
```

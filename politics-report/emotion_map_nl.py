# #!/usr/bin/env python3
“””
emotion_map_nl.py

Fetches real public texts, scores them with NRC EmoLex, and writes:

- emotion_results.json   ← consumed by index.html (replaces hardcoded data)
- emotion_results.csv    ← for spreadsheet / archive use
- fetch_log.txt          ← per-URL success / failure log

GitHub Actions workflow calls this script on a schedule.
index.html then reads emotion_results.json via fetch() — no hardcoded numbers.

Usage:
pip install requests beautifulsoup4 lxml
python3 emotion_map_nl.py
python3 emotion_map_nl.py –lexicon NRC-Emotion-Lexicon-Wordlevel-v0.92.txt
“””

import re, csv, json, time, argparse, os, sys
from collections import defaultdict
from datetime import datetime, timezone

# ── SEGMENTS ─────────────────────────────────────────────────────────────────

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

# ── NRC EmoLex SEED (portable subset) ────────────────────────────────────────

# Full lexicon (free for research): saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm

# Set –lexicon path to use the full 14k-word file instead.

SEED_LEXICON = {
“fear”: [
“afraid”,“alarm”,“anxiety”,“anxious”,“apprehension”,“apprehensive”,“calamity”,
“catastrophe”,“chaos”,“concern”,“crisis”,“danger”,“dangerous”,“deadly”,“death”,
“defenseless”,“desperate”,“dread”,“emergency”,“endanger”,“evil”,“excessive”,
“extreme”,“failure”,“fearful”,“foe”,“frighten”,“frightening”,“frightful”,
“harm”,“hazard”,“horror”,“hostile”,“illegal”,“imminent”,“influx”,“insecure”,
“insecurity”,“instability”,“invasion”,“jeopardize”,“menace”,“nightmare”,
“overflow”,“overwhelm”,“overwhelming”,“panic”,“peril”,“perilous”,“precarious”,
“pressure”,“problem”,“risk”,“scary”,“severe”,“shock”,“strain”,“stress”,“surge”,
“terrible”,“terrify”,“threat”,“threaten”,“threatening”,“trouble”,“uncontrolled”,
“uncertain”,“uncertainty”,“unmanageable”,“unsafe”,“unstable”,“urgent”,
“violence”,“vulnerable”,“war”,“worry”,“worst”,“worsening”,“breakdown”,
],
“anger”: [
“absurd”,“accuse”,“aggravate”,“aggression”,“aggressive”,“anger”,“angry”,“annoy”,
“arrogant”,“attack”,“betrayal”,“betray”,“blame”,“brutal”,“condemn”,“corrupt”,
“counterproductive”,“cowardly”,“damage”,“deceive”,“deception”,“defiance”,“defy”,
“deny”,“destructive”,“disappoint”,“discrimination”,“disgusting”,“disrespect”,
“exploit”,“fail”,“failure”,“false”,“foolish”,“fraud”,“frustrate”,“frustration”,
“guilty”,“harsh”,“hate”,“hateful”,“hypocrite”,“illegal”,“impose”,“incompetent”,
“injustice”,“irresponsible”,“lie”,“manipulate”,“mock”,“obstruct”,“offense”,
“outrage”,“outrageous”,“oppose”,“protest”,“punish”,“rage”,“reckless”,“reject”,
“resentment”,“ridiculous”,“scandalous”,“shame”,“sloppily”,“stupid”,“terrible”,
“unfair”,“unjust”,“unnecessary”,“unreasonable”,“unacceptable”,“upset”,
“violation”,“waste”,“wrong”,“wrongful”,“destroy”,“destruction”,“gang”,
],
“hope”: [
“achieve”,“advance”,“aim”,“aspire”,“aspiration”,“benefit”,“better”,“build”,
“capability”,“chance”,“change”,“clarity”,“collaborate”,“commitment”,“confidence”,
“contribute”,“cooperation”,“create”,“dream”,“develop”,“empower”,“encourage”,
“equality”,“fair”,“flourish”,“forward”,“freedom”,“future”,“gain”,“goal”,“good”,
“grow”,“growth”,“heal”,“helpful”,“hopeful”,“humanitarian”,“improve”,“inclusion”,
“innovate”,“inspire”,“integrate”,“integration”,“invest”,“investment”,“justice”,
“lead”,“merit”,“new”,“open”,“opportunity”,“participate”,“partner”,“peace”,
“possible”,“potential”,“progress”,“promise”,“prospect”,“protect”,“rebuild”,
“reform”,“renew”,“resolve”,“restore”,“right”,“safe”,“safety”,“solution”,“solve”,
“stable”,“strength”,“succeed”,“success”,“support”,“together”,“trust”,“unite”,
“welcome”,“wellbeing”,“work”,“worthy”,“positive”,“constructive”,
],
“trust”: [
“accountability”,“accurate”,“agree”,“assurance”,“authentic”,“authority”,
“capable”,“clear”,“collaborate”,“commitment”,“competent”,“compliant”,
“confidence”,“consistent”,“cooperate”,“correct”,“credible”,“dependable”,
“effective”,“efficient”,“establish”,“evidence”,“expertise”,“fair”,“faithful”,
“firm”,“framework”,“guarantee”,“guidance”,“honest”,“implement”,“implementing”,
“integrity”,“lawful”,“legal”,“legitimate”,“measured”,“objective”,“obligation”,
“official”,“order”,“procedure”,“proportionate”,“protect”,“protocol”,“ratify”,
“reliable”,“responsibility”,“responsible”,“rule”,“secure”,“security”,
“stability”,“stable”,“standard”,“strong”,“structured”,“systematic”,
“transparent”,“verified”,“regulation”,“compliance”,“mandate”,“pact”,
“agreement”,“treaty”,“coordination”,
],
}

STOPWORDS = set(”””
a about above after again against all also am an and any are as at be because
been before being below between both but by can cannot could did do does doing
don down during each few for from further had has have having he her here
hers herself him himself his how i if in into is it its itself let me more
most my myself no nor not of off on once only or other our ours ourselves out
over own same she should so some such than that the their theirs them
themselves then there these they this those through to too under until up very
was we were what when where which while who will with would you your yours
yourself yourselves
“””.split())

# ── LEXICON LOADER ────────────────────────────────────────────────────────────

def build_lexicon(path=None):
lex = defaultdict(set)
if path and os.path.exists(path):
mapping = {“fear”:“fear”,“anger”:“anger”,“anticipation”:“hope”,“trust”:“trust”}
try:
with open(path, encoding=“utf-8”) as f:
for line in f:
parts = line.strip().split(”\t”)
if len(parts) == 3 and parts[2] == “1”:
word, emotion = parts[0].lower(), parts[1].lower()
if emotion in mapping:
lex[word].add(mapping[emotion])
print(f”  [NRC] Loaded full lexicon from {path}”)
return lex
except Exception as e:
print(f”  [NRC] Could not load file: {e}. Falling back to seed.”)
for emotion, words in SEED_LEXICON.items():
for w in words:
lex[w.lower()].add(emotion)
total = sum(len(v) for v in SEED_LEXICON.values())
print(f”  [NRC] Using seed lexicon ({total} word-emotion pairs)”)
return lex

# ── FETCH ─────────────────────────────────────────────────────────────────────

def fetch_url(url, timeout=15):
try:
import requests
from bs4 import BeautifulSoup
headers = {“User-Agent”: “Mozilla/5.0 (research; NL migration emotion study)”}
r = requests.get(url, headers=headers, timeout=timeout)
r.raise_for_status()
soup = BeautifulSoup(r.text, “lxml”)
for tag in soup([“script”,“style”,“nav”,“footer”,“header”,“aside”,“form”]):
tag.decompose()
text = soup.get_text(separator=” “, strip=True)
return re.sub(r”\s+”, “ “, text).strip(), None
except Exception as e:
return “”, str(e)

# ── SCORING ───────────────────────────────────────────────────────────────────

def tokenize(text):
tokens = re.findall(r”[a-z]+(?:’[a-z]+)?”, text.lower())
return [t for t in tokens if t not in STOPWORDS and len(t) > 2]

def score_text(text, lexicon):
counts = defaultdict(int)
for token in tokenize(text):
for emotion in lexicon.get(token, []):
counts[emotion] += 1
emotions = [“fear”,“anger”,“hope”,“trust”]
total = sum(counts.get(e, 0) for e in emotions)
if total == 0:
return None, 0
pcts = {e: round(100 * counts.get(e, 0) / total, 1) for e in emotions}
return pcts, total

# ── MAIN ──────────────────────────────────────────────────────────────────────

def run(lexicon_path=None):
print(”\n” + “=”*60)
print(”  emotion_map_nl.py — NL Migration Discourse 2026”)
print(”=”*60)

```
lexicon = build_lexicon(lexicon_path)
results = []
log = [f"Run: {datetime.now(timezone.utc).isoformat()}"]

for seg in SEGMENTS:
    print(f"\n▶  {seg['label']}")
    all_text = ""

    for url in seg["urls"]:
        print(f"   Fetching {url[:72]}…")
        text, err = fetch_url(url)
        if err:
            log.append(f"FAIL {url} — {err[:80]}")
            print(f"   ✗ {err[:60]}")
        else:
            all_text += " " + text
            log.append(f"OK   {url} ({len(text):,} chars)")
            print(f"   ✓ {len(text):,} chars")
        time.sleep(1)

    pcts, n = score_text(all_text, lexicon)

    if pcts is None:
        print("   ⚠  No emotion tokens found — segment will show as null")
        log.append(f"EMPTY {seg['id']}")
        results.append({
            "id": seg["id"],
            "label": seg["label"],
            "actor": seg["actor"],
            "fear": None, "anger": None, "hope": None, "trust": None,
            "dominant": None,
            "n": 0,
            "low_sample": True,
            "scored": False,
        })
        continue

    dominant = max(["fear","anger","hope","trust"], key=lambda e: pcts[e])
    low = n < 30
    flag = " ⚠ LOW SAMPLE" if low else ""
    print(f"   Fear {pcts['fear']}%  Anger {pcts['anger']}%  "
          f"Hope {pcts['hope']}%  Trust {pcts['trust']}%  "
          f"→ {dominant.upper()}  n={n}{flag}")
    log.append(f"SCORE {seg['id']}: F={pcts['fear']} A={pcts['anger']} "
               f"H={pcts['hope']} T={pcts['trust']} n={n}{flag}")

    results.append({
        "id": seg["id"],
        "label": seg["label"],
        "actor": seg["actor"],
        "fear": pcts["fear"],
        "anger": pcts["anger"],
        "hope": pcts["hope"],
        "trust": pcts["trust"],
        "dominant": dominant,
        "n": n,
        "low_sample": low,
        "scored": True,
    })

ts = datetime.now(timezone.utc).isoformat()

# ── Write emotion_results.json  ← THIS is what index.html reads ──
payload = {
    "generated": ts,
    "lexicon": "NRC EmoLex full" if (lexicon_path and os.path.exists(lexicon_path or ""))
               else "NRC EmoLex seed subset",
    "note": "Scores computed from live web text. See fetch_log.txt for source URLs.",
    "segments": results,
}
with open("emotion_results.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=2, ensure_ascii=False)
print("\n✅  emotion_results.json written")

# ── Write CSV ──
with open("emotion_results.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["Segment","Actor","Fear (%)","Anger (%)","Hope (%)","Trust (%)",
                "Dominant","Emotion Tokens","Low Sample?","Scored?"])
    for r in results:
        w.writerow([r["label"], r["actor"],
                    r["fear"], r["anger"], r["hope"], r["trust"],
                    r["dominant"], r["n"],
                    "YES" if r["low_sample"] else "no",
                    "YES" if r["scored"] else "FAILED"])
print("✅  emotion_results.csv written")

# ── Write log ──
with open("fetch_log.txt", "w") as f:
    f.write("\n".join(log))
print("✅  fetch_log.txt written")

# ── Summary table ──
print("\n" + "─"*68)
print(f"{'Segment':<28} {'Fear':>6} {'Anger':>6} {'Hope':>6} {'Trust':>6}  {'Dom':<8} n")
print("─"*68)
for r in results:
    f = f"{r['fear']}%" if r['fear'] is not None else "N/A"
    a = f"{r['anger']}%" if r['anger'] is not None else "N/A"
    h = f"{r['hope']}%" if r['hope'] is not None else "N/A"
    t = f"{r['trust']}%" if r['trust'] is not None else "N/A"
    d = (r['dominant'] or 'N/A').upper()
    flag = "⚠" if r["low_sample"] else " "
    print(f"{flag} {r['label']:<27} {f:>6} {a:>6} {h:>6} {t:>6}  {d:<8} {r['n']}")
print("─"*68)
print("⚠ = low sample (<30 emotion tokens)")
print(f"\nGenerated: {ts}")
```

if **name** == “**main**”:
parser = argparse.ArgumentParser()
parser.add_argument(”–lexicon”, default=None,
help=“Path to full NRC EmoLex file (optional)”)
args = parser.parse_args()
run(args.lexicon)

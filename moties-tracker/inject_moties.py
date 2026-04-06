#!/usr/bin/env python3
"""
inject_moties.py — injects moties.json data into index.html’s INIT array.

Must be run AFTER fetch_moties.py and fix_moties_json.py.
Reads moties.json, finds the INIT= line in index.html, replaces it.

Usage: python3 inject_moties.py
"""
import json
import re
import sys
import os
from datetime import date

MOTIES_FILE = 'moties.json'
HTML_FILE   = 'index.html'

def main():
print(f’inject_moties.py — {date.today().isoformat()}’)

```
# ── Load moties.json ──
if not os.path.exists(MOTIES_FILE):
    print(f'ERROR: {MOTIES_FILE} niet gevonden', file=sys.stderr)
    sys.exit(1)

with open(MOTIES_FILE, encoding='utf-8') as f:
    moties = json.load(f)
print(f'Geladen: {len(moties)} moties uit {MOTIES_FILE}')

# ── Load index.html ──
if not os.path.exists(HTML_FILE):
    print(f'ERROR: {HTML_FILE} niet gevonden', file=sys.stderr)
    sys.exit(1)

with open(HTML_FILE, encoding='utf-8') as f:
    html = f.read()

# ── Find and replace INIT= line ──
# Pattern matches:  var INIT=[...];
# The [...] can be multiline but in our HTML it's always one line
pattern = r'var INIT=\[.*?\];'
moties_json = json.dumps(moties, ensure_ascii=False, separators=(',', ':'))
replacement = f'var INIT={moties_json};'

new_html, n = re.subn(pattern, replacement, html, flags=re.DOTALL)

if n == 0:
    print('ERROR: INIT= variabele niet gevonden in index.html', file=sys.stderr)
    sys.exit(1)

print(f'INIT vervangen: {len(moties)} moties geïnjecteerd in index.html')

# ── Also inject agenda if agenda.json exists ──
if os.path.exists('agenda.json'):
    with open('agenda.json', encoding='utf-8') as f:
        agenda = json.load(f)
    agenda_json = json.dumps(agenda, ensure_ascii=False, separators=(',', ':'))
    agenda_pattern = r'var AGENDA=\[.*?\];'
    new_html, n2 = re.subn(agenda_pattern, f'var AGENDA={agenda_json};', new_html, flags=re.DOTALL)
    if n2 > 0:
        print(f'AGENDA vervangen: {len(agenda)} items geïnjecteerd')
    else:
        print('AGENDA= variabele niet gevonden, overgeslagen')

# ── Write back ──
with open(HTML_FILE, 'w', encoding='utf-8') as f:
    f.write(new_html)

print(f'Klaar: {HTML_FILE} bijgewerkt')

# ── Stats ──
aang  = sum(1 for m in moties if m.get('status') == 'aangenomen')
verw  = sum(1 for m in moties if m.get('status') == 'verworpen')
inb   = sum(1 for m in moties if m.get('status') == 'in_behandeling')
print(f'  Aangenomen: {aang}  Verworpen: {verw}  In behandeling: {inb}')
```

if **name** == ‘**main**’:
main()

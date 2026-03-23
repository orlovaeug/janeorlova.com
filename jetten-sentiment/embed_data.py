#!/usr/bin/env python3
"""
embed_data.py — bakt data.json direct in index.html
Zodat GitHub Pages nooit een aparte fetch nodig heeft.
Draait als onderdeel van de GitHub Action na fetch_news.py.
"""
import json, re

with open('data.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace the SEED_DATA array in the HTML with fresh data
new_seed = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

# Find and replace between var SEED_DATA= and the closing ];
html = re.sub(
    r'var SEED_DATA=\[.*?\];',
    'var SEED_DATA=' + new_seed + ';',
    html,
    flags=re.DOTALL
)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f'✅ Embedded {len(data)} items into index.html')

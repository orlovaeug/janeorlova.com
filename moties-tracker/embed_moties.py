#!/usr/bin/env python3
"""
embed_moties.py — bakt moties.json en agenda.json in index.html
Uses safe string replacement, NOT regex with DOTALL (which eats JS code).
"""
import json, re, os
from datetime import date

with open('moties.json', 'r', encoding='utf-8') as f:
    fresh = json.load(f)

agenda = []
if os.path.exists('agenda.json'):
    with open('agenda.json', 'r', encoding='utf-8') as f:
        agenda = json.load(f)

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

def replace_js_var(html, varname, new_value_json):
    """
    Safely replace  var NAME=[...];  by scanning for the exact opening token
    and matching bracket depth — so large JSON blobs never swallow surrounding code.
    """
    token = f'var {varname}=['
    start = html.find(token)
    if start == -1:
        return html
    bracket_start = start + len(token) - 1  # index of '['
    depth = 0
    i = bracket_start
    while i < len(html):
        if html[i] == '[':
            depth += 1
        elif html[i] == ']':
            depth -= 1
            if depth == 0:
                break
        i += 1
    end = i + 1
    if end < len(html) and html[end] == ';':
        end += 1
    new_decl = f'var {varname}={new_value_json};'
    return html[:start] + new_decl + html[end:]

new_init   = json.dumps(fresh,  ensure_ascii=False, separators=(',', ':'))
new_agenda = json.dumps(agenda, ensure_ascii=False, separators=(',', ':'))

html = replace_js_var(html, 'INIT',   new_init)
html = replace_js_var(html, 'AGENDA', new_agenda)
html = replace_js_var(html, 'NIEUW',  '[]')

# Bump storage key
today = date.today().strftime('%Y%m%d')
html = re.sub(r'var SK="motie-v[\w]+"', f'var SK="motie-v{today}"', html)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html)

print(f"✅ {len(fresh)} moties embedded, {len(agenda)} agenda-items, SK bumped to motie-v{today}")

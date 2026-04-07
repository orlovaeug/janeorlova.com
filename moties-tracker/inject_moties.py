#!/usr/bin/env python3
"""
inject_moties.py — injects moties.json into index.html
"""

import json
import re
import sys
import os
from datetime import date

MOTIES_FILE = 'moties.json'
HTML_FILE = 'index.html'


def main():
    print(f'inject_moties.py — {date.today().isoformat()}')

    if not os.path.exists(MOTIES_FILE):
        print(f'ERROR: {MOTIES_FILE} niet gevonden', file=sys.stderr)
        sys.exit(1)

    with open(MOTIES_FILE, encoding='utf-8') as f:
        moties = json.load(f)

    print(f'Geladen: {len(moties)} moties')

    if not os.path.exists(HTML_FILE):
        print(f'ERROR: {HTML_FILE} niet gevonden', file=sys.stderr)
        sys.exit(1)

    with open(HTML_FILE, encoding='utf-8') as f:
        html = f.read()

    pattern = r'var\s+INIT\s*=\s*\[.*?\];'
    data = json.dumps(moties, ensure_ascii=False, separators=(',', ':'))
    replacement = f'var INIT={data};'

    new_html, n = re.subn(pattern, replacement, html, flags=re.DOTALL)

    if n == 0:
        print('ERROR: INIT niet gevonden', file=sys.stderr)
        sys.exit(1)

    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(new_html)

    print('Klaar: index.html bijgewerkt')


if __name__ == '__main__':
    main()

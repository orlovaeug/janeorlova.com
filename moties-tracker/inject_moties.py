#!/usr/bin/env python3
"""
inject_moties.py — injects moties.json data into index.html's INIT array.
"""

import json
import re
import sys
import os
from datetime import date

MOTIES_FILE = 'moties.json'
HTML_FILE = 'moties-tracker/index.html'


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

    new_html = html  # ensure defined

    # ── Inject INIT ──
    moties_json = json.dumps(moties, ensure_ascii=False, separators=(',', ':'))

    new_html, n = re.subn(
        r'var\s+INIT\s*=\s*\[.*?\];',
        f'var INIT={moties_json};',
        new_html,
        flags=re.DOTALL
    )

    if n == 0:
        print('WAARSCHUWING: INIT niet gevonden')
    else:
        print(f'INIT bijgewerkt: {len(moties)} moties')

    # ── Inject AGENDA ──
    if os.path.exists('agenda.json'):
        with open('agenda.json', encoding='utf-8') as f:
            agenda = json.load(f)

        agenda_json = json.dumps(agenda, ensure_ascii=False, separators=(',', ':'))

        new_html, n2 = re.subn(
            r'var\s+AGENDA\s*=\s*\[.*?\];',
            f'var AGENDA={agenda_json};',
            new_html,
            flags=re.DOTALL
        )

        if n2 > 0:
            print(f'AGENDA bijgewerkt: {len(agenda)} items')
        else:
            print('AGENDA niet gevonden — overgeslagen')

    # ── Write file ──
    with open(HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(new_html)

    # ── Stats ──
    aang = sum(1 for m in moties if m.get('status') == 'aangenomen')
    verw = sum(1 for m in moties if m.get('status') == 'verworpen')
    inb = sum(1 for m in moties if m.get('status') == 'in_behandeling')

    print(f'Klaar — aangenomen:{aang} verworpen:{verw} in_behandeling:{inb}')


if __name__ == '__main__':
    main()

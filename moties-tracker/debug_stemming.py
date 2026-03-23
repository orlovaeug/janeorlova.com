#!/usr/bin/env python3
"""Debug: fetch one stemmingsuitslagen detail page and print raw structure."""
import urllib.request, html as html_module, re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Encoding': 'identity',
}

def fetch(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        return html_module.unescape(r.read().decode('utf-8', errors='replace'))

list_url = ('https://www.tweedekamer.nl/kamerstukken/stemmingsuitslagen'
            '?qry=%2A&fld_tk_categorie=Kamerstukken'
            '&fld_prl_kamerstuk=Stemmingsuitslagen&srt=date%3Adesc%3Adate&page=0')

print("=== LIST PAGE ===")
html = fetch(list_url)
detail_links = list(dict.fromkeys(re.findall(
    r'href="(/kamerstukken/stemmingsuitslagen/detail\?[^"]+)"', html
)))
print(f"Found {len(detail_links)} detail links")
for l in detail_links[:3]:
    print(f"  {l}")

if not detail_links:
    print("NO DETAIL LINKS FOUND — printing 2000 chars of list page:")
    print(html[3000:5000])
else:
    detail_url = 'https://www.tweedekamer.nl' + detail_links[0].replace('&amp;', '&')
    print(f"\n=== DETAIL PAGE: {detail_url} ===")
    detail = fetch(detail_url).replace('&amp;', '&')
    
    print("\n--- First 3000 chars ---")
    clean = re.sub(r'<[^>]+>', ' ', detail[:3000])
    clean = re.sub(r'\s+', ' ', clean)
    print(clean[:2000])
    
    zaak_ids = re.findall(r'[?&]id=(\d{4}Z\w+)', detail)
    print(f"\n--- Zaak IDs found: {len(zaak_ids)} ---")
    for z in zaak_ids[:10]:
        print(f"  {z}")
    
    besluit_hits = [(m.start(), m.group()) for m in re.finditer(r'Besluit[^<]{0,50}', detail, re.IGNORECASE)]
    print(f"\n--- Besluit occurrences: {len(besluit_hits)} ---")
    for pos, txt in besluit_hits[:5]:
        print(f"  pos={pos}: {txt!r}")
    
    if zaak_ids:
        first_zaak_pos = detail.find(zaak_ids[0])
        print(f"\n--- 500 chars around first zaak ID ({zaak_ids[0]}) at pos {first_zaak_pos} ---")
        chunk = detail[max(0,first_zaak_pos-50):first_zaak_pos+500]
        clean2 = re.sub(r'<[^>]+>', ' ', chunk)
        clean2 = re.sub(r'\s+', ' ', clean2)
        print(clean2)

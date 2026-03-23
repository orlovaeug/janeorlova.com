#!/usr/bin/env python3
"""
debug_fetch.py — test scraper en print wat er gevonden wordt
Run dit handmatig: python debug_fetch.py
"""
import urllib.request, re, html as html_module

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'nl-NL,nl;q=0.9',
}

url = 'https://www.tweedekamer.nl/kamerstukken/moties?qry=%2A&fld_tk_categorie=Kamerstukken&fld_prl_kamerstuk=Moties&srt=date%3Adesc%3Adate&page=0'

print("Fetching:", url)
req = urllib.request.Request(url, headers=HEADERS)
with urllib.request.urlopen(req, timeout=25) as r:
    raw = r.read().decode('utf-8', errors='replace')

print(f"Got {len(raw)} bytes")

idx = raw.find('/kamerstukken/moties/detail?')
if idx < 0:
    print("ERROR: No motie detail links found at all!")
    print("First 2000 chars of response:")
    print(raw[:2000])
else:
    print(f"\nFirst motie link at position {idx}")
    print("Context (500 chars before, 300 after):")
    print(repr(raw[max(0,idx-500):idx+300]))
    
    links = re.findall(r'/kamerstukken/moties/detail\?[^"\'>\s]+', raw)
    print(f"\nTotal motie detail links on page: {len(links)}")
    print("First 5:", links[:5])

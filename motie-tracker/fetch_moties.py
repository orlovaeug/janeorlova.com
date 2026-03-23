#!/usr/bin/env python3
"""fetch_moties.py — haalt moties op en verrijkt met datum + stemmen in één run."""
import json, re, time, hashlib, urllib.request, urllib.parse
import html as html_module
from datetime import date

DATA_FILE  = 'moties.json'
TODAY      = date.today().isoformat()
START_DATE = '2026-02-23'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'nl-NL,nl;q=0.9,en;q=0.8',
    'Accept-Encoding': 'identity',
    'Connection': 'keep-alive',
}

MONTHS = {
    'januari':1,'februari':2,'maart':3,'april':4,'mei':5,'juni':6,
    'juli':7,'augustus':8,'september':9,'oktober':10,'november':11,'december':12
}

# Coalitie kabinet-Jetten: VVD, D66, CDA
COALITIE  = {"VVD","D66","CDA"}
OPPOSITIE = {"PVV","GL-PvdA","NSC","BBB","SP","PvdD","CU","SGP","Volt","DENK","FvD","JA21","50PLUS","Gr.Markuszower","Groep-Keijzer"}

LEDEN_PARTIJ = {
    # PVV
    "Wilders":"PVV","Geert Wilders":"PVV","Agema":"PVV","Fleur Agema":"PVV",
    "Bosma":"PVV","Martin Bosma":"PVV","Madlener":"PVV","Barry Madlener":"PVV",
    "Emiel van Dijk":"PVV","Léon de Jong":"PVV","Leon de Jong":"PVV",
    "El Boujdaini":"PVV","Heutink":"PVV","Helder":"PVV","Faber":"PVV",
    "Fritsma":"PVV","Graus":"PVV","Beertema":"PVV","De Graaf":"PVV",
    "Duvekot":"PVV","Kerseboom":"PVV",
    # VVD
    "Hermans":"VVD","Yesilgöz":"VVD","Dilan Yesilgöz":"VVD",
    "Michon-Derkzen":"VVD","Rajkowski":"VVD","Becker":"VVD","Bikkers":"VVD",
    "Ellian":"VVD","Brekelmans":"VVD","Hagen":"VVD","Six Dijkstra":"VVD",
    "Klink":"VVD","Peter de Groot":"VVD","Klos":"VVD","Erkens":"VVD",
    "Minhas":"VVD","Palmen":"VVD","Soepboer":"VVD","Wesselink":"VVD",
    "Gündogan":"VVD","Van der Werf":"VVD",
    # NSC
    "Omtzigt":"NSC","Pieter Omtzigt":"NSC","Van Hijum":"NSC","Struijs":"NSC",
    "Boelsma-Hoekstra":"NSC","Lammers":"NSC","Crijns":"NSC","Podt":"NSC","Hartman":"NSC",
    # BBB
    "Van der Plas":"BBB","Caroline van der Plas":"BBB","Hamstra":"BBB","Aardema":"BBB","Tuinman":"BBB",
    "Wendel":"BBB","Jumelet":"BBB","Van Oosterhout":"BBB","Vermeer":"BBB","Kostić":"BBB",
    # GL-PvdA
    "Klaver":"GL-PvdA","Jesse Klaver":"GL-PvdA","Timmermans":"GL-PvdA",
    "Maatoug":"GL-PvdA","Nijboer":"GL-PvdA","Bushoff":"GL-PvdA",
    "Kathmann":"GL-PvdA","Mohandis":"GL-PvdA","Köse":"GL-PvdA","Moorman":"GL-PvdA",
    "Bromet":"GL-PvdA","Chakor":"GL-PvdA","Gijs van Dijk":"GL-PvdA",
    "Hammelburg":"GL-PvdA","Mutluer":"GL-PvdA","Piri":"GL-PvdA",
    "Thijssen":"GL-PvdA","Westerveld":"GL-PvdA","Kuiken":"GL-PvdA",
    "Fatihya Abdi":"GL-PvdA",
    # D66
    "Paternotte":"D66","Jan Paternotte":"D66","Vervuurt":"D66",
    "Van Asten":"D66","Wuite":"D66","Raemakers":"D66","White":"D66","Van der Laan":"D66",
    # CDA
    "Bontenbal":"CDA","Henri Bontenbal":"CDA","Boswijk":"CDA","Vedder":"CDA",
    "Krul":"CDA","Van den Berg":"CDA","Van Ark":"CDA","Armut":"CDA",
    "Van den Brink":"CDA","Inge van Dijk":"CDA",
    # SP
    "Jimmy Dijk":"SP","Dobbe":"SP","Beckerman":"SP","Temmink":"SP",
    "Van Nispen":"SP","Leijten":"SP",
    # PvdD
    "Simons":"PvdD","Teunissen":"PvdD","Vestering":"PvdD","Van Raan":"PvdD",
    # CU
    "Bikker":"CU","Mirjam Bikker":"CU","Ceder":"CU","Grinwis":"CU",
    # SGP
    "Diederik van Dijk":"SGP","Stoffer":"SGP","Flach":"SGP",
    # Volt
    "Dassen":"Volt","Koekkoek":"Volt","Nanninga":"Volt",
    # DENK
    "Stephan van Baarle":"DENK","Van Baarle":"DENK","El Abassi":"DENK",
    "Ergin":"DENK","Kırcalı":"DENK","Kircali":"DENK",
    # JA21
    "Eerdmans":"JA21",
    # FvD
    "Baudet":"FvD",
    # Groep Markuszower
    "Markuszower":"Gr.Markuszower",
    # Groep Keijzer
    "Keijzer":"Groep-Keijzer",
    # 50PLUS
    "Baay-Timmerman":"50PLUS",
}

# ── Party name normalization (OData / HTML variants → canonical) ──────────────
PARTY_NORM_GLOBAL = {
    'GroenLinks-PvdA': 'GL-PvdA',
    'ChristenUnie': 'CU',
    'Groep Markuszower': 'Gr.Markuszower',
    'Lid Keijzer': 'Groep-Keijzer',
    'FVD': 'FvD',
    'FvD': 'FvD',
    'Partij voor de Dieren': 'PvdD',
    'Socialistische Partij': 'SP',
    'Volkspartij voor Vrijheid en Democratie': 'VVD',
    'Democraten 66': 'D66',
    'Christen-Democratisch Appèl': 'CDA',
    'Christen-Democratisch App\u00e8l': 'CDA',
    'Partij voor de Vrijheid': 'PVV',
    'Nieuw Sociaal Contract': 'NSC',
    'BoerBurgerBeweging': 'BBB',
    'Forum voor Democratie': 'FvD',
    'Staatkundig Gereformeerde Partij': 'SGP',
    # Short aliases that appear in HTML tables
    'GL-PvdA': 'GL-PvdA',
    'PVV': 'PVV', 'VVD': 'VVD', 'NSC': 'NSC', 'BBB': 'BBB',
    'D66': 'D66', 'CDA': 'CDA', 'SP': 'SP', 'PvdD': 'PvdD',
    'CU': 'CU', 'SGP': 'SGP', 'Volt': 'Volt', 'DENK': 'DENK',
    'JA21': 'JA21', '50PLUS': '50PLUS',
    'Gr.Markuszower': 'Gr.Markuszower', 'Groep-Keijzer': 'Groep-Keijzer',
}

def norm_party(name):
    """Normalize a party name to canonical form."""
    return PARTY_NORM_GLOBAL.get(name, name)

def norm_stemmen(stemmen):
    """Normalize all party keys in a stemmen dict to canonical names."""
    if not stemmen:
        return stemmen
    return {norm_party(k): v for k, v in stemmen.items()}


STRIJDIG_KEYWORDS = [
    "klimaatdoel","kinderopvang gratis","eigen risico afschaffen",
    "asielzoekers meer","vluchtelingen opvang","discriminatie aanpakken",
]
CONFORM_KEYWORDS = [
    "asielinstroom beperken","grenzen sluiten","defensie versterken",
    "kernenergie","belastingverlaging","navo","terugkeer","grenscontrole",
]

THEMA_KEYWORDS = {
    "Defensie":["defensie","militair","navo","leger","oekra","wapen","krijgsmacht","luchtmacht","marine","vredesmissie","uitzend","evertsen","fregat","missie"],
    "Bestaanszekerheid":["aow","pensioen","uitkering","armoede","minimumloon","bijstand","bestaanszekerheid"],
    "Klimaat & Energie":["klimaat","energie","windmolen","kerncentrale","co2","netcongestie","zonnepaneel","warmtepomp","fossiel"],
    "Wonen & Bouwen":["woning","huur","hypotheek","bouwen","nieuwbouw","woningmarkt","huurder","corporatie"],
    "Zorg":["zorg","eigen risico","ggz","ziekenhuis","verpleging","mantelzorg","huisarts","medicijn","apotheek"],
    "Asiel & Migratie":["asiel","migratie","vluchteling","ind","azc","verblijf","inburgering","grenstoezicht","asielzoekers"],
    "Onderwijs":["onderwijs","school","leraar","student","universiteit","mbo","kinderopvang","studie"],
    "Landbouw & Natuur":["landbouw","boer","stikstof","natuur","natura","veehouderij","mest","visserij"],
    "Financiën":["belasting","begroting","box 3","btw","rijksbegroting","staatsschuld","belastingdienst"],
    "Buitenlandse Zaken":["europa","oekra","buitenland","sanctie","diplomatie","israel","gaza","ukraine"],
    "Democratie & Rechtsstaat":["democratie","grondwet","rechtsstaat","referendum","verkiezing","rechter"],
    "Economie":["economie","ondernemen","mkb","arbeidsmarkt","concurrentie","export","innovatie"],
    "Bereikbaarheid":["trein","spoor","fiets","ov","snelweg","mobiliteit","bereikbaarheid","schiphol"],
    "Overig":[],
}

def detect_thema(text):
    t = text.lower()
    best, best_score = "Overig", 0
    for thema, kws in THEMA_KEYWORDS.items():
        score = sum(1 for k in kws if k in t)
        if score > best_score:
            best, best_score = thema, score
    return best

def detect_indiener(titel):
    # Strip " - [Debat title]" suffix appended by TK website
    titel_clean = re.sub(r'\s+-\s+[A-Z][^-]{5,}$', '', titel).strip()
    m = re.search(
        r'(?:(?:Nader\s+)?[Gg]ewijzigde\s+)?[Mm]otie\s+van\s+(?:het\s+lid|de\s+leden)\s+'
        r'([A-Z][a-zA-Z\u00C0-\u017E\-]+(?:\s+[a-zA-Z\u00C0-\u017E\-]+){0,4}?)'
        r'(?:\s+c\.s\.|\s+over\s|\s+en\s+[A-Z]|\s+-\s+[A-Z]|$)',
        titel_clean
    )
    name_ctx = m.group(1).strip() if m else titel_clean
    for naam in sorted(LEDEN_PARTIJ.keys(), key=len, reverse=True):
        pat = r'(?<![A-Za-z\u00C0-\u017E])' + re.escape(naam) + r'(?![A-Za-z\u00C0-\u017E])'
        if re.search(pat, name_ctx, re.IGNORECASE):
            return LEDEN_PARTIJ[naam]
    for p in ["PVV","VVD","NSC","BBB","D66","GL-PvdA","CDA","SP","PvdD","CU","SGP","Volt","DENK","FvD","JA21","50PLUS"]:
        if p in titel:
            return p
    return "Onbekend"

def detect_alignment(titel, indiener):
    t = titel.lower()
    for kw in STRIJDIG_KEYWORDS:
        if kw in t: return "strijdig"
    for kw in CONFORM_KEYWORDS:
        if kw in t: return "conform"
    if indiener in COALITIE: return "conform"
    if indiener in OPPOSITIE: return "strijdig"
    return "neutraal"

def make_id(val):
    return 'tk' + hashlib.md5(str(val).encode()).hexdigest()[:10]

def parse_dutch_date(s):
    if not s:
        return None
    m = re.search(
        r'(\d{1,2})\s+(januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)\s+(20\d{2})',
        s, re.IGNORECASE
    )
    if m:
        mo = MONTHS.get(m.group(2).lower(), 0)
        if mo:
            return f"{m.group(3)}-{mo:02d}-{int(m.group(1)):02d}"
    return None

def fetch_html(url):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read().decode('utf-8', errors='replace')
        return html_module.unescape(raw)
    except Exception as e:
        print(f'  Fetch fout: {e}')
        return ''

def extract_zaak_id(url_or_str):
    """Extract zaak ID from URL — any year (2025Z, 2026Z, etc.)"""
    m = re.search(r'[?&]id=(\d{4}Z\w+)', url_or_str)
    return m.group(1) if m else None

def extract_doc_id(url_or_str):
    """Extract document ID (2026D...) from URL — used as fallback when zaak ID absent."""
    # Try did= parameter first, then id= with D-type
    m = re.search(r'[?&]did=(\d{4}D\w+)', url_or_str)
    if m: return m.group(1)
    m = re.search(r'[?&]id=(\d{4}D\w+)', url_or_str)
    return m.group(1) if m else None

# ── Live Kamerleden scrape ──

def fetch_leden_partij():
    PARTY_NORM = {
        "GroenLinks-PvdA":"GL-PvdA","ChristenUnie":"CU",
        "Groep Markuszower":"Gr.Markuszower","Lid Keijzer":"Groep-Keijzer","FVD":"FvD",
    }
    result = {}
    html = fetch_html("https://www.tweedekamer.nl/kamerleden_en_commissies/alle_kamerleden")
    if not html:
        return {}
    cards = re.findall(
        r'/alle_kamerleden/[^"]+">([^<]+)</a>\s*</h3>\s*<[^>]+>\s*([A-Za-z0-9\-\s]+?)[\s<]',
        html
    )
    for full_name, party in cards:
        full_name = full_name.strip()
        party = PARTY_NORM.get(party.strip(), party.strip())
        if not full_name or not party or len(party) > 25:
            continue
        result[full_name] = party
        parts = full_name.split()
        for i in range(len(parts)-1, -1, -1):
            if parts[i][0].isupper():
                last = parts[i]
                # Only add last-name shortcut if it doesn't already exist in LEDEN_PARTIJ
                # with a DIFFERENT party (avoid clobbering known entries)
                if last not in result:
                    result[last] = party
                break
    print(f'  Kamerleden geladen: {len(result)} namen')
    return result

# ── Stemmingsuitslagen ──

def scrape_stemmingen():
    """
    Scrape stemmingsuitslagen since START_DATE.
    Returns dict: zaak_id -> {datum, besluit}
    """
    stemmingen = {}
    base = (
        'https://www.tweedekamer.nl/kamerstukken/stemmingsuitslagen'
        '?qry=%2A&fld_tk_categorie=Kamerstukken'
        '&fld_prl_kamerstuk=Stemmingsuitslagen&srt=date%3Adesc%3Adate&page='
    )

    for page in range(25):
        html = fetch_html(base + str(page))
        if not html:
            break

        detail_links = list(dict.fromkeys(re.findall(
            r'href="(/kamerstukken/stemmingsuitslagen/detail\?[^"]+)"', html
        )))
        if not detail_links:
            print(f'  Stemmingen pagina {page+1}: geen links — stoppen')
            break

        print(f'  Stemmingen pagina {page+1}: {len(detail_links)} sessies')

        oldest_on_page = None

        for link in detail_links:
            link_url = 'https://www.tweedekamer.nl' + link.replace('&amp;', '&')
            detail = fetch_html(link_url)
            if not detail:
                continue

            detail = detail.replace('&amp;', '&')
            session_datum = None
            footer_m = re.search(r'fromdate=(20\d{2}-\d{2}-\d{2})', detail)
            if footer_m:
                session_datum = footer_m.group(1)
            
            if not session_datum:
                detail_text = re.sub(r'<[^>]+>', ' ', detail)
                pv_m = re.search(
                    r'Plenaire\s+vergadering\s+(\d{1,2}\s+\w+\s+20\d{2})',
                    detail_text, re.IGNORECASE
                )
                if pv_m:
                    session_datum = parse_dutch_date(pv_m.group(1))
            
            if not session_datum:
                detail_text = re.sub(r'<[^>]+>', ' ', detail)
                any_m = re.search(
                    r'(\d{1,2}\s+(?:januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)\s+20\d{2})',
                    detail_text, re.IGNORECASE
                )
                if any_m:
                    session_datum = parse_dutch_date(any_m.group(1))

            if not session_datum:
                print(f'    Geen datum gevonden: {link_url[:80]}')
                continue

            if oldest_on_page is None or session_datum < oldest_on_page:
                oldest_on_page = session_datum

            if session_datum < START_DATE:
                print(f'    Sessie {session_datum} voor {START_DATE} — overslaan')
                continue

            for split_pat in [
                r'(?=class="js-clickable[^"]*")',
                r'(?=class="search-result)',
                r'(?=<article)',
                r'(?=<li[^>]*kamerstuk)',
            ]:
                cards = re.split(split_pat, detail)
                if len(cards) > 2:
                    break
            
            if len(cards) <= 2:
                cards = re.split(r'(?=href="[^"]*[?&]id=\d{4}Z)', detail)

            found_besluit = 0
            found_moties = 0

            for card in cards:
                # Try Z-type zaak ID first (e.g. 2026Z04934)
                id_m = re.search(r'href="([^"]*[?&]id=(\d{4}Z\w+)[^"]*)"', card)
                if not id_m:
                    id_m2 = re.search(r'[?&]id=(\d{4}Z\w+)', card)
                    if id_m2:
                        zaak_id = id_m2.group(1)
                        href = ''
                    else:
                        # No Z-type ID — try D-type doc ID (e.g. ?id=2026D11247)
                        # These appear on stemmingsuitslagen when only the document
                        # is linked, not the zaak. We record it; cross-ref happens below.
                        id_d = re.search(r'[?&](?:id|did)=(\d{4}D\w+)', card)
                        if not id_d:
                            continue
                        # Store as doc_id key; will be resolved via existing_by_doc later
                        zaak_id = None
                        doc_id = id_d.group(1)
                        href = ''
                else:
                    href = 'https://www.tweedekamer.nl' + id_m.group(1) if id_m.group(1).startswith('/') else id_m.group(1)
                    zaak_id = id_m.group(2)
                    doc_id = None
                found_moties += 1

                card_text = re.sub(r'<[^>]+>', ' ', card)
                bm = re.search(r'Besluit[:\s]+(Aangenomen|Verworpen|Aangehouden)', card_text, re.IGNORECASE)
                if not bm:
                    bm = re.search(r'\b(Aangenomen|Verworpen|Aangehouden)\b', card_text, re.IGNORECASE)
                besluit = bm.group(1).lower() if bm else None
                if besluit:
                    found_besluit += 1

                score_m = re.search(r'Besluit:[^(]*(\(\d+-\d+\))', card_text, re.IGNORECASE)
                score = score_m.group(1) if score_m else None

                # Store by zaak_id (Z-type) or doc_id (D-type) as fallback
                key = zaak_id if zaak_id else doc_id if 'doc_id' in dir() else None
                if not key:
                    continue
                if key not in stemmingen:
                    stemmingen[key] = {'datum': session_datum, 'besluit': besluit, 'score': score, 'href': href}
                else:
                    if besluit and not stemmingen[key].get('besluit'):
                        stemmingen[key]['besluit'] = besluit
                    if score and not stemmingen[key].get('score'):
                        stemmingen[key]['score'] = score
                    if href and not stemmingen[key].get('href'):
                        stemmingen[key]['href'] = href

            print(f'    {session_datum}: {found_moties} moties, {found_besluit} besluit')
            time.sleep(0.5)

        if oldest_on_page and oldest_on_page < START_DATE:
            print(f'  Oudste sessie: {oldest_on_page} — stoppen')
            break

        time.sleep(1)

    voted = sum(1 for v in stemmingen.values() if v.get('besluit'))
    print(f'  Stemmingen totaal: {len(stemmingen)} moties, {voted} met besluit')
    return stemmingen


# ── Motie detail page ──

def fetch_motie_datum(url):
    if not url.startswith('http'):
        url = 'https://www.tweedekamer.nl' + url
    html = fetch_html(url)
    if not html:
        return None
    for pattern in [
        r'Datum[:\s]+(\d{1,2}\s+\w+\s+20\d{2})',
        r'Voorgesteld\s+(\d{1,2}\s+\w+\s+20\d{2})',
        r'(\d{1,2}\s+(?:januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)\s+20\d{2})',
    ]:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            d = parse_dutch_date(m.group(1))
            if d and d >= START_DATE:
                return d
    return None

def fetch_motie_title(url):
    """Fetch the real title from a motie detail page <title> tag."""
    if not url.startswith('http'):
        url = 'https://www.tweedekamer.nl' + url
    html = fetch_html(url)
    if not html:
        return None
    m = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if m:
        t = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        t = t.split('|')[0].strip()
        if t and len(t) > 10 and t.lower() not in ('motie','moties'):
            return t
    m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
    if m:
        t = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        t = re.sub(r'\s+', ' ', t)
        if t and len(t) > 10:
            return t
    return None


def fetch_motie_detail(url):
    """Fetch date, title, and besluit from motie detail page in one HTTP request."""
    if not url.startswith('http'):
        url = 'https://www.tweedekamer.nl' + url
    html = fetch_html(url)
    if not html:
        return None, None, None
    text = re.sub(r'<[^>]+>', ' ', html)
    title = None
    m = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if m:
        t = re.sub(r'<[^>]+>', '', m.group(1)).strip()
        t = t.split('|')[0].strip()
        if t and len(t) > 10 and t.lower() not in ('motie', 'moties'):
            title = t
    if not title:
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.IGNORECASE | re.DOTALL)
        if m:
            t = re.sub(r'<[^>]+>', '', m.group(1)).strip()
            t = re.sub(r'\s+', ' ', t)
            if t and len(t) > 10:
                title = t
    datum = None
    for pattern in [
        r'Datum[:\s]+(\d{1,2}\s+\w+\s+20\d{2})',
        r'Voorgesteld\s+(\d{1,2}\s+\w+\s+20\d{2})',
        r'(\d{1,2}\s+(?:januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)\s+20\d{2})',
    ]:
        m = re.search(pattern, html, re.IGNORECASE)
        if m:
            d = parse_dutch_date(m.group(1))
            if d and d >= START_DATE:
                datum = d
                break
    besluit = None
    bm = re.search(r'Besluit[:\s]+(Aangenomen|Verworpen|Aangehouden)', text, re.IGNORECASE)
    if bm:
        besluit = bm.group(1).lower()
    return datum, title, besluit

def fetch_stemmen(url):
    """Fetch per-party vote breakdown from motie detail page."""
    if not url.startswith('http'):
        url = 'https://www.tweedekamer.nl' + url
    html = fetch_html(url)
    if not html:
        return {}
    stemmen = {}
    for tr in re.findall(r'<tr\b[^>]*>(.*?)</tr>', html, re.IGNORECASE | re.DOTALL):
        cells = re.findall(r'<td\b[^>]*>(.*?)</td>', tr, re.IGNORECASE | re.DOTALL)
        if len(cells) >= 3:
            party = re.sub(r'<[^>]+>', '', cells[0]).strip()
            vote_raw = re.sub(r'<[^>]+>', '', cells[2]).strip()
            vote_match = re.match(r'(Voor|Tegen|Niet deelgenomen|Onthouden)', vote_raw, re.IGNORECASE)
            if party and vote_match and party.lower() not in ('fracties', 'fractie'):
                canon = norm_party(party)
                stemmen[canon] = vote_match.group(1).lower().replace('niet deelgenomen', 'afwezig')
    return stemmen


def fetch_zaak_besluit(zaak_nummer):
    """Fetch besluit status via OData Zaak->expand Besluit. Returns (status, besluit_id)."""
    BASE = 'https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/'
    HDR = {**HEADERS, 'Accept': 'application/json'}
    try:
        url = (BASE + 'Zaak?$filter=' + urllib.parse.quote(f"Nummer eq '{zaak_nummer}'")
               + '&$expand=Besluit($select=Id,BesluitTekst,StemmingsSoort)'
               + '&$select=Id,Nummer&$top=1')
        req = urllib.request.Request(url, headers=HDR)
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
        items = data.get('value', [])
        if not items:
            return None, None
        besluiten = items[0].get('Besluit', [])
        if not besluiten:
            return None, None
        b = besluiten[0]
        tekst = (b.get('BesluitTekst') or '').lower()
        besluit_id = b.get('Id', '')
        if 'aangenomen' in tekst:
            return 'aangenomen', besluit_id
        elif 'verworpen' in tekst:
            return 'verworpen', besluit_id
        elif 'aangehouden' in tekst:
            return 'aangehouden', besluit_id
        return None, besluit_id
    except Exception as e:
        try:
            body = e.read().decode()[:300]
            print(f'    OData besluit fout ({zaak_nummer}): {e} | {body}')
        except:
            print(f'    OData besluit fout ({zaak_nummer}): {e}')
        return None, None


def fetch_stemmen_odata(zaak_nummer):
    """Fetch per-party votes via single OData expand chain: Zaak->Besluit->Stemming.
    Returns dict with canonical party names.
    """
    VOTE_NORM = {'voor': 'voor', 'tegen': 'tegen', 'niet deelgenomen': 'afwezig'}
    BASE = 'https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/'
    HDR = {**HEADERS, 'Accept': 'application/json'}
    try:
        expand = 'Besluit($expand=Stemming($select=Soort,ActorNaam,ActorFractie);$select=Id,BesluitTekst)'
        url = (BASE + 'Zaak?$filter=' + urllib.parse.quote(f"Nummer eq '{zaak_nummer}'")
               + '&$expand=' + expand
               + '&$select=Id,Nummer&$top=1')
        req = urllib.request.Request(url, headers=HDR)
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
        items = data.get('value', [])
        if not items:
            return {}
        besluiten = items[0].get('Besluit', [])
        stemmingen_raw = []
        for b in besluiten:
            s = b.get('Stemming', [])
            if s:
                stemmingen_raw = s
                break
        if not stemmingen_raw:
            return {}
        stemmen = {}
        for item in stemmingen_raw:
            naam = (item.get('ActorFractie') or item.get('ActorNaam') or '').strip()
            naam = norm_party(naam)   # ← always normalize
            soort = (item.get('Soort') or '').lower()
            vote = VOTE_NORM.get(soort, soort)
            if naam and vote and naam not in stemmen:
                stemmen[naam] = vote
        return stemmen
    except Exception as e:
        try:
            body = e.read().decode()[:300]
            print(f'    OData stemmen fout ({zaak_nummer}): {e} | {body}')
        except:
            print(f'    OData stemmen fout ({zaak_nummer}): {e}')
        return {}


def fetch_agenda():
    """Fetch plenaire agenda from TK OData API."""
    today = date.today().isoformat()
    future = (date.today() + __import__('datetime').timedelta(days=21)).isoformat()
    filter_str = f"Datum ge {today} and Datum le {future} and Verwijderd eq false"
    url = (
        "https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/Activiteit"
        "?$filter=" + urllib.parse.quote(filter_str)
        + "&$orderby=" + urllib.parse.quote("Datum asc,Aanvangstijd asc")
        + "&$select=Id,Nummer,Onderwerp,Datum,Aanvangstijd,Locatie,Soort"
        + "&$top=60"
    )
    try:
        req = urllib.request.Request(url, headers={**HEADERS, 'Accept': 'application/json'})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode('utf-8'))
        items = data.get('value', [])
        PLENAIR_SOORTEN = {
            'Plenair debat (debat)', 'Plenair debat (wetgeving)',
            'Plenair debat (tweeminutendebat)', 'Plenair debat (overig)',
            'Stemmingen', 'Hamerstukken', 'Regeling van werkzaamheden'
        }
        plenair = [a for a in items if a.get('Soort','') in PLENAIR_SOORTEN]
        if not plenair:
            plenair = items
        agenda = []
        for a in plenair:
            datum = (a.get('Datum') or '')[:10]
            nummer = a.get('Nummer','')
            if nummer:
                tk_url = f"https://www.tweedekamer.nl/debat_en_vergadering/plenaire_vergaderingen/details/activiteit?id={nummer}"
            else:
                tk_url = "https://www.tweedekamer.nl/debat_en_vergadering/plenaire_vergaderingen"
            agenda.append({
                'datum':   datum,
                'tijd':    (a.get('Aanvangstijd') or '')[:5],
                'titel':   a.get('Onderwerp') or a.get('Nummer') or 'Vergadering',
                'locatie': a.get('Locatie') or 'Plenaire zaal',
                'soort':   a.get('Soort') or 'Plenair',
                'url':     tk_url,
            })
        print(f'  Agenda: {len(agenda)} activiteiten geladen')
        return agenda
    except Exception as e:
        print(f'  Agenda ophalen mislukt: {e}')
        return []


# ── Moties list scrape ──

def fetch_page(page=0):
    url = (
        'https://www.tweedekamer.nl/kamerstukken/moties'
        '?qry=%2A&fld_tk_categorie=Kamerstukken&fld_prl_kamerstuk=Moties'
        f'&srt=date%3Adesc%3Adate&page={page}'
    )
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read().decode('utf-8', errors='replace')
        return raw
    except Exception as e:
        print(f'  Fout pagina {page+1}: {e}')
        return ''

def parse_moties_from_html(raw):
    seen_links = {}
    seen_dates = {}
    raw = html_module.unescape(raw)
    for m in re.finditer(r'<a\b[^>]*href="(/kamerstukken/moties/detail\?[^"]+)"[^>]*>(.*?)</a>', raw, re.DOTALL):
        link = 'https://www.tweedekamer.nl' + m.group(1).replace('&amp;', '&')
        title = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        title = re.sub(r'\s+', ' ', title)
        title = re.sub(r'^[Mm]otie\s*:\s*', '', title).strip()
        if not title or len(title) < 15 or 'motie' not in title.lower():
            continue
        if '\n' in title:
            continue
        if link not in seen_links or len(title) > len(seen_links[link]):
            seen_links[link] = title
            start = max(0, m.start() - 300)
            ctx = raw[start:m.start()]
            date_m = re.search(
                r'(\d{1,2})\s+(januari|februari|maart|april|mei|juni|juli|augustus|september|oktober|november|december)\s+(20\d{2})',
                ctx, re.IGNORECASE
            )
            if date_m:
                mo = MONTHS.get(date_m.group(2).lower(), 0)
                seen_dates[link] = f"{date_m.group(3)}-{mo:02d}-{int(date_m.group(1)):02d}" if mo else ''
            else:
                seen_dates[link] = ''
    return [{'titel': seen_links[l], 'list_date': seen_dates.get(l,''), 'link': l} for l in seen_links]

# ── Main ──

def main():
    print(f'Moties ophalen — {TODAY}')

    try:
        with open(DATA_FILE, encoding='utf-8') as f:
            existing = json.load(f)
    except FileNotFoundError:
        existing = []

    # Purge any existing moties before START_DATE
    before = len(existing)
    existing = [m for m in existing if m.get('datum','') >= START_DATE]
    if len(existing) < before:
        print(f'Gezuiverd: {before - len(existing)} moties voor {START_DATE} verwijderd')

    # ── FIX: Normalize party names in existing stemmen ──────────────────────
    normalized_stemmen = 0
    for m in existing:
        if m.get('stemmen'):
            new_stemmen = norm_stemmen(m['stemmen'])
            if new_stemmen != m['stemmen']:
                m['stemmen'] = new_stemmen
                normalized_stemmen += 1
    if normalized_stemmen:
        print(f'Partijnamen genormaliseerd in {normalized_stemmen} bestaande moties')

    # ── FIX: Re-detect thema and indiener for moties that may have wrong values ──
    # Re-run for all moties where thema might be wrong (e.g. "Bereikbaarheid" for
    # a ship/defence motie, or indiener "Onbekend" for known members)
    redetected = 0
    for m in existing:
        if not m.get('titel'):
            continue
        new_thema = detect_thema(m['titel'])
        new_indiener = detect_indiener(m['titel'])
        changed = False
        # Always re-detect thema (cheap, fixes bad classifications)
        if new_thema != m.get('thema'):
            m['thema'] = new_thema
            changed = True
        # Fix indiener only if currently "Onbekend" or empty
        if m.get('indiener') in ('Onbekend', '', None) and new_indiener != 'Onbekend':
            m['indiener'] = new_indiener
            changed = True
        if changed:
            # Also re-run alignment with updated indiener
            m['alignment'] = detect_alignment(m['titel'], m['indiener'])
            redetected += 1
    if redetected:
        print(f'Thema/indiener herdetectie: {redetected} moties bijgewerkt')

    existing_links   = {x.get('tk_url','') for x in existing}
    existing_by_zaak = {
        extract_zaak_id(x.get('tk_url','')): x
        for x in existing
        if extract_zaak_id(x.get('tk_url',''))
    }
    # Secondary index: doc ID (2026D...) -> motie
    # Covers moties where the stemmingsuitslagen page links by did= not id=
    existing_by_doc = {
        extract_doc_id(x.get('tk_url','')): x
        for x in existing
        if extract_doc_id(x.get('tk_url',''))
    }

    print(f'Bestaande moties: {len(existing)}')

    # Load live Kamerleden — but DON'T overwrite existing LEDEN_PARTIJ entries
    print('Kamerleden ophalen...')
    live_leden = fetch_leden_partij()
    if live_leden:
        for naam, partij in live_leden.items():
            if naam not in LEDEN_PARTIJ:   # ← only add, never overwrite
                LEDEN_PARTIJ[naam] = partij

    scraped_count = sum(1 for x in existing if str(x.get('id','')).startswith('tk'))
    is_backfill   = scraped_count == 0
    max_pages     = 50 if is_backfill else 30
    print(f'Mode: {"backfill" if is_backfill else "daily"} (max {max_pages} paginas)')

    # ── Step 1: Stemmingsuitslagen ──
    print('\nStemmingsuitslagen ophalen...')
    stemmingen = scrape_stemmingen()

    # Apply to existing moties
    updated_vote = 0
    matched = 0

    # ── Diagnostics ──
    z_hits = sum(1 for k in stemmingen if k in existing_by_zaak)
    d_hits = sum(1 for k in stemmingen if k in existing_by_doc)
    unmatched_keys = [k for k in stemmingen if k not in existing_by_zaak and k not in existing_by_doc]
    print(f'  DEBUG: stemmingen={len(stemmingen)}, zaak_hits={z_hits}, doc_hits={d_hits}, unmatched={len(unmatched_keys)}')
    if unmatched_keys:
        print(f'  DEBUG unmatched sample: {unmatched_keys[:8]}')
    if existing_by_zaak:
        print(f'  DEBUG existing_by_zaak sample: {list(existing_by_zaak.keys())[:5]}')

    for key, stemming in stemmingen.items():
        # key is either a zaak_id (2026Z...) or doc_id (2026D...)
        m = existing_by_zaak.get(key) or existing_by_doc.get(key)
        if not m:
            continue
        zaak_id = key
        matched += 1
        changed = False
        if stemming.get('datum') and m.get('datum','') in ('', TODAY):
            m['datum'] = stemming['datum']
            changed = True
        if stemming.get('besluit') and m.get('status','') not in ('aangenomen','verworpen','aangehouden'):
            m['status'] = stemming['besluit']
            m['archief'] = False
            m.pop('stemmen_na', None)
            changed = True
        if stemming.get('score') and not m.get('score'):
            m['score'] = stemming['score']
            changed = True
        if changed:
            updated_vote += 1
    already_final = matched - updated_vote
    unmatched_count = len(stemmingen) - matched
    print(f'  Stemresultaten: {updated_vote} bijgewerkt, {already_final} al correct, {unmatched_count} niet gevonden in moties.json')

    # ── Step 1a: fetch moties that were voted but not yet in our list ──
    unmatched_stemmingen = [
        kid for kid in stemmingen
        if kid not in existing_by_zaak and kid not in existing_by_doc
    ]
    if unmatched_stemmingen:
        print(f'  Ongematchte stemmingen ({len(unmatched_stemmingen)}): ophalen...')
        added_from_stemming = 0
        for stem_key in unmatched_stemmingen[:200]:
            stemming_entry = stemmingen[stem_key]
            # Only Z-type keys map directly to a motie URL
            # D-type keys (doc IDs) can't be used to construct a motie URL — skip
            if not re.match(r'\d{4}Z', stem_key):
                continue
            zaak_id = stem_key
            link = f'https://www.tweedekamer.nl/kamerstukken/moties/detail?id={zaak_id}'
            if link in existing_links:
                continue
            item_id = make_id(link)
            try:
                real_date, real_title, real_besluit = fetch_motie_detail(link)
            except Exception:
                continue
            time.sleep(0.4)
            if not real_title:
                continue
            if not real_date:
                real_date = stemming_entry.get('datum') or TODAY
            if not real_date or real_date < START_DATE:
                continue
            status = real_besluit or stemming_entry.get('besluit') or 'in_behandeling'
            thema    = detect_thema(real_title)
            indiener = detect_indiener(real_title)
            new_m = {
                'id': item_id, 'titel': real_title, 'indiener': indiener,
                'datum': real_date, 'thema': thema, 'status': status,
                'alignment': detect_alignment(real_title, indiener),
                'vergadering': '', 'tk_url': link, 'toelichting': '',
                'stemmen': {}, 'archief': False,
            }
            if stemming_entry.get('score'):
                new_m['score'] = stemming_entry['score']
            existing.append(new_m)
            existing_by_zaak[zaak_id] = new_m
            existing_links.add(link)
            added_from_stemming += 1
        print(f'  {added_from_stemming} nieuwe moties toegevoegd vanuit stemmingen')
        existing_by_zaak = {
            extract_zaak_id(x.get('tk_url', '')): x
            for x in existing
            if extract_zaak_id(x.get('tk_url', ''))
        }
        existing_by_doc = {
            extract_doc_id(x.get('tk_url', '')): x
            for x in existing
            if extract_doc_id(x.get('tk_url', ''))
        }

    # ── Step 1b: Fix moties still in_behandeling ──
    # Pass 1: fast fix via stemmingen dict
    fixed_besluit = 0
    still_in_behandeling = []
    for m in existing:
        if m.get('status') != 'in_behandeling':
            continue
        zaak_id = extract_zaak_id(m.get('tk_url', ''))
        doc_id = extract_doc_id(m.get('tk_url', ''))
        stemming = stemmingen.get(zaak_id) or (stemmingen.get(doc_id) if doc_id else None)
        if stemming and stemming.get('besluit'):
            m['status'] = stemming['besluit']
            m['archief'] = False
            m.pop('stemmen_na', None)
            if stemming.get('datum') and m.get('datum', '') in ('', TODAY):
                m['datum'] = stemming['datum']
            if stemming.get('score') and not m.get('score'):
                m['score'] = stemming['score']
            fixed_besluit += 1
        else:
            # Not in stemmingen dict — could still have been voted; queue for OData check
            still_in_behandeling.append(m)
    if fixed_besluit:
        print(f'  {fixed_besluit} in_behandeling moties bijgewerkt via stemmingen dict')

    # Pass 2: OData check for ALL remaining in_behandeling moties
    # Catches moties absent from stemmingen scrape (older sessions, zaak-ID mismatch, etc.)
    if still_in_behandeling:
        check_count = min(60, len(still_in_behandeling))
        print(f'  OData besluit-check: {check_count} resterende in_behandeling moties')
        fixed2 = 0
        for m in still_in_behandeling[:60]:
            zaak_id = extract_zaak_id(m.get('tk_url', ''))
            if not zaak_id:
                continue
            besluit, _ = fetch_zaak_besluit(zaak_id)
            time.sleep(0.4)
            if besluit:
                m['status'] = besluit
                m['archief'] = False
                m.pop('stemmen_na', None)
                fixed2 += 1
                print(f'    OData fix: {zaak_id} -> {besluit}')
        if fixed2:
            print(f'    {fixed2} moties bijgewerkt via OData')

    # Reset stemmen_na for moties now confirmed voted (status fixed above by OData/stemmingen)
    # Must run AFTER step 1b so newly-fixed statuses are included
    reset_count = 0
    for m in existing:
        if m.get('stemmen_na') and not m.get('stemmen') and m.get('status') in ('aangenomen','verworpen'):
            m.pop('stemmen_na', None)
            reset_count += 1
    if reset_count:
        print(f'  stemmen_na gereset voor {reset_count} moties (leeg stemmen, wel status)')

    # Fetch per-party votes for voted moties that don't have them yet (max 80 per run)
    needs_stemmen = [
        m for m in existing
        if m.get('status') in ('aangenomen', 'verworpen')
        and not m.get('stemmen')
        and not m.get('stemmen_na')
        and m.get('tk_url')
    ]
    if needs_stemmen:
        print(f'  Partijstemmen ophalen: {len(needs_stemmen)} moties')
        fetched_stemmen = 0
        for m in needs_stemmen[:80]:
            stemmen = {}
            zaak_id = extract_zaak_id(m.get('tk_url', ''))
            if zaak_id:
                stemmen = fetch_stemmen_odata(zaak_id)
                time.sleep(0.3)
            if not stemmen and m.get('tk_url'):
                stemmen = fetch_stemmen(m['tk_url'])
                time.sleep(0.4)
            if stemmen:
                m['stemmen'] = norm_stemmen(stemmen)   # ← normalize on store
                fetched_stemmen += 1
            else:
                m['stemmen_na'] = True
        print(f'    {fetched_stemmen} moties partijstemmen opgehaald')

    # ── Step 2: Scrape new moties ──
    new_items = []
    seen_ids = {x['id'] for x in existing if 'id' in x}
    seen_zaak_ids = {extract_zaak_id(x.get('tk_url','')) for x in existing if extract_zaak_id(x.get('tk_url',''))}
    consecutive_empty = 0

    for page in range(max_pages):
        raw = fetch_page(page)
        if not raw:
            print(f'  Pagina {page+1}: fetch mislukt (leeg)')
            break

        results = parse_moties_from_html(raw)
        if not results:
            import re as _re
            classes = _re.findall(r'class="([^"]{10,60})"', raw)
            motie_classes = [c for c in classes if any(x in c.lower() for x in ['result','item','search','motie','card','list'])]
            print(f'  Pagina {page+1}: geen moties gevonden (HTML len={len(raw)})')
            print(f'  Relevante classes: {list(set(motie_classes))[:10]}')
            break
        print(f'  Pagina {page+1}: {len(results)} moties')
        if page == 0:
            for r in results:
                print(f'    - {extract_zaak_id(r["link"])} | {r["titel"][:60]}')

        found_new_on_page = False
        for r in results:
            link    = r['link']
            zaak_id = extract_zaak_id(link)
            item_id = make_id(link)

            def _is_broken(t):
                t = (t or '').strip()
                tl = t.lower()
                if not t or len(tl) < 10: return True
                if tl in ('moties','motie'): return True
                if '\n' in t: return True
                if tl.startswith('motie\n') or tl.startswith('motie :\n'): return True
                if 'indiener' not in tl and 'lid' not in tl and 'leden' not in tl and len(tl) < 30: return True
                return False

            if item_id in seen_ids:
                ex = next((x for x in existing if x.get('id') == item_id), None)
                if ex and _is_broken(ex.get('titel','')):
                    real = fetch_motie_title(link)
                    time.sleep(0.3)
                    if real:
                        ex['titel']     = real
                        ex['indiener']  = detect_indiener(real)
                        ex['thema']     = detect_thema(real)
                        ex['alignment'] = detect_alignment(real, ex['indiener'])
                        print(f'    FIX titel: {zaak_id} → {real[:60]}')
                    else:
                        print(f'    FIX failed: {zaak_id}')
                elif page == 0:
                    print(f'    SKIP item_id: {zaak_id}')
                continue
            if zaak_id and zaak_id in seen_zaak_ids:
                ex = next((x for x in existing if extract_zaak_id(x.get('tk_url','')) == zaak_id), None)
                if ex and _is_broken(ex.get('titel','')):
                    real = fetch_motie_title(link)
                    time.sleep(0.3)
                    if real:
                        ex['titel']     = real
                        ex['indiener']  = detect_indiener(real)
                        ex['thema']     = detect_thema(real)
                        ex['alignment'] = detect_alignment(real, ex['indiener'])
                        print(f'    FIX titel (zaak): {zaak_id} → {real[:60]}')
                    else:
                        print(f'    FIX failed: {zaak_id}')
                elif page == 0:
                    print(f'    SKIP zaak_id: {zaak_id}')
                continue
            if link in existing_links:
                if page == 0: print(f'    SKIP link: {zaak_id} → {link}')
                continue
            if zaak_id and zaak_id in existing_by_zaak:
                matched_m = existing_by_zaak[zaak_id]
                if _is_broken(matched_m.get('titel','')):
                    matched_m['titel']     = r['titel']
                    matched_m['indiener']  = detect_indiener(r['titel'])
                    matched_m['thema']     = detect_thema(r['titel'])
                    matched_m['alignment'] = detect_alignment(r['titel'], matched_m['indiener'])
                    print(f'    FIX titel (by_zaak): {zaak_id} → {r["titel"][:60]}')
                elif page == 0:
                    print(f'    SKIP zaak_id match: {zaak_id} → {matched_m.get("tk_url","?")}')
                continue

            real_date = None
            status    = 'in_behandeling'

            if zaak_id and zaak_id in stemmingen:
                real_date = stemmingen[zaak_id].get('datum')
                if stemmingen[zaak_id].get('besluit'):
                    status = stemmingen[zaak_id]['besluit']

            if not real_date:
                real_date = fetch_motie_datum(link)
                time.sleep(0.4)

            if not real_date:
                real_date = r['list_date'] or TODAY

            if real_date != TODAY and real_date < START_DATE:
                print(f'    SKIP (datum {real_date} < {START_DATE}): {r["titel"][:60]}')
                continue

            found_new_on_page = True
            seen_ids.add(item_id)
            if zaak_id: seen_zaak_ids.add(zaak_id)
            existing_links.add(link)

            thema    = detect_thema(r['titel'])
            indiener = detect_indiener(r['titel'])

            new_items.append({
                'id':         item_id,
                'titel':      r['titel'],
                'indiener':   indiener,
                'datum':      real_date,
                'thema':      thema,
                'status':     status,
                'alignment':  detect_alignment(r['titel'], indiener),
                'vergadering':'',
                'tk_url':     link,
                'toelichting':'',
                'stemmen':    {},
                'archief':    False,
            })

        if not is_backfill and not found_new_on_page:
            consecutive_empty += 1
            if consecutive_empty >= 5:
                print(f'  Geen nieuwe moties meer — klaar')
                break
        else:
            consecutive_empty = 0

        time.sleep(1.5)

    # ── Step 2b: Fix broken titles ──
    broken_titles = [m for m in existing if m.get('titel','').strip().lower() in ('moties','motie','')]
    if broken_titles:
        print(f'\n  Kapotte titels herstellen: {len(broken_titles)} moties')
        for m in broken_titles[:50]:
            if not m.get('tk_url'): continue
            html_raw = fetch_html(m['tk_url'])
            if html_raw:
                t = re.search(r'<h1[^>]*>(.*?)</h1>', html_raw, re.DOTALL)
                if t:
                    title = re.sub(r'<[^>]+>','',t.group(1)).strip()
                    if title and len(title) > 10:
                        m['titel'] = title
                        m['indiener'] = detect_indiener(title)
                        m['thema'] = detect_thema(title)
                        m['alignment'] = detect_alignment(title, m['indiener'])
            time.sleep(0.4)

    # ── Step 3: Fix dates still showing TODAY ──
    needs_date = [m for m in existing if m.get('datum','') >= TODAY and m.get('tk_url','')]
    if needs_date:
        print(f'\nDatum fixup: {min(150, len(needs_date))} van {len(needs_date)} moties')
        for m in needs_date[:150]:
            zaak_id = extract_zaak_id(m.get('tk_url',''))
            if zaak_id and stemmingen.get(zaak_id, {}).get('datum'):
                m['datum'] = stemmingen[zaak_id]['datum']
                continue
            nd = fetch_motie_datum(m['tk_url'])
            if nd:
                m['datum'] = nd if nd >= START_DATE else START_DATE
            time.sleep(0.3)

    print(f'\nNieuwe moties: {len(new_items)}')
    for m in new_items[:5]:
        print(f'  + {m["datum"]} | {m["status"]:15} | {m["titel"][:60]}')

    # ── Step 4: Archive logic ──
    all_moties = existing + new_items
    for m in all_moties:
        status = m.get('status', '')
        if status in ('aangenomen', 'verworpen'):
            m['archief'] = False
            continue
        try:
            age = (date.today() - date.fromisoformat(m.get('datum', TODAY))).days
        except Exception:
            age = 0
        if status == 'in_behandeling':
            m['archief'] = age > 5
        elif status == 'aangehouden':
            m['archief'] = age > 30

    active = sum(1 for m in all_moties if not m.get('archief'))
    voted  = sum(1 for m in all_moties if m.get('status') in ('aangenomen','verworpen'))
    print(f'Totaal: {len(all_moties)} moties ({active} actief, {voted} gestemd)')

    # Fetch and save agenda
    print('\nAgenda ophalen...')
    agenda = fetch_agenda()
    with open('agenda.json', 'w', encoding='utf-8') as f:
        json.dump(agenda, f, ensure_ascii=False, indent=2)

    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_moties, f, ensure_ascii=False, indent=2)
    print('Opgeslagen.')

if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""
fix_moties_json.py — patcht moties.json direct via OData, geen scraping.

Wat het doet:
  1. Leest moties.json
  2. Voor elke motie met status "in_behandeling": vraag OData om besluit + stemmen
  3. Normaliseert partijnamen in bestaande stemmen (GL-PvdA, FvD, CU, etc.)
  4. Herdetecteert thema + indiener waar nodig
  5. Slaat gecorrigeerde moties.json op (backup eerst)

Gebruik: python3 fix_moties_json.py
"""
import json, re, time, urllib.request, urllib.parse, shutil
from datetime import date

DATA_FILE = 'moties.json'
BACKUP    = 'moties.backup.json'

# ── Party normalization ────────────────────────────────────────────────────────
PARTY_NORM = {
    'GroenLinks-PvdA': 'GL-PvdA',
    'ChristenUnie': 'CU',
    'Groep Markuszower': 'Gr.Markuszower',
    'Lid Keijzer': 'Groep-Keijzer',
    'FVD': 'FvD',
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
}

def norm_party(name):
    return PARTY_NORM.get(name, name)

def norm_stemmen(stemmen):
    if not stemmen:
        return stemmen
    return {norm_party(k): v for k, v in stemmen.items()}

# ── Member → party ─────────────────────────────────────────────────────────────
LEDEN_PARTIJ = {
    # PVV (19 zetels)
    "Wilders": "PVV",
    "Bosma": "PVV",
    "Boon": "PVV",
    "Van Dijck": "PVV",
    "Tony van Dijck": "PVV",
    "Emiel van Dijk": "PVV",
    "Faber": "PVV",
    "Graus": "PVV",
    "Jansen": "PVV",
    "Chris Jansen": "PVV",
    "Kops": "PVV",
    "Maeijer": "PVV",
    "Van Meetelen": "PVV",
    "Mooiman": "PVV",
    "Mulder": "PVV",
    "Prickaertz": "PVV",
    "Raijer": "PVV",
    "De Roon": "PVV",
    "Stöteler": "PVV",
    "Stoteler": "PVV",
    "Vlottes": "PVV",
    "Vondeling": "PVV",

    # VVD (24 zetels)
    "Becker": "VVD",
    "Bevers": "VVD",
    "Bikkers": "VVD",
    "Brekelmans": "VVD",
    "Van Campen": "VVD",
    "Thom van Campen": "VVD",
    "De Beer": "VVD",
    "Martin de Beer": "VVD",
    "Den Hollander": "VVD",
    "Renate den Hollander": "VVD",
    "Ellian": "VVD",
    "Van Eijk": "VVD",
    "Wendy van Eijk": "VVD",
    "Peter de Groot": "VVD",
    "Kisteman": "VVD",
    "De Kort": "VVD",
    "Daan de Kort": "VVD",
    "Maes": "VVD",
    "Van der Maas": "VVD",
    "Martens-America": "VVD",
    "Meulenkamp": "VVD",
    "Michon-Derkzen": "VVD",
    "Müller": "VVD",
    "Nobel": "VVD",
    "Rajkowski": "VVD",
    "Schutz": "VVD",
    "Wendel": "VVD",

    # GroenLinks-PvdA (25 zetels)
    "Abdi": "GL-PvdA",
    "Fatihya Abdi": "GL-PvdA",
    "Bromet": "GL-PvdA",
    "Bushoff": "GL-PvdA",
    "De Hoop": "GL-PvdA",
    "Habtamu de Hoop": "GL-PvdA",
    "Kathmann": "GL-PvdA",
    "Klaver": "GL-PvdA",
    "Kröger": "GL-PvdA",
    "Kroger": "GL-PvdA",
    "Lahlah": "GL-PvdA",
    "Mohandis": "GL-PvdA",
    "Moorman": "GL-PvdA",
    "Mutluer": "GL-PvdA",
    "Van Oosterhout": "GL-PvdA",
    "Sjoukje van Oosterhout": "GL-PvdA",
    "Patijn": "GL-PvdA",
    "Piri": "GL-PvdA",
    "Stultiens": "GL-PvdA",
    "Thijssen": "GL-PvdA",
    "Tseggai": "GL-PvdA",
    "Van der Lee": "GL-PvdA",
    "Tom van der Lee": "GL-PvdA",
    "Vliegenthart": "GL-PvdA",
    "Westerveld": "GL-PvdA",

    # D66 (26 zetels)
    "Bamenga": "D66",
    "Belhirch": "D66",
    "Biekman": "D66",
    "Heera Dijk": "D66",
    "El Boujdaini": "D66",
    "Sarah El Boujdaini": "D66",
    "Huidekooper": "D66",
    "Huizenga": "D66",
    "Jagtenberg": "D66",
    "Klos": "D66",
    "Felix Klos": "D66",
    "Köse": "D66",
    "Ulaş Köse": "D66",
    "Mathlouti": "D66",
    "Neijenhuis": "D66",
    "Oualhadj": "D66",
    "Oosterhuis": "D66",
    "Paternotte": "D66",
    "Paulusma": "D66",
    "Podt": "D66",
    "Rooderkerk": "D66",
    "Schoonis": "D66",
    "Sneller": "D66",
    "Synhaeve": "D66",
    "Van Asten": "D66",
    "Van der Werf": "D66",
    "Hanneke van der Werf": "D66",
    "Van Leijen": "D66",
    "Vellinga-Beemsterboer": "D66",
    "Vervuurt": "D66",
    "Wuite": "D66",

    # CDA (16 zetels)
    "Armut": "CDA",
    "Van Ark": "CDA",
    "Elles van Ark": "CDA",
    "Boelsma-Hoekstra": "CDA",
    "Bontenbal": "CDA",
    "Boswijk": "CDA",
    "Bühler": "CDA",
    "Hamstra": "CDA",
    "Sarath Hamstra": "CDA",
    "Inge van Dijk": "CDA",
    "Jumelet": "CDA",
    "Koorevaar": "CDA",
    "Jan Arie Koorevaar": "CDA",
    "Krul": "CDA",
    "Lanschot": "CDA",
    "Maes van Lanschot": "CDA",
    "Lohman": "CDA",
    "Poortman": "CDA",
    "Steen": "CDA",
    "Straatman": "CDA",
    "Tijmstra": "CDA",
    "Tijs van den Brink": "CDA",
    "Van den Brink": "CDA",
    "Vedder": "CDA",

    # JA21 (17 zetels)
    "Boomsma": "JA21",
    "Ceulemans": "JA21",
    "Clemminck": "JA21",
    "Coenradie": "JA21",
    "Eerdmans": "JA21",
    "Goudzwaard": "JA21",
    "Hoogeveen": "JA21",
    "Michiel Hoogeveen": "JA21",
    "Nanninga": "JA21",
    "Van den Berg": "JA21",
    "Daniël van den Berg": "JA21",

    # FvD (6 zetels)
    "Baudet": "FvD",
    "Dekker": "FvD",
    "Ralf Dekker": "FvD",
    "Van Duijvenvoorde": "FvD",
    "Van Houwelingen": "FvD",
    "Jansen": "FvD",         # opgelet: gebruik "Frederik Jansen" om van Chris Jansen (PVV) te onderscheiden
    "Frederik Jansen": "FvD",
    "Van Meijeren": "FvD",
    "De Vos": "FvD",
    "Russcher": "FvD",

    # BBB (7 zetels)
    "Van der Plas": "BBB",
    "Caroline van der Plas": "BBB",
    "Vermeer": "BBB",
    "Wiersma": "BBB",
    "Femke Wiersma": "BBB",

    # Groep Markuszower (7 zetels)
    "Markuszower": "Gr.Markuszower",
    "Claassen": "Gr.Markuszower",
    "Heutink": "Gr.Markuszower",
    "Lammers": "Gr.Markuszower",
    "Annelotte Lammers": "Gr.Markuszower",
    "Moinat": "Gr.Markuszower",
    "Nicole Moinat": "Gr.Markuszower",
    "Schilder": "Gr.Markuszower",
    "Ten Hove": "Gr.Markuszower",
    "ten Hove": "Gr.Markuszower",
    "Tamara ten Hove": "Gr.Markuszower",

    # SP (5 zetels)
    "Jimmy Dijk": "SP",
    "Dobbe": "SP",
    "Beckerman": "SP",
    "Temmink": "SP",
    "Van Nispen": "SP",
    "Leijten": "SP",

    # PvdD (4 zetels)
    "Kostić": "PvdD",
    "Kostic": "PvdD",
    "Ines Kostić": "PvdD",
    "Ouwehand": "PvdD",
    "Teunissen": "PvdD",

    # ChristenUnie (3 zetels)
    "Bikker": "CU",
    "Mirjam Bikker": "CU",
    "Ceder": "CU",
    "Grinwis": "CU",

    # SGP (3 zetels)
    "Diederik van Dijk": "SGP",
    "Stoffer": "SGP",
    "Flach": "SGP",

    # Volt (2 zetels)
    "Dassen": "Volt",
    "Koekkoek": "Volt",

    # DENK (3 zetels)
    "Stephan van Baarle": "DENK",
    "Van Baarle": "DENK",
    "El Abassi": "DENK",
    "Ergin": "DENK",
    "Kırcalı": "DENK",
    "Kircali": "DENK",

    # 50PLUS (2 zetels)
    "Struijs": "50PLUS", "Struijs": "50PLUS",
    "Jan Struijs": "50PLUS",
    "Van Brenk": "50PLUS",
    "Corrie van Brenk": "50PLUS",

    # Lid Keijzer (1 zetel)
    "Keijzer": "Groep-Keijzer",
    "Mona Keijzer": "Groep-Keijzer",
}

COALITIE  = {"VVD","D66","CDA"}
OPPOSITIE = {"PVV","GL-PvdA","NSC","BBB","SP","PvdD","CU","SGP","Volt","DENK","FvD","JA21","50PLUS","Gr.Markuszower","Groep-Keijzer"}

THEMA_KEYWORDS = {
    "Defensie":["defensie","militair","navo","leger","oekra","wapen","krijgsmacht",
                "luchtmacht","marine","vredesmissie","uitzend","evertsen","fregat","missie"],
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

STRIJDIG_KEYWORDS = ["klimaatdoel","kinderopvang gratis","eigen risico afschaffen","asielzoekers meer","vluchtelingen opvang","discriminatie aanpakken"]
CONFORM_KEYWORDS  = ["asielinstroom beperken","grenzen sluiten","defensie versterken","kernenergie","belastingverlaging","navo","terugkeer","grenscontrole"]

def detect_thema(text):
    t = text.lower()
    best, best_score = "Overig", 0
    for thema, kws in THEMA_KEYWORDS.items():
        score = sum(1 for k in kws if k in t)
        if score > best_score:
            best, best_score = thema, score
    return best

def detect_indiener(titel):
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

def extract_zaak_id(url):
    m = re.search(r'[?&]id=(\d{4}Z\w+)', url or '')
    return m.group(1) if m else None

# ── OData helpers ──────────────────────────────────────────────────────────────
BASE  = 'https://gegevensmagazijn.tweedekamer.nl/OData/v4/2.0/'
HDR   = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json'}

VOTE_NORM = {'voor': 'voor', 'tegen': 'tegen', 'niet deelgenomen': 'afwezig', 'onthouden': 'onthouden'}

def odata_get(url):
    req = urllib.request.Request(url, headers=HDR)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())

def fetch_besluit_en_stemmen(zaak_nummer):
    """
    Één OData call: Zaak → Besluit → Stemming.
    Geeft terug: (besluit_str, stemmen_dict)
    besluit_str: 'aangenomen' | 'verworpen' | 'aangehouden' | None
    stemmen_dict: {partij: 'voor'/'tegen'/'afwezig'/'onthouden'}
    """
    expand = 'Besluit($expand=Stemming($select=Soort,ActorNaam,ActorFractie);$select=Id,BesluitTekst)'
    url = (BASE + 'Zaak?$filter=' + urllib.parse.quote(f"Nummer eq '{zaak_nummer}'")
           + '&$expand=' + expand
           + '&$select=Id,Nummer&$top=1')
    try:
        data  = odata_get(url)
        items = data.get('value', [])
        if not items:
            return None, {}

        besluiten = items[0].get('Besluit', [])
        if not besluiten:
            return None, {}

        besluit_str = None
        stemmen     = {}

        for b in besluiten:
            tekst = (b.get('BesluitTekst') or '').lower()
            if 'aangenomen' in tekst:
                besluit_str = 'aangenomen'
            elif 'verworpen' in tekst:
                besluit_str = 'verworpen'
            elif 'aangehouden' in tekst:
                besluit_str = 'aangehouden'

            for item in b.get('Stemming', []):
                naam  = (item.get('ActorFractie') or item.get('ActorNaam') or '').strip()
                naam  = norm_party(naam)
                soort = (item.get('Soort') or '').lower()
                vote  = VOTE_NORM.get(soort, soort)
                if naam and vote and naam not in stemmen:
                    stemmen[naam] = vote

            if besluit_str and stemmen:
                break   # found what we need

        return besluit_str, stemmen

    except Exception as e:
        print(f'    OData fout ({zaak_nummer}): {e}')
        return None, {}


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print(f'fix_moties_json.py — {date.today().isoformat()}')

    # Load
    with open(DATA_FILE, encoding='utf-8') as f:
        moties = json.load(f)
    print(f'Geladen: {len(moties)} moties')

    # Backup
    shutil.copy(DATA_FILE, BACKUP)
    print(f'Backup: {BACKUP}')

    changed_total = 0

    # ── Pass 1: normalize party names in all existing stemmen ─────────────────
    norm_count = 0
    for m in moties:
        if m.get('stemmen'):
            new_st = norm_stemmen(m['stemmen'])
            if new_st != m['stemmen']:
                m['stemmen'] = new_st
                norm_count += 1
    print(f'\nPass 1 — partijnamen: {norm_count} moties genormaliseerd')
    changed_total += norm_count

    # ── Pass 2: re-detect thema + indiener for all moties ────────────────────
    redet_count = 0
    for m in moties:
        if not m.get('titel'):
            continue
        new_thema    = detect_thema(m['titel'])
        new_indiener = detect_indiener(m['titel'])
        changed = False
        if new_thema != m.get('thema'):
            print(f'  thema: [{m.get("thema")}] → [{new_thema}]  {m["titel"][:60]}')
            m['thema'] = new_thema
            changed = True
        if m.get('indiener') in ('Onbekend', '', None) and new_indiener != 'Onbekend':
            print(f'  indiener: [{m.get("indiener")}] → [{new_indiener}]  {m["titel"][:60]}')
            m['indiener'] = new_indiener
            changed = True
        if changed:
            m['alignment'] = detect_alignment(m['titel'], m['indiener'])
            redet_count += 1
    print(f'Pass 2 — thema/indiener: {redet_count} moties bijgewerkt')
    changed_total += redet_count

    # ── Pass 3: fix in_behandeling moties via OData ───────────────────────────
    needs_fix = [m for m in moties if m.get('status') == 'in_behandeling' and m.get('tk_url')]
    print(f'\nPass 3 — in_behandeling: {len(needs_fix)} moties te controleren via OData')

    fixed_status = 0
    fixed_stemmen = 0
    still_open = 0

    for i, m in enumerate(needs_fix):
        zaak_id = extract_zaak_id(m['tk_url'])
        if not zaak_id:
            print(f'  [{i+1}/{len(needs_fix)}] SKIP (geen zaak ID): {m["titel"][:50]}')
            still_open += 1
            continue

        print(f'  [{i+1}/{len(needs_fix)}] {zaak_id} — {m["titel"][:55]}')
        besluit, stemmen = fetch_besluit_en_stemmen(zaak_id)
        time.sleep(0.5)

        if besluit:
            m['status']  = besluit
            m['archief'] = False
            m.pop('stemmen_na', None)
            fixed_status += 1
            print(f'    → {besluit}', end='')
            if stemmen:
                m['stemmen'] = stemmen
                fixed_stemmen += 1
                print(f', {len(stemmen)} partijstemmen', end='')
            print()
            changed_total += 1
        else:
            still_open += 1
            print(f'    → nog geen besluit (echt in behandeling)')

    print(f'\nPass 3 resultaat:')
    print(f'  {fixed_status} status bijgewerkt (waarvan {fixed_stemmen} met stemmen)')
    print(f'  {still_open} echt nog in behandeling')

    # ── Pass 4: fetch missing stemmen for already-voted moties ───────────────
    needs_stemmen = [
        m for m in moties
        if m.get('status') in ('aangenomen', 'verworpen')
        and not m.get('stemmen')
        and not m.get('stemmen_na')
        and m.get('tk_url')
    ]
    print(f'\nPass 4 — ontbrekende stemmen: {len(needs_stemmen)} moties')

    fetched_stemmen = 0
    for i, m in enumerate(needs_stemmen):
        zaak_id = extract_zaak_id(m['tk_url'])
        if not zaak_id:
            continue
        print(f'  [{i+1}/{len(needs_stemmen)}] {zaak_id}')
        _, stemmen = fetch_besluit_en_stemmen(zaak_id)
        time.sleep(0.4)
        if stemmen:
            m['stemmen'] = stemmen
            fetched_stemmen += 1
            changed_total += 1
            print(f'    → {len(stemmen)} partijstemmen')
        else:
            m['stemmen_na'] = True
            print(f'    → geen stemmen (handopsteken?)')

    print(f'Pass 4: {fetched_stemmen} moties stemmen opgehaald')

    # ── Save ──────────────────────────────────────────────────────────────────
    print(f'\nTotaal gewijzigd: {changed_total} moties')
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(moties, f, ensure_ascii=False, indent=2)
    print(f'Opgeslagen → {DATA_FILE}')
    print(f'Backup bewaard → {BACKUP}')

if __name__ == '__main__':
    main()

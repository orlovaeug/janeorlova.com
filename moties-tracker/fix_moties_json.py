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
    "Wilders":"PVV","Agema":"PVV","Bosma":"PVV","Madlener":"PVV",
    "Emiel van Dijk":"PVV","Léon de Jong":"PVV","Leon de Jong":"PVV",
    "El Boujdaini":"PVV","Heutink":"PVV","Helder":"PVV","Faber":"PVV",
    "Fritsma":"PVV","Graus":"PVV","Beertema":"PVV","De Graaf":"PVV",
    "Duvekot":"PVV","Kerseboom":"PVV",
    "Hermans":"VVD","Yesilgöz":"VVD","Michon-Derkzen":"VVD","Rajkowski":"VVD",
    "Becker":"VVD","Bikkers":"VVD","Ellian":"VVD","Brekelmans":"VVD",
    "Hagen":"VVD","Six Dijkstra":"VVD","Klink":"VVD","Peter de Groot":"VVD",
    "Klos":"VVD","Erkens":"VVD","Minhas":"VVD","Palmen":"VVD",
    "Soepboer":"VVD","Wesselink":"VVD","Gündogan":"VVD","Van der Werf":"VVD",
    "Omtzigt":"NSC","Van Hijum":"NSC","Struijs":"NSC","Boelsma-Hoekstra":"NSC",
    "Lammers":"NSC","Crijns":"NSC","Podt":"NSC","Hartman":"NSC",
    "Van der Plas":"BBB","Hamstra":"BBB","Aardema":"BBB","Tuinman":"BBB",
    "Wendel":"BBB","Jumelet":"BBB","Van Oosterhout":"BBB","Vermeer":"BBB","Kostić":"BBB",
    "Klaver":"GL-PvdA","Timmermans":"GL-PvdA","Maatoug":"GL-PvdA","Nijboer":"GL-PvdA",
    "Bushoff":"GL-PvdA","Kathmann":"GL-PvdA","Mohandis":"GL-PvdA","Köse":"GL-PvdA",
    "Moorman":"GL-PvdA","Bromet":"GL-PvdA","Chakor":"GL-PvdA","Gijs van Dijk":"GL-PvdA",
    "Hammelburg":"GL-PvdA","Mutluer":"GL-PvdA","Piri":"GL-PvdA","Thijssen":"GL-PvdA",
    "Westerveld":"GL-PvdA","Kuiken":"GL-PvdA","Fatihya Abdi":"GL-PvdA",
    "Paternotte":"D66","Vervuurt":"D66","Van Asten":"D66","Wuite":"D66",
    "Raemakers":"D66","White":"D66","Van der Laan":"D66",
    "Bontenbal":"CDA","Boswijk":"CDA","Vedder":"CDA","Krul":"CDA",
    "Van den Berg":"CDA","Van Ark":"CDA","Armut":"CDA",
    "Van den Brink":"CDA","Inge van Dijk":"CDA",
    "Jimmy Dijk":"SP","Dobbe":"SP","Beckerman":"SP","Temmink":"SP",
    "Van Nispen":"SP","Leijten":"SP",
    "Simons":"PvdD","Teunissen":"PvdD","Vestering":"PvdD","Van Raan":"PvdD",
    "Bikker":"CU","Mirjam Bikker":"CU","Ceder":"CU","Grinwis":"CU",
    "Diederik van Dijk":"SGP","Stoffer":"SGP","Flach":"SGP",
    "Dassen":"Volt","Koekkoek":"Volt","Nanninga":"Volt",
    "Stephan van Baarle":"DENK","Van Baarle":"DENK","El Abassi":"DENK",
    "Ergin":"DENK","Kırcalı":"DENK","Kircali":"DENK",
    "Eerdmans":"JA21",
    "Baudet":"FvD",
    "Markuszower":"Gr.Markuszower",
    "Keijzer":"Groep-Keijzer",
    "Baay-Timmerman":"50PLUS",
    # Extra members seen in recent moties
    "den Hollander":"VVD","Vellinga-Beemsterboer":"D66","Ceulemans":"JA21","Mulder":"PVV","Moinat":"PVV","de Beer":"VVD","Ouwehand":"PvdD","Patijn":"GL-PvdA","Lahlah":"GL-PvdA","Stoteler":"PVV", "Van der Lee":"GL-PvdA","Van Brenk":"50PLUS","Hoogeven":"JA21","Neijenhuis":"D66","Clemminck":"JA21", "Boomsma":"JA21","de Hoop":"GL-PvdA","Nobel":"VVD","Mooiman":"PVV", "Kostic":"PvdD", "Jansen":"PVV", "Koorevaar":"CDA", "Goudzwaard":"JA21",
    "Tijs van den Brink":"CDA","Van den Brink":"CDA",
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

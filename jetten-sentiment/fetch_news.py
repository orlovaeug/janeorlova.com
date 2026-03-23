#!/usr/bin/env python3
"""
fetch_news.py — dagelijkse automatische nieuwsupdate
Draait als GitHub Action (gratis, geen API-sleutel nodig)
"""

import json, re, hashlib, time
from datetime import datetime, date
import requests
import feedparser

START_DATE = '2026-02-23'
DATA_FILE  = 'data.json'
TODAY      = date.today().isoformat()
SUBJECT    = 'jetten'

# ── Directe RSS-feeds van Nederlandse media ──────────────────────────────────
NL_FEEDS = [
    ('NOS',              '📺', 'nl', 'https://feeds.nos.nl/nosnieuwspolitiek'),
    ('NOS',              '📺', 'nl', 'https://feeds.nos.nl/nosnieuws'),
    ('NRC',              '📰', 'nl', 'https://www.nrc.nl/rss/'),
    ('de Volkskrant',    '📰', 'nl', 'https://www.volkskrant.nl/nieuws-achtergrond/rss.xml'),
    ('AD',               '📰', 'nl', 'https://www.ad.nl/nieuws/rss.xml'),
    ('Trouw',            '📰', 'nl', 'https://www.trouw.nl/nieuws/rss.xml'),
    ('NU.nl',            '🌐', 'nl', 'https://www.nu.nl/rss/algemeen'),
    ('RTL Nieuws',       '📺', 'nl', 'https://www.rtlnieuws.nl/rss.xml'),
    ('FD',               '📰', 'nl', 'https://fd.nl/rss'),
    ('De Telegraaf',     '📰', 'nl', 'https://www.telegraaf.nl/rss'),
    ('EenVandaag',       '📊', 'nl', 'https://eenvandaag.avrotros.nl/rss'),
    ('BNR',              '📻', 'nl', 'https://www.bnr.nl/rss'),
    ('Follow the Money', '💶', 'blog', 'https://www.ftm.nl/rss'),
    ('De Correspondent', '✍️', 'blog', 'https://decorrespondent.nl/feeds/rss'),
    ('Joop/BNNVARA',     '✍️', 'blog', 'https://www.bnnvara.nl/joop/artikelen/rss'),
    ('Elsevier',         '📰', 'nl',   'https://www.elsevierweekblad.nl/rss/'),
]

# ── Google News searches — extended to 11+ languages ──────────────────────
GOOGLE_QUERIES = [
    # Dutch
    ('Rob Jetten premier',                    'nl',   'nl', 'NL'),
    ('Jetten kabinet',                        'nl',   'nl', 'NL'),
    ('kabinet-Jetten',                        'nl',   'nl', 'NL'),
    ('Jetten AOW vakbonden',                  'nl',   'nl', 'NL'),
    ('Jetten EU klimaat',                     'nl',   'nl', 'NL'),
    # English (US)
    ('Rob Jetten Netherlands prime minister', 'en',   'en', 'US'),
    ('Jetten Dutch PM coalition',             'en',   'en', 'US'),
    ('Netherlands cabinet Jetten 2026',       'en',   'en', 'US'),
    # English (UK)
    ('Rob Jetten Netherlands PM',             'en-GB','en', 'GB'),
    ('Jetten Dutch government',               'en-GB','en', 'GB'),
    # German
    ('Jetten Ministerpräsident Niederlande',  'de',   'de', 'DE'),
    ('Niederlande Premier Jetten',            'de',   'de', 'DE'),
    # French
    ('Jetten premier ministre Pays-Bas',      'fr',   'fr', 'FR'),
    ('Pays-Bas gouvernement Jetten',          'fr',   'fr', 'FR'),
    # Spanish
    ('Jetten primer ministro Países Bajos',   'es',   'es', 'ES'),
    # Italian
    ('Jetten primo ministro Olanda',          'it',   'it', 'IT'),
    # Russian
    ('Йеттен премьер Нидерланды',             'ru',   'ru', 'RU'),
    ('Нидерланды правительство Jetten',       'ru',   'ru', 'RU'),
    # Ukrainian
    ("Нідерланди прем'єр Єттен",              'uk',   'uk', 'UA'),
    # Polish
    ('Jetten premier Holandia',               'pl',   'pl', 'PL'),
    # Norwegian
    ('Jetten statsminister Nederland',        'no',   'no', 'NO'),
    # Swedish
    ('Jetten premiärminister Nederländerna',  'sv',   'sv', 'SE'),
]

# ── Left/Right NL media classification ───────────────────────────────────────
LEFT_MEDIA = [
    'de volkskrant', 'volkskrant', 'trouw', 'de correspondent', 'correspondent',
    'joop', 'bnnvara', 'fnv', 'sp ', 'groenlinks', 'gl-pvda', 'pvda',
    'follow the money', 'ftm', 'vers beton', 'de groene amsterdammer',
    'groene', 'human', 'vpro',
]
RIGHT_MEDIA = [
    'de telegraaf', 'telegraaf', 'geenstijl', 'elsevier', 'elsevier weekblad',
    'bnr', 'pvv', 'vvd', 'nrc', 'fd', 'financieel dagblad', 'wynia',
    "wynia's week", 'de dagelijkse standaard', 'dagelijkse standaard',
    'rtlz', 'z nieuws',
]

def classify_lr(src: str) -> str | None:
    s = src.lower()
    for m in LEFT_MEDIA:
        if m in s:
            return 'left'
    for m in RIGHT_MEDIA:
        if m in s:
            return 'right'
    return None

# ── International source → flag ───────────────────────────────────────────────
INTL_FLAGS = [
    (['guardian', 'independent', 'times', 'bbc', 'telegraph', 'sky news'], 'GB'),
    (['nytimes', 'new york times', 'washington post', 'wapo', 'bloomberg',
      'reuters', 'ap news', 'associated press', 'cnn', 'wsj', 'wall street journal',
      'politico', 'npr', 'vice'], 'US'),
    (['spiegel', 'frankfurter', 'faz', 'zeit', 'welt', 'süddeutsche', 'bild',
      'focus', 'stern', 'handelsblatt', 'tagesschau', 'zdf', 'ard'], 'DE'),
    (['monde', 'figaro', 'liberation', 'libération', 'lexpress', "l'express",
      'le point', 'france24', 'rfi', 'bfmtv'], 'FR'),
    (['el pais', 'el país', 'elmundo', 'el mundo', 'abc.es', 'lavanguardia',
      'la vanguardia', 'rtve', 'el confidencial', 'eldiario'], 'ES'),
    (['corriere', 'la repubblica', 'repubblica', 'stampa', 'la stampa',
      'messaggero', 'fatto quotidiano', 'sole 24', 'rai'], 'IT'),
    (['kommersant', 'коммерсант', 'vedomosti', 'ведомости', 'rbc', 'рбк',
      'novaya gazeta', 'meduza', 'медуза', 'fontanka', 'новая газета'], 'RU'),
    (['ukrinform', 'ukrainska pravda', 'pravda.com.ua', 'kyiv post',
      'kyiv independent', 'hromadske', 'lb.ua', 'unian'], 'UA'),
    (['vrt', 'rtbf', 'de morgen', 'het nieuwsblad', 'la libre', 'le soir',
      'nieuwsblad', 'standaard', 'humo'], 'BE'),
    (['gazeta wyborcza', 'wyborcza', 'rzeczpospolita', 'onet', 'tvn24',
      'polsat', 'wprost', 'polityka', 'newsweek.pl'], 'PL'),
    (['aftenposten', 'vg.no', 'dagbladet', 'nrk', 'tv2.no'], 'NO'),
    (['svt', 'dn.se', 'aftonbladet', 'expressen', 'svenska dagbladet'], 'SE'),
    (['politiken', 'berlingske', 'dr.dk', 'tv2.dk', 'jyllandsposten'], 'DK'),
    (['yle', 'helsingin sanomat', 'ilta-sanomat'], 'FI'),
    (['publico', 'expresso', 'observador', 'jornal de noticias', 'dn.pt',
      'cmjornal', 'rtp'], 'PT'),
    (['hurriyet', 'sabah', 'milliyet', 'cumhuriyet', 'anadolu', 'trt'], 'TR'),
    (['politico.eu', 'euractiv', 'europarl', 'european'], 'EU'),
]

# Flag emojis mapped to country code
FLAG_EMOJI = {
    'GB': '🇬🇧', 'US': '🇺🇸', 'DE': '🇩🇪', 'FR': '🇫🇷',
    'ES': '🇪🇸', 'IT': '🇮🇹', 'RU': '🇷🇺', 'UA': '🇺🇦',
    'BE': '🇧🇪', 'PL': '🇵🇱', 'NO': '🇳🇴', 'SE': '🇸🇪',
    'DK': '🇩🇰', 'FI': '🇫🇮', 'PT': '🇵🇹', 'TR': '🇹🇷', 'EU': '🇪🇺',
}

NL_SOURCES = [
    'nos', 'nrc', 'volkskrant', 'telegraaf', 'trouw', 'ad.nl', 'rtl nieuws',
    'rtlnieuws', 'nu.nl', 'fd.nl', 'bnr', 'eenvandaag', 'fnv', 'cnv',
    'bnnvara', 'joop', 'ftm', 'follow the money', 'correspondent',
    'geenstijl', 'elsevier', 'nieuwsuur', 'wnl',
]

def detect_intl_flag(src: str) -> str:
    s = src.lower()
    for keys, code in INTL_FLAGS:
        if any(k in s for k in keys):
            return FLAG_EMOJI.get(code, '🌍')
    return '🌍'

def is_intl_source(src: str) -> bool:
    s = src.lower()
    if any(nl in s for nl in NL_SOURCES):
        return False
    return any(any(k in s for k in keys) for keys, _ in INTL_FLAGS)

# ── Sentiment detection — expanded ───────────────────────────────────────────
POS_WORDS = [
    'positief','steunt','steun','lof','succesvol','goed','stabiel','vertrouwen',
    'historisch','premier beëdigd','kans','winst','doorbraak','akkoord','hoop',
    'samenwerking','daadkracht','succes','groei','investering','vooruitgang',
    'gewaardeerd','sterk','ambitieus','oplossing','bereikt','blij','tevreden',
    'support','welcomes','praises','praised','backs','youngest','coalition',
    'agreement','breakthrough','succeeds','wins','celebrates','applauds',
    'backing','landmark','progress','record','optimistic',
    # German pos
    'einigung','erfolg','stärkt','unterstützt','begrüßt',
    # French pos
    'accord','succès','soutien','approuve',
    # Spanish pos
    'acuerdo','éxito','apoyo','aprueba',
]
NEG_WORDS = [
    'kritiek','negatief','verzet','protest','staking','stakingen','motie','wantrouwen',
    'weigert','fout','gevaar','crisis','aow','bezuinig','mislukking','verlies',
    'conflict','ruzie','aanval','beschuldig','schandaal','falen','verdeeld',
    'ontslag','aftreden','schuld','blunder','omstreden','teleurstelling',
    'mislukt','onrust','spanning','druk','woede','boos','zorgen','dreigt',
    'waarschuwt','risico','gevaarlijk','chaos','impasse','zwak','aangevallen',
    'verwijt','tegenwerking','rampzalig',
    # FIXED: previously missing Dutch negatives
    'vuur','onder vuur','blazen af','staakt','breekt','instabiel',
    'valt','loopt weg','opgeblazen','breuk','verhit','verwerpelijk',
    'afkraken','hekelen','hekelt','sloopt','felle','furieus','geschokt',
    'verontwaardigd','verontwaardiging','afwijst',
    # English neg
    'rejects','opposes','slams','blasts','criticises','criticizes',
    'resigns','collapses','walkout','protests','strikes','under fire',
    'demonstration','demonstratie',
    # German neg
    'kritik','krise','rücktritt','scheitert','streik','warnt','ablehnt',
    'gefahr','instabil','protest','scheitert',
    # French neg
    'critique','crise','démission','échec','proteste','grève','rejette',
    # Spanish neg
    'crítica','crisis','dimisión','fracaso','protesta','huelga','rechaza',
    # Italian neg
    'critica','crisi','dimissioni','fallimento','protesta','sciopero','rifiuta',
    # Russian neg
    'критик','протест','кризис','отставка','провал','неудача','скандал',
    'конфликт','угроза','обвинение','осуждает',
    # Ukrainian neg
    'критика','протест','криза','відставка',
    # Polish neg
    'krytyka','kryzys','rezygnacja','protest','strajk',
]
STRONG_NEG = [
    'valt','crisis','wantrouwen','ontslag','aftreden','schandaal','chaos',
    'mislukt','collapse','under fire','vuur','loopt weg','blazen af',
    'instabiel','rampzalig','furieus','кризис','отставка','Rücktritt',
]
STRONG_POS = [
    'doorbraak','akkoord','historisch','winst','succes','breakthrough',
    'landmark','record','celebrates',
]

def detect_sentiment(title: str) -> str:
    t = title.lower()
    pos = sum(1 for w in POS_WORDS if w in t)
    neg = sum(1 for w in NEG_WORDS if w in t)
    for w in STRONG_NEG:
        if w in t: neg += 2
    for w in STRONG_POS:
        if w in t: pos += 2
    if pos > neg: return 'p'
    if neg > pos: return 'n'
    if pos and neg: return 'a'
    if re.search(r'waarom|hoe kan|wanneer stopt|mag dit|klopt het|wat nu|under fire|vuur', t):
        return 'n'
    return 'u'

def make_id(title: str) -> str:
    return 'g' + hashlib.md5(title.lower().strip().encode()).hexdigest()[:12]

def parse_date(entry) -> str:
    try:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            return datetime(*entry.published_parsed[:3]).strftime('%Y-%m-%d')
    except Exception:
        pass
    raw = getattr(entry, 'published', '') or getattr(entry, 'updated', '')
    for fmt in ('%a, %d %b %Y %H:%M:%S %z', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(raw[:len(fmt)], fmt).strftime('%Y-%m-%d')
        except Exception:
            pass
    return TODAY

HEADERS = {'User-Agent': 'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)'}

def fetch_nl_feed(src_name, icon, item_type, feed_url) -> list:
    results = []
    try:
        resp = requests.get(feed_url, timeout=15, headers=HEADERS)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        for entry in feed.entries[:40]:
            title = entry.get('title', '').strip()
            if SUBJECT not in title.lower():
                continue
            pub_date = parse_date(entry)
            if pub_date < START_DATE:
                continue
            lr = classify_lr(src_name)
            item = {
                'id':    make_id(title),
                'type':  item_type,
                'src':   src_name,
                'icon':  icon,
                'title': title,
                'date':  pub_date,
                'sent':  detect_sentiment(title),
                'link':  entry.get('link', ''),
            }
            if lr:
                item['lr'] = lr
            results.append(item)
    except Exception as e:
        print(f'  ⚠️  Feed {src_name} ({feed_url[:50]}…): {e}')
    return results

def fetch_google_query(query, item_type, lang, country) -> list:
    url = (
        f'https://news.google.com/rss/search'
        f'?q={requests.utils.quote(query)}'
        f'&hl={lang}&gl={country}&ceid={country}:{lang}'
    )
    results = []
    try:
        resp = requests.get(url, timeout=15, headers=HEADERS)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        for entry in feed.entries[:20]:
            title = entry.get('title', '').strip()
            if not title:
                continue
            pub_date = parse_date(entry)
            if pub_date < START_DATE:
                continue
            src = ''
            if hasattr(entry, 'source') and hasattr(entry.source, 'title'):
                src = entry.source.title
            if not src:
                m = re.search(r'https?://(?:www\.)?([^/]+)', entry.get('link', ''))
                src = m.group(1).replace('.nl','').replace('.com','') if m else 'Google News'

            # Determine actual type based on source
            if is_intl_source(src) or lang != 'nl':
                actual_type = 'intl'
            else:
                src_l = src.lower()
                title_l = title.lower()
                if any(x in title_l for x in ['twitter', 'x.com', 'trending', 'viraal', 'hashtag']):
                    actual_type = 'x'
                elif any(x in src_l for x in ['joop', 'correspondent', 'geenstijl', 'ftm',
                                               'follow', 'cnv', 'fnv', 'vakbond', 'elsevier', 'groene']):
                    actual_type = 'blog'
                else:
                    actual_type = 'nl'

            lr = classify_lr(src)
            item = {
                'id':    make_id(title),
                'type':  actual_type,
                'src':   src,
                'title': title,
                'date':  pub_date,
                'sent':  detect_sentiment(title),
                'link':  entry.get('link', ''),
            }
            if actual_type == 'intl':
                item['flag'] = detect_intl_flag(src)
            else:
                item['icon'] = '✍️' if actual_type == 'blog' else '🔥' if actual_type == 'x' else '📰'
                if lr:
                    item['lr'] = lr
            results.append(item)
    except Exception as e:
        print(f'  ⚠️  Google query "{query}" ({lang}): {e}')
    return results


# ── Bluesky — publieke AT Protocol API (geen sleutel nodig) ──────────────────
BSKY_QUERIES = [
    'Jetten premier',
    'Rob Jetten',
    'kabinet-Jetten',
    'Йеттен',
    'єттен',
]

def fetch_bluesky(query: str) -> list:
    """Zoek posts via de publieke Bluesky/AT Protocol API."""
    url = 'https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts'
    params = {'q': query, 'limit': 25, 'sort': 'latest'}
    results = []
    try:
        bsky_headers = {**HEADERS, 'Accept': 'application/json', 'Accept-Language': 'en'}
        resp = requests.get(url, params=params, timeout=12, headers=bsky_headers)
        resp.raise_for_status()
        data = resp.json()
        for p in data.get('posts', []):
            record = p.get('record', {})
            text = record.get('text', '').strip()
            if not text or not matches_subject(text):
                continue
            created_at = record.get('createdAt') or p.get('indexedAt', '')
            try:
                date_str = created_at[:10] if created_at else TODAY
            except Exception:
                date_str = TODAY
            if date_str < START_DATE:
                continue
            author = p.get('author', {})
            handle = author.get('handle', '')
            display_name = author.get('displayName') or handle or '?'
            uri = p.get('uri', '')
            rkey = uri.split('/')[-1] if uri else ''
            post_url = f'https://bsky.app/profile/{handle}/post/{rkey}' if handle and rkey else ''
            likes   = p.get('likeCount', 0)
            reposts = p.get('repostCount', 0)
            item_id = make_id('bsky_' + uri)
            results.append({
                'id':    item_id,
                'type':  'x',
                'src':   f'{display_name} (Bluesky)',
                'icon':  '🦋',
                'title': text[:200],
                'date':  date_str,
                'sent':  detect_sentiment(text),
                'link':  post_url,
                'stats': f'{likes} likes · {reposts} reposts',
            })
    except Exception as e:
        print(f'  ⚠️  Bluesky query "{query}": {e}')
    return results

def main():
    print(f'📰 Jetten nieuws ophalen — {TODAY}')
    try:
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            existing = json.load(f)
        print(f'   Bestaande items: {len(existing)}')
    except FileNotFoundError:
        existing = []

    existing_ids = {item['id'] for item in existing}
    new_items = []

    def add(items):
        for item in items:
            if item['id'] not in existing_ids:
                existing_ids.add(item['id'])
                new_items.append(item)

    print('\n📡 Directe NL media RSS feeds:')
    for src_name, icon, item_type, url in NL_FEEDS:
        results = fetch_nl_feed(src_name, icon, item_type, url)
        if results:
            print(f'   ✓ {src_name}: {len(results)} Jetten-artikelen')
        add(results)
        time.sleep(0.5)

    print('\n🔍 Google News zoekopdrachten (NL + intl):')
    for query, hl, lang, country in GOOGLE_QUERIES:
        results = fetch_google_query(query, 'intl' if hl != 'nl' else 'nl', lang, country)
        if results:
            print(f'   ✓ [{hl}] "{query}": {len(results)} resultaten')
        add(results)
        time.sleep(0.8)


    print('\n🦋 Bluesky zoekopdrachten:')
    for query in BSKY_QUERIES:
        results = fetch_bluesky(query)
        if results:
            print(f'   ✓ "{query}": {len(results)} posts')
        add(results)
        time.sleep(0.5)
    print(f'\n   Nieuwe items: {len(new_items)}')
    if new_items:
        all_items = existing + new_items
        all_items.sort(key=lambda x: x.get('date', ''), reverse=True)
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_items, f, ensure_ascii=False, indent=2)
        print(f'✅ data.json bijgewerkt — totaal {len(all_items)} items')
        # Print breakdown
        by_lang = {}
        for it in new_items:
            t = it.get('type', '?')
            by_lang[t] = by_lang.get(t, 0) + 1
        for k, v in sorted(by_lang.items()):
            print(f'   {k}: {v}')
    else:
        print('✅ Geen nieuwe items — data.json ongewijzigd')

if __name__ == '__main__':
    main()

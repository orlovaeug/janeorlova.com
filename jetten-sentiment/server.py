#!/usr/bin/env python3
"""
Jetten Sentimenttracker — optionele Python backend
Run: python server.py
Open: http://localhost:5000
Vereist: pip install flask flask-cors requests feedparser
"""

import json, re, requests, feedparser
from datetime import datetime
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

START_DATE = '2026-02-23'

QUERIES = [
    ('Rob Jetten premier',                    'nl', 'NL'),
    ('Jetten kabinet',                        'nl', 'NL'),
    ('Rob Jetten prime minister Netherlands', 'en', 'US'),
    ('Jetten Dutch PM coalition',             'en', 'GB'),
    ('Jetten Ministerpräsident Niederlande',  'de', 'DE'),
    ('Jetten premier ministre Pays-Bas',      'fr', 'FR'),
    ('Йеттен премьер Нидерланды',             'ru', 'RU'),
]

POS = ['positief','steunt','succesvol','stabiel','vertrouwen','historisch','akkoord',
       'doorbraak','support','welcomes','praised','agreement','breakthrough']
NEG = ['kritiek','verzet','protest','staking','motie','wantrouwen','crisis','aow',
       'bezuinig','schandaal','ontslag','aftreden','chaos','vuur','onder vuur',
       'blazen af','furieus','hekelt','rejects','slams','collapses','under fire',
       'kritik','krise','critique','crise','crítica','critica','кризис','протест']

def detect_sentiment(title):
    t = title.lower()
    p = sum(1 for w in POS if w in t)
    n = sum(1 for w in NEG if w in t)
    if p > n: return 'p'
    if n > p: return 'n'
    if p and n: return 'a'
    return 'u'

INTL_FLAGS = [
    (['guardian','bbc','telegraph','times','independent','sky news'], 'GB'),
    (['nytimes','washington post','wapo','bloomberg','reuters','ap news','cnn','wsj','politico','npr'], 'US'),
    (['spiegel','frankfurter','faz','zeit','welt','süddeutsche','tagesschau'], 'DE'),
    (['monde','figaro','liberation','france24','rfi'], 'FR'),
    (['el pais','elmundo','lavanguardia','rtve'], 'ES'),
    (['corriere','repubblica','stampa','rai'], 'IT'),
    (['kommersant','vedomosti','rbc','meduza','novaya gazeta'], 'RU'),
    (['ukrinform','kyiv post','kyiv independent','ukrainska pravda'], 'UA'),
    (['vrt','rtbf','de morgen','nieuwsblad','standaard'], 'BE'),
    (['wyborcza','rzeczpospolita','onet','tvn24'], 'PL'),
    (['aftenposten','nrk','dagbladet'], 'NO'),
    (['svt','aftonbladet','expressen'], 'SE'),
    (['politiko.eu','euractiv','europarl'], 'EU'),
]
NL_SOURCES = ['nos','nrc','volkskrant','telegraaf','trouw','ad.nl','rtlnieuws',
              'nu.nl','fd.nl','bnr','eenvandaag','bnnvara','joop','ftm','correspondent','geenstijl','elsevier']

def get_flag(src):
    s = src.lower()
    for keys, code in INTL_FLAGS:
        if any(k in s for k in keys):
            return code
    return 'INTL'

def is_intl(src):
    s = src.lower()
    if any(nl in s for nl in NL_SOURCES): return False
    return any(any(k in s for k in keys) for keys, _ in INTL_FLAGS)

def fetch(q, hl, gl):
    url = f'https://news.google.com/rss/search?q={requests.utils.quote(q)}&hl={hl}&gl={gl}&ceid={gl}:{hl}'
    results = []
    try:
        feed = feedparser.parse(requests.get(url, timeout=12).content)
        for e in feed.entries:
            title = e.get('title','').strip()
            if not title: continue
            try:
                d = datetime(*e.published_parsed[:3]).strftime('%Y-%m-%d') if hasattr(e,'published_parsed') and e.published_parsed else ''
            except: d = ''
            if not d or d < START_DATE: continue
            src = getattr(getattr(e,'source',None),'title','') or ''
            if not src:
                m = re.search(r'https?://(?:www\.)?([^/]+)', e.get('link',''))
                src = m.group(1).replace('.nl','').replace('.com','') if m else 'Google News'
            item_type = 'intl' if (is_intl(src) or hl != 'nl') else 'nl'
            item = {'id': title.lower().replace(' ','')[:60], 'type': item_type,
                    'src': src, 'title': title, 'date': d,
                    'sent': detect_sentiment(title), 'link': e.get('link','')}
            if item_type == 'intl': item['flag'] = get_flag(src)
            else: item['icon'] = '📰'
            results.append(item)
    except Exception as ex:
        print(f'  ⚠️ {q}: {ex}')
    return results

@app.route('/')
def index(): return app.send_static_file('index.html')

@app.route('/api/refresh', methods=['POST'])
def refresh():
    seen, all_items = set(), []
    for q, hl, gl in QUERIES:
        for item in fetch(q, hl, gl):
            if item['id'] not in seen:
                seen.add(item['id'])
                all_items.append(item)
    return jsonify({'items': all_items, 'count': len(all_items)})

if __name__ == '__main__':
    print('Jetten Tracker op http://localhost:5000')
    app.run(debug=True, port=5000)

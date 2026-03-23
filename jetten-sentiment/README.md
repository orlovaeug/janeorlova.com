# Jetten in de Media — Sentimenttracker

Sentimenttracker voor de berichtgeving over premier Rob Jetten (feb 2026–heden).

## Gratis — geen API-sleutel nodig

De **Vernieuwen**-knop gebruikt Google News RSS via een gratis proxy.
Geen account, geen credits, geen kosten.

## Bestanden

| Bestand | Doel |
|---------|------|
| `index.html` | Volledige frontend — werkt standalone in de browser |
| `data.json` | Basisdata — geverifieerde artikelen 23 feb – 10 mrt 2026 |
| `server.py` | Optionele Python backend (gebruikt ook Google News RSS) |
| `fetch_news.py` | Dagelijkse automatische nieuwsupdate (GitHub Action) |
| `requirements.txt` | Python dependencies voor server.py en fetch_news.py |

## Snel starten

**Alleen de HTML** (geen installatie nodig):
```
Open index.html in je browser
```

**Met Python backend**:
```bash
pip install flask flask-cors requests feedparser
python server.py
# Open http://localhost:5000
```

**Dagelijkse update via script**:
```bash
pip install requests feedparser
python fetch_news.py
```

## Functies

- Sentimentmeter (positief / negatief / neutraal)
- Links vs Rechts media tracker
- Internationale pers: EN, DE, FR, ES, IT, RU, UA, PL, NO, SV en meer
- Automatische weekknoppen (Week 1, 2, 3… tot vandaag)
- Volledige tijdlijn met alle dagen — scrollbaar
- Export naar JSON

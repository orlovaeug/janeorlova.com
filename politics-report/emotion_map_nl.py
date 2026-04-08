#!/usr/bin/env python3
import re, csv, json, time, argparse, os
from collections import defaultdict
from datetime import datetime, timezone

SEGMENTS = [
    {
        "id": "jetten_coalition",
        "label": "Jetten I Coalition",
        "actor": "Coalitieakkoord + regeringsverklaring Jetten",
        "urls": [
            "https://www.government.nl/binaries/government/officieel-bekendgemaakt/2026/02/23/regeerakkoord-2026/Coalition+Agreement+2026.pdf",
            "https://www.rijksoverheid.nl/actueel/nieuws/2026/02/23/regeringsverklaring-premier-jetten",
        ],
    },
    {
        "id": "min_vdbrink",
        "label": "Min. Van den Brink",
        "actor": "CDA / Ministerie van Asiel en Migratie",
        "urls": [
            "https://ind.nl/nl/nieuws/asielaanvragen-en-gezinshereniging-actuele-ontwikkelingen",
            "https://www.rijksoverheid.nl/ministeries/ministerie-van-justitie-en-veiligheid/nieuws",
        ],
    },
    {
        "id": "pvv_opposition",
        "label": "PVV Oppositie",
        "actor": "Wilders / PVV, 19 zetels",
        "urls": [
            "https://www.pvv.nl/nieuws.html",
            "https://www.tweedekamer.nl/kamerstukken/plenaire_verslagen",
        ],
    },
    {
        "id": "glpvda_opposition",
        "label": "GL-PvdA Oppositie",
        "actor": "Klaver / GroenLinks-PvdA, 20 zetels",
        "urls": [
            "https://groenlinks.nl/nieuws",
            "https://www.pvda.nl/nieuws",
        ],
    },
    {
        "id": "ngo_ecre",
        "label": "NGO / VluchtelingenWerk",
        "actor": "VluchtelingenWerk NL, Amnesty NL",
        "urls": [
            "https://www.vluchtelingenwerk.nl/nieuws",
            "https://www.amnesty.nl/actueel/themas/vluchtelingen-en-migranten",
        ],
    },
    {
        "id": "ind_eu_pact",
        "label": "IND / EU Pact",
        "actor": "IND berichten + EU Migratiepact",
        "urls": [
            "https://ind.nl/nl/nieuws",
            "https://www.rijksoverheid.nl/onderwerpen/asielbeleid/europees-migratiepact",
        ],
    },
    {
        "id": "media_framing",
        "label": "Media Framing",
        "actor": "NOS, NRC, de Volkskrant",
        "urls": [
            "https://nos.nl/thema/migratie",
            "https://www.nrc.nl/tag/migratie/",
            "https://www.volkskrant.nl/nieuws-achtergrond/migratie/",
        ],
    },
]

# Dutch NRC-style emotion lexicon
SEED_LEXICON = {
    "fear": [
        # crisis / bedreiging
        "crisis", "bedreiging", "bedreigd", "gevaar", "gevaarlijk", "gevaarlijke",
        "onveilig", "onveiligheid", "angst", "bang", "vrees", "vrezen",
        "noodsituatie", "noodtoestand", "instabiliteit", "instabiel",
        "ramp", "catastrofe", "chaos", "onrust", "spanning",
        # instroom / druk
        "instroom", "toestroom", "overbelasting", "overbelast", "druk",
        "ongecontroleerd", "onbeheerst", "overlast", "probleem", "problemen",
        # onzekerheid
        "onzekerheid", "onzeker", "kwetsbaar", "kwetsbaarheid",
        "risico", "gevaren", "dreigend", "dreiging", "alarm",
        # geweld / oorlog
        "geweld", "oorlog", "vlucht", "vluchten", "gevluchte",
        "vervolging", "terreur", "aanslagen",
        # ergst / worst case
        "ernstig", "ernstige", "ongekend", "uitzichtloos", "noodopvang",
        "noodmaatregel", "spoedeisend", "spoedwet", "asielcrisis",
    ],
    "anger": [
        # falen / mislukking
        "falen", "faalt", "gefaald", "mislukt", "mislukking", "tekortkoming",
        "onverantwoordelijk", "onacceptabel", "onaanvaardbaar",
        # oneerlijk / onrechtvaardig
        "oneerlijk", "onrechtvaardig", "onrecht", "discriminatie",
        "uitbuiting", "schending", "schendingen",
        # woede / verontwaardiging
        "woede", "woedend", "verontwaardiging", "verontwaardigd",
        "frustratie", "gefrustreerd", "boosheid", "boos",
        # bezuinigingen / aanval
        "bezuinigingen", "bezuiniging", "afbraak", "aanval", "aanvallen",
        "tegenwerken", "blokkeren", "saboteren",
        # beschuldiging
        "beschuldigd", "beschuldiging", "verwijt", "verwijten",
        "wanbeleid", "incompetent", "nalatig", "nalatigheid",
        # destructief / contraproductief
        "destructief", "contraproductief", "schandalig", "schandelijk",
        "schande", "walgelijk", "empörend",
    ],
    "hope": [
        # toekomst / kans
        "toekomst", "kansen", "kans", "mogelijkheid", "mogelijkheden",
        "perspectief", "vooruitzicht", "vooruitgang", "verbetering",
        # oplossing / aanpak
        "oplossing", "oplossingen", "aanpak", "aanpakken",
        "samenwerking", "samenwerken", "solidariteit",
        # integratie / participatie
        "integratie", "integreren", "participatie", "inburgering",
        "inburgeren", "deelname", "bijdragen", "bijdrage",
        # investering / bouwen
        "investering", "investeren", "bouwen", "opbouwen",
        "ontwikkeling", "groeien", "groei",
        # veiligheid / bescherming (positief)
        "bescherming", "beschermen", "veilig", "veiligheid",
        "opvang", "ondersteuning", "ondersteunen", "hulp",
        # positief / hoopvol
        "positief", "hoopvol", "hoop", "optimistisch", "optimisme",
        "welkom", "inclusief", "inclusiviteit", "menselijk", "menselijkheid",
        "rechtvaardig", "rechtvaardigheid",
    ],
    "trust": [
        # stabiliteit / betrouwbaarheid
        "stabiliteit", "stabiel", "betrouwbaar", "betrouwbaarheid",
        "vertrouwen", "verantwoordelijk", "verantwoordelijkheid",
        # procedure / wet
        "procedure", "procedures", "wetgeving", "wettelijk", "rechtsstatelijk",
        "rechtsstaat", "regelgeving", "regels", "kader", "juridisch",
        # implementatie / uitvoering
        "implementatie", "implementeren", "uitvoering", "uitvoeren",
        "handhaving", "handhaven", "naleving", "naleven",
        # akkoord / afspraken
        "akkoord", "afspraken", "verdrag", "overeenkomst", "verbintenis",
        "toezegging", "commitment", "protocol",
        # transparantie / controle
        "transparantie", "transparant", "controle", "toezicht",
        "verantwoording", "accountability", "zorgvuldig", "zorgvuldigheid",
        # competent / effectief
        "competent", "effectief", "efficiënt", "degelijk", "solide",
        "consistent", "coherent",
    ],
}

STOPWORDS = set(
    # Dutch stopwords
    "de het een en van in is dat op zijn met voor ook maar als ze er aan "
    "bij was wordt worden door dit die nog dan naar heeft niet om hebben "
    "hij ze we zij meer over zo wel na zou worden kunnen worden worden "
    "al tot uit te worden zijn worden zijn zijn zijn zijn zijn zijn zijn "
    "wordt worden werd werden zal zullen zou zouden kan kunnen moet moeten "
    "mag mogen wil willen hen hun zich zelf hun onze uw mijn jouw jij je "
    "ik wij jullie u zij hem haar mee toch echter omdat terwijl hoewel "
    "dus want want want want want want want want want want want "
    "al reeds nu nog steeds altijd nooit soms vaak "
    "hier daar waar wanneer hoe waarom welk welke wat wie "
    "nieuwe nieuwe nieuw meer minder veel weinig alle beide elk ieder "
    # English stopwords (pages may mix)
    "a the and or but in on at to for of is are was were be been "
    "have has had do does did will would could should may might "
    "this that these those it its with from by an as if not".split()
)


def build_lexicon(path=None):
    lex = defaultdict(set)
    if path and os.path.exists(path):
        # NRC EmoLex Dutch version: NRC-Emotion-Lexicon-v0.92-In105Languages-Nov2017Translations.txt
        # Column order: English word, Dutch translation, Afrikaans, ... emotion columns
        # Simpler: use the Dutch NRC translation file if available
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split("\t")
                    if len(parts) >= 2 and parts[-1] == "1":
                        word = parts[0].lower()
                        emotion = parts[1].lower() if len(parts) > 2 else ""
                        mapping = {"fear": "fear", "anger": "anger",
                                   "anticipation": "hope", "trust": "trust"}
                        if emotion in mapping:
                            lex[word].add(mapping[emotion])
            print("  [NRC] Loaded lexicon from " + path)
            return lex
        except Exception as e:
            print("  [NRC] Could not load: " + str(e))
    for emotion, words in SEED_LEXICON.items():
        for w in words:
            lex[w.lower()].add(emotion)
    total = sum(len(v) for v in SEED_LEXICON.values())
    print("  [NRC] Using Dutch seed lexicon (" + str(total) + " word-emotion pairs)")
    return lex


def fetch_url(url, timeout=15):
    try:
        import requests
        from bs4 import BeautifulSoup
        headers = {
            "User-Agent": "Mozilla/5.0 (research; NL migratie studie)",
            "Accept-Language": "nl-NL,nl;q=0.9",
        }
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        return re.sub(r"\s+", " ", text).strip(), None
    except Exception as e:
        return "", str(e)


def tokenize(text):
    tokens = re.findall(r"[a-z\u00e0-\u024f]+", text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 2]


def score_text(text, lexicon):
    counts = defaultdict(int)
    for token in tokenize(text):
        for emotion in lexicon.get(token, []):
            counts[emotion] += 1
    emotions = ["fear", "anger", "hope", "trust"]
    total = sum(counts.get(e, 0) for e in emotions)
    if total == 0:
        return None, 0
    pcts = {e: round(100 * counts.get(e, 0) / total, 1) for e in emotions}
    return pcts, total


def run(lexicon_path=None):
    print("=" * 60)
    print("  emotion_map_nl.py — Dutch language version")
    print("=" * 60)

    lexicon = build_lexicon(lexicon_path)
    results = []
    log = ["Run: " + datetime.now(timezone.utc).isoformat()]

    for seg in SEGMENTS:
        print("\n  Segment: " + seg["label"])
        all_text = ""

        for url in seg["urls"]:
            print("    Fetching " + url[:70] + "...")
            text, err = fetch_url(url)
            if err:
                log.append("FAIL " + url + " -- " + err[:80])
                print("    FAIL: " + err[:60])
            else:
                all_text += " " + text
                log.append("OK   " + url + " (" + str(len(text)) + " chars)")
                print("    OK: " + str(len(text)) + " chars")
            time.sleep(1)

        pcts, n = score_text(all_text, lexicon)

        if pcts is None:
            print("    WARNING: geen emotie-tokens gevonden")
            log.append("EMPTY " + seg["id"])
            results.append({
                "id": seg["id"],
                "label": seg["label"],
                "actor": seg["actor"],
                "fear": None,
                "anger": None,
                "hope": None,
                "trust": None,
                "dominant": None,
                "n": 0,
                "low_sample": True,
                "scored": False,
            })
            continue

        dominant = max(["fear", "anger", "hope", "trust"], key=lambda e: pcts[e])
        low = n < 30
        print("    Fear " + str(pcts["fear"]) + "%  Anger " + str(pcts["anger"]) +
              "%  Hope " + str(pcts["hope"]) + "%  Trust " + str(pcts["trust"]) +
              "%  -> " + dominant.upper() + "  n=" + str(n))

        results.append({
            "id": seg["id"],
            "label": seg["label"],
            "actor": seg["actor"],
            "fear": pcts["fear"],
            "anger": pcts["anger"],
            "hope": pcts["hope"],
            "trust": pcts["trust"],
            "dominant": dominant,
            "n": n,
            "low_sample": low,
            "scored": True,
        })
        log.append("SCORE " + seg["id"] + " F=" + str(pcts["fear"]) +
                   " A=" + str(pcts["anger"]) + " H=" + str(pcts["hope"]) +
                   " T=" + str(pcts["trust"]) + " n=" + str(n))

    ts = datetime.now(timezone.utc).isoformat()
    payload = {
        "generated": ts,
        "lexicon": "Dutch NRC seed lexicon",
        "note": "Scores computed from Dutch-language source text. See fetch_log.txt.",
        "segments": results,
    }

    with open("emotion_results.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print("\nOK  emotion_results.json geschreven")

    with open("emotion_results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Segment", "Actor", "Fear (%)", "Anger (%)", "Hope (%)", "Trust (%)",
                    "Dominant", "n", "Low Sample?", "Scored?"])
        for r in results:
            w.writerow([r["label"], r["actor"], r["fear"], r["anger"],
                        r["hope"], r["trust"], r["dominant"], r["n"],
                        "YES" if r["low_sample"] else "no",
                        "YES" if r["scored"] else "FAILED"])
    print("OK  emotion_results.csv geschreven")

    with open("fetch_log.txt", "w") as f:
        f.write("\n".join(log))
    print("OK  fetch_log.txt geschreven")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--lexicon", default=None,
                        help="Pad naar NRC EmoLex Dutch translation file")
    args = parser.parse_args()
    run(args.lexicon)

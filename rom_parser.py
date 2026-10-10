"""
rom_parser.py — Smart udtrækning af rom-info fra alle tilgængelige felter.

Tries data sources in order:
1. Product name (typisk mest pålidelig)
2. Slug (struktureret, ingen HTML)
3. Brands felt
4. Tags / categories
5. Description (HTML)
6. HTML fallback (hvis enrich_from_html(url) kaldes)
"""
import re
import requests
import time
from html import unescape

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def clean_html(text):
    """Fjern HTML tags + entities"""
    if not text:
        return ""
    # Fjern HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    # Unescape HTML entities
    text = unescape(text)
    # Saml whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ────────────────────────────────────────────────────────────
# VOLUME EXTRACTION
# ────────────────────────────────────────────────────────────
def extract_volume(name, slug="", description="", short_desc=""):
    """
    Find volume i cl. Rom er typisk 70cl, men kan være 5cl, 35cl, 50cl, 100cl osv.
    """
    name = name or ""
    slug = slug or ""
    desc = clean_html(description) if description else ""
    short = clean_html(short_desc) if short_desc else ""

    # Prøv hver kilde — navn først, så slug, så descriptions
    sources = [name, slug.replace("-", " "), short, desc]

    for source in sources:
        source_lower = source.lower()

        # Match "700ml", "70cl", "0,7 l", "1l", "1 l", "0.7l"
        patterns = [
            r"(\d+(?:[.,]\d+)?)\s*ml\b",
            r"(\d+(?:[.,]\d+)?)\s*cl\b",
            r"(\d+(?:[.,]\d+)?)\s*l\b",
        ]

        for pattern in patterns:
            matches = re.findall(pattern, source_lower)
            for m in matches:
                val = float(m.replace(",", "."))
                if "ml" in pattern:
                    cl = val / 10
                elif "cl" in pattern:
                    cl = val
                else:  # liter
                    cl = val * 100

                # Sanity check for rom (5cl miniature → 300cl magnum)
                if 2 <= cl <= 300:
                    return cl

    return None


# ────────────────────────────────────────────────────────────
# ABV EXTRACTION
# ────────────────────────────────────────────────────────────
def _pct_values(text):
    """Alle 'X %' i en tekst som (værdi, start, slut)."""
    out = []
    for m in re.finditer(r"(?<!\d)(?<!\d[.,])(\d{1,3}(?:[.,]\d{1,2})?)\s*%", text):
        out.append((float(m.group(1).replace(",", ".")), m.start(), m.end()))
    return out


_ABV_CONTEXT = re.compile(r"alkohol|procent|\babv\b|\balc\b|\balc\.|\bvol\b|\bvol\.|volumen|styrke|strength|proof|fadstyrke|cask strength", re.I)
# "76,2% - 70 cl": butikkerne skriver ofte styrken lige foran flaskestørrelsen, og det tæller som en tydelig angivelse
_VOL_AFTER = re.compile(r"\s*[-\u2013\u2014]?\s*\d+(?:[.,]\d+)?\s*(?:cl|ml|l)\b", re.I)
_ABV_STRONG = re.compile(r"proof|\b151\b|overproof|navy strength|cask strength|fadstyrke|brut de (?:colonne|fut)", re.I)
_AGE_WORDS = {"ar", "aar", "yo", "y", "years", "year", "anos", "ans", "old", "ars"}
_UNIT_WORDS = {"cl", "ml", "l", "ltr", "liter", "dl"}
_NUMBER_WORDS = {"no", "nr", "nummer", "number", "batch", "cask", "vol", "release", "edition", "nr.", "lot", "bottle", "series"}
# Adressen er det svageste signal: kun almindelige butiksstyrker accepteres derfra (aldrig 50-65, som ofte er serie-numre)
_SLUG_ABV = {37, 38, 40, 41, 42, 43, 45, 46, 47, 48}


def extract_abv(name, slug="", description="", short_desc=""):
    """
    Find alkoholprocent. Rækkefølge efter pålidelighed:
      1. Navnet: et eksplicit 'X%' (30-80 %), fx 'Stroh 80%' eller 'Smith & Cross -57%'.
      2. Tekst, kilde for kilde (den korte beskrivelse før den lange): 'alkoholprocent på X' eller et 'X%'
         med alkohol-ord tæt på (alkohol, procent, ABV, vol, proof, styrke) - ellers første 'X%' mellem 30 og
         69,9 %. Op til 80 % kun, hvis produktet tydeligt er en høj styrke (proof, 151, overproof, navy/cask
         strength). Hedder produktet 'cask strength' o.l., ignoreres alt under 45 %.
      4. Adressen (slug): kun et frittstående tal fra _SLUG_ABV, aldrig en flaskestørrelse ('70-cl'),
         en alder ('12-ar') eller et nummer ('no-66').
    Rettet: den gamle slug-regel tog 70/75 fra '...-70-cl' som alkoholprocent (Plantation 3 Stars 70 %,
    Hampden 15 75 % m.fl.) og '35' fra '35 cl'.
    """
    name = name or ""
    short = clean_html(short_desc) if short_desc else ""
    desc = clean_html(description) if description else ""
    strong = bool(_ABV_STRONG.search(" ".join((name, short, desc))))

    # 1) navnet
    for val, _s, _e in _pct_values(name):
        if 30 <= val <= 80:
            return val

    floor = 45 if re.search(r"cask strength|fadstyrke|navy strength|overproof|\bproof\b", name, re.I) else 0

    # 2+3) tekst, kilde for kilde (den korte før den lange): først et tal med alkohol-ord, ellers første tal
    top = 80 if strong else 69.99
    for source in (short, desc):
        m = re.search(r"alkoholprocent\s*(?:på|:)?\s*(\d+(?:[.,]\d+)?)", source, re.IGNORECASE)
        if m:
            val = float(m.group(1).replace(",", "."))
            if 30 <= val <= 80 and val >= floor:
                return val
        found = _pct_values(source)
        for val, s, e in found:
            if 30 <= val <= 80 and val >= floor and (_ABV_CONTEXT.search(source[max(0, s - 25): e + 25]) or _VOL_AFTER.match(source[e:e + 25])):
                return val
        for val, _s, _e in found:
            if 30 <= val <= top and val >= floor:
                return val

    # 4) adressen
    if slug:
        toks = [t for t in re.split(r"[-\s]+", slug.lower()) if t]
        for i, t in enumerate(toks):
            if not re.fullmatch(r"\d{2}", t) or int(t) not in _SLUG_ABV:
                continue
            nxt = toks[i + 1] if i + 1 < len(toks) else ""
            prv = toks[i - 1] if i > 0 else ""
            if nxt in _UNIT_WORDS or nxt in _AGE_WORDS or prv in _NUMBER_WORDS:
                continue
            return float(t)

    return None


# ────────────────────────────────────────────────────────────
# AGE EXTRACTION
# ────────────────────────────────────────────────────────────
_AGE_PATTERNS = [
    r"(\d+)\s*år",
    r"(\d+)\s*years?",
    r"(\d+)\s*y\.?o\.?",
    r"(\d+)\s*-?\s*y\.?o\.?",
    r"(\d+)\s*ans",
    r"(\d+)\s*años",
    r"(\d+)\s*anos",
    r"aged\s+(\d+)",
]
# I beskrivelser tæller et tal kun som alder, hvis et alder-ord står lige ved siden af
_AGE_CONTEXT = re.compile(r"lagret|lagring|modnet|gammel|aged|aging|ageing|alder|year old|years old|y\.o\.", re.I)


def _numeric_age(source, need_context=False):
    s = source.lower()
    for pattern in _AGE_PATTERNS:
        for m in re.finditer(pattern, s):
            age = int(m.group(1))
            if not 1 <= age <= 50:
                continue
            if need_context and not _AGE_CONTEXT.search(s[max(0, m.start() - 30): m.end() + 30]):
                continue
            return f"{age} år"
    return None


def _word_age(source):
    s = source.lower()
    if re.search(r"\bxo\b", s):
        return "XO"
    if "solera" in s:
        return "Solera"
    if re.search(r"\breserva\b", s) and "gran reserva" not in s:
        return "Reserva"
    return None


def extract_age(name, slug="", description="", short_desc=""):
    """
    Find alder: 12 år, XO, Solera, Reserva.

    Rækkefølge (navnet er det, butikkerne sammenlignes på, så det vejer tungest):
      1. navnet: tal ('12 år'), derefter ordbetegnelse (XO / Solera / Reserva)
      2. adressen (slug): tal, derefter ordbetegnelse
      3. beskrivelsen: KUN et tal med et alder-ord lige ved siden af ('lagret i 23 år', 'aged 12 years')
    Rettet: den gamle regel tog et hvilket som helst "N år/years" fra beskrivelsen, så "Plantation XO 20th
    Anniversary" fik 20 år, "Venezuela XO 25th Anniversary" 6 år og "Don Q Gold" 1 år. Samme flaske fik så
    forskellig alder i to butikker, og alder-porten afviste den.
    """
    name = name or ""
    slug_clean = (slug or "").lower().replace("-", " ").replace("_", " ")
    desc = clean_html(description) if description else ""
    short = clean_html(short_desc) if short_desc else ""

    for source in (name, slug_clean):
        age = _numeric_age(source) or _word_age(source)
        if age:
            return age
    for source in (short, desc):
        age = _numeric_age(source, need_context=True)
        if age:
            return age
    return None


# ────────────────────────────────────────────────────────────
# BRAND EXTRACTION
# ────────────────────────────────────────────────────────────
# Kendte brands - mest pålidelig kilde
KNOWN_BRANDS = [
    # Store internationale
    "Zacapa", "Diplomatico", "Diplomático", "Foursquare", "Plantation",
    "El Dorado", "Mount Gay", "Appleton Estate", "Appleton", "Bacardi",
    "Havana Club", "Captain Morgan", "Brugal", "Matusalem", "Flor de Caña",
    "Botran", "Abuelo", "Ron Abuelo", "Angostura", "Santa Teresa",
    "Worthy Park", "Hampden", "Smith & Cross", "Cartavio", "Millonario",
    "Doorly's", "Doorly", "Pusser's", "Pussers", "Pyrat", "Goslings",
    "Mount Gay", "Myers", "Don Q", "Ron de Jeremy", "Kraken",
    
    # Mindre / nicheted
    "Rum Nation", "Bristol Spirits", "Bristol", "Old St. Croix", "St. Croix",
    "Old Pascas", "Pascas", "Cabo Bay", "Hansen", "Stroh", "Bumbu",
    "Patridom", "Chairman's Reserve", "Chairman", "Dictador", "Botucal",
    "Don Papa", "Plantation", "Compagnie des Indes", "CDI",
    "Rum Sixty Six", "Sixty Six", "Real McCoy", "Pampero",
    
    # Danske
    "A.H. Riise", "Riise", "AH Riise", "Stauning", "Skotlander",
    
    # Cachaça
    "Cachaça 51", "Pirassununga", "Velho Barreiro", "Leblon", "Avuá",
    
    # Rhum agricole
    "La Favorite", "Clément", "Clement", "Rhum JM", "Rhum Damoiseau",
    "Trois Rivières",
    
    # Spiced
    "Sailor Jerry", "Captain Morgan", "Kraken",
]


def extract_brand(name, slug="", brands_field=None, tags=None):
    """
    Find brand. Forsøg flere kilder.
    """
    # 1. WooCommerce 'brands' felt
    if brands_field:
        for b in brands_field:
            if isinstance(b, dict):
                name_val = b.get("name", "").strip()
                if name_val:
                    return name_val
            elif isinstance(b, str):
                return b.strip()

    # 2. Match kendte brands mod navn (case-insensitive)
    name_lower = (name or "").lower()
    for brand in KNOWN_BRANDS:
        if brand.lower() in name_lower:
            return brand

    # 3. Match kendte brands mod tags
    if tags:
        for tag in tags:
            tag_name = tag.get("name", "") if isinstance(tag, dict) else str(tag)
            tag_lower = tag_name.lower()
            for brand in KNOWN_BRANDS:
                if brand.lower() == tag_lower or brand.lower() in tag_lower:
                    return brand

    # 4. Match mod slug
    slug_lower = (slug or "").lower().replace("-", " ")
    for brand in KNOWN_BRANDS:
        if brand.lower() in slug_lower:
            return brand

    return None


# ────────────────────────────────────────────────────────────
# COUNTRY EXTRACTION
# ────────────────────────────────────────────────────────────
# Brand → land mapping (mere pålideligt end at gætte fra navn)
BRAND_COUNTRY_MAP = {
    "Zacapa": "Guatemala",
    "Botran": "Guatemala",
    "Diplomatico": "Venezuela",
    "Diplomático": "Venezuela",
    "Santa Teresa": "Venezuela",
    "Pampero": "Venezuela",
    "Foursquare": "Barbados",
    "Mount Gay": "Barbados",
    "Doorly's": "Barbados",
    "Doorly": "Barbados",
    "Real McCoy": "Barbados",
    "Cockspur": "Barbados",
    "Rum Sixty Six": "Barbados",
    "Sixty Six": "Barbados",
    "Appleton Estate": "Jamaica",
    "Appleton": "Jamaica",
    "Worthy Park": "Jamaica",
    "Hampden": "Jamaica",
    "Smith & Cross": "Jamaica",
    "Myers": "Jamaica",
    "Bacardi": "Puerto Rico",
    "Don Q": "Puerto Rico",
    "Havana Club": "Cuba",
    "Brugal": "Dominikansk",
    "Matusalem": "Dominikansk",
    "Ron Esclavo": "Dominikansk",
    "Quorhum": "Dominikansk",
    "Flor de Caña": "Nicaragua",
    "El Dorado": "Guyana",
    "Cartavio": "Peru",
    "Millonario": "Peru",
    "Abuelo": "Panama",
    "Ron Abuelo": "Panama",
    "Angostura": "Trinidad",
    "A.H. Riise": "Dansk",
    "Riise": "Dansk",
    "AH Riise": "Dansk",
    "Stauning": "Dansk",
    "Old St. Croix": "Dansk",
    "St. Croix": "Dansk",
    "Hansen": "Dansk",
    "Stroh": "Østrig",
    "Dictador": "Colombia",
    "La Favorite": "Martinique",
    "Clément": "Martinique",
    "Clement": "Martinique",
    "Rhum JM": "Martinique",
    "Trois Rivières": "Martinique",
    "Don Papa": "Filippinerne",
    "Bumbu": "Barbados",
    "Patridom": "Dominikansk",
    "Cachaça 51": "Brasilien",
    "Velho Barreiro": "Brasilien",
    "Pirassununga": "Brasilien",
}

# Søgeord der peger på land
COUNTRY_KEYWORDS = {
    "Cuba": ["cuba", "cuban", "havana"],
    "Jamaica": ["jamaica", "jamaican"],
    "Barbados": ["barbados"],
    "Puerto Rico": ["puerto rico"],
    "Dominikansk": ["dominican", "dominikansk", "dom. rep", "dominicana"],
    "Guatemala": ["guatemala"],
    "Venezuela": ["venezuela", "venezolansk"],
    "Panama": ["panama"],
    "Guyana": ["guyana", "demerara"],
    "Trinidad": ["trinidad"],
    "Martinique": ["martinique"],
    "Nicaragua": ["nicaragua"],
    "Peru": ["peru"],
    "Colombia": ["colombia"],
    "Brasilien": ["brasilien", "brazil", "brasileiro"],
    "Filippinerne": ["filippin", "philippines"],
    "Dansk": ["dansk rom", "danish rum", "denmark"],
    "Østrig": ["østrig", "austria"],
}


def extract_country(name, brand=None, tags=None, categories=None, description="", short_desc=""):
    """Find oprindelsesland"""
    # 1. Hvis vi kender brandet, slå op
    if brand and brand in BRAND_COUNTRY_MAP:
        return BRAND_COUNTRY_MAP[brand]

    # 2. Søg i tags
    if tags:
        for tag in tags:
            tag_name = (tag.get("name", "") if isinstance(tag, dict) else str(tag)).lower()
            for country, keywords in COUNTRY_KEYWORDS.items():
                if any(kw in tag_name for kw in keywords):
                    return country

    # 3. Søg i kategorier
    if categories:
        for cat in categories:
            cat_name = (cat.get("name", "") if isinstance(cat, dict) else str(cat)).lower()
            for country, keywords in COUNTRY_KEYWORDS.items():
                if any(kw in cat_name for kw in keywords):
                    return country

    # 4. Søg i navn + beskrivelse
    text = (name or "") + " " + clean_html(short_desc) + " " + clean_html(description)
    text_lower = text.lower()
    for country, keywords in COUNTRY_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            return country

    return None


# ────────────────────────────────────────────────────────────
# TYPE EXTRACTION
# ────────────────────────────────────────────────────────────
def extract_type(name, age=None, tags=None, categories=None, description="", short_desc=""):
    """Find rom-type"""
    text = (name or "") + " " + clean_html(short_desc) + " " + clean_html(description)
    
    if tags:
        text += " " + " ".join((t.get("name", "") if isinstance(t, dict) else str(t)) for t in tags)
    if categories:
        text += " " + " ".join((c.get("name", "") if isinstance(c, dict) else str(c)) for c in categories)
    
    text_lower = text.lower()

    # Mest specifik først
    if "agricole" in text_lower or "rhum agricole" in text_lower:
        return "Rhum Agricole"
    if "overproof" in text_lower or "navy strength" in text_lower:
        return "Overproof"
    if "navy" in text_lower:
        return "Navy Rum"
    if "spiced" in text_lower or "krydret" in text_lower:
        return "Spiced"
    if "cachaç" in text_lower or "cachac" in text_lower:
        return "Cachaça"
    if "white rum" in text_lower or "lys rom" in text_lower or "hvid rom" in text_lower or "blanc" in text_lower:
        return "Hvid rom"
    if "gold rum" in text_lower or "golden rum" in text_lower or "gylden rom" in text_lower:
        return "Gylden rom"
    if "dark rum" in text_lower or "mørk rom" in text_lower or "black rum" in text_lower:
        return "Mørk rom"

    # Hvis vi har en alder, så er det aged rom
    if age:
        return "Aged rom"

    if "aged" in text_lower or "extra old" in text_lower or "solera" in text_lower or "reserva" in text_lower:
        return "Aged rom"

    return None


# ────────────────────────────────────────────────────────────
# EDITION KEYWORDS — vigtigt for matching
# ────────────────────────────────────────────────────────────
EDITION_KEYWORDS = [
    "edición negra", "edicion negra",
    "single cask",
    "limited edition",
    "special reserve",
    "exceptional cask",
    "penultimus",
    "vintage",
    "anniversary",
    "armonia", "la armonia",
    "el alma",
    "la doma",
    "la pasion", "la pasión",
    "heavenly casks", "heavenly cask",
    "passion cask",
    "ambar",
    "cognac cask", "sherry cask", "port cask", "wine cask",
    "master blender",
]


# Butikkerne staver fadlagrings-finish forskelligt: "Port Finish", "Port Casks", "Oloroso Cask", "Sherry Cask Finish".
# De samles til ét nøgleord pr. type, så det ikke afviser den samme flaske som to forskellige udgaver.
_FINISH_PATTERNS = [
    ("port cask", r"\bport\s+(?:wine\s+)?(?:casks?|finish|fad)\b|\b(?:casks?|finish)\s+port\b"),
    ("sherry cask", r"\bsherry\s+(?:casks?|finish|fad)\b|\boloroso\b|\bpedro\s+ximenez\b|\bpx\s+(?:sherry|casks?|finish)\b|\b(?:casks?|finish)\s+sherry\b"),
    ("cognac cask", r"\bcognac\s+(?:casks?|finish|fad)\b|\b(?:casks?|finish)\s+cognac\b"),
    ("wine cask", r"\b(?:red\s+|white\s+)?wine\s+(?:casks?|finish|fad)\b"),
]


def extract_editions(name, description="", short_desc=""):
    """
    Find edition keywords i navnet/beskrivelsen.
    Returner et set af keywords der findes.
    """
    # Kun NAVNET: beskrivelser nævner ofte andre udgaver ("anniversary", "limited edition"), og så afviste
    # udgave-porten identiske flasker fra to butikker som forskellige produkter.
    text = name or ""
    text_lower = text.lower()
    
    found = set()
    for kw in EDITION_KEYWORDS:
        if kw in text_lower:
            found.add(kw)
    
    for canonical, pattern in _FINISH_PATTERNS:
        if re.search(pattern, text_lower):
            found.add(canonical)

    return found


# ────────────────────────────────────────────────────────────
# HTML FALLBACK — hent produktside hvis data mangler
# ────────────────────────────────────────────────────────────
def enrich_from_html(url, cache=None):
    """
    Hent produktside HTML og prøv at finde mere info.
    Returner dict med eventuel ABV, volume, age osv.
    """
    if cache is None:
        cache = {}
    
    if url in cache:
        return cache[url]
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            cache[url] = {}
            return {}
        html = r.text
    except Exception as e:
        cache[url] = {}
        return {}
    
    # Parse HTML for facts
    clean_text = clean_html(html)
    
    result = {}
    result["abv"] = extract_abv("", "", clean_text)
    result["volume_cl"] = extract_volume("", "", clean_text)
    result["age"] = extract_age("", "", clean_text)
    
    # Vær venlig mod serveren
    time.sleep(0.3)
    
    cache[url] = result
    return result


# ────────────────────────────────────────────────────────────
# HOVED-FUNKTION — extract alt på én gang
# ────────────────────────────────────────────────────────────
def parse_product(product):
    """
    Hovedfunktion: tag et WooCommerce produkt-dict og udtræk alle felter.
    """
    name = product.get("name", "").strip()
    slug = product.get("slug", "")
    short_desc = product.get("short_description", "")
    description = product.get("description", "")
    brands_field = product.get("brands", [])
    tags = product.get("tags", [])
    categories = product.get("categories", [])

    # Træk ud
    brand = extract_brand(name, slug, brands_field, tags)
    volume_cl = extract_volume(name, slug, description, short_desc)
    abv = extract_abv(name, slug, description, short_desc)
    age = extract_age(name, slug, description, short_desc)
    country = extract_country(name, brand, tags, categories, description, short_desc)
    rom_type = extract_type(name, age, tags, categories, description, short_desc)
    editions = extract_editions(name, description, short_desc)

    return {
        "name": name,
        "brand": brand,
        "volume_cl": volume_cl,
        "abv": abv,
        "age": age,
        "country": country,
        "type": rom_type,
        "editions": editions,
    }


# ────────────────────────────────────────────────────────────
# TEST når kørt direkte
# ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Test eksempler
    tests = [
        {
            "name": "Ron Zacapa Centenario 23 SISTEMA SOLERA Gran Reserva",
            "slug": "ron-zacapa-centenario-23-sistema-solera-gran-reserva",
            "short_description": "<p>Ron Zacapa 23 år 40%</p>",
            "description": "",
            "brands": [],
            "tags": [{"name": "Guatemala"}, {"name": "Rom"}],
            "categories": [],
        },
        {
            "name": "Ron Zacapa Armonia Heavenly Casks 40%,",
            "slug": "ron-zacapa-armonia-heavenly-casks-40",
            "short_description": "",
            "description": "<p>Solera rom 40%, 70cl</p>",
            "brands": [],
            "tags": [{"name": "Guatemala"}, {"name": "Ron Zacapa"}, {"name": "Armonia"}],
            "categories": [],
        },
        {
            "name": "Zacapa 12 Y.O. Ambar 1L",
            "slug": "zacapa-12-y-o-ambar-1l",
            "short_description": "",
            "description": "",
            "brands": [],
            "tags": [],
            "categories": [{"name": "Zacapa"}],
        },
    ]
    
    for test in tests:
        result = parse_product(test)
        print(f"\n📦 {result['name']}")
        print(f"   Brand:   {result['brand']}")
        print(f"   Volume:  {result['volume_cl']} cl")
        print(f"   ABV:     {result['abv']}%")
        print(f"   Alder:   {result['age']}")
        print(f"   Land:    {result['country']}")
        print(f"   Type:    {result['type']}")
        print(f"   Editions: {result['editions']}")
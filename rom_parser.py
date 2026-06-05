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
def extract_abv(name, slug="", description="", short_desc=""):
    """
    Find ABV. Rom er typisk 35-75%.
    """
    name = name or ""
    slug = slug or ""
    desc = clean_html(description) if description else ""
    short = clean_html(short_desc) if short_desc else ""

    sources = [name, short, desc]

    for source in sources:
        # "alkoholprocent på X" - dansk forklarende
        m = re.search(r"alkoholprocent\s+(?:på|:)\s*(\d+(?:[.,]\d+)?)", source, re.IGNORECASE)
        if m:
            val = float(m.group(1).replace(",", "."))
            if 30 <= val <= 80:
                return val

        # Standard "X%" mønster
        matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*%", source)
        for match in matches:
            val = float(match.replace(",", "."))
            if 30 <= val <= 80:
                return val

    # Slug fallback - "armonia-40" eller "rum-57" mønster (sidste tal i slug)
    if slug:
        # Match tal i slug der kunne være ABV (40, 43, 46, 57 osv.)
        slug_clean = slug.lower().replace("-", " ")
        # Find tal der står alene (ikke som del af alder som "23")
        # Vi leder efter typiske ABV-tal: 35-75
        nums = re.findall(r"\b(\d{2})\b", slug_clean)
        for num in nums:
            val = int(num)
            if 35 <= val <= 75:
                # Skip hvis det også kunne være alder (12, 15, 18, 20-25)
                if val not in [12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25]:
                    return float(val)

    return None


# ────────────────────────────────────────────────────────────
# AGE EXTRACTION
# ────────────────────────────────────────────────────────────
def extract_age(name, slug="", description="", short_desc=""):
    """
    Find alder: 12 år, XO, Solera, Reserva.
    """
    sources = [name or "", clean_html(short_desc) if short_desc else "", clean_html(description) if description else ""]

    # Slug kan også indeholde alder
    if slug:
        slug_clean = slug.lower().replace("-", " ").replace("_", " ")
        sources.insert(1, slug_clean)

    for source in sources:
        source_lower = source.lower()

        # "XO" - skal stå alene
        if re.search(r"\bxo\b", source_lower):
            return "XO"

        # "Solera" som standalone alder
        if "solera" in source_lower:
            # Men ikke hvis der også er et tal (så er det fx "23 år Solera")
            year_match = re.search(r"(\d+)\s*(?:år|years?|y\.?o\.?|ans)", source_lower)
            if year_match:
                age = int(year_match.group(1))
                if 1 <= age <= 50:
                    return f"{age} år"
            return "Solera"

        # Eksplicit alder
        age_patterns = [
            r"(\d+)\s*år",
            r"(\d+)\s*years?",
            r"(\d+)\s*y\.?o\.?",
            r"(\d+)\s*-?\s*y\.?o\.?",  # "12-Y-O" eller "12 yo"
            r"(\d+)\s*ans",
            r"aged\s+(\d+)",
        ]
        for pattern in age_patterns:
            m = re.search(pattern, source_lower)
            if m:
                age = int(m.group(1))
                if 1 <= age <= 50:
                    return f"{age} år"

        # Reserva uden specifik alder
        if re.search(r"\breserva\b", source_lower) and "gran reserva" not in source_lower:
            return "Reserva"

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


def extract_editions(name, description="", short_desc=""):
    """
    Find edition keywords i navnet/beskrivelsen.
    Returner et set af keywords der findes.
    """
    text = (name or "") + " " + clean_html(short_desc) + " " + clean_html(description)
    text_lower = text.lower()
    
    found = set()
    for kw in EDITION_KEYWORDS:
        if kw in text_lower:
            found.add(kw)
    
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
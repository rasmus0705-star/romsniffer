"""
conmaz_rom.py — Scraper for Con Maz (conmaz.dk), WooCommerce Store API v1.

Con Maz eksponerer strukturerede attributter — Land, Lagring, ABV, Stoerrelse —
hvilket er langt mere paalideligt end at udlede felterne fra produktnavnet.
Vi bruger dem derfor direkte, med navne-udtraek som fallback.

VIGTIGT om brand: butikkens 'Producent' er DESTILLERIET (fx "Clarendon
Distillery"), ikke brandet (fx "Rest & Be Thankful"). Bruges destilleriet som
brand, afviser brand_gate aegte match mod andre butikker. Brand hentes derfor
med rom_parser.extract_brand() som i de oevrige scrapere.
"""
import re
import time
from html import unescape

import requests

from rom_parser import (
    extract_abv,
    extract_age,
    extract_brand,
    extract_editions,
    extract_type,
    extract_volume,
)

SHOP_NAME = "Con Maz"
BASE = "https://conmaz.dk/wp-json/wc/store/v1/products"
ROM_CATEGORY = 229          # "Rom" (84 produkter)
SUGAR_CANE_CATEGORY = 865   # "Spiritus baseret paa sukkerroer" (cachaca m.m.)

PER_PAGE = 100
MAX_PAGES = 10
PAUSE = 1.0                 # hoeflighed mod en lille butik

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Con Maz-landenavne -> pipelinens vokabular
COUNTRY_MAP = {
    "den dominikanske republik": "Dominikansk",
    "dominikanske republik": "Dominikansk",
    "trinidad & tobago": "Trinidad",
    "trinidad og tobago": "Trinidad",
    "st. lucia": "Saint Lucia",
    "reunion": "Réunion",
}


# ────────────────────────────────────────────────────────────
# ATTRIBUT-HJAELPERE
# ────────────────────────────────────────────────────────────

def _attr_map(product):
    """
    Byg {attributnavn_lowercase: [term-navne]} fra Store API-attributter.
    """
    out = {}
    for attr in product.get("attributes") or []:
        navn = (attr.get("name") or attr.get("taxonomy") or "").strip().lower()
        if not navn:
            continue
        terms = [unescape(t.get("name", "")).strip()
                 for t in (attr.get("terms") or [])
                 if t.get("name")]
        if not terms and attr.get("value"):
            terms = [unescape(str(attr["value"])).strip()]
        if terms:
            out[navn] = terms
    return out


def parse_age(vaerdi):
    """
    'Lagring' -> alder i pipelinens format ("12 aar") eller None.

    NAS  = No Age Statement       -> None
    0 aar                          -> None (ulagret)
    5-15 aar / 5-10 aar (interval) -> None (for upraecist til age_gate)
    8,5 aar / 10.50 aar            -> "8 aar" / "10 aar" (heltal, saa den
                                      matcher andre butikkers angivelse)
    """
    if not vaerdi:
        return None
    v = str(vaerdi).strip().lower()

    if "nas" in v:
        return None

    # Interval: 5-15 år, 5-10 år
    if re.search(r"\d\s*[-–]\s*\d", v):
        return None

    m = re.search(r"(\d+(?:[.,]\d+)?)", v)
    if not m:
        return None
    try:
        tal = float(m.group(1).replace(",", "."))
    except ValueError:
        return None

    if tal <= 0 or tal > 80:
        return None

    return f"{int(tal)} år"


def parse_abv(vaerdi):
    """'52.40%' / '58.60' / '52.40%, 58.60' -> float eller None."""
    if not vaerdi:
        return None
    m = re.search(r"(\d{1,2}(?:[.,]\d{1,2})?)", str(vaerdi))
    if not m:
        return None
    try:
        val = float(m.group(1).replace(",", "."))
    except ValueError:
        return None
    return val if 15 <= val <= 80 else None


def parse_volume(vaerdi):
    """'0,7 L' / '70 cl' / '700 ml' / '1,5 L' -> cl eller None."""
    if not vaerdi:
        return None
    v = str(vaerdi).strip().lower().replace(",", ".")

    m = re.search(r"(\d+(?:\.\d+)?)\s*cl", v)
    if m:
        cl = float(m.group(1))
    else:
        m = re.search(r"(\d+(?:\.\d+)?)\s*ml", v)
        if m:
            cl = float(m.group(1)) / 10
        else:
            m = re.search(r"(\d+(?:\.\d+)?)\s*l", v)
            if m:
                cl = float(m.group(1)) * 100
            else:
                return None

    return cl if 1 <= cl <= 500 else None


def parse_country(vaerdi):
    """'Den Dominikanske Republik' -> 'Dominikansk'."""
    if not vaerdi:
        return None
    v = str(vaerdi).strip()
    return COUNTRY_MAP.get(v.lower(), v)


def parse_prices(product):
    """
    Store API angiver priser i mindste enhed (oere).
    Returnerer (price, old_price, discount_pct).
    """
    p = product.get("prices") or {}
    minor = p.get("currency_minor_unit", 2)
    faktor = 10 ** int(minor) if minor else 1

    def _tal(x):
        if x in (None, ""):
            return None
        try:
            return float(x) / faktor
        except (TypeError, ValueError):
            return None

    pris = _tal(p.get("price"))
    regulaer = _tal(p.get("regular_price"))
    tilbud = _tal(p.get("sale_price"))

    if pris is None:
        return None, None, None

    old_price = None
    discount = None
    if product.get("on_sale") and regulaer and regulaer > pris:
        old_price = regulaer
        discount = round(100 * (regulaer - pris) / regulaer, 1)
    elif tilbud and regulaer and regulaer > tilbud:
        old_price = regulaer
        discount = round(100 * (regulaer - tilbud) / regulaer, 1)

    return pris, old_price, discount


def build_item(product):
    """Konvertér et Store API-produkt til pipelinens item-dict."""
    navn = product.get("name") or ""
    if not navn:
        return None

    pris, old_price, discount = parse_prices(product)
    if pris is None or pris <= 0:
        return None

    attrs = _attr_map(product)

    def a(*navne):
        for n in navne:
            if n in attrs and attrs[n]:
                return attrs[n][0]
        return None

    slug = product.get("slug") or ""
    desc = product.get("description") or ""
    short = product.get("short_description") or ""

    # Attributter foerst, navne-udtraek som fallback
    age = parse_age(a("lagring")) or extract_age(navn, slug=slug)
    abv = parse_abv(a("abv", "alkohol", "alkoholprocent")) or extract_abv(navn, slug=slug)
    volume = parse_volume(a("størrelse", "stoerrelse", "size")) or extract_volume(navn, slug=slug)
    country = parse_country(a("land")) or None

    billede = None
    imgs = product.get("images") or []
    if imgs:
        billede = imgs[0].get("src") or imgs[0].get("thumbnail")

    return {
        "name": navn,
        "shop_name": SHOP_NAME,
        "price": pris,
        "old_price": old_price,
        "discount_pct": discount,
        "url": product.get("permalink"),
        "image": billede,
        "brand": extract_brand(navn, slug=slug),
        "age": age,
        "abv": abv,
        "volume_cl": volume,
        "country": country,
        "type": extract_type(navn, age=age, description=desc, short_desc=short),
        "editions": extract_editions(navn, description=desc, short_desc=short),
        "sku": product.get("sku"),
    }


# ────────────────────────────────────────────────────────────
# HOVEDFUNKTION
# ────────────────────────────────────────────────────────────

def _hent_kategori(cat_id, kun_paa_lager=True):
    """Hent alle produkter i én kategori."""
    items = []
    for side in range(1, MAX_PAGES + 1):
        url = f"{BASE}?category={cat_id}&per_page={PER_PAGE}&page={side}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
        except Exception as e:
            print(f"   ⚠️  Netvaerksfejl side {side}: {e}")
            break

        if r.status_code == 400:
            break          # ingen flere sider
        if r.status_code != 200:
            print(f"   ❌ HTTP {r.status_code} paa side {side}")
            break

        try:
            data = r.json()
        except ValueError:
            print(f"   ❌ Ugyldigt JSON paa side {side}")
            break

        if not data:
            break

        print(f"   📦 Side {side}: {len(data)} produkter")
        for p in data:
            if kun_paa_lager and not p.get("is_in_stock", True):
                continue
            it = build_item(p)
            if it:
                items.append(it)

        if len(data) < PER_PAGE:
            break
        time.sleep(PAUSE)

    return items


def scrape_conmaz_rom(inkluder_sukkerroer=True):
    """
    Hent alle rom fra Con Maz.

    inkluder_sukkerroer: medtag ogsaa kategorien "Spiritus baseret paa
    sukkerroer" (cachaca, clairin m.m. — 17 produkter).
    """
    print("🥃 Henter rom fra Con Maz (WooCommerce Store API)...")

    items = _hent_kategori(ROM_CATEGORY)

    if inkluder_sukkerroer:
        print("   🌿 Henter sukkerroer-baseret spiritus...")
        time.sleep(PAUSE)
        set_urls = {i["url"] for i in items}
        for it in _hent_kategori(SUGAR_CANE_CATEGORY):
            if it["url"] not in set_urls:
                items.append(it)

    print(f"\n✅ {len(items)} rom-produkter hentet fra Con Maz")
    return items


# ────────────────────────────────────────────────────────────
# SELVTEST — parsing mod faktiske vaerdier fra sonden
# ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("── parse_age ──")
    for ind, ventet in [
        ("24 år", "24 år"), ("12 år", "12 år"), ("3 år", "3 år"),
        ("NAS", None), ("0 år", None),
        ("5-15 år", None), ("5-10 år", None),
        ("8,5 år", "8 år"), ("10.50 år", "10 år"),
        ("1 år", "1 år"), ("", None), (None, None),
    ]:
        fik = parse_age(ind)
        print(f"   {'OK  ' if fik == ventet else 'FEJL'} {str(ind):>10s} -> {str(fik):>7s}  (ventet {ventet})")

    print("\n── parse_abv ──")
    for ind, ventet in [
        ("52.40%", 52.4), ("58.60", 58.6), ("52.40%, 58.60", 52.4),
        ("40%", 40.0), ("", None), ("abc", None), ("5", None),
    ]:
        fik = parse_abv(ind)
        print(f"   {'OK  ' if fik == ventet else 'FEJL'} {str(ind):>16s} -> {str(fik):>6s}  (ventet {ventet})")

    print("\n── parse_volume ──")
    for ind, ventet in [
        ("0,7 L", 70.0), ("0.7 L", 70.0), ("70 cl", 70.0),
        ("700 ml", 70.0), ("1,5 L", 150.0), ("20 cl", 20.0),
        ("", None), ("N/A", None),
    ]:
        fik = parse_volume(ind)
        print(f"   {'OK  ' if fik == ventet else 'FEJL'} {str(ind):>10s} -> {str(fik):>7s}  (ventet {ventet})")

    print("\n── parse_prices (oere -> kroner) ──")
    tests = [
        ({"prices": {"price": "269800", "regular_price": "269800",
                     "sale_price": "269800", "currency_minor_unit": 2},
          "on_sale": False}, (2698.0, None, None)),
        ({"prices": {"price": "74900", "regular_price": "99900",
                     "sale_price": "74900", "currency_minor_unit": 2},
          "on_sale": True}, (749.0, 999.0, 25.0)),
        ({"prices": {"price": "49900", "regular_price": "49900",
                     "sale_price": "49900", "currency_minor_unit": 2},
          "on_sale": False}, (499.0, None, None)),
    ]
    for prod, ventet in tests:
        fik = parse_prices(prod)
        print(f"   {'OK  ' if fik == ventet else 'FEJL'} {fik}  (ventet {ventet})")

    print("\n── parse_country ──")
    for ind, ventet in [
        ("Den Dominikanske Republik", "Dominikansk"),
        ("Trinidad & Tobago", "Trinidad"),
        ("Jamaica", "Jamaica"), ("Barbados", "Barbados"),
    ]:
        fik = parse_country(ind)
        print(f"   {'OK  ' if fik == ventet else 'FEJL'} {ind:>28s} -> {fik}")

    print("\n── _attr_map paa faktisk sonde-output ──")
    prod = {"attributes": [
        {"id": 10, "name": "Land", "taxonomy": "pa_land",
         "terms": [{"id": 786, "name": "Jamaica", "slug": "jamaica"}]},
        {"id": 11, "name": "Producent", "taxonomy": "pa_producent",
         "terms": [{"id": 902, "name": "Clarendon Distillery"}]},
        {"id": 12, "name": "Lagring", "taxonomy": "pa_lagring",
         "terms": [{"name": "24 år"}]},
        {"id": 13, "name": "ABV", "terms": [{"name": "52.40%"}, {"name": "58.60"}]},
        {"id": 14, "name": "Størrelse", "terms": [{"name": "0,7 L"}]},
    ]}
    m = _attr_map(prod)
    for k, v in m.items():
        print(f"   {k:12s} = {v}")
    print(f"\n   -> age    = {parse_age(m['lagring'][0])}")
    print(f"   -> abv    = {parse_abv(m['abv'][0])}")
    print(f"   -> volume = {parse_volume(m['størrelse'][0])}")
    print(f"   -> land   = {parse_country(m['land'][0])}")
"""
whiskydk_rom.py — Scraper for whisky.dk, DanDomain-platform.

whisky.dk kører DanDomain og eksponerer ingen API.
Vi scraper HTML-kategorisiden side for side.

Specs (ABV, volumen, land) udtrækkes fra USP-beskrivelsens
"Specifikationer"-afsnit, med rom_parser som fallback på navn/slug.
"""

import re
import time

import requests
from bs4 import BeautifulSoup

from rom_parser import (
    extract_abv,
    extract_age,
    extract_brand,
    extract_editions,
    extract_type,
    extract_volume,
)

SHOP_NAME   = "Whisky.dk"
BASE_URL    = "https://www.whisky.dk"
CAT_URL     = "https://www.whisky.dk/shop/rom-4s{page}.html"
MAX_PAGES   = 40
PAUSE       = 1.5   # DanDomain er ikke en stor server

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "da-DK,da;q=0.9",
}


# ────────────────────────────────────────────────────────────
# SPEC-UDTRAEK FRA USP-TEKST
# ────────────────────────────────────────────────────────────

def _specs_from_usp(usp_text: str) -> dict:
    """
    Udtraek ABV, volumen og land fra 'Specifikationer'-afsnittet i USP-teksten.

    Eksempel-linjer:
        ABV: 42%
        Størrelse: 70 CL
        Region/Land: Guatemala og Belize
    """
    out = {}
    if not usp_text:
        return out

    # ABV
    m = re.search(r"ABV\s*:\s*(\d{1,2}(?:[.,]\d{1,2})?)\s*%", usp_text, re.I)
    if m:
        try:
            val = float(m.group(1).replace(",", "."))
            if 15 <= val <= 80:
                out["abv"] = val
        except ValueError:
            pass

    # Størrelse / volumen
    m = re.search(
        r"St(?:ø|oe)rrelse\s*:\s*(\d+(?:[.,]\d+)?)\s*(CL|ML|L)\b",
        usp_text, re.I
    )
    if m:
        try:
            tal = float(m.group(1).replace(",", "."))
            enhed = m.group(2).upper()
            if enhed == "CL":
                cl = tal
            elif enhed == "ML":
                cl = tal / 10
            else:  # L
                cl = tal * 100
            if 1 <= cl <= 500:
                out["volume_cl"] = cl
        except ValueError:
            pass

    # Land / Region
    m = re.search(r"(?:Region/)?Land\s*:\s*(.+)", usp_text, re.I)
    if m:
        land = m.group(1).strip().split("\n")[0].strip()
        if land:
            out["country"] = land

    return out


# ────────────────────────────────────────────────────────────
# PRODUKT-PARSING
# ────────────────────────────────────────────────────────────

def _parse_product(div) -> dict | None:
    """Konvertér ét .product-div til pipelinens item-dict."""

    # Navn
    name_tag = div.select_one(".information .name a")
    if not name_tag:
        return None
    navn = name_tag.get_text(strip=True)
    if not navn:
        return None

    # URL
    href = name_tag.get("href", "")
    url = href if href.startswith("http") else BASE_URL + href

    # Slug (til rom_parser-fallbacks)
    slug = re.sub(r"[^a-z0-9]+", "-", navn.lower()).strip("-")

    # Pris (actualPrice > span[itemprop=price] > content-attribut)
    pris = None
    price_span = div.select_one("span[itemprop='price']")
    if price_span:
        raw = price_span.get("content") or price_span.get_text(strip=True)
        raw = raw.replace(",", ".").replace(".", "", raw.count(".") - 1)
        try:
            pris = float(raw.replace(",", "."))
        except ValueError:
            pass

    if pris is None or pris <= 0:
        return None

    # Tilbudspris (price-before)
    old_price   = None
    discount    = None
    before_div  = div.select_one(".price-before")
    if before_div:
        raw_before = before_div.get_text(strip=True).replace(".", "").replace(",", ".")
        m = re.search(r"(\d+(?:\.\d+)?)", raw_before)
        if m:
            try:
                op = float(m.group(1))
                if op > pris:
                    old_price = op
                    discount  = round(100 * (op - pris) / op, 1)
            except ValueError:
                pass

    # Billede
    img_tag = div.select_one(".image img")
    billede = None
    if img_tag:
        src = img_tag.get("src", "")
        # Fjern width-parameter for at få fuld opløsning
        billede = re.sub(r"\?.*$", "", src)

    # USP-tekst til spec-udtræk
    usp_div  = div.select_one(".usp")
    usp_text = usp_div.get_text(separator="\n") if usp_div else ""
    specs    = _specs_from_usp(usp_text)

    # Beskrivelse til extract_type / extract_editions
    desc  = usp_div.get_text(" ") if usp_div else ""
    short = ""

    return {
        "name":        navn,
        "shop_name":   SHOP_NAME,
        "price":       pris,
        "old_price":   old_price,
        "discount_pct": discount,
        "url":         url,
        "image":       billede,
        "brand":       extract_brand(navn, slug=slug),
        "age":         extract_age(navn, slug=slug),
        "abv":         specs.get("abv")       or extract_abv(navn, slug=slug),
        "volume_cl":   specs.get("volume_cl") or extract_volume(navn, slug=slug),
        "country":     specs.get("country"),
        "type":        extract_type(navn, description=desc, short_desc=short),
        "editions":    extract_editions(navn, description=desc, short_desc=short),
        "sku":         div.get("data-productnumber"),
    }


# ────────────────────────────────────────────────────────────
# PAGINATION
# ────────────────────────────────────────────────────────────

def _max_page(soup) -> int:
    """Find højeste sidenummer fra pagineringslinks."""
    highest = 1
    for a in soup.select("a[href]"):
        m = re.search(r"rom-4s(\d+)\.html", a["href"])
        if m:
            highest = max(highest, int(m.group(1)))
    return highest


# ────────────────────────────────────────────────────────────
# HOVEDFUNKTION
# ────────────────────────────────────────────────────────────

def scrape_whiskydk_rom() -> list[dict]:
    """Hent alle rom-produkter fra whisky.dk."""
    print("🥃 Henter rom fra whisky.dk (DanDomain HTML-scraping)...")

    items     = []
    set_urls  = set()
    max_page  = MAX_PAGES

    for page in range(1, MAX_PAGES + 1):
        url = CAT_URL.format(page=page)
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
        except Exception as e:
            print(f"   ⚠️  Netværksfejl side {page}: {e}")
            break

        if r.status_code != 200:
            print(f"   ❌ HTTP {r.status_code} på side {page} — stopper")
            break

        soup     = BeautifulSoup(r.text, "html.parser")
        products = soup.select(".product")

        if not products:
            print(f"   ℹ️  Ingen produkter på side {page} — stopper")
            break

        # Find maks-side fra første side
        if page == 1:
            max_page = min(_max_page(soup), MAX_PAGES)
            print(f"   📄 {max_page} sider fundet")

        print(f"   📦 Side {page}/{max_page}: {len(products)} produkter")

        for div in products:
            item = _parse_product(div)
            if item and item["url"] not in set_urls:
                set_urls.add(item["url"])
                items.append(item)

        if page >= max_page:
            break

        time.sleep(PAUSE)

    print(f"\n✅ {len(items)} rom-produkter hentet fra whisky.dk")
    return items


# ────────────────────────────────────────────────────────────
# SELVTEST
# ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("── _specs_from_usp ──")
    tests = [
        ("ABV: 42%\nStørrelse: 70 CL\nRegion/Land: Jamaica",
         {"abv": 42.0, "volume_cl": 70.0, "country": "Jamaica"}),
        ("ABV: 58,30%\nStørrelse: 700 ML\nRegion/Land: Barbados",
         {"abv": 58.3, "volume_cl": 70.0, "country": "Barbados"}),
        ("ABV: 40%\nStørrelse: 1 L\nLand: Cuba",
         {"abv": 40.0, "volume_cl": 100.0, "country": "Cuba"}),
        ("Ingen specs her", {}),
    ]
    for tekst, ventet in tests:
        fik = _specs_from_usp(tekst)
        ok  = fik == ventet
        print(f"   {'OK  ' if ok else 'FEJL'} {fik}  (ventet {ventet})")

    print("\n── Fuld scrape ──")
    produkter = scrape_whiskydk_rom()
    if produkter:
        p = produkter[0]
        print(f"\nFørste produkt:")
        for k, v in p.items():
            print(f"  {k:12s}: {v}")

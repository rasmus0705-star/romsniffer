"""
juuls_rom.py — Scraper for Juul's Vin & Spiritus (juuls.dk).

juuls.dk eksponerer /system/data/products-with-filters, som returnerer JSON,
men hvert produkt er en HTML-streng (listItemHtml). Kategori-filtrering via
URL virker ikke, saa vi henter HELE kataloget (ca. 46 sider a 100) og
beholder kun produkter med data-product-category2 i ROM_KATEGORIER.

Data i listItemHtml:
  data-product-name / -price / -number / -category2  (paa yderste div)
  h3.e-productlist-item-name a[href]                  -> URL
  img.e-productlist-item-image[src]                   -> billede
  .custom-product-list-item-spiritinfo-container      -> "Mørk rom fra Jamaica" + "70cl · 46% vol"
  .custom-productlist-stock-state p[class]            -> lagerstatus
"""

import re
import time
from collections import Counter
from html import unescape

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

SHOP_NAME = "Juuls"
BASE_URL  = "https://www.juuls.dk"
API_URL   = (BASE_URL + "/system/data/products-with-filters"
             "?GroupID={group}&PageNum={page}&PageSize={size}")

ROM_GROUP = "GROUP336"   # /rom
PAGE_SIZE = 100
MAX_PAGES = 30           # sikkerhedsloft — stopper normalt ved tom/gentaget side
PAUSE     = 1.0

# Gruppen er allerede rom; category2 bruges kun som rapport i selvtesten.
# Saet FILTRER_KATEGORI = True hvis gruppen viser sig at indeholde andet end rom.
FILTRER_KATEGORI = False
ROM_KATEGORIER = {"rom"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.juuls.dk/rom",
}


# ────────────────────────────────────────────────────────────
# HJAELPERE
# ────────────────────────────────────────────────────────────

def _to_float(txt):
    """'1.299,00' / '229.00' / '189,00' -> float eller None."""
    if not txt:
        return None
    t = str(txt).strip()
    if "," in t:                       # dansk format
        t = t.replace(".", "").replace(",", ".")
    m = re.search(r"\d+(?:\.\d+)?", t)
    return float(m.group(0)) if m else None


COUNTRY_MAP = {
    "reunion": "Réunion",
    "den dominikanske republik": "Dominikansk",
    "dominikanske republik": "Dominikansk",
    "trinidad & tobago": "Trinidad",
    "trinidad og tobago": "Trinidad",
    "st. lucia": "Saint Lucia",
}


def _norm_country(land):
    """'Guadeloupe (Frankrig)' -> 'Guadeloupe', 'Reunion (Frankrig)' -> 'Réunion'."""
    if not land:
        return None
    v = re.sub(r"\s*\(.*?\)\s*", "", land).strip()
    return COUNTRY_MAP.get(v.lower(), v) or None


def _parse_spiritinfo(soup):
    """
    Returnér (typetekst, land, volume_cl, abv) fra infoboksen:
        <p>Mørk rom <span>fra Jamaica</span></p>
        <p class="text-nowrap">70cl · 46% vol</p>
    """
    box = soup.select_one(".custom-product-list-item-spiritinfo-container")
    if not box:
        return None, None, None, None

    typetekst = land = volume = abv = None

    span = box.select_one("span")
    if span:
        land = re.sub(r"^\s*fra\s+", "", span.get_text(" ", strip=True), flags=re.I) or None
        span_txt = span.get_text(" ", strip=True)
        first_p = span.find_parent("p")
        if first_p:
            typetekst = first_p.get_text(" ", strip=True).replace(span_txt, "").strip() or None

    info = box.get_text(" ", strip=True)

    m = re.search(r"(\d+(?:[.,]\d+)?)\s*cl", info, re.I)
    if m:
        cl = float(m.group(1).replace(",", "."))
        if 1 <= cl <= 500:
            volume = cl

    m = re.search(r"(\d{1,2}(?:[.,]\d{1,2})?)\s*%\s*vol", info, re.I)
    if m:
        val = float(m.group(1).replace(",", "."))
        if 15 <= val <= 80:
            abv = val

    return typetekst, land, volume, abv


def _paa_lager(soup):
    """True medmindre lagerfeltet tydeligt siger udsolgt."""
    p = soup.select_one(".custom-productlist-stock-state p")
    if not p:
        return True
    klasser = " ".join(p.get("class", [])).lower()
    tekst = p.get_text(" ", strip=True).lower()
    if "out" in klasser or "udsolgt" in tekst or "ikke på lager" in tekst:
        return False
    return True


def _old_price(soup, pris):
    """
    Foerpris ved tilbud. Struktur ikke verificeret endnu — vi leder efter en
    overstreget/'before'-pris og accepterer den kun hvis den er hoejere.
    """
    for sel in ["del", "s", "[class*='before']", "[class*='old']", "[class*='normal']"]:
        el = soup.select_one(f".e-productlist-item-price {sel}") or soup.select_one(sel)
        if el:
            op = _to_float(el.get_text(" ", strip=True))
            if op and pris and op > pris:
                return op, round(100 * (op - pris) / op, 1)
    return None, None


# ────────────────────────────────────────────────────────────
# PRODUKT-PARSING
# ────────────────────────────────────────────────────────────

def _build_item(listitem_html):
    soup = BeautifulSoup(listitem_html, "html.parser")
    div = soup.select_one("[data-product-name]")
    if not div:
        return None, None

    cat2 = (div.get("data-product-category2") or "").strip()
    if FILTRER_KATEGORI and cat2.lower() not in ROM_KATEGORIER:
        return None, cat2

    navn = unescape(div.get("data-product-name") or "").strip()
    pris = _to_float(div.get("data-product-price"))
    if not navn or not pris or pris <= 0:
        return None, cat2

    if not _paa_lager(soup):
        return None, cat2

    a = soup.select_one("h3.e-productlist-item-name a") or soup.select_one("a[href*='/varekort/']")
    href = a.get("href", "") if a else ""
    url = href if href.startswith("http") else BASE_URL + href
    slug = href.rstrip("/").split("/")[-1] if href else ""

    img = soup.select_one("img.e-productlist-item-image")
    billede = None
    if img and img.get("src"):
        src = img["src"]
        billede = src if src.startswith("http") else BASE_URL + src

    typetekst, land, vol, abv = _parse_spiritinfo(soup)
    old_price, discount = _old_price(soup, pris)

    desc = typetekst or ""

    item = {
        "name":         navn,
        "shop_name":    SHOP_NAME,
        "price":        pris,
        "old_price":    old_price,
        "discount_pct": discount,
        "url":          url,
        "image":        billede,
        "brand":        extract_brand(navn, slug=slug),
        "age":          extract_age(navn, slug=slug),
        "abv":          abv or extract_abv(navn, slug=slug),
        "volume_cl":    vol or extract_volume(navn, slug=slug),
        "country":      _norm_country(land),
        "type":         extract_type(navn, description=desc, short_desc=""),
        "editions":     extract_editions(navn, description=desc, short_desc=""),
        "sku":          div.get("data-product-number"),
    }
    return item, cat2


# ────────────────────────────────────────────────────────────
# HOVEDFUNKTION
# ────────────────────────────────────────────────────────────

def scrape_juuls_rom(vis_kategorier=False):
    """
    Hent alle rom fra juuls.dk.

    vis_kategorier: print en optaelling af alle category2-vaerdier,
    saa man kan se om der er rom-relaterede kategorier vi mangler.
    """
    print(f"🥃 Henter rom fra Juul's (products-with-filters, {ROM_GROUP})...")

    items, set_urls = [], set()
    set_ids = set()
    kategorier = Counter()

    for page in range(1, MAX_PAGES + 1):
        url = API_URL.format(group=ROM_GROUP, page=page, size=PAGE_SIZE)
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
        except Exception as e:
            print(f"   ⚠️  Netvaerksfejl side {page}: {e}")
            break

        if r.status_code != 200:
            print(f"   ❌ HTTP {r.status_code} paa side {page} — stopper")
            break

        try:
            data = r.json()
        except ValueError:
            print(f"   ❌ Ugyldigt JSON paa side {page}")
            break

        produkter = data.get("products") or []
        if not produkter:
            break

        side_ids = {p.get("id") for p in produkter}
        if side_ids <= set_ids:
            print(f"   ℹ️  Side {page} gentager tidligere produkter — stopper")
            break
        set_ids |= side_ids

        fundet = 0
        for p in produkter:
            item, cat2 = _build_item(p.get("listItemHtml") or "")
            if cat2:
                kategorier[cat2] += 1
            if item and item["url"] not in set_urls:
                set_urls.add(item["url"])
                items.append(item)
                fundet += 1

        print(f"   📦 Side {page}: {len(produkter)} produkter, {fundet} rom")

        if len(produkter) < PAGE_SIZE:
            break
        time.sleep(PAUSE)

    if vis_kategorier:
        print("\n── category2-vaerdier i kataloget ──")
        for k, n in kategorier.most_common():
            mark = "  ✅" if k.lower() in ROM_KATEGORIER else "    "
            print(f"{mark} {k:30s} {n}")

    print(f"\n✅ {len(items)} rom-produkter hentet fra Juul's")
    return items


# ────────────────────────────────────────────────────────────
# SELVTEST
# ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("── _to_float ──")
    for ind, ventet in [("229.00", 229.0), ("189,00", 189.0), ("1.299,00", 1299.0), ("", None)]:
        fik = _to_float(ind)
        print(f"   {'OK  ' if fik == ventet else 'FEJL'} {ind!r:12} -> {fik}")

    print()
    produkter = scrape_juuls_rom(vis_kategorier=True)
    if produkter:
        print("\nFoerste produkt:")
        for k, v in produkter[0].items():
            print(f"  {k:12s}: {v}")

        import random
        print("\nSpot-tjek:")
        for p in random.sample(produkter, min(8, len(produkter))):
            print(f"  {p['name'][:45]:45s} | {p['price']:>8.2f} kr | "
                  f"ABV {p['abv']} | {p['volume_cl']} cl | {p['country']}")

        tilbud = [p for p in produkter if p["old_price"]]
        print(f"\nProdukter med foerpris: {len(tilbud)}")

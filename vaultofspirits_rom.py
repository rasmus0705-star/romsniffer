"""
vaultofspirits_rom.py — Scraper for Vault of Spirits (vaultofspirits.dk),
WooCommerce Store API v1.

Vault of Spirits eksponerer strukturerede attributter via WC Store API:
  pa_abv            → ABV
  pa_land           → oprindelsesland
  pa_flaskestoerrelse → volumen i cl
  pa_aftapper       → aftapper (bruges som brand-fallback)
  pa_aargang        → destillationsårgang

Priser angives i øre (currency_minor_unit=2).

Kategorier der medtages:
  19  — Rom          (forældrekategori, 304 produkter)
  57  — Rombaseret   (29 produkter — cachaca, clairin m.m.)
"""

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

SHOP_NAME = "Vault of Spirits"
BASE      = "https://www.vaultofspirits.dk/wp-json/wc/store/v1/products"

ROM_CATEGORY       = 19   # Rom (forældrekategori)
ROMBASERET_CATEGORY = 57  # Rombaseret (cachaca m.m.)

PER_PAGE  = 100
MAX_PAGES = 20
PAUSE     = 1.0

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


# ────────────────────────────────────────────────────────────
# ATTRIBUT-HJÆLPERE
# ────────────────────────────────────────────────────────────

def _attr_map(product: dict) -> dict:
    """Byg {taxonomy: [term-navne]} fra Store API-attributter."""
    out = {}
    for attr in product.get("attributes") or []:
        tax = (attr.get("taxonomy") or attr.get("name") or "").strip().lower()
        if not tax:
            continue
        terms = [
            unescape(t.get("name", "")).strip()
            for t in (attr.get("terms") or [])
            if t.get("name")
        ]
        if terms:
            out[tax] = terms
    return out


def _parse_prices(product: dict):
    """Returnér (price, old_price, discount_pct) — priser i øre → kroner."""
    p      = product.get("prices") or {}
    minor  = p.get("currency_minor_unit", 2)
    faktor = 10 ** int(minor) if minor else 1

    def _tal(x):
        if x in (None, ""):
            return None
        try:
            return float(x) / faktor
        except (TypeError, ValueError):
            return None

    pris     = _tal(p.get("price"))
    regulaer = _tal(p.get("regular_price"))

    if pris is None or pris <= 0:
        return None, None, None

    old_price = None
    discount  = None
    if product.get("on_sale") and regulaer and regulaer > pris:
        old_price = regulaer
        discount  = round(100 * (regulaer - pris) / regulaer, 1)

    return pris, old_price, discount


# ────────────────────────────────────────────────────────────
# PRODUKT-PARSING
# ────────────────────────────────────────────────────────────

def _build_item(product: dict) -> dict | None:
    navn = unescape(product.get("name") or "")
    if not navn:
        return None

    pris, old_price, discount = _parse_prices(product)
    if pris is None:
        return None

    # Kun produkter der er til salg
    if not product.get("is_purchasable", True):
        return None

    attrs = _attr_map(product)

    def a(*keys):
        for k in keys:
            if k in attrs and attrs[k]:
                return attrs[k][0]
        return None

    slug  = product.get("slug") or ""
    desc  = product.get("description") or ""
    short = product.get("short_description") or ""

    # Volumen: pa_flaskestoerrelse angiver cl direkte som heltal ("70")
    volume_cl = None
    raw_vol = a("pa_flaskestoerrelse")
    if raw_vol:
        try:
            cl = float(raw_vol)
            if 1 <= cl <= 500:
                volume_cl = cl
        except ValueError:
            pass
    if volume_cl is None:
        volume_cl = extract_volume(navn, slug=slug)

    # ABV: pa_abv angiver procent uden %-tegn ("46")
    abv = None
    raw_abv = a("pa_abv")
    if raw_abv:
        try:
            val = float(raw_abv)
            if 15 <= val <= 80:
                abv = val
        except ValueError:
            pass
    if abv is None:
        abv = extract_abv(navn, slug=slug)

    # Land
    country = a("pa_land")

    # Aftapper som brand-fallback
    aftapper = a("pa_aftapper")
    brand    = extract_brand(navn, slug=slug) or aftapper

    # Billede — brug fuld src fremfor thumbnail
    billede = None
    imgs = product.get("images") or []
    if imgs:
        billede = imgs[0].get("src") or imgs[0].get("thumbnail")

    return {
        "name":         navn,
        "shop_name":    SHOP_NAME,
        "price":        pris,
        "old_price":    old_price,
        "discount_pct": discount,
        "url":          product.get("permalink"),
        "image":        billede,
        "brand":        brand,
        "age":          extract_age(navn, slug=slug),
        "abv":          abv,
        "volume_cl":    volume_cl,
        "country":      country,
        "type":         extract_type(navn, description=desc, short_desc=short),
        "editions":     extract_editions(navn, description=desc, short_desc=short),
        "sku":          product.get("sku") or str(product.get("id", "")),
    }


# ────────────────────────────────────────────────────────────
# HENT ÉN KATEGORI
# ────────────────────────────────────────────────────────────

def _hent_kategori(cat_id: int, kun_paa_lager: bool = True) -> list[dict]:
    items = []
    for side in range(1, MAX_PAGES + 1):
        url = f"{BASE}?category={cat_id}&per_page={PER_PAGE}&page={side}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=25)
        except Exception as e:
            print(f"   ⚠️  Netværksfejl side {side}: {e}")
            break

        if r.status_code == 400:
            break
        if r.status_code != 200:
            print(f"   ❌ HTTP {r.status_code} på side {side}")
            break

        try:
            data = r.json()
        except ValueError:
            print(f"   ❌ Ugyldigt JSON på side {side}")
            break

        if not data:
            break

        print(f"   📦 Side {side}: {len(data)} produkter")

        for p in data:
            if kun_paa_lager and not p.get("is_in_stock", True):
                continue
            it = _build_item(p)
            if it:
                items.append(it)

        if len(data) < PER_PAGE:
            break

        time.sleep(PAUSE)

    return items


# ────────────────────────────────────────────────────────────
# HOVEDFUNKTION
# ────────────────────────────────────────────────────────────

def scrape_vaultofspirits_rom(inkluder_rombaseret: bool = True) -> list[dict]:
    """
    Hent alle rom-produkter fra Vault of Spirits.

    inkluder_rombaseret: medtag kategorien 'Rombaseret' (cachaca, clairin m.m.)
    """
    print("🥃 Henter rom fra Vault of Spirits (WooCommerce Store API)...")

    items = _hent_kategori(ROM_CATEGORY)

    if inkluder_rombaseret:
        print("   🌿 Henter rombaseret spiritus...")
        time.sleep(PAUSE)
        set_urls = {i["url"] for i in items}
        for it in _hent_kategori(ROMBASERET_CATEGORY):
            if it["url"] not in set_urls:
                items.append(it)

    print(f"\n✅ {len(items)} rom-produkter hentet fra Vault of Spirits")
    return items


# ────────────────────────────────────────────────────────────
# SELVTEST
# ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    produkter = scrape_vaultofspirits_rom()
    if produkter:
        p = produkter[0]
        print(f"\nFørste produkt:")
        for k, v in p.items():
            print(f"  {k:12s}: {v}")

        print(f"\nSpot-tjek på 5 tilfældige produkter:")
        import random
        for p in random.sample(produkter, min(5, len(produkter))):
            print(f"  {p['name'][:50]:50s} | {p['price']:>8.2f} kr | "
                  f"ABV: {p['abv']} | {p['volume_cl']} cl | {p['country']}")

"""
Rombo.dk — rom scraper via Shopify JSON API.
Bruger rom_parser til smart datauddrag.
Danmarks største rom-butik med ~550 flasker.
"""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import random
import time

import requests
from rom_parser import parse_product

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "da-DK,da;q=0.9,en;q=0.8",
}

BASE_URL = "https://rombo.dk"
COLLECTION = "rom"  # /collections/rom/products.json
MAX_ATTEMPTS = 2
MAX_RETRY_AFTER = 120


class RomboScrapeFejl(Exception):
    def __init__(self, message, *, status_code=None, page=None):
        super().__init__(message)
        self.status_code = status_code
        self.page = page


def _retry_after(response):
    raw = response.headers.get("Retry-After", "").strip()
    if raw.isdigit():
        return min(int(raw), MAX_RETRY_AFTER)
    if raw:
        try:
            when = parsedate_to_datetime(raw)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            return min(max(0, int((when - datetime.now(timezone.utc)).total_seconds())), MAX_RETRY_AFTER)
        except (TypeError, ValueError, OverflowError):
            pass
    return 30


def _get_products(session, url, page):
    last_error = "ukendt fejl"
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = session.get(url, timeout=20)
        except requests.RequestException as exc:
            last_error = f"netværksfejl ({exc.__class__.__name__})"
            if attempt < MAX_ATTEMPTS:
                time.sleep(5)
                continue
            raise RomboScrapeFejl(f"Rombo: {last_error} på side {page}", page=page) from exc

        if response.status_code == 429:
            last_error = "HTTP 429"
            if attempt < MAX_ATTEMPTS:
                delay = _retry_after(response)
                print(f"   ⏳ Rombo: HTTP 429 — venter {delay}s som Shopify beder om, prøver én gang til...")
                time.sleep(delay)
                continue
            raise RomboScrapeFejl(f"Rombo: gav op efter {attempt} forsøg (HTTP 429) på side {page}",
                                  status_code=429, page=page)
        if response.status_code >= 500 and attempt < MAX_ATTEMPTS:
            last_error = f"HTTP {response.status_code}"
            time.sleep(5)
            continue
        if response.status_code == 404 and page > 1:
            return []
        if response.status_code != 200:
            raise RomboScrapeFejl(f"Rombo: HTTP {response.status_code} på side {page}",
                                  status_code=response.status_code, page=page)
        try:
            payload = response.json()
        except ValueError as exc:
            raise RomboScrapeFejl(f"Rombo: ugyldigt JSON-svar på side {page}", page=page) from exc
        products = payload.get("products") if isinstance(payload, dict) else None
        if not isinstance(products, list):
            raise RomboScrapeFejl(f"Rombo: JSON-svaret mangler produktlisten på side {page}", page=page)
        return products
    raise RomboScrapeFejl(f"Rombo: {last_error} på side {page}", page=page)


def scrape_rombo_rom():
    items = []
    page = 1

    skip_keywords = [
        "glas", "krus", "opener", "trøje", "gave", "gavekort",
        "merchandise", "snack", "chokolade", "abonnement", "pant",
        "tilbehør", "cocktail kit", "smagning", "magasinet",
        "t-shirt", "plakat", "bog ", "bøger",
    ]

    print("🥃 Henter rom fra Rombo.dk (Shopify)...")
    session = requests.Session()
    session.headers.update(HEADERS)

    while True:
        url = f"{BASE_URL}/collections/{COLLECTION}/products.json?limit=250&page={page}"
        products = _get_products(session, url, page)

        if not products:
            break

        print(f"📦 Side {page}: {len(products)} produkter")

        for product in products:
            name = product.get("title", "").strip()
            if not name:
                continue

            # Skip ikke-rom produkter
            if any(kw in name.lower() for kw in skip_keywords):
                continue

            # Hent pris fra første variant
            variants = product.get("variants", [])
            if not variants:
                continue

            variant = variants[0]
            try:
                price = float(variant.get("price", "0"))
            except (ValueError, TypeError):
                price = 0

            if price < 50:
                continue

            # Tilbudspris
            old_price = None
            compare = variant.get("compare_at_price")
            if compare:
                try:
                    compare_price = float(compare)
                    if compare_price > price:
                        old_price = compare_price
                except (ValueError, TypeError):
                    pass

            discount = None
            if old_price and old_price > price:
                discount = round((old_price - price) / old_price * 100, 1)

            # URL og billede
            handle = product.get("handle", "")
            permalink = f"{BASE_URL}/products/{handle}" if handle else ""

            images = product.get("images", [])
            image = images[0].get("src", "") if images else ""

            # Byg et produkt-dict der matcher rom_parser's forventede input
            slug = handle or ""
            body_html = product.get("body_html", "")
            vendor = product.get("vendor", "")
            product_type = product.get("product_type", "")
            tags_raw = product.get("tags", [])

            # Shopify tags er en liste af strings
            if isinstance(tags_raw, str):
                tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()]
            else:
                tags_list = tags_raw if isinstance(tags_raw, list) else []

            # Byg tags som list of dicts (matcher WooCommerce format)
            tags = [{"name": t} for t in tags_list]

            # Byg categories fra product_type
            categories = []
            if product_type:
                categories.append({"name": product_type})

            # Byg brands fra vendor
            brands = []
            if vendor:
                brands.append({"name": vendor})

            # Kald rom_parser med WooCommerce-lignende dict
            parser_input = {
                "name": name,
                "slug": slug,
                "short_description": "",
                "description": body_html,
                "brands": brands,
                "tags": tags,
                "categories": categories,
            }
            parsed = parse_product(parser_input)

            items.append({
                "name": name,
                "price": price,
                "old_price": old_price,
                "discount_pct": discount,
                "url": permalink,
                "shop_name": "Rombo",
                "volume_cl": parsed["volume_cl"],
                "abv": parsed["abv"],
                "image": image,
                "type": parsed["type"],
                "brand": parsed["brand"] or vendor or None,
                "country": parsed["country"],
                "age": parsed["age"],
                "editions": list(parsed["editions"]),
                "category": "rom",
            })

        # Shopify returnerer max 250 per side
        if len(products) < 250:
            break
        page += 1
        time.sleep(random.uniform(2.0, 3.5))

    print(f"\n✅ {len(items)} rom-produkter hentet fra Rombo")
    return items


if __name__ == "__main__":
    items = scrape_rombo_rom()
    if not items:
        print("Ingen produkter fundet")
        exit()

    with_brand = sum(1 for it in items if it.get("brand"))
    with_volume = sum(1 for it in items if it.get("volume_cl"))
    with_abv = sum(1 for it in items if it.get("abv"))
    with_age = sum(1 for it in items if it.get("age"))
    with_country = sum(1 for it in items if it.get("country"))

    print(f"\n📊 Coverage:")
    print(f"  Brand:    {with_brand}/{len(items)} ({100*with_brand//len(items)}%)")
    print(f"  Volume:   {with_volume}/{len(items)} ({100*with_volume//len(items)}%)")
    print(f"  ABV:      {with_abv}/{len(items)} ({100*with_abv//len(items)}%)")
    print(f"  Alder:    {with_age}/{len(items)} ({100*with_age//len(items)}%)")
    print(f"  Land:     {with_country}/{len(items)} ({100*with_country//len(items)}%)")

    # Vis de 10 dyreste
    items.sort(key=lambda x: x["price"], reverse=True)
    print(f"\n💎 Top 10 dyreste:")
    for it in items[:10]:
        print(f"  {it['price']:>8.0f} kr  {it['name'][:55]}")

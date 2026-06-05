"""
Kokkens Vinhus — rom scraper via WooCommerce Store API.
Bruger rom_parser til smart datauddrag.
"""
import requests
from rom_parser import parse_product

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "da-DK,da;q=0.9,en;q=0.8",
}

BASE_URL = "https://www.kokkensvinhus.dk"


def scrape_kokkensvinhus_rom():
    items = []
    page = 1
    per_page = 100

    print("🔍 Finder rom-kategori på Kokkens Vinhus...")
    try:
        cat_response = requests.get(
            f"{BASE_URL}/wp-json/wc/store/v1/products/categories?per_page=100",
            headers=HEADERS,
            timeout=15
        )
        categories = cat_response.json()
        rom_cat_id = None
        for cat in categories:
            if cat.get("name", "").lower() == "rom" or cat.get("slug", "").lower() == "rom":
                rom_cat_id = cat["id"]
                print(f"✅ Fandt rom kategori: id={rom_cat_id}")
                break
        if not rom_cat_id:
            print("❌ Fandt ikke 'rom' kategori")
            return items
    except Exception as e:
        print(f"❌ Kunne ikke hente kategorier: {e}")
        return items

    skip_keywords = [
        "glas", "krus", "opener", "trøje", "gave", "gavekort",
        "merchandise", "snack", "chokolade", "abonnement", "pant",
        "tilbehør", "cocktail kit", "smagekasse", "smagning"
    ]

    while True:
        url = f"{BASE_URL}/wp-json/wc/store/v1/products?category={rom_cat_id}&per_page={per_page}&page={page}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
        except Exception as e:
            print(f"❌ Fejl på side {page}: {e}")
            break
        if r.status_code != 200:
            break
        try:
            products = r.json()
        except:
            break
        if not products:
            break

        print(f"📦 Side {page}: {len(products)} produkter")

        for product in products:
            name = product.get("name", "").strip()
            if not name:
                continue
            if any(kw in name.lower() for kw in skip_keywords):
                continue

            # Pris
            prices = product.get("prices", {})
            currency_minor = prices.get("currency_minor_unit", 2)
            divisor = 10 ** currency_minor

            try:
                price = float(prices.get("price", 0)) / divisor
            except:
                price = 0
            try:
                regular = float(prices.get("regular_price", 0)) / divisor
            except:
                regular = 0
            try:
                sale = float(prices.get("sale_price", 0)) / divisor
            except:
                sale = 0

            actual_price = price
            old_price = None
            if sale > 0 and regular > 0 and sale < regular:
                actual_price = sale
                old_price = regular

            if actual_price < 50:
                continue

            discount = None
            if old_price and old_price > actual_price:
                discount = round((old_price - actual_price) / old_price * 100, 1)

            permalink = product.get("permalink", "")
            images = product.get("images", [])
            image = images[0].get("src", "") if images else ""

            # Brug smart parser
            parsed = parse_product(product)

            items.append({
                "name": name,
                "price": actual_price,
                "old_price": old_price,
                "discount_pct": discount,
                "url": permalink,
                "shop_name": "Kokkens Vinhus",
                "volume_cl": parsed["volume_cl"],
                "abv": parsed["abv"],
                "image": image,
                "type": parsed["type"],
                "brand": parsed["brand"],
                "country": parsed["country"],
                "age": parsed["age"],
                "editions": list(parsed["editions"]),
                "category": "rom",
            })

        if len(products) < per_page:
            break
        page += 1

    print(f"\n✅ {len(items)} rom-produkter hentet")
    return items


if __name__ == "__main__":
    items = scrape_kokkensvinhus_rom()
    if not items:
        exit()

    with_brand = sum(1 for it in items if it.get("brand"))
    with_volume = sum(1 for it in items if it.get("volume_cl"))
    with_abv = sum(1 for it in items if it.get("abv"))
    with_age = sum(1 for it in items if it.get("age"))
    with_country = sum(1 for it in items if it.get("country"))
    with_type = sum(1 for it in items if it.get("type"))

    print(f"\n📊 Coverage:")
    print(f"  Brand:    {with_brand}/{len(items)} ({100*with_brand//len(items)}%)")
    print(f"  Volume:   {with_volume}/{len(items)} ({100*with_volume//len(items)}%)")
    print(f"  ABV:      {with_abv}/{len(items)} ({100*with_abv//len(items)}%)")
    print(f"  Alder:    {with_age}/{len(items)} ({100*with_age//len(items)}%)")
    print(f"  Land:     {with_country}/{len(items)} ({100*with_country//len(items)}%)")
    print(f"  Type:     {with_type}/{len(items)} ({100*with_type//len(items)}%)")
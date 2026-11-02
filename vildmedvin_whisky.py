"""Whisky-feed fra Vild med Vins offentlige Vue Storefront-katalogindeks."""
import re
import time

import requests

from rom_parser import extract_abv, extract_age, extract_brand, extract_editions, extract_type, extract_volume


SHOP_NAME = "Vild med Vin"
BASE_URL = "https://www.vildmedvin.dk"
SEARCH_URL = BASE_URL + "/api/catalog/vue_storefront_magento_1/product/_search"
WHISKY_CATEGORY_ID = 695  # /spiritus/whisky -> whisky-695 i sidens offentlige Vue Storefront-route
PAGE_SIZE = 100
PAUSE = 0.5
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RomSniffer/1.0)", "Accept": "application/json"}


def _float(value):
    try:
        return float(str(value).replace(",", ".")) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _image_url(value):
    if not value:
        return None
    if value.startswith("//"):
        return "https:" + value
    return value if value.startswith("http") else BASE_URL + value


def _attribute_options(code):
    """Hent værdierne bag Magento-attributternes option-id'er."""
    try:
        response = requests.get(
            BASE_URL + f"/api/catalog/vue_storefront_magento_1/attribute/_search",
            params={"q": f"attribute_code:{code}", "size": 1},
            headers=HEADERS,
            timeout=20,
        )
        response.raise_for_status()
        hits = response.json().get("hits", {}).get("hits", [])
        options = (hits[0].get("_source") or {}).get("options", []) if hits else []
        return {str(option.get("value")): option.get("label") for option in options}
    except (requests.RequestException, ValueError, IndexError):
        return {}


def _build_item(product, abv_options, volume_options):
    stock = product.get("stock") or {}
    if stock.get("is_in_stock") is not True:
        return None

    name = (product.get("name") or "").strip()
    if re.search(r"\b(liqueur|likør|kalender|whiskyglas)\b", name, re.I):
        return None
    path = product.get("url_path") or product.get("request_path")
    if not name or not path:
        return None

    # Magento-indekset gemmer katalogpriser uden moms og eksponerer den viste
    # forbrugerpris som final_price_incl_tax.
    price = _float(product.get("final_price_incl_tax"))
    if price is None:
        price = _float(product.get("price_incl_tax"))
    if not price or price <= 0:
        return None

    old_price = _float(product.get("original_price_incl_tax"))
    if old_price is None or old_price <= price:
        old_price = None
    discount = round(100 * (old_price - price) / old_price, 1) if old_price else None

    abv_label = abv_options.get(str(product.get("alcohol_percentage")))
    abv = _float(abv_label)
    if abv is None or not 15 <= abv <= 85:
        abv = extract_abv(name, path, product.get("description"), product.get("short_description"))
    volume_label = volume_options.get(str(product.get("bottle_size")))
    volume = extract_volume(name, path, product.get("description"), product.get("short_description"))
    if volume is None:
        volume = extract_volume(volume_label, path, product.get("description"), product.get("short_description"))
    return {
        "name": name,
        "shop_name": SHOP_NAME,
        "price": price,
        "old_price": old_price,
        "discount_pct": discount,
        "url": BASE_URL + "/" + path.lstrip("/"),
        "image": _image_url(product.get("image") or product.get("thumbnail")),
        "brand": extract_brand(name, slug=path),
        "age": extract_age(name, path, product.get("description"), product.get("short_description")),
        "abv": abv,
        "volume_cl": volume,
        "type": extract_type(name, description=product.get("description", ""), short_desc=product.get("short_description", "")),
        "editions": extract_editions(name, product.get("description", ""), product.get("short_description", "")),
        "ean": str(product.get("ean") or "").strip() or None,
        "sku": str(product.get("sku") or "").strip() or None,
        "category": "whisky",
    }


def scrape_vildmedvin_whisky():
    """Hent samtlige whisky-kategoriprodukter; behold kun eksplicit lagerførte varer."""
    print(f"🥃 Henter whisky fra Vild med Vin (kategori {WHISKY_CATEGORY_ID})...")
    session = requests.Session()
    session.headers.update(HEADERS)
    items, seen = [], set()
    total = None
    abv_options = _attribute_options("alcohol_percentage")
    volume_options = _attribute_options("bottle_size")

    for start in range(0, 5000, PAGE_SIZE):
        params = {"q": f"category_ids:{WHISKY_CATEGORY_ID}", "size": PAGE_SIZE, "from": start}
        try:
            response = session.get(SEARCH_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            if start == 0:
                raise RuntimeError(f"Vild med Vin whisky-feed fejlede: {exc}") from exc
            print(f"   ⚠️  Feed stoppede efter offset {start}: {exc}")
            break

        hits = data.get("hits", {})
        total_data = hits.get("total", 0)
        total = total_data.get("value", 0) if isinstance(total_data, dict) else total_data
        products = hits.get("hits") or []
        if not products:
            break

        added = 0
        for hit in products:
            product = hit.get("_source") or {}
            item = _build_item(product, abv_options, volume_options)
            if item and item["url"] not in seen:
                seen.add(item["url"])
                items.append(item)
                added += 1
        print(f"   📦 {start + 1}-{start + len(products)} af {total}: {added} på lager")

        if start + len(products) >= total:
            break
        time.sleep(PAUSE)

    print(f"✅ Vild med Vin: {len(items)} whiskyvarer på lager af {total or 0} i kategorien")
    return items


if __name__ == "__main__":
    products = scrape_vildmedvin_whisky()
    print(f"EAN: {sum(bool(p.get('ean')) for p in products)}/{len(products)}")
    print(f"ABV: {sum(p.get('abv') is not None for p in products)}/{len(products)}")
    print(f"Volumen: {sum(p.get('volume_cl') is not None for p in products)}/{len(products)}")

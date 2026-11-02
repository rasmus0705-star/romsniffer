"""Byg et lokalt, upubliceret whisky-datasæt fra Whisky.dk og Juuls."""
import argparse
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from juuls_rom import scrape_juuls_rom
from vildmedvin_whisky import scrape_vildmedvin_whisky
from whiskydk_rom import scrape_whiskydk_rom


WHISKY_DK_URL = "https://www.whisky.dk/shop/whisky-17s{page}.html"
JUULS_GROUP = "GROUP335"
OUTPUT = Path("whisky_pilot_data.json")
RAW_OUTPUT = Path("whisky_pilot_raw.json")
SOURCE_FILES = {
    "Whisky.dk": Path("whisky_pilot_whiskydk.json"),
    "Juuls": Path("whisky_pilot_juuls.json"),
    "Vild med Vin": Path("whisky_pilot_vildmedvin.json"),
}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; RomSniffer/1.0)"}


def _name_key(name):
    """Normalisér stavning og generiske ord; behold udgaver, alderstal og fadtype."""
    value = unicodedata.normalize("NFKD", (name or "").casefold())
    value = "".join(c for c in value if unicodedata.category(c) != "Mn")
    value = re.sub(r"[’'`´]", "", value)
    value = value.replace("&", " and ")
    value = value.replace("strenght", "strength").replace("campbelltown", "campbeltown")
    value = value.replace("okologisk", "organic")
    value = re.sub(r"\boko\b", "organic", value)
    value = re.sub(r"\b(\d+)y\b", r"\1", value)
    value = re.sub(r"\b\d+(?:[.,]\d+)?\s*(?:ml|cl|l|%)", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\b(?:whisky|whiskey)\b", " ", value)
    value = re.sub(r"\b(?:years?|old|yo|ars?|aars?|vintage)\b", " ", value)
    # Butikker kan bytte om på produktnavnets ordstilling. Alle variantord
    # bevares, men rækkefølgen ignoreres.
    return " ".join(sorted(value.split()))


def _same_bottle(a, b):
    """EAN-match eller identisk normaliseret navn plus verificeret flaskeinfo."""
    ean_a = re.sub(r"\D", "", str(a.get("ean") or ""))
    ean_b = re.sub(r"\D", "", str(b.get("ean") or ""))
    ean_match = bool(ean_a and ean_b and ean_a == ean_b)
    if ean_a and ean_b and ean_a != ean_b:
        return False

    va, vb = a.get("volume_cl"), b.get("volume_cl")
    aa, ab = a.get("abv"), b.get("abv")
    if va is not None and vb is not None and abs(float(va) - float(vb)) > 1:
        return False
    if aa is not None and ab is not None and abs(float(aa) - float(ab)) > 0.2:
        return False
    if ean_match:
        return True
    if (
        _name_key(a.get("name"))
        and _name_key(a.get("name")) == _name_key(b.get("name"))
        and va is not None and vb is not None
        and aa is not None and ab is not None
    ):
        return True

    sku_a = str(a.get("sku") or "").strip().casefold()
    sku_b = str(b.get("sku") or "").strip().casefold()
    if not sku_a or sku_a != sku_b or va is None or vb is None or aa is None or ab is None:
        return False

    name_a, name_b = set(_name_key(a.get("name")).split()), set(_name_key(b.get("name")).split())
    if not name_a or not name_b:
        return False
    score = 2 * len(name_a & name_b) / (len(name_a) + len(name_b))
    if score < 0.65:
        return False

    # Et ekstra frigivelsesår eller aldersnummer kan pege på en anden aftapning.
    nums_a = set(re.findall(r"\d+", _name_key(a.get("name"))))
    nums_b = set(re.findall(r"\d+", _name_key(b.get("name"))))
    if nums_a != nums_b:
        return False

    def style(name):
        tokens = set(_name_key(name).split())
        for label, required in (
            ("single_pot_still", {"single", "pot", "still"}),
            ("single_grain", {"single", "grain"}),
            ("single_malt", {"single", "malt"}),
            ("blended_malt", {"blended", "malt"}),
            ("blended", {"blended"}),
            ("bourbon", {"bourbon"}),
            ("rye", {"rye"}),
        ):
            if required <= tokens:
                return label
        return None

    style_a, style_b = style(a.get("name")), style(b.get("name"))
    if style_a and style_b and style_a != style_b:
        return False
    return True


def _whisky_dk_product_info(url):
    """Hent produktspecifik lagerstatus og GTIN fra Whisky.dk."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        if response.status_code != 200:
            return None, None
        soup = BeautifulSoup(response.text, "html.parser")
        stock = soup.select_one(".stock-message") or soup.select_one("span.Description_Productinfo")
        status = None
        if stock:
            text = " ".join(stock.get_text(" ", strip=True).casefold().split())
            if any(term in text for term in ("udsolgt", "ikke på lager", "ikke paa lager", "out of stock")):
                status = False
            elif "på lager" in text or "paa lager" in text or "in stock" in text:
                status = True
        gtin = soup.select_one('[itemprop="gtin13"], [itemprop="gtin"]')
        ean = (gtin.get("content") or gtin.get_text(" ", strip=True)) if gtin else None
        ean = re.sub(r"\D", "", str(ean or "")) or None
        return status, ean
    except requests.RequestException:
        return None, None


def _check_match_stock(matches):
    """Tjek Whisky.dk-lager og sammenhold EAN, når begge sider eksponerer det."""
    available, unknown, checked, ean_conflicts = [], 0, 0, 0
    for match in matches:
        whisky_offer = next((p for p in match["prices"] if p["shop_name"] == "Whisky.dk"), None)
        if not whisky_offer:
            match["whisky_dk_stock"] = "not_listed"
            available.append(match)
            continue
        status, whisky_ean = _whisky_dk_product_info(whisky_offer["url"])
        checked += 1
        catalog_ean = re.sub(r"\D", "", str(match.get("ean") or "")) or None
        if catalog_ean and whisky_ean:
            if catalog_ean != whisky_ean:
                match["ean_check"] = "conflict"
                ean_conflicts += 1
                continue
            match["ean_check"] = "verified"
        else:
            match["ean_check"] = "not_available"
        if status is True:
            match["whisky_dk_stock"] = "in_stock"
            available.append(match)
        elif status is False:
            match["whisky_dk_stock"] = "out_of_stock"
        else:
            match["whisky_dk_stock"] = "unknown"
            unknown += 1
    return available, unknown, checked, ean_conflicts


def _make_groups(items):
    # Danner kandidatpar via normaliseret titel og EAN. Udgaveord bevares.
    by_name, by_ean, by_sku = defaultdict(list), defaultdict(list), defaultdict(list)
    for item in items:
        key = _name_key(item.get("name"))
        if key:
            by_name[key].append(item)
        ean = re.sub(r"\D", "", str(item.get("ean") or ""))
        if ean:
            by_ean[ean].append(item)
        sku = str(item.get("sku") or "").strip().casefold()
        if sku:
            by_sku[sku].append(item)

    parent = list(range(len(items)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    indices = {id(item): i for i, item in enumerate(items)}
    for bucket in list(by_name.values()) + list(by_ean.values()) + list(by_sku.values()):
        for i, a in enumerate(bucket):
            for b in bucket[i + 1:]:
                if a.get("shop_name") == b.get("shop_name") or not _same_bottle(a, b):
                    continue
                ia, ib = find(indices[id(a)]), find(indices[id(b)])
                if ia != ib:
                    parent[ib] = ia

    grouped = defaultdict(list)
    for i, item in enumerate(items):
        grouped[find(i)].append(item)

    output = []
    for products in grouped.values():
        # Dette Koval-produkt er ulagret grain spirit, ikke whisky.
        if any("grain spirit" in (p.get("name") or "").casefold() for p in products):
            continue
        shops = {p.get("shop_name") for p in products}
        if len(shops) < 2 or not _same_bottle(products[0], products[-1]):
            continue
        if len(shops) != len(products):
            continue
        if any(not _same_bottle(a, b) for i, a in enumerate(products) for b in products[i + 1:]):
            continue
        prices = sorted(products, key=lambda p: p["price"])
        output.append({
            "name": prices[0]["name"],
            "volume_cl": prices[0].get("volume_cl"),
            "abv": prices[0].get("abv"),
            "ean": next((p.get("ean") for p in prices if p.get("ean")), None),
            "prices": [{k: p.get(k) for k in ("shop_name", "price", "old_price", "url", "ean")} for p in prices],
            "price_spread": round(prices[-1]["price"] - prices[0]["price"], 2),
        })
    return sorted(output, key=lambda g: (-g["price_spread"], g["name"].casefold()))


def _write_source(path, items):
    path.write_text(json.dumps(items, ensure_ascii=False, default=list), encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit-pages", type=int, help="Begræns antal sider pr. butik til en prøve")
    parser.add_argument("--check-stock-only", action="store_true", help="Genbrug pilotens matches og tjek Whisky.dk-lagerstatus")
    parser.add_argument("--reuse-scrapes", action="store_true", help="Genbrug lokale butikshentninger")
    parser.add_argument("--refresh-vildmedvin-only", action="store_true", help="Opdatér kun Vild med Vins lokale kildedata")
    args = parser.parse_args(argv)

    if args.refresh_vildmedvin_only:
        items = scrape_vildmedvin_whisky()
        if not items:
            raise SystemExit("Vild med Vin leverede ingen whiskyvarer; lokal kildedata er uændret.")
        _write_source(SOURCE_FILES["Vild med Vin"], items)
        print(f"Lokal Vild med Vin-kilde opdateret: {len(items)} varer")
        return
    elif args.check_stock_only:
        if not OUTPUT.is_file():
            raise SystemExit(f"Pilotdata ikke fundet: {OUTPUT}")
        output = json.loads(OUTPUT.read_text(encoding="utf-8"))
        groups = [
            match for match in output.get("matches", [])
            if "grain spirit" not in (match.get("name") or "").casefold()
        ]
        shops = output.get("shops", [])
        listings = output.get("stats", {}).get("listings", 0)
        with_volume = output.get("stats", {}).get("with_volume", 0)
        with_abv = output.get("stats", {}).get("with_abv", 0)
    else:
        if args.reuse_scrapes:
            missing = [str(path) for path in SOURCE_FILES.values() if not path.is_file()]
            if missing:
                raise SystemExit("Mangler lokale kildedata: " + ", ".join(missing))
            source_data = {
                shop: json.loads(path.read_text(encoding="utf-8"))
                for shop, path in SOURCE_FILES.items()
            }
            whisky_dk_items = source_data["Whisky.dk"]
            juuls_items = source_data["Juuls"]
            vildmedvin_items = source_data["Vild med Vin"]
        else:
            cap = args.limit_pages
            whisky_dk_items = scrape_whiskydk_rom(category_url=WHISKY_DK_URL, max_pages=cap)
            _write_source(SOURCE_FILES["Whisky.dk"], whisky_dk_items)
            juuls_items = scrape_juuls_rom(group=JUULS_GROUP, max_pages=cap)
            _write_source(SOURCE_FILES["Juuls"], juuls_items)
            vildmedvin_items = scrape_vildmedvin_whisky()
            _write_source(SOURCE_FILES["Vild med Vin"], vildmedvin_items)
        if not whisky_dk_items or not juuls_items or not vildmedvin_items:
            raise SystemExit("Pilotdata ikke opdateret: alle tre butikker skal levere produkter.")
        items = whisky_dk_items + juuls_items + vildmedvin_items
        shops = sorted({p.get("shop_name") for p in items})
        groups = _make_groups(items)
        listings = len(items)
        with_volume = sum(p.get("volume_cl") is not None for p in items)
        with_abv = sum(p.get("abv") is not None for p in items)
        _write_source(RAW_OUTPUT, items)

    in_stock, unknown_stock, stock_checked, ean_conflicts = _check_match_stock(groups)
    output = {
        "updated": datetime.now().isoformat(timespec="seconds"),
        "category": "whisky",
        "shops": shops,
        "stats": {
            "listings": listings,
            "with_volume": with_volume,
            "with_abv": with_abv,
            "strict_cross_shop_matches": len(groups),
            "in_stock_cross_shop_matches": len(in_stock),
            "whisky_dk_stock_checked": stock_checked,
            "whisky_dk_stock_unknown": unknown_stock,
            "ean_verified_matches": sum(m.get("ean_check") == "verified" for m in in_stock),
            "ean_conflicts": ean_conflicts,
        },
        "matches": in_stock,
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nPilotdata gemt lokalt: {OUTPUT}")
    print(json.dumps(output["stats"], ensure_ascii=False, indent=2))
    print("Lager er kontrolleret på Whisky.dk for de match, hvor butikken indgår; Juuls og Vild med Vin-feedene er lagerfiltreret.")


if __name__ == "__main__":
    main()

"""Build whisky data and reuse RomSniffer's established listing interface."""
import hashlib
from html import escape
import json
import re
from pathlib import Path
from slugify_rom import make_unique_slug

PILOT = Path("whisky_pilot_data.json")
TEMPLATE = Path("_rom_home_template.html")
DATA = Path("whisky_data.json")
OUTPUT = Path("whisky") / "index.html"


def _type(name):
    n = name.casefold()
    if "springbank" in n:
        return "Single malt"
    for needle, label in (("single pot still", "Single pot still"), ("single grain", "Single grain"),
                          ("blended malt", "Blended malt"), ("single malt", "Single malt"),
                          ("rye whiskey", "Rye"), ("rye whisky", "Rye"),
                          ("blended", "Blended whisky")):
        if needle in n:
            return label
    # These names are single-malt distilleries/brands even when retailers omit
    # the style from the product title.
    if re.search(r"\b(?:balvenie|port askaig|macallan|glenfiddich|glenlivet|laphroaig|lagavulin|ardbeg|talisker|highland park|oban|bunnahabhain|bowmore|caol ila|dalmore|glenmorangie|arran|jura|benriach|glenallachie|kilchoman|springbank)\b", n):
        return "Single malt"
    bourbon_cask = re.search(r"\b(?:ex[- ]?)?bourbon\s+(?:cask|barrel|wood|finish|matured|maturation)\b", n)
    if "bourbon" in n and not bourbon_cask:
        return "Bourbon"
    if re.search(r"\brye\b", n):
        return "Rye"
    return "Whisky"


def _age(name):
    m = re.search(r"\b(\d{1,2})\s*(?:years?\s*old|years?\s*|yo\b|år\b)", name, re.I)
    return f"{m.group(1)} år" if m else None


def _age_sort(value):
    match = re.search(r"\d+", value)
    return (0, int(match.group())) if match else (1, value.casefold())


def _catalog(pilot):
    items = []
    for match in pilot.get("listings", pilot.get("matches", [])):
        offers = sorted(match.get("prices", []), key=lambda p: float(p.get("price") or 0))
        if not offers:
            continue
        low, high = float(offers[0]["price"]), float(offers[-1]["price"])
        spread = round((high - low) / high * 100, 1) if high and len(offers) > 1 else 0
        shop_discount = max((float(p.get("discount_pct") or 0) for p in offers), default=0)
        name = match.get("name") or "Whisky"
        items.append({
            "name": name, "brand": "", "type": _type(name), "age": match.get("age") or _age(name),
            "country": match.get("country"),
            "abv": match.get("abv"), "volume_cl": match.get("volume_cl"), "image": match.get("image"),
            "slug": "", "category": "whisky", "shop_count": len(offers),
            "min_price": low, "cheapest_price": low,
            "max_discount_pct": max(spread, shop_discount), "prices": offers,
        })
    items.sort(key=lambda r: r["name"].casefold())
    used_slugs = set()
    for item in items:
        item["slug"] = make_unique_slug(item["name"], used_slugs)
    return {
        "updated": pilot.get("updated"),
        "stats": {
            "total": len(items), "multi_shop": sum(r["shop_count"] > 1 for r in items),
            "deals": sum(r["max_discount_pct"] > 0 for r in items),
            "cheapest": min((r["min_price"] for r in items), default=0),
            "shop_names": sorted({p["shop_name"] for r in items for p in r["prices"]}),
            "countries": sorted({r["country"] for r in items if r.get("country")}),
            "types": sorted({r["type"] for r in items}),
            "ages": sorted({r["age"] for r in items if r["age"]}, key=_age_sort),
        },
        "roms": items,
    }


def _render(source, catalog):
    html = source
    replacements = {
        '<title>Sammenlign rom-priser fra danske webshops | RomSniffer</title>': '<title>Sammenlign whiskypriser fra danske webshops | RomSniffer</title>',
        'Sammenlign rom-priser fra danske webshops | RomSniffer': 'Sammenlign whiskypriser fra danske webshops | RomSniffer',
        'Find den bedste pris på rom. Vi sammenligner priser fra danske webshops og viser dig hvor du sparer mest.': 'Sammenlign whiskypriser fra danske webshops, og find den bedste pris.',
        '<body data-cat="rom">': '<body data-cat="whisky">',
        'Find de bedste rom-priser i Danmark — RomSniffer': 'Sammenlign whiskypriser fra danske webshops',
        '<h2 class="hero-title">Samme flaske. <em>Laveste pris.</em></h2>': '<h1 class="hero-title">Find whisky til den bedste pris</h1>',
        '<a href="/">Alle rom</a>': '<a href="/whisky/">Alle whisky</a>',
        'Sammenlign <strong id="hero-count">1.000+</strong> rom fra danske webshops — opdateres dagligt': 'Sammenlign <strong id="hero-count">–</strong> whiskyer fra danske webshops — opdateres dagligt',
        'Ingen produkter matchede dine filtre': 'Ingen whiskyer matchede dine filtre',
        'placeholder="Søg rom, brand, land..."': 'placeholder="Søg whisky, type eller butik..."',
        'aria-label="Søg efter rom, brand eller land"': 'aria-label="Søg efter whisky, type eller butik"',
        '<div class="stat-lbl">Rom i alt</div>': '<div class="stat-lbl">Whisky i alt</div>',
        'class="sidebar-filter-btn active" data-filter="all">Alle rom': 'class="sidebar-filter-btn active" data-filter="all">Al whisky',
        'Premium (over 1.500 kr)': 'Over 1.500 kr',
        '>Premium</button>': '>Over 1.500 kr</button>',
        'Hverdagsrom (under 500 kr)': 'Hverdagswhisky (under 500 kr)',
        'Henter rom-data...': 'Henter whisky...',
        'Vis flere rom ↓': 'Vis flere whiskyer ↓',
        'Danmarks rom-prisaggregator. Vi sammenligner priser fra danske webshops så du altid får den bedste deal på din næste flaske rom.': 'RomSniffer sammenligner whiskypriser fra danske webshops, så du nemt kan finde den bedste pris.',
        'localStorage.getItem(\'rom_favs\')': 'localStorage.getItem(\'whisky_favs\')',
        'localStorage.setItem(\'rom_favs\'': 'localStorage.setItem(\'whisky_favs\'',
        'fetch(\'rom_data.json?v=\' + DATA_VERSION)': 'fetch(\'/whisky_data.json?v=\' + DATA_VERSION)',
        'Kunne ikke hente rom_data.json': 'Kunne ikke hente whisky_data.json',
        'Kunne ikke hente rom-data — tjek at rom_data.json findes': 'Kunne ikke hente whiskydata — prøv igen senere',
    }
    for old, new in replacements.items():
        html = html.replace(old, new)
    html = html.replace('<div class="nav-links">\n        <a href="/om.html">Om</a>\n    </div>', '<div class="nav-links"><a href="/rom/">Rom</a><a href="/om.html">Om</a></div>')

    description = (f'Sammenlign priser på {catalog["stats"]["total"]:,} whiskyer fra danske webshops. '
                   'Se butikkernes priser og find din næste flaske til en god pris.').replace(',', '.')
    html = re.sub(r'<meta name="description" content="[^"]*">',
                  f'<meta name="description" content="{description}">', html, count=1)
    html = re.sub(r'<meta property="og:description" content="[^"]*">',
                  f'<meta property="og:description" content="{description}">', html, count=1)

    # Every relative link in the root navigation must remain rooted from /whisky/.
    for page in ("premium.html", "guide.html", "om.html"):
        html = html.replace(f'href="{page}"', f'href="/{page}"')
    html = html.replace('<a href="/premium.html">Premium</a>', '')
    html = html.replace('<a href="/guide.html">Guide</a>', '')
    html = html.replace('<a href="/whisky/">Alle whisky</a>', '')

    html = html.replace('<span>Lande <span id="country-count-badge"', '<span>Oprindelse <span id="country-count-badge"')
    html = re.sub(r'\s*<a href="/rom/land/jamaica/" class="sidebar-cat-link">Se alle lande →</a>', '', html)
    html = html.replace('<div class="sidebar-title">Typer ', '<div class="sidebar-title">Stilarter ')
    html = html.replace('<span>Typer <span id="type-count-badge"', '<span>Stilarter <span id="type-count-badge"')
    html = re.sub(r'\s*<a href="/rom/(?:type/aged-rom|alder/xo)/" class="sidebar-cat-link">Se alle (?:typer|aldre) →</a>', '', html)
    html = html.replace('<span>Lande <span id="country-count-badge"', '<span>Oprindelse <span id="country-count-badge"')

    # Keep product discovery on RomSniffer; each whisky gets a static comparison page.
    html = html.replace('href="/rom/${r.slug}/" class="card-img-wrap"', 'href="/whisky/${r.slug}/" class="card-img-wrap"')
    html = html.replace('<div class="card-name"><a href="/rom/${r.slug}/"', '<div class="card-name"><a href="/whisky/${r.slug}/"')
    html = html.replace('href="/rom/${r.slug}/" class="top-card"', 'href="/whisky/${r.slug}/" class="top-card"')
    html = html.replace('https://www.romsniffer.dk/">\n<meta property="og:type"', 'https://www.romsniffer.dk/whisky/">\n<meta property="og:type"')
    html = html.replace('content="https://www.romsniffer.dk/">', 'content="https://www.romsniffer.dk/whisky/">')
    html = html.replace('src="logo.png"', 'src="/logo.png"')
    html = re.sub(r"(?m)^[ \t]+$", "", html)
    html = _add_static_catalog(html, catalog)
    html = re.sub(r'<h1 style="position:absolute;width:1px;height:1px;[^>]*>.*?</h1>', '', html, count=1, flags=re.S)
    version = hashlib.sha1(json.dumps(catalog, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]
    html = re.sub(r"const DATA_VERSION = '[^']*';", f"const DATA_VERSION = '{version}';", html, count=1)
    return html


def _add_static_catalog(html, catalog):
    items = sorted(catalog["roms"], key=lambda r: (-r.get("shop_count", 0), r.get("min_price", 0)))
    sample = items[:40]
    cards = []
    for item in sample:
        name = escape(item["name"], quote=True)
        href = f'/whisky/{item["slug"]}/'
        image = f'<img class="card-img" src="{escape(item["image"], quote=True)}" width="300" height="300" alt="{name}" loading="lazy">' if item.get("image") else ''
        cheapest = min(item["prices"], key=lambda p: float(p.get("price") or 0))
        shop = escape(str(cheapest.get("shop_name", "")), quote=True)
        price = f'{float(cheapest["price"]):,.2f}'.replace(",", "X").replace(".", ",").replace("X", ".")
        cards.append(
            f'<article class="card" role="listitem"><a href="{href}" class="card-img-wrap">{image}</a>'
            f'<div class="card-body"><div class="card-name"><a href="{href}">{name}</a></div>'
            f'<div class="price-row"><span class="price-row-shop">{shop}</span>'
            f'<span class="price-row-amount">{price} kr</span></div></div></article>'
        )
    html = html.replace('<div class="grid" id="grid">\n                <div class="loading"><div class="spinner"></div>Henter whisky...</div>\n            </div>',
                        '<div class="grid" id="grid">' + ''.join(cards) + '</div>')
    html = html.replace('<strong id="result-count">0</strong>', f'<strong id="result-count">{catalog["stats"]["total"]:,}</strong>'.replace(',', '.'))
    list_schema = {
        "@type": "ItemList", "name": "Sammenlign whiskypriser fra danske webshops",
        "numberOfItems": catalog["stats"]["total"],
        "itemListElement": [{"@type": "ListItem", "position": i, "url": f'https://www.romsniffer.dk/whisky/{r["slug"]}/', "name": r["name"]} for i, r in enumerate(sample, 1)],
    }
    schema = {"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "name": "Sammenlign whiskypriser", "url": "https://www.romsniffer.dk/whisky/", "mainEntity": list_schema},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Forside", "item": "https://www.romsniffer.dk/"},
            {"@type": "ListItem", "position": 2, "name": "Whisky", "item": "https://www.romsniffer.dk/whisky/"},
        ]},
    ]}
    html = html.replace('</head>', '<script type="application/ld+json">' + json.dumps(schema, ensure_ascii=False) + '</script>\n</head>', 1)
    return html


def main():
    if not PILOT.is_file() or not TEMPLATE.is_file():
        raise SystemExit("Whisky-pilotdata eller RomSniffer-forsidens skabelon mangler.")
    catalog = _catalog(json.loads(PILOT.read_text(encoding="utf-8")))
    DATA.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(_render(TEMPLATE.read_text(encoding="utf-8"), catalog), encoding="utf-8")
    from generate_whisky_product_pages import generate
    generate(catalog)
    print(f"Whisky-side genereret med RomSniffer-layout: {OUTPUT.resolve()} ({catalog['stats']['total']} produkter)")


if __name__ == "__main__":
    main()

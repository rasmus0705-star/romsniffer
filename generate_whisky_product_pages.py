"""Generate indexable static whisky comparison pages."""
from __future__ import annotations

import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE = "https://www.romsniffer.dk"
OUT = ROOT / "whisky"


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def money(value: object) -> str:
    return f"{float(value or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _page(item: dict) -> str:
    name = str(item.get("name") or "Whisky")
    slug = item["slug"]
    canonical = f"{SITE}/whisky/{slug}/"
    offers = sorted((p for p in item.get("prices", []) if float(p.get("price") or 0) > 0), key=lambda p: float(p["price"]))
    if not offers:
        return ""
    cheapest = offers[0]
    low, high = float(offers[0]["price"]), float(offers[-1]["price"])
    details = [x for x in (item.get("country"), item.get("type"), item.get("age"), f'{item["volume_cl"]} cl' if item.get("volume_cl") else None, f'{item["abv"]}% vol.' if item.get("abv") else None) if x]
    facts = " · ".join(map(str, details))
    descriptor = f"Sammenlign priser på {name} hos {len(offers)} danske webshops. Laveste pris {money(low)} kr."
    if facts:
        descriptor += f" {facts}."
    description = descriptor[:152].rstrip() + ("..." if len(descriptor) > 155 else "")
    image = str(item.get("image") or "")
    product = {
        "@type": "Product",
        "name": name,
        "url": canonical,
        "category": "Whisky",
        "description": description,
        "offers": {
            "@type": "AggregateOffer",
            "priceCurrency": "DKK",
            "lowPrice": f"{low:.2f}",
            "highPrice": f"{high:.2f}",
            "offerCount": len(offers),
            "offers": [
                {"@type": "Offer", "url": p.get("url"), "priceCurrency": "DKK",
                 "price": f'{float(p["price"]):.2f}', "availability": "https://schema.org/InStock",
                 "seller": {"@type": "Organization", "name": p.get("shop_name", "Webshop")}}
                for p in offers if p.get("url")
            ],
        },
    }
    if image:
        product["image"] = image
    if item.get("brand"):
        product["brand"] = {"@type": "Brand", "name": item["brand"]}
    additional = []
    for label, key in (("Alcohol by volume", "abv"), ("Volume", "volume_cl"), ("Type", "type"), ("Age", "age"), ("Country of origin", "country")):
        if item.get(key):
            additional.append({"@type": "PropertyValue", "name": label, "value": item[key]})
    if additional:
        product["additionalProperty"] = additional
    breadcrumb = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Forside", "item": f"{SITE}/"},
            {"@type": "ListItem", "position": 2, "name": "Whisky", "item": f"{SITE}/whisky/"},
            {"@type": "ListItem", "position": 3, "name": name, "item": canonical},
        ],
    }
    schema = json.dumps({"@context": "https://schema.org", "@graph": [product, breadcrumb]}, ensure_ascii=False)
    image_html = f'<img class="product-image" src="{esc(image)}" alt="{esc(name)}">' if image else ""
    offer_rows = []
    for offer in offers:
        old = offer.get("old_price")
        old_html = f"<del>{money(old)} kr</del>" if old else ""
        buy_html = (
            f'<a href="{esc(offer.get("url"))}" rel="sponsored nofollow noopener" target="_blank">Køb hos butikken →</a>'
            if offer.get("url") else ""
        )
        offer_rows.append(
            f'<article class="offer"><div><strong>{esc(offer.get("shop_name", "Webshop"))}</strong>'
            f'<div class="price">{money(offer["price"])} kr {old_html}</div></div>{buy_html}</article>'
        )
    return f'''<!doctype html>
<html lang="da"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(name)} — sammenlign whiskypriser | RomSniffer</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="product"><meta property="og:site_name" content="RomSniffer">
<meta property="og:title" content="{esc(name)} — RomSniffer"><meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}"><meta property="og:image" content="{esc(image or SITE + '/og-image.png')}">
<meta name="twitter:card" content="summary_large_image">
<link rel="stylesheet" href="/fonts/fonts.css"><link rel="stylesheet" href="/theme.css">
<script type="application/ld+json">{schema}</script>
<style>
body{{margin:0;background:#07060a;color:#f0e8d8;font:16px/1.6 'DM Sans',system-ui,sans-serif}}
nav,main,footer{{width:min(1040px,calc(100% - 32px));margin:auto}}nav{{padding:20px 0;border-bottom:1px solid #28200e}}
nav a,main a{{color:#e8c868}}.brand{{font:500 20px Georgia,serif;letter-spacing:.25em;text-decoration:none}}
main{{padding:24px 0 50px}}.crumbs{{color:#a39887;font-size:13px;margin-bottom:18px}}.crumbs a{{text-decoration:none}}
.product{{display:grid;grid-template-columns:minmax(240px, .9fr) minmax(300px,1.1fr);gap:36px}}
.product-image{{width:100%;max-height:480px;object-fit:contain;background:#f2ead7;border-radius:8px}}
h1{{font:500 clamp(30px,5vw,44px)/1.15 'Playfair Display',Georgia,serif;color:#e8c868;margin:0 0 12px}}
.facts{{color:#a39887;margin:0 0 22px}}.offers{{display:grid;gap:10px;margin-top:22px}}
.offer{{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:16px;border:1px solid #59431b;background:#100d13}}
.price{{font-size:21px;color:#f0e8d8}}del{{font-size:14px;color:#a39887;margin-left:8px}}.offer a{{padding:9px 12px;border:1px solid #c9a84c;text-decoration:none;white-space:nowrap}}
footer{{border-top:1px solid #28200e;padding:18px 0 28px;color:#a39887;font-size:13px}}footer a{{color:#e8c868}}
@media(max-width:650px){{.product{{grid-template-columns:1fr;gap:20px}}.product-image{{max-height:340px}}.offer{{align-items:flex-start;flex-direction:column}}}}
</style></head><body data-cat="whisky">
<nav><a class="brand" href="/">ROMSNIFFER</a></nav>
<main><div class="crumbs"><a href="/">Forside</a> › <a href="/whisky/">Whisky</a> › {esc(name)}</div>
<article class="product">{image_html}<div><h1>{esc(name)}</h1><p class="facts">{esc(facts)}</p>
<p>Laveste pris lige nu: <strong>{money(low)} kr</strong> hos {esc(cheapest.get("shop_name", "webshoppen"))}. Sammenlign priser fra {len(offers)} butikker.</p>
<section class="offers" aria-label="Priser fra webshops">{''.join(offer_rows)}</section></div></article></main>
<footer><a href="/whisky/">Alle whiskypriser</a> · <a href="/">RomSniffer</a><br>Priser opdateres dagligt. Køb sker hos forhandleren.</footer>
</body></html>'''


def generate(catalog: dict | None = None) -> int:
    if catalog is None:
        catalog = json.loads((ROOT / "whisky_data.json").read_text(encoding="utf-8"))
    OUT.mkdir(exist_ok=True)
    items = catalog.get("roms", [])
    for item in items:
        if not item.get("slug"):
            continue
        target = OUT / item["slug"]
        target.mkdir(exist_ok=True)
        (target / "index.html").write_text(_page(item), encoding="utf-8")
    return sum(1 for x in items if x.get("slug"))


if __name__ == "__main__":
    print(f"Genererede {generate()} whiskyproduktsider")

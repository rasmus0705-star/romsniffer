"""Generate the category chooser at / and the RomSniffer rum listing at /rom/."""
import json
import re
from pathlib import Path
from datetime import datetime
from html import escape

TEMPLATE = Path("_rom_home_template.html")
ROM_PAGE = Path("rom") / "index.html"
HOME = Path("index.html")


def _stats(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")).get("stats", {})
    except (OSError, ValueError, TypeError):
        return {}


def _price_example(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        candidates = []
        for item in data.get("roms", []):
            prices = [p for p in item.get("prices", []) if float(p.get("price") or 0) > 0 and p.get("url", "").startswith("http")]
            if not prices:
                continue
            prices.sort(key=lambda row: float(row["price"]))
            spread = float(prices[-1]["price"]) - float(prices[0]["price"])
            candidates.append((spread, len(prices), item, prices[0], len(prices)))
        _, _, item, best_price, shop_count = max(candidates, key=lambda row: (row[0], row[1]))
        price = float(best_price["price"])
        formatted_price = f"{price:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if formatted_price.endswith(",00"):
            formatted_price = formatted_price[:-3]
        updated = datetime.fromisoformat(data["updated"]) if data.get("updated") else None
        if updated:
            months = ("januar", "februar", "marts", "april", "maj", "juni", "juli", "august", "september", "oktober", "november", "december")
            updated_label = f"{updated.day}. {months[updated.month - 1]} kl. {updated:%H.%M}"
        else:
            updated_label = "tidspunkt ukendt"
        return {
            "name": " ".join(item.get("name", "").split()[:7]),
            "price": formatted_price,
            "shop": best_price.get("shop_name", "webshoppen"),
            "url": best_price["url"],
            "shops": shop_count,
            "updated": updated_label,
        }
    except (OSError, ValueError, TypeError, KeyError):
        return None


def _make_rom_page(template, rom_data):
    html = template
    html = html.replace('<link rel="canonical" href="https://www.romsniffer.dk/">',
                        '<link rel="canonical" href="https://www.romsniffer.dk/rom/">')
    html = html.replace('<meta property="og:url" content="https://www.romsniffer.dk/">',
                        '<meta property="og:url" content="https://www.romsniffer.dk/rom/">')
    html = html.replace('<a href="/">Alle rom</a>', '<a href="/rom/">Rom</a>')
    html = html.replace('<a href="/rom/">Rom</a>', '')
    html = html.replace("fetch('rom_data.json?v=' + DATA_VERSION)", "fetch('/rom_data.json?v=' + DATA_VERSION)")
    html = html.replace('<div class="nav-links">\n        <a href="/om.html">Om</a>\n    </div>', '<div class="nav-links"><a href="/whisky/">Whisky</a><a href="/om.html">Om</a></div>')
    html = html.replace('<h2 class="hero-title">Samme flaske. <em>Laveste pris.</em></h2>', '<h1 class="hero-title">Find rom til den bedste pris</h1>')
    html = re.sub(r'<h1 style="position:absolute;width:1px;height:1px;[^>]*>.*?</h1>', '', html, count=1, flags=re.S)
    html = _add_static_catalog(html, rom_data)
    for page in ("premium.html", "guide.html", "om.html"):
        html = html.replace(f'href="{page}"', f'href="/{page}"')
    return html


def _add_static_catalog(page, data):
    roms = data.get("roms", [])
    sample = sorted(roms, key=lambda r: (-int(r.get("shop_count") or 0), float(r.get("min_price") or 0)))[:40]
    cards = []
    for item in sample:
        name = escape(str(item.get("name") or "Rom"), quote=True)
        slug = escape(str(item.get("slug") or ""), quote=True)
        image = item.get("image")
        image_html = f'<img class="card-img" src="{escape(str(image), quote=True)}" width="300" height="300" alt="{name}" loading="lazy">' if image else ""
        prices = [p for p in item.get("prices", []) if float(p.get("price") or 0) > 0]
        if not prices:
            continue
        cheapest = min(prices, key=lambda p: float(p["price"]))
        shop = escape(str(cheapest.get("shop_name") or ""), quote=True)
        price = f'{float(cheapest["price"]):,.2f}'.replace(",", "X").replace(".", ",").replace("X", ".")
        href = f"/rom/{slug}/"
        cards.append(f'<article class="card" role="listitem"><a href="{href}" class="card-img-wrap">{image_html}</a>'
                     f'<div class="card-body"><div class="card-name"><a href="{href}">{name}</a></div>'
                     f'<div class="price-row"><span class="price-row-shop">{shop}</span><span class="price-row-amount">{price} kr</span></div></div></article>')
    page = page.replace('<div class="grid" id="grid">\n                <div class="loading"><div class="spinner"></div>Henter rom-data...</div>\n            </div>',
                        '<div class="grid" id="grid">' + ''.join(cards) + '</div>')
    total = int(data.get("stats", {}).get("total") or len(roms))
    page = page.replace('<strong id="result-count">0</strong>', f'<strong id="result-count">{total:,}</strong>'.replace(",", "."))
    page = page.replace('<strong id="hero-count">1.000+</strong>', f'<strong id="hero-count">{total:,}</strong>'.replace(",", "."))
    item_list = {
        "@type": "ItemList", "name": "Rom til salg hos danske webshops",
        "numberOfItems": total,
        "itemListElement": [{"@type": "ListItem", "position": i, "url": f'https://www.romsniffer.dk/rom/{r.get("slug", "")}/', "name": r.get("name", "")}
                            for i, r in enumerate(sample, 1) if r.get("slug")],
    }
    schema = {"@context": "https://schema.org", "@graph": [
        {"@type": "CollectionPage", "name": "Sammenlign rompriser fra danske webshops", "url": "https://www.romsniffer.dk/rom/", "mainEntity": item_list},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Forside", "item": "https://www.romsniffer.dk/"},
            {"@type": "ListItem", "position": 2, "name": "Rom", "item": "https://www.romsniffer.dk/rom/"},
        ]},
    ]}
    schema_tag = '<script type="application/ld+json">' + json.dumps(schema, ensure_ascii=False) + '</script>'
    page = page.replace('</head>', schema_tag + '\n</head>', 1)
    return page


def _make_home(rom_stats, whisky_stats, rom_deal, whisky_deal):
    def fmt(value):
        return f"{int(value or 0):,}".replace(",", ".")

    rom_products = fmt(rom_stats.get("total"))
    whisky_products = fmt(whisky_stats.get("total"))
    total_products = fmt(int(rom_stats.get("total") or 0) + int(whisky_stats.get("total") or 0))
    meta_description = f"Sammenlign priser på {total_products} rom og whisky fra danske webshops. Se aktuelle tilbud og find din næste flaske til en god pris."
    def deal_markup(deal):
        if not deal:
            return "<span class=\"choice-deal\"><small>Aktuel pris</small><strong>Se dagens priser</strong></span>"
        return (f"<a class=\"choice-deal\" href=\"{escape(deal['url'], quote=True)}\" target=\"_blank\" rel=\"sponsored nofollow noopener\" aria-label=\"Se {escape(deal['name'], quote=True)} hos {escape(deal['shop'], quote=True)}\">"
                f"<small>Senest registreret {escape(deal['updated'])}</small>"
                f"<strong>{escape(deal['name'])}</strong>"
                f"<span>{escape(deal['price'])} kr. hos {escape(deal['shop'])}</span>"
                f"<small class=\"deal-compare\">Sammenlignet hos {deal['shops']} butikker</small></a>")
    schema = {
        "@context": "https://schema.org", "@graph": [
            {"@type": "Organization", "@id": "https://www.romsniffer.dk/#organization", "name": "RomSniffer", "url": "https://www.romsniffer.dk/", "logo": "https://www.romsniffer.dk/og-image.png"},
            {"@type": "WebSite", "@id": "https://www.romsniffer.dk/#website", "url": "https://www.romsniffer.dk/", "name": "RomSniffer", "publisher": {"@id": "https://www.romsniffer.dk/#organization"}},
        ]
    }
    return f'''<!doctype html>
<html lang="da">
<head>
  <!-- Start cookieyes banner -->
  <script id="cookieyes" type="text/javascript" src="https://cdn-cookieyes.com/client_data/89fa8867d76958bb0adf126ff23ddbf6/script.js"></script>
  <!-- End cookieyes banner -->
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{escape(meta_description, quote=True)}">
  <link rel="canonical" href="https://www.romsniffer.dk/">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="RomSniffer">
  <meta property="og:title" content="Find rom og whisky til den bedste pris | RomSniffer">
  <meta property="og:description" content="{escape(meta_description, quote=True)}">
  <meta property="og:url" content="https://www.romsniffer.dk/">
  <meta property="og:image" content="https://www.romsniffer.dk/og-image.jpg">
  <meta property="og:image:alt" content="RomSniffer — rom og whisky">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <script type="application/ld+json">{json.dumps(schema, ensure_ascii=False)}</script>
  <title>Find rom og whisky til den bedste pris | RomSniffer</title>
  <link rel="icon" type="image/png" href="/favicon.png">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <link rel="preload" href="/fonts/playfair-display-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/fonts/dm-sans-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/fonts/fonts.css">
  <link rel="stylesheet" href="/theme.css">
  <link rel="preload" as="image" href="/category-rum.jpg">
  <link rel="preload" as="image" href="/category-whisky.jpg">
  <script src="/theme.js?v=menu-category-3"></script>
  <style>
    * {{ box-sizing:border-box }}
    body {{ margin:0; min-height:100vh; min-height:100svh; display:flex; flex-direction:column; background:#07060a; color:#f0e8d8; font:16px/1.55 'DM Sans',system-ui,sans-serif; }}
    nav {{ min-height:58px; display:flex; align-items:center; justify-content:space-between; padding:10px max(22px,calc((100vw - 1120px)/2)); }}
    .nav-logo {{ color:#e8c868; text-decoration:none; font:500 19px Georgia,serif; letter-spacing:.3em; text-transform:uppercase; }}
    .nav-links a {{ color:#a39887; text-decoration:none; text-transform:uppercase; font-size:12px; letter-spacing:.16em; }}
    main {{ width:min(1040px,calc(100% - 36px)); flex:1; display:flex; flex-direction:column; justify-content:center; margin:8px auto; }}
    .hero {{ min-height:clamp(110px,14svh,140px); display:flex; align-items:center; justify-content:center; padding:10px 20px; margin-bottom:10px; text-align:center; background:radial-gradient(ellipse at 50% 100%,rgba(201,168,76,.09),transparent 68%); }}
    .hero-copy {{ max-width:820px; }}
    .eyebrow {{ color:#c9a84c; font-size:10px; text-transform:uppercase; letter-spacing:.22em; }}
    h1 {{ margin:7px 0 6px; color:#e8c868; font:500 clamp(32px,4.5vw,48px)/1.06 'Playfair Display',Georgia,serif; }}
    .intro {{ max-width:620px; margin:0 auto; color:#a39887; font-size:15px; }}
    .choices {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; }}
    .choice {{ position:relative; display:flex; min-height:clamp(230px,27svh,270px); flex-direction:column; justify-content:space-between; padding:22px; overflow:hidden; border:1px solid rgba(201,168,76,.25); background:#0f0c13; color:#f0e8d8; text-decoration:none; transition:border-color .2s,transform .2s,background .2s; }}
    .choice::before {{ content:""; position:absolute; inset:0; z-index:1; background:linear-gradient(90deg,#0b0a0f 0%,rgba(11,10,15,.98) 42%,rgba(11,10,15,.82) 62%,rgba(11,10,15,.25) 100%); transition:opacity .2s; }}
    .choice-image {{ position:absolute; inset:0; width:100%; height:100%; object-fit:cover; object-position:right center; transition:transform .35s; }}
    .choice-hit {{ position:absolute; inset:0; z-index:2; }}
    .choice-content {{ position:relative; z-index:3; display:flex; flex:1; flex-direction:column; justify-content:space-between; pointer-events:none; }}
    .choice-content a {{ pointer-events:auto; }}
    .choice:hover {{ border-color:#c9a84c; transform:translateY(-3px); }}
    .choice:hover .choice-image {{ transform:scale(1.04); }}
    .choice-name {{ display:flex; align-items:center; gap:14px; color:#e8c868; font:500 clamp(32px,5vw,48px)/1.1 'Playfair Display',Georgia,serif; }}
    .choice-stats {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:8px; margin:12px 0; }}
    .choice-stat {{ border-left:1px solid rgba(201,168,76,.3); padding-left:10px; color:#a39887; font-size:11px; line-height:1.35; }}
    .choice-stat strong {{ display:block; color:#f0e8d8; font:500 19px/1.2 'DM Sans',system-ui,sans-serif; margin-bottom:4px; }}
    .choice-deal {{ display:flex; flex-direction:column; gap:2px; width:fit-content; max-width:min(75%,460px); color:#d7c9ae; font-size:12px; line-height:1.35; text-decoration:none; }}
    .choice-deal small {{ color:#c9a84c; font-size:9px; letter-spacing:.13em; text-transform:uppercase; }}
    .choice-deal strong {{ overflow:hidden; color:#f0e8d8; font-weight:500; text-overflow:ellipsis; white-space:nowrap; }}
    .deal-compare {{ color:#a39887 !important; font-size:10px !important; letter-spacing:0 !important; text-transform:none !important; }}
    .choice-cta {{ display:inline-flex; align-items:center; gap:8px; width:fit-content; margin-top:1.5rem; padding:10px 15px; border:1px solid #c9a84c; color:#e8c868; text-transform:uppercase; font-size:11px; letter-spacing:.16em; text-decoration:none; transition:background .2s,color .2s; }}
    .choice-cta:hover {{ background:#c9a84c; color:#0b0a0f; }}
    footer {{ padding:8px 18px 12px; color:#a39887; text-align:center; font-size:12px; letter-spacing:.06em; }}
    @media(max-width:640px) {{ nav {{ min-height:50px; padding:8px 18px }} .nav-logo {{ font-size:17px }} main {{ width:calc(100% - 28px); margin:4px auto }} .hero {{ min-height:clamp(85px,12svh,105px); padding:8px 12px; margin-bottom:7px }} .eyebrow {{ font-size:8px; letter-spacing:.12em }} h1 {{ font-size:clamp(26px,6.5vw,32px); margin:5px 0 3px }} .intro {{ font-size:12px; line-height:1.3 }} .choices {{ grid-template-columns:1fr; gap:8px }} .choice {{ min-height:clamp(205px,29svh,235px); padding:14px 16px 12px }} .choice::before {{ background:linear-gradient(90deg,#0b0a0f 0%,rgba(11,10,15,.98) 45%,rgba(11,10,15,.82) 64%,rgba(11,10,15,.32) 100%) }} .choice-content {{ max-width:80% }} .choice-name {{ gap:10px; font-size:30px }} .choice-stats {{ grid-template-columns:repeat(3,minmax(0,1fr)); margin:8px 0; gap:5px }} .choice-stat {{ padding-left:7px; font-size:9px }} .choice-stat strong {{ font-size:16px; margin-bottom:2px }} .choice-deal {{ max-width:100%; font-size:11px }} .choice-cta {{ font-size:11px }} footer {{ padding:6px 10px 8px; font-size:10px }} }}
    @media(max-width:640px) and (max-height:700px) {{ .hero {{ min-height:90px; padding:8px 10px; margin-bottom:6px }} h1 {{ font-size:27px; margin:5px 0 3px }} .intro {{ font-size:11px }} .choice {{ min-height:clamp(185px,26svh,205px); padding:10px 14px 9px }} .choice-name {{ font-size:27px }} .choice-stats {{ margin:7px 0; gap:4px }} .choice-stat strong {{ font-size:15px }} .choice-deal {{ font-size:10px }} .choice-cta {{ margin-top:12px; padding:8px 12px }} footer {{ padding-block:4px }} }}
  </style>
</head>
<body data-cat="home">
  <nav aria-label="Hovedmenu">
    <a href="/" class="nav-logo"><span>RomSniffer</span></a>
  </nav>
  <main>
    <section class="hero" aria-labelledby="home-title">
      <div class="hero-copy">
      <div class="eyebrow">Sammenlign danske webshops</div>
      <h1 id="home-title">Find den billigste flaske</h1>
      <p class="intro">Vi sammenligner priser fra danske webshops, så du altid betaler mindst muligt.</p>
      </div>
    </section>
    <section class="choices" aria-label="Vælg rom eller whisky">
      <article class="choice">
        <img class="choice-image" src="/category-rum.jpg" alt="" loading="eager">
        <a class="choice-hit" href="/rom/" aria-label="Se {rom_products} rom" tabindex="-1"></a>
        <div class="choice-content">
        <span class="choice-name">Rom</span>
        <span class="choice-stats">
          <span class="choice-stat"><strong>{rom_products}</strong>produkter</span>
          <span class="choice-stat"><strong>{fmt(rom_stats.get('multi_shop'))}</strong>kan sammenlignes</span>
          <span class="choice-stat"><strong>{fmt(rom_stats.get('deals'))}</strong>aktive tilbud</span>
        </span>
        {deal_markup(rom_deal)}
        <a class="choice-cta" href="/rom/">Find rom →</a>
        </div>
      </article>
      <article class="choice">
        <img class="choice-image" src="/category-whisky.jpg" alt="" loading="eager">
        <a class="choice-hit" href="/whisky/" aria-label="Se {whisky_products} whiskyer" tabindex="-1"></a>
        <div class="choice-content">
        <span class="choice-name">Whisky</span>
        <span class="choice-stats">
          <span class="choice-stat"><strong>{whisky_products}</strong>produkter</span>
          <span class="choice-stat"><strong>{fmt(whisky_stats.get('multi_shop'))}</strong>kan sammenlignes</span>
          <span class="choice-stat"><strong>{fmt(whisky_stats.get('deals'))}</strong>aktive tilbud</span>
        </span>
        {deal_markup(whisky_deal)}
        <a class="choice-cta" href="/whisky/">Find whisky →</a>
        </div>
      </article>
    </section>
  </main>
  <footer>Priser opdateres dagligt <span aria-hidden="true">·</span> Gratis prissammenligning <span aria-hidden="true">·</span> RomSniffer kan modtage provision via forhandlerlinks.</footer>
</body>
</html>
'''


def main():
    if not TEMPLATE.is_file():
        raise SystemExit(f"RomSniffer-skabelonen mangler: {TEMPLATE}")
    source = TEMPLATE.read_text(encoding="utf-8")
    ROM_PAGE.parent.mkdir(parents=True, exist_ok=True)
    rom_data = json.loads(Path("rom_data.json").read_text(encoding="utf-8")) if Path("rom_data.json").is_file() else {"roms": [], "stats": {}}
    ROM_PAGE.write_text(_make_rom_page(source, rom_data), encoding="utf-8")
    HOME.write_text(_make_home(
        _stats("rom_data.json"), _stats("whisky_data.json"),
        _price_example("rom_data.json"), _price_example("whisky_data.json"),
    ), encoding="utf-8")
    print(f"Kategoriforside genereret: {HOME.resolve()}; romoversigt: {ROM_PAGE.resolve()}")


if __name__ == "__main__":
    main()

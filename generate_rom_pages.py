"""
generate_rom_pages.py — Generér statiske produktsider for hver rom.

Bygger /rom/{slug}/index.html med:
- Prissammenligning på tværs af butikker
- Product + AggregateOffer JSON-LD
- Relaterede rom (samme brand eller type)
- SEO-optimeret meta description
- Matchende dark mahogny-tema fra hovedsiden

Køres som del af build-pipeline i build_rom_data.py.
"""
import json
import os
import shutil
import sys
from datetime import datetime
from html import escape

from slugify_rom import slugify, make_unique_slug

# ────────────────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────────────────
ROM_DATA_FILE = "rom_data.json"
OUTPUT_DIR = "rom"
SITE_URL = "https://www.romsniffer.dk"
MAX_RELATED = 6

# ────────────────────────────────────────────────────────────
# HELPERS
# ────────────────────────────────────────────────────────────

def esc(text):
    """HTML-escape med fallback for None."""
    return escape(str(text)) if text else ""


def generate_description(rom):
    """Auto-generér en naturlig dansk beskrivelse fra metadata."""
    name = rom["name"]
    brand = rom.get("brand")
    country = rom.get("country")
    rom_type = rom.get("type")
    age = rom.get("age")
    abv = rom.get("abv")
    volume = rom.get("volume_cl")

    sentences = []

    # Åbningssætning — variér baseret på hvad vi ved
    if brand and country:
        sentences.append(f"{name} er en rom fra {brand}, produceret i {country}.")
    elif brand:
        sentences.append(f"{name} er en rom fra {brand}.")
    elif country:
        sentences.append(f"{name} er en rom med oprindelse i {country}.")
    else:
        sentences.append(f"{name} er en rom tilgængelig hos danske forhandlere.")

    # Type-beskrivelse
    type_descriptions = {
        "Aged rom": "Det er en lagret rom, modnet på egetræsfade for ekstra dybde og kompleksitet.",
        "Spiced": "Det er en spiced rom, tilsat krydderier som vanilje, kanel og muskatnød for en aromatisk smagsprofil.",
        "Hvid rom": "Det er en hvid rom — let, frisk og ideel som cocktailbase i drinks som Mojito og Daiquiri.",
        "Mørk rom": "Det er en mørk rom med fyldig karakter og noter af melasse, tørrede frugter og karamel.",
        "Overproof": "Det er en overproof rom med høj alkoholstyrke — intens i smag og velegnet til tiki-cocktails.",
        "Rhum Agricole": "Det er en rhum agricole, fremstillet af frisk presset sukkerrørsjuice, som giver en frisk og floral karakter.",
        "Cachaça": "Det er en cachaça — Brasiliens nationaldrik, lavet af frisk sukkerrørsjuice og uundværlig i en Caipirinha.",
        "Navy Rum": "Det er en navy rum med robust karakter og traditionelt høj styrke, inspireret af Royal Navys historiske ration.",
        "Gylden rom": "Det er en gylden rom med en balanceret smag mellem let hvid rom og fyldig mørk rom.",
    }
    if rom_type and rom_type in type_descriptions:
        sentences.append(type_descriptions[rom_type])

    # Alder
    if age and age not in ("Reserva",):
        if age == "XO":
            sentences.append("Betegnelsen XO (Extra Old) signalerer langvarig lagring, typisk 6 år eller mere.")
        elif age == "Solera":
            sentences.append("Den er produceret med solera-metoden, hvor rom af forskellige aldre blandes løbende for en kompleks og afrundet smag.")
        elif "år" in str(age):
            sentences.append(f"Med en lagring på {age} har denne rom haft tid til at udvikle dybere smagsnoter fra fadet.")

    # Tekniske detaljer
    details = []
    if abv:
        abv_str = f"{abv:.0f}" if abv == int(abv) else f"{abv}"
        details.append(f"en alkoholprocent på {abv_str}%")
    if volume:
        details.append(f"en flaskestørrelse på {volume:.0f} cl")
    if details:
        sentences.append(f"Rommen har {' og '.join(details)}.")

    # Prissammenligning-vinkel
    if rom["shop_count"] > 1:
        sentences.append(f"Sammenlign priser fra {rom['shop_count']} danske butikker her på RomSniffer og find den billigste pris.")
    else:
        sentences.append("Se den aktuelle pris og køb direkte via RomSniffer.")

    return " ".join(sentences)


def meta_description(rom):
    """SEO-optimeret meta description for en rom-side."""
    name = rom["name"]
    price = rom["min_price"]
    shop_count = rom["shop_count"]
    parts = []

    if shop_count > 1:
        parts.append(f"Sammenlign priser på {name} fra {shop_count} danske butikker.")
    else:
        parts.append(f"Se pris på {name} fra danske webshops.")

    parts.append(f"Billigste pris: {price:.0f} kr.")

    extras = []
    if rom.get("brand"):
        extras.append(rom["brand"])
    if rom.get("country"):
        extras.append(rom["country"])
    if rom.get("age"):
        extras.append(rom["age"])
    if rom.get("type"):
        extras.append(rom["type"])
    if extras:
        parts.append(" — ".join(extras) + ".")

    desc = " ".join(parts)
    # Google viser ~155 tegn
    if len(desc) > 155:
        desc = desc[:152] + "..."
    return desc


def json_ld(rom, slug):
    """Product + AggregateOffer structured data."""
    offers = []
    for p in rom["prices"]:
        offer = {
            "@type": "Offer",
            "url": p["url"],
            "priceCurrency": "DKK",
            "price": f"{p['price']:.2f}",
            "availability": "https://schema.org/InStock",
            "seller": {
                "@type": "Organization",
                "name": p["shop_name"],
            },
        }
        offers.append(offer)

    data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": rom["name"],
        "url": f"{SITE_URL}/rom/{slug}/",
        "category": "Rom",
    }

    if rom.get("image"):
        data["image"] = rom["image"]
    if rom.get("brand"):
        data["brand"] = {"@type": "Brand", "name": rom["brand"]}
    if rom.get("abv"):
        data["additionalProperty"] = [
            {"@type": "PropertyValue", "name": "ABV", "value": f"{rom['abv']}%"}
        ]

    if offers:
        data["offers"] = {
            "@type": "AggregateOffer",
            "lowPrice": f"{rom['min_price']:.2f}",
            "highPrice": f"{max(p['price'] for p in rom['prices']):.2f}",
            "priceCurrency": "DKK",
            "offerCount": len(offers),
            "offers": offers,
        }

    return json.dumps(data, ensure_ascii=False, indent=2)


def find_related(rom, all_roms, slug_map):
    """Find relaterede rom: først same brand, derefter same type."""
    related = []
    seen = {rom["name"]}

    # Samme brand
    if rom.get("brand"):
        for r in all_roms:
            if r["name"] in seen:
                continue
            if r.get("brand") == rom["brand"]:
                related.append(r)
                seen.add(r["name"])
                if len(related) >= MAX_RELATED:
                    break

    # Fyld op med same type
    if len(related) < MAX_RELATED and rom.get("type"):
        for r in all_roms:
            if r["name"] in seen:
                continue
            if r.get("type") == rom["type"]:
                related.append(r)
                seen.add(r["name"])
                if len(related) >= MAX_RELATED:
                    break

    return related


# ────────────────────────────────────────────────────────────
# HTML TEMPLATE
# ────────────────────────────────────────────────────────────

def render_page(rom, slug, related, slug_map, updated):
    """Generér HTML for en rom-side."""

    name_esc = esc(rom["name"])
    desc_esc = esc(meta_description(rom))
    brand_esc = esc(rom.get("brand") or "")
    country_esc = esc(rom.get("country") or "")
    type_esc = esc(rom.get("type") or "")
    age_esc = esc(rom.get("age") or "")
    image_url = esc(rom.get("image") or "")
    canonical = f"{SITE_URL}/rom/{slug}/"

    # Metadata pills (land, type, alder linker til kategorisider)
    pills = []
    if rom.get("brand"):
        pills.append(f'<span class="pill">{brand_esc}</span>')
    if rom.get("country"):
        c_slug = slugify(rom["country"])
        pills.append(f'<a href="{SITE_URL}/rom/land/{c_slug}/" class="pill pill-link">{country_esc}</a>')
    if rom.get("type"):
        t_slug = slugify(rom["type"])
        pills.append(f'<a href="{SITE_URL}/rom/type/{t_slug}/" class="pill pill-link">{type_esc}</a>')
    if rom.get("age"):
        a_slug = slugify(rom["age"])
        pills.append(f'<a href="{SITE_URL}/rom/alder/{a_slug}/" class="pill pill-link">{age_esc}</a>')
    if rom.get("abv"):
        pills.append(f'<span class="pill">{rom["abv"]}%</span>')
    if rom.get("volume_cl"):
        pills.append(f'<span class="pill">{rom["volume_cl"]:.0f} cl</span>')
    pills_html = "\n            ".join(pills)

    # Pristabel
    prices_rows = []
    for i, p in enumerate(rom["prices"]):
        shop_esc = esc(p["shop_name"])
        price_str = f'{p["price"]:.0f} kr'
        old_price_html = ""
        if p.get("old_price") and p["old_price"] > p["price"]:
            old_price_html = f'<span class="old-price">{p["old_price"]:.0f} kr</span>'
        discount_html = ""
        if p.get("discount_pct") and p["discount_pct"] > 0:
            discount_html = f'<span class="discount-badge">-{p["discount_pct"]:.0f}%</span>'

        cheapest_class = ' class="cheapest"' if i == 0 and len(rom["prices"]) > 1 else ""

        prices_rows.append(f"""            <tr{cheapest_class}>
                <td class="shop-name">{shop_esc}</td>
                <td class="price-cell">
                    {old_price_html}
                    <span class="current-price">{price_str}</span>
                    {discount_html}
                </td>
                <td class="buy-cell"><a href="{esc(p['url'])}" target="_blank" rel="noopener noreferrer nofollow" class="buy-btn">Køb →</a></td>
            </tr>""")
    prices_html = "\n".join(prices_rows)

    # Besparelse
    savings_html = ""
    if len(rom["prices"]) > 1:
        highest = max(p["price"] for p in rom["prices"])
        lowest = rom["min_price"]
        if highest > lowest:
            savings = highest - lowest
            savings_html = f'<p class="savings">Spar op til <strong>{savings:.0f} kr</strong> ved at vælge den billigste butik</p>'

    # Relaterede rom
    related_cards = []
    for r in related:
        r_slug = slug_map.get(r["name"], "")
        if not r_slug:
            continue
        r_img = esc(r.get("image") or "")
        r_name = esc(r["name"])
        r_price = f'{r["min_price"]:.0f} kr'
        r_badge = ""
        if r["shop_count"] > 1:
            r_badge = f'<span class="rel-shops">{r["shop_count"]} butikker</span>'
        img_tag = f'<img src="{r_img}" alt="{r_name}" loading="lazy">' if r_img else '<div class="no-img">🥃</div>'
        related_cards.append(f"""        <a href="{SITE_URL}/rom/{r_slug}/" class="rel-card">
            <div class="rel-img">{img_tag}</div>
            <div class="rel-info">
                <p class="rel-name">{r_name}</p>
                <p class="rel-price">{r_price} {r_badge}</p>
            </div>
        </a>""")
    related_html = "\n".join(related_cards)
    related_section = ""
    if related_cards:
        related_section = f"""
    <section class="related">
        <h2>Relaterede rom</h2>
        <div class="rel-grid">
{related_html}
        </div>
    </section>"""

    # Image
    img_section = ""
    if image_url:
        img_section = f'<img src="{image_url}" alt="{name_esc}" class="product-img">'
    else:
        img_section = '<div class="product-img no-img-hero">🥃</div>'

    return f"""<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name_esc} — Sammenlign priser | RomSniffer</title>
<meta name="description" content="{desc_esc}">
<link rel="canonical" href="{canonical}">
<link rel="icon" href="{SITE_URL}/logo.png">
<meta property="og:title" content="{name_esc} — RomSniffer">
<meta property="og:description" content="{desc_esc}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="product">
{f'<meta property="og:image" content="{image_url}">' if image_url else ''}
<meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<script type="application/ld+json">
{json_ld(rom, slug)}
</script>
<style>
:root {{
    --bg: #0a0604;
    --surface: #1a0f08;
    --surface2: #251810;
    --surface3: #2f1f14;
    --caramel: #c8741e;
    --caramel-light: #f0a050;
    --copper: #b87333;
    --copper-light: #d99458;
    --text: #f5e4cf;
    --text-muted: #a08570;
    --border: #2e1d10;
    --border-light: #3d2818;
    --discount: #3dba6f;
    --gold: #d4a847;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'DM Sans', sans-serif;
    line-height: 1.6;
    min-height: 100vh;
}}
a {{ color: var(--copper-light); text-decoration: none; }}
a:hover {{ color: var(--caramel-light); }}

/* NAV */
nav {{
    background: rgba(10,6,4,0.97);
    backdrop-filter: blur(12px);
    border-bottom: 1px solid var(--border);
    padding: 0.85rem 2rem;
    display: flex;
    justify-content: space-between;
    align-items: center;
    position: sticky;
    top: 0;
    z-index: 200;
}}
.nav-logo {{
    display: flex;
    align-items: center;
    gap: 0.6rem;
    text-decoration: none;
}}
.nav-logo img {{ width: 40px; height: 40px; object-fit: contain; }}
.nav-logo span {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.5rem;
    letter-spacing: 0.06em;
    background: linear-gradient(135deg, var(--copper-light), var(--copper));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}}
.nav-links {{ display: flex; gap: 1.5rem; }}
.nav-links a {{
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--text-muted);
    letter-spacing: 0.03em;
}}
.nav-links a:hover {{ color: var(--text); }}
@media (max-width: 600px) {{
    nav {{ padding: 0.7rem 1rem; }}
    .nav-links {{ gap: 0.8rem; }}
    .nav-links a {{ font-size: 0.78rem; }}
}}

/* BREADCRUMB */
.breadcrumb {{
    max-width: 900px;
    margin: 1.2rem auto 0;
    padding: 0 1.5rem;
    font-size: 0.82rem;
    color: var(--text-muted);
}}
.breadcrumb a {{ color: var(--copper-light); }}

/* PRODUCT HERO */
.product-hero {{
    max-width: 900px;
    margin: 1.5rem auto 0;
    padding: 0 1.5rem;
    display: grid;
    grid-template-columns: 220px 1fr;
    gap: 2rem;
    align-items: start;
}}
@media (max-width: 700px) {{
    .product-hero {{
        grid-template-columns: 1fr;
        text-align: center;
    }}
    .product-hero .img-wrap {{ justify-self: center; }}
}}
.img-wrap {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1rem;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 240px;
}}
.product-img {{
    max-width: 100%;
    max-height: 280px;
    object-fit: contain;
    border-radius: 8px;
}}
.no-img-hero {{
    font-size: 5rem;
    opacity: 0.3;
    width: 100%;
    text-align: center;
}}
h1 {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: 2rem;
    letter-spacing: 0.03em;
    line-height: 1.15;
    color: var(--text);
    margin-bottom: 0.75rem;
}}
.pills {{
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
    margin-bottom: 1rem;
}}
.pill {{
    background: var(--surface2);
    border: 1px solid var(--border-light);
    border-radius: 20px;
    padding: 0.25rem 0.75rem;
    font-size: 0.78rem;
    color: var(--text-muted);
    white-space: nowrap;
}}
.hero-price {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: 2.8rem;
    color: var(--caramel-light);
    line-height: 1;
    margin-bottom: 0.3rem;
}}
.hero-price-sub {{
    font-size: 0.85rem;
    color: var(--text-muted);
    margin-bottom: 1rem;
}}
.hero-buy {{
    display: inline-block;
    background: var(--caramel);
    color: #fff;
    padding: 0.7rem 1.8rem;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.95rem;
    transition: background 0.15s;
}}
.hero-buy:hover {{ background: var(--caramel-light); color: #1a0f08; }}

/* DESCRIPTION */
.description {{
    max-width: 900px;
    margin: 2rem auto 0;
    padding: 0 1.5rem;
}}
.description h2 {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.3rem;
    letter-spacing: 0.05em;
    color: var(--copper-light);
    margin-bottom: 0.6rem;
}}
.description p {{
    color: var(--text-muted);
    font-size: 0.92rem;
    line-height: 1.7;
}}

/* PRICES TABLE */
.prices-section {{
    max-width: 900px;
    margin: 2.5rem auto 0;
    padding: 0 1.5rem;
}}
.prices-section h2 {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.3rem;
    letter-spacing: 0.05em;
    color: var(--copper-light);
    margin-bottom: 0.8rem;
}}
.prices-table {{
    width: 100%;
    border-collapse: collapse;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
}}
.prices-table tr {{ border-bottom: 1px solid var(--border); }}
.prices-table tr:last-child {{ border-bottom: none; }}
.prices-table td {{ padding: 0.85rem 1rem; vertical-align: middle; }}
.shop-name {{ font-weight: 500; color: var(--text); }}
.price-cell {{ text-align: right; white-space: nowrap; }}
.current-price {{ font-weight: 700; font-size: 1.05rem; }}
.old-price {{
    text-decoration: line-through;
    color: var(--text-muted);
    font-size: 0.85rem;
    margin-right: 0.5rem;
}}
.discount-badge {{
    background: var(--discount);
    color: #fff;
    font-size: 0.72rem;
    font-weight: 700;
    padding: 0.15rem 0.45rem;
    border-radius: 4px;
    margin-left: 0.4rem;
}}
.buy-cell {{ text-align: right; }}
.buy-btn {{
    display: inline-block;
    background: var(--surface2);
    border: 1px solid var(--border-light);
    color: var(--copper-light);
    padding: 0.45rem 1rem;
    border-radius: 6px;
    font-size: 0.82rem;
    font-weight: 600;
    transition: all 0.15s;
}}
.buy-btn:hover {{ background: var(--caramel); color: #fff; border-color: var(--caramel); }}
.cheapest .current-price {{ color: var(--discount); }}
.cheapest .shop-name::after {{
    content: "Billigst";
    background: var(--discount);
    color: #fff;
    font-size: 0.65rem;
    font-weight: 700;
    padding: 0.1rem 0.4rem;
    border-radius: 3px;
    margin-left: 0.5rem;
    vertical-align: middle;
}}
.savings {{
    margin-top: 0.6rem;
    font-size: 0.85rem;
    color: var(--discount);
}}
@media (max-width: 600px) {{
    .prices-table td {{ padding: 0.65rem 0.6rem; font-size: 0.88rem; }}
    .buy-btn {{ padding: 0.4rem 0.7rem; font-size: 0.78rem; }}
}}

/* RELATED */
.related {{
    max-width: 900px;
    margin: 3rem auto 0;
    padding: 0 1.5rem;
}}
.related h2 {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.3rem;
    letter-spacing: 0.05em;
    color: var(--copper-light);
    margin-bottom: 1rem;
}}
.rel-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 0.8rem;
}}
.rel-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
    transition: border-color 0.15s;
    text-decoration: none;
}}
.rel-card:hover {{ border-color: var(--copper); }}
.rel-img {{
    height: 130px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--surface2);
    overflow: hidden;
}}
.rel-img img {{ max-height: 120px; max-width: 100%; object-fit: contain; }}
.no-img {{ font-size: 2.5rem; opacity: 0.25; }}
.rel-info {{ padding: 0.6rem 0.7rem; }}
.rel-name {{
    font-size: 0.78rem;
    font-weight: 500;
    color: var(--text);
    line-height: 1.3;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}}
.rel-price {{
    font-size: 0.82rem;
    font-weight: 700;
    color: var(--caramel-light);
    margin-top: 0.25rem;
}}
.rel-shops {{
    font-size: 0.68rem;
    font-weight: 500;
    color: var(--discount);
    margin-left: 0.3rem;
}}

/* FOOTER */
footer {{
    max-width: 900px;
    margin: 3rem auto 0;
    padding: 1.5rem;
    border-top: 1px solid var(--border);
    text-align: center;
    color: var(--text-muted);
    font-size: 0.78rem;
    line-height: 1.8;
}}
footer a {{ color: var(--copper-light); }}
</style>
</head>
<body>
    <nav>
        <a href="{SITE_URL}/" class="nav-logo">
            <img src="{SITE_URL}/logo.png" alt="RomSniffer">
            <span>RomSniffer</span>
        </a>
        <div class="nav-links">
            <a href="{SITE_URL}/">Alle rom</a>
            <a href="{SITE_URL}/premium.html">Premium</a>
            <a href="{SITE_URL}/guide.html">Guide</a>
            <a href="{SITE_URL}/om.html">Om</a>
        </div>
    </nav>

    <div class="breadcrumb">
        <a href="{SITE_URL}/">RomSniffer</a> › <a href="{SITE_URL}/">Alle rom</a> › {name_esc}
    </div>

    <div class="product-hero">
        <div class="img-wrap">
            {img_section}
        </div>
        <div>
            <h1>{name_esc}</h1>
            <div class="pills">
            {pills_html}
            </div>
            <div class="hero-price">{rom["min_price"]:.0f} kr</div>
            <p class="hero-price-sub">Billigste pris fra {esc(rom["prices"][0]["shop_name"])}</p>
            <a href="{esc(rom["prices"][0]["url"])}" target="_blank" rel="noopener noreferrer nofollow" class="hero-buy">Køb billigst →</a>
        </div>
    </div>

    <section class="description">
        <h2>Om denne rom</h2>
        <p>{esc(generate_description(rom))}</p>
    </section>

    <section class="prices-section">
        <h2>Priser fra {rom["shop_count"]} butik{"ker" if rom["shop_count"] > 1 else ""}</h2>
        <table class="prices-table">
{prices_html}
        </table>
        {savings_html}
        <p style="font-size:0.75rem; color:var(--text-muted); margin-top:0.6rem;">
            Priser opdateret {updated} — tjek altid den endelige pris hos butikken.
        </p>
    </section>
{related_section}

    <footer>
        <a href="{SITE_URL}/">← Alle rom og priser</a><br>
        <strong>Affiliate disclosure:</strong> RomSniffer kan modtage provision via links. Det koster dig intet ekstra.<br>
        🥃 RomSniffer © 2026 — Kun for personer over 18 år
    </footer>
</body>
</html>"""


# ────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────

def main():
    print("\n📄 Genererer rom-sider...")

    # Indlæs data
    if not os.path.exists(ROM_DATA_FILE):
        print(f"   ❌ {ROM_DATA_FILE} ikke fundet — kør build_rom_data.py først")
        sys.exit(1)

    with open(ROM_DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    roms = data.get("roms", [])
    updated_raw = data.get("updated", "")
    try:
        updated = datetime.fromisoformat(updated_raw).strftime("%d. %b %Y")
    except Exception:
        updated = updated_raw[:10] if updated_raw else "ukendt"

    if not roms:
        print("   ❌ Ingen rom i data")
        return

    # Byg slugs
    seen_slugs = set()
    slug_map = {}  # name → slug
    for rom in roms:
        slug = make_unique_slug(rom["name"], seen_slugs)
        slug_map[rom["name"]] = slug

    # Ryd gammel output (slet mapper der ikke længere har en rom)
    # Mapper der ikke skal slettes (kategorisider)
    PROTECTED_DIRS = {"land", "type", "alder"}
    existing_dirs = set()
    if os.path.isdir(OUTPUT_DIR):
        for entry in os.listdir(OUTPUT_DIR):
            full = os.path.join(OUTPUT_DIR, entry)
            if os.path.isdir(full) and entry not in PROTECTED_DIRS:
                existing_dirs.add(entry)

    new_slugs = set(slug_map.values())
    stale = existing_dirs - new_slugs
    if stale:
        print(f"   🧹 Sletter {len(stale)} forældede rom-mapper...")
        for s in stale:
            shutil.rmtree(os.path.join(OUTPUT_DIR, s), ignore_errors=True)

    # Generér sider
    count = 0
    for rom in roms:
        slug = slug_map[rom["name"]]
        related = find_related(rom, roms, slug_map)
        html = render_page(rom, slug, related, slug_map, updated)

        out_dir = os.path.join(OUTPUT_DIR, slug)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "index.html")

        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)

        count += 1

    print(f"   ✅ {count} rom-sider genereret i /{OUTPUT_DIR}/")

    # Stats
    multi = sum(1 for r in roms if r["shop_count"] > 1)
    print(f"   📊 Heraf {multi} med prissammenligning (flere butikker)")

    return slug_map


if __name__ == "__main__":
    main()
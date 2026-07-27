"""
generate_category_pages.py — Generér statiske kategorisider.

Bygger:
- /rom/land/{slug}/index.html   (ét land pr. side)
- /rom/type/{slug}/index.html   (én type pr. side)
- /rom/alder/{slug}/index.html  (én alder pr. side)

Hver side har:
- Filtreret produktgrid med links til /rom/{slug}/
- SEO meta description
- CollectionPage JSON-LD
- Krydslinks til andre kategorier

Køres som del af build-pipeline i build_rom_data.py.
"""
import json
import os
import shutil
import sys
from datetime import datetime
from html import escape

from slugify_rom import slugify

# ────────────────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────────────────
ROM_DATA_FILE = "rom_data.json"
OUTPUT_BASE = "rom"
SITE_URL = "https://www.romsniffer.dk"
MAX_PRODUCTS_PER_PAGE = 200

# ────────────────────────────────────────────────────────────
# CATEGORY DEFINITIONS
# ────────────────────────────────────────────────────────────

# Danske SEO-tekster for typer
TYPE_DESCRIPTIONS = {
    "Aged rom": "Lagret rom modnet på egetræsfade — dybde, kompleksitet og rig smag fra årelang lagring. Perfekt til nydelse pur eller i premium cocktails.",
    "Spiced": "Spiced rom tilsat krydderier som vanilje, kanel og muskatnød. Aromatisk og alsidig — god pur, med cola eller i tiki-drinks.",
    "Hvid rom": "Let og frisk hvid rom — den perfekte cocktailbase til Mojito, Daiquiri og andre klassikere. Ren smag af sukkerrør.",
    "Mørk rom": "Fyldig mørk rom med intense noter af melasse, tørrede frugter og karamel. Velegnet til pur nydelse og kraftige cocktails.",
    "Overproof": "Overproof rom med høj alkoholstyrke — intens smag og fylde. Uundværlig i tiki-cocktails og Rum Punch.",
    "Rhum Agricole": "Rhum Agricole fra de franske Caribien — fremstillet af frisk sukkerrørsjuice for en unik floral og grøn karakter.",
    "Cachaça": "Brasiliens nationaldrik lavet af frisk sukkerrørsjuice. Uundværlig til Caipirinha og andre brasilianske cocktails.",
    "Navy Rum": "Traditionel navy rum med robust karakter og høj styrke, inspireret af Royal Navys historiske daglige ration.",
    "Gylden rom": "Gylden rom med en balanceret smag — lettere end mørk, mere karakter end hvid. Alsidig til både pur nydelse og cocktails.",
}

# Danske SEO-tekster for lande
COUNTRY_DESCRIPTIONS = {
    "Barbados": "Barbados er rom-industriens vugge og hjemsted for legendariske destillerier som Foursquare og Mount Gay.",
    "Jamaica": "Jamaicansk rom er kendt for sin kraftige, funky smag med høje estere — fra Hampden Estate til Appleton.",
    "Cuba": "Cubansk rom er verdenskendt for sin lethed og elegance. Havana Club og Santiago de Cuba definerer stilen.",
    "Guatemala": "Guatemala producerer nogle af verdens mest raffinerede rom — Ron Zacapa og Botran er flagskibene.",
    "Guyana": "Guyana er hjemsted for El Dorado og den legendariske Demerara-destillering med unikke trækontinuerlige stillere.",
    "Trinidad": "Trinidad byder på Angostura og Diplomatico-traditioner med balancerede, elegante rom.",
    "Martinique": "Martinique er centrum for Rhum Agricole — AOC-beskyttet rom lavet af frisk sukkerrørsjuice.",
    "Panama": "Panamansk rom er typisk blød og tilgængelig — Abuelo og Ron Centenario er populære valg.",
    "Nicaragua": "Nicaraguansk rom fra Flor de Caña er kendt for sin vulkanske filtrering og miljøbevidste produktion.",
    "Venezuela": "Venezuelansk rom fra Santa Teresa og Diplomatico er fyldig og elegant med solera-traditioner.",
    "Dominikansk": "Den Dominikanske Republik producerer bløde, venlige rom — Brugal, Barceló og Ron Bermúdez.",
    "Colombia": "Colombiansk rom med Dictador i spidsen byder på innovative fade og premium single cask-udgivelser.",
    "Peru": "Peruansk rom fra Cartavio og Millonario er kendetegnet ved sødme og tropisk frugtighed.",
    "Brasilien": "Brasilien er hjemsted for cachaça — verdens tredjestørste spirituskategori, lavet af frisk sukkerrør.",
    "Filippinerne": "Filippinsk rom fra Don Papa byder på tropisk sødme og en unik asiatisk tilgang til rom.",
    "Puerto Rico": "Puerto Rico er hjemsted for Bacardi og en lang tradition for let, elegant rom.",
    "Dansk": "Danske rom-producenter og bottlere bringer nordisk kvalitet og kreativitet til rom-verdenen.",
}


def esc(text):
    return escape(str(text)) if text else ""


def category_slug(name):
    """Slug for kategorinavne."""
    return slugify(name)


# ────────────────────────────────────────────────────────────
# PRODUCT CARD HTML
# ────────────────────────────────────────────────────────────

def render_product_card(rom):
    """Render et produktkort med link til rom-side."""
    slug = rom.get("slug", "")
    name_esc = esc(rom["name"])
    price_str = f'{rom["min_price"]:.0f} kr'
    image = rom.get("image") or ""

    img_html = f'<img src="{esc(image)}" alt="{name_esc}" loading="lazy">' if image else '<div class="card-ph">🥃</div>'

    pills = []
    if rom.get("brand"):
        pills.append(esc(rom["brand"]))
    if rom.get("age"):
        pills.append(esc(rom["age"]))
    if rom.get("abv"):
        pills.append(f'{rom["abv"]}%')
    pills_html = " · ".join(pills)

    shop_badge = ""
    if rom["shop_count"] > 1:
        shop_badge = f'<span class="card-shops">{rom["shop_count"]} butikker</span>'

    discount_badge = ""
    if rom.get("max_discount_pct") and rom["max_discount_pct"] > 0:
        discount_badge = f'<span class="card-discount">-{rom["max_discount_pct"]:.0f}%</span>'

    return f'''<a href="{SITE_URL}/rom/{slug}/" class="cat-card">
        {discount_badge}
        <div class="card-img">{img_html}</div>
        <div class="card-info">
            <p class="card-name">{name_esc}</p>
            <p class="card-pills">{pills_html}</p>
            <div class="card-bottom">
                <span class="card-price">{price_str}</span>
                {shop_badge}
            </div>
        </div>
    </a>'''


# ────────────────────────────────────────────────────────────
# PAGE TEMPLATE
# ────────────────────────────────────────────────────────────

def render_category_page(title, description, breadcrumb_label, breadcrumb_path,
                         roms, canonical, related_cats, updated, category_type):
    """Generér HTML for en kategoriside."""

    title_esc = esc(title)
    desc_esc = esc(description[:155])

    # Produktkort
    cards_html = "\n".join(render_product_card(r) for r in roms[:MAX_PRODUCTS_PER_PAGE])

    # Stats
    count = len(roms)
    min_price = min(r["min_price"] for r in roms) if roms else 0
    max_price = max(r["min_price"] for r in roms) if roms else 0
    multi = sum(1 for r in roms if r["shop_count"] > 1)

    # Relaterede kategorier
    related_html = ""
    if related_cats:
        links = []
        for cat_name, cat_path in related_cats[:12]:
            links.append(f'<a href="{SITE_URL}{cat_path}" class="rel-tag">{esc(cat_name)}</a>')
        related_html = f'''
    <section class="related-cats">
        <h2>Udforsk mere</h2>
        <div class="rel-tags">{" ".join(links)}</div>
    </section>'''

    # JSON-LD
    json_ld = json.dumps({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": title,
        "description": description[:155],
        "url": canonical,
        "numberOfItems": count,
    }, ensure_ascii=False, indent=2)

    return f'''<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title_esc} | RomSniffer</title>
<meta name="description" content="{desc_esc}">
<link rel="canonical" href="{canonical}">
<link rel="icon" href="{SITE_URL}/logo.png">
<meta property="og:title" content="{title_esc}">
<meta property="og:description" content="{desc_esc}">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<script type="application/ld+json">
{json_ld}
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
    --text-dim: #5a4838;
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
    display: flex; align-items: center; gap: 0.6rem; text-decoration: none;
}}
.nav-logo img {{ width: 40px; height: 40px; object-fit: contain; }}
.nav-logo span {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.5rem; letter-spacing: 0.06em;
    background: linear-gradient(135deg, var(--copper-light), var(--copper));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}}
.nav-links {{ display: flex; gap: 1.5rem; }}
.nav-links a {{ font-size: 0.85rem; font-weight: 500; color: var(--text-muted); }}
.nav-links a:hover {{ color: var(--text); }}
@media (max-width: 600px) {{
    nav {{ padding: 0.7rem 1rem; }}
    .nav-links {{ gap: 0.8rem; }}
    .nav-links a {{ font-size: 0.78rem; }}
}}

.breadcrumb {{
    max-width: 1100px; margin: 1.2rem auto 0; padding: 0 1.5rem;
    font-size: 0.82rem; color: var(--text-muted);
}}
.breadcrumb a {{ color: var(--copper-light); }}

.cat-hero {{
    max-width: 1100px; margin: 1.5rem auto 0; padding: 0 1.5rem 2rem;
    border-bottom: 1px solid var(--border);
}}
.cat-hero h1 {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: 2.2rem; letter-spacing: 0.03em; line-height: 1.15;
    margin-bottom: 0.5rem;
}}
.cat-hero p {{
    color: var(--text-muted); font-size: 0.92rem; line-height: 1.7;
    max-width: 700px;
}}
.cat-stats {{
    display: flex; gap: 1.5rem; margin-top: 1rem; flex-wrap: wrap;
}}
.cat-stat {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 0.5rem 1rem;
    font-size: 0.82rem; color: var(--text-muted);
}}
.cat-stat strong {{
    color: var(--caramel-light); font-family: 'Bebas Neue', sans-serif;
    font-size: 1.2rem; margin-right: 0.3rem;
}}

.cat-grid {{
    max-width: 1100px; margin: 2rem auto 0; padding: 0 1.5rem;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 0.8rem;
}}
@media (max-width: 500px) {{
    .cat-grid {{ grid-template-columns: repeat(2, 1fr); gap: 0.6rem; }}
}}

.cat-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; overflow: hidden;
    text-decoration: none; display: block;
    transition: border-color 0.15s, transform 0.15s;
    position: relative;
}}
.cat-card:hover {{ border-color: var(--copper); transform: translateY(-2px); }}
.card-img {{
    height: 150px; display: flex; align-items: center; justify-content: center;
    background: var(--surface2); overflow: hidden;
}}
.card-img img {{ max-height: 140px; max-width: 100%; object-fit: contain; }}
.card-ph {{ font-size: 2.5rem; opacity: 0.25; }}
.card-info {{ padding: 0.6rem 0.7rem; }}
.card-name {{
    font-size: 0.78rem; font-weight: 500; color: var(--text);
    line-height: 1.3;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    overflow: hidden; min-height: 2.1em;
}}
.card-pills {{
    font-size: 0.7rem; color: var(--text-dim); margin-top: 0.2rem;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.card-bottom {{
    display: flex; align-items: center; gap: 0.4rem;
    margin-top: 0.35rem;
}}
.card-price {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.1rem; color: var(--caramel-light);
}}
.card-shops {{
    font-size: 0.65rem; font-weight: 600; color: var(--discount);
    background: rgba(61,186,111,0.1); padding: 0.1rem 0.4rem;
    border-radius: 3px;
}}
.card-discount {{
    position: absolute; top: 0.4rem; right: 0.4rem;
    background: var(--discount); color: #fff;
    font-size: 0.68rem; font-weight: 700;
    padding: 0.15rem 0.4rem; border-radius: 4px;
}}

.related-cats {{
    max-width: 1100px; margin: 3rem auto 0; padding: 0 1.5rem;
}}
.related-cats h2 {{
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.3rem; letter-spacing: 0.05em;
    color: var(--copper-light); margin-bottom: 0.8rem;
}}
.rel-tags {{ display: flex; flex-wrap: wrap; gap: 0.5rem; }}
.rel-tag {{
    background: var(--surface2); border: 1px solid var(--border-light);
    border-radius: 20px; padding: 0.35rem 0.9rem;
    font-size: 0.8rem; color: var(--text-muted);
    transition: all 0.15s;
}}
.rel-tag:hover {{ border-color: var(--copper); color: var(--text); }}

footer {{
    max-width: 1100px; margin: 3rem auto 0; padding: 1.5rem;
    border-top: 1px solid var(--border);
    text-align: center; color: var(--text-muted); font-size: 0.78rem; line-height: 1.8;
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
        <a href="{SITE_URL}/">RomSniffer</a> › <a href="{SITE_URL}/">Alle rom</a> › {esc(breadcrumb_label)}
    </div>

    <div class="cat-hero">
        <h1>{title_esc}</h1>
        <p>{esc(description)}</p>
        <div class="cat-stats">
            <div class="cat-stat"><strong>{count}</strong> rom</div>
            <div class="cat-stat"><strong>{min_price:.0f}–{max_price:.0f}</strong> kr</div>
            {"<div class='cat-stat'><strong>" + str(multi) + "</strong> med prissammenligning</div>" if multi > 0 else ""}
        </div>
    </div>

    <div class="cat-grid">
{cards_html}
    </div>
{related_html}

    <footer>
        <a href="{SITE_URL}/">← Alle rom og priser</a><br>
        🥃 RomSniffer © 2026 — Kun for personer over 18 år
    </footer>
</body>
</html>'''


# ────────────────────────────────────────────────────────────
# BUILDERS
# ────────────────────────────────────────────────────────────

def build_country_pages(roms, updated, all_types, all_ages):
    """Byg /rom/land/{slug}/index.html for hvert land."""
    countries = {}
    for r in roms:
        c = r.get("country")
        if c:
            countries.setdefault(c, []).append(r)

    count = 0
    for country, country_roms in sorted(countries.items()):
        slug = category_slug(country)
        path = f"/rom/land/{slug}/"
        canonical = f"{SITE_URL}{path}"

        desc = COUNTRY_DESCRIPTIONS.get(country, f"Udforsk rom fra {country}.")
        desc += f" Sammenlign priser på {len(country_roms)} rom fra {country} hos danske webshops."

        # Relaterede: andre lande + typer
        related = [(c, f"/rom/land/{category_slug(c)}/") for c in sorted(countries.keys()) if c != country]
        related += [(t, f"/rom/type/{category_slug(t)}/") for t in all_types[:6]]

        html = render_category_page(
            title=f"Rom fra {country}",
            description=desc,
            breadcrumb_label=country,
            breadcrumb_path=path,
            roms=sorted(country_roms, key=lambda x: x["min_price"]),
            canonical=canonical,
            related_cats=related,
            updated=updated,
            category_type="land",
        )

        out_dir = os.path.join(OUTPUT_BASE, "land", slug)
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
        count += 1

    return count, list(countries.keys())


def build_type_pages(roms, updated, all_countries, all_ages):
    """Byg /rom/type/{slug}/index.html for hver type."""
    types = {}
    for r in roms:
        t = r.get("type")
        if t:
            types.setdefault(t, []).append(r)

    count = 0
    for rom_type, type_roms in sorted(types.items()):
        slug = category_slug(rom_type)
        path = f"/rom/type/{slug}/"
        canonical = f"{SITE_URL}{path}"

        desc = TYPE_DESCRIPTIONS.get(rom_type, f"Udforsk {rom_type.lower()} rom.")
        desc += f" Sammenlign priser på {len(type_roms)} {rom_type.lower()} hos danske webshops."

        # Relaterede: andre typer + lande
        related = [(t, f"/rom/type/{category_slug(t)}/") for t in sorted(types.keys()) if t != rom_type]
        related += [(c, f"/rom/land/{category_slug(c)}/") for c in all_countries[:6]]

        html = render_category_page(
            title=f"{rom_type} — Sammenlign priser",
            description=desc,
            breadcrumb_label=rom_type,
            breadcrumb_path=path,
            roms=sorted(type_roms, key=lambda x: x["min_price"]),
            canonical=canonical,
            related_cats=related,
            updated=updated,
            category_type="type",
        )

        out_dir = os.path.join(OUTPUT_BASE, "type", slug)
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
        count += 1

    return count, list(types.keys())


def build_age_pages(roms, updated, all_countries, all_types):
    """Byg /rom/alder/{slug}/index.html for hver alder."""
    ages = {}
    for r in roms:
        a = r.get("age")
        if a:
            ages.setdefault(a, []).append(r)

    # Spring aldersgrupper med under 3 produkter over
    ages = {k: v for k, v in ages.items() if len(v) >= 3}

    count = 0
    for age, age_roms in sorted(ages.items(), key=lambda x: _age_sort_key(x[0])):
        slug = category_slug(age)
        path = f"/rom/alder/{slug}/"
        canonical = f"{SITE_URL}{path}"

        if age == "XO":
            desc = "XO (Extra Old) rom har typisk en lagring på mindst 6 år og byder på dyb kompleksitet."
        elif age == "Solera":
            desc = "Solera-rom er produceret med den traditionelle solera-metode, hvor rom af forskellige aldre blandes for en afrundet smag."
        elif "år" in age:
            desc = f"Rom lagret i {age} på egetræsfade — udforsk udvalget og sammenlign priser."
        else:
            desc = f"Udforsk rom med betegnelsen {age}."
        desc += f" {len(age_roms)} rom med prissammenligning fra danske webshops."

        # Relaterede: andre aldre + typer
        related = [(a, f"/rom/alder/{category_slug(a)}/") for a in sorted(ages.keys(), key=_age_sort_key) if a != age][:10]
        related += [(t, f"/rom/type/{category_slug(t)}/") for t in all_types[:4]]

        html = render_category_page(
            title=f"Rom — {age}",
            description=desc,
            breadcrumb_label=age,
            breadcrumb_path=path,
            roms=sorted(age_roms, key=lambda x: x["min_price"]),
            canonical=canonical,
            related_cats=related,
            updated=updated,
            category_type="alder",
        )

        out_dir = os.path.join(OUTPUT_BASE, "alder", slug)
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
        count += 1

    return count, list(ages.keys())


def _age_sort_key(age):
    """Sortér aldre: numeriske først, derefter specielle."""
    if "år" in age:
        try:
            return (0, int(age.split()[0]))
        except (ValueError, IndexError):
            return (1, 0)
    if age == "XO":
        return (2, 0)
    if age == "Solera":
        return (2, 1)
    return (3, 0)


# ────────────────────────────────────────────────────────────
# SITEMAP INTEGRATION
# ────────────────────────────────────────────────────────────

def get_category_urls():
    """Returnér liste af alle kategori-URLs til sitemap."""
    urls = []
    for cat_type in ["land", "type", "alder"]:
        cat_dir = os.path.join(OUTPUT_BASE, cat_type)
        if os.path.isdir(cat_dir):
            for entry in sorted(os.listdir(cat_dir)):
                if os.path.isdir(os.path.join(cat_dir, entry)):
                    urls.append(f"/rom/{cat_type}/{entry}/")
    return urls


# ────────────────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────────────────

def main():
    print("\n📂 Genererer kategorisider...")

    if not os.path.exists(ROM_DATA_FILE):
        print(f"   ❌ {ROM_DATA_FILE} ikke fundet")
        sys.exit(1)

    with open(ROM_DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    roms = data.get("roms", [])
    updated_raw = data.get("updated", "")
    try:
        updated = datetime.fromisoformat(updated_raw).strftime("%d. %b %Y")
    except Exception:
        updated = updated_raw[:10]

    if not roms:
        print("   ❌ Ingen rom i data")
        return

    # Ryd gamle kategorimapper
    for cat_type in ["land", "type", "alder"]:
        cat_dir = os.path.join(OUTPUT_BASE, cat_type)
        if os.path.isdir(cat_dir):
            shutil.rmtree(cat_dir)

    # Saml lister til krydslinks
    all_types = sorted(set(r["type"] for r in roms if r.get("type")))
    all_countries = sorted(set(r["country"] for r in roms if r.get("country")))
    all_ages = sorted(set(r["age"] for r in roms if r.get("age")), key=_age_sort_key)

    # Byg sider
    n_countries, countries = build_country_pages(roms, updated, all_types, all_ages)
    n_types, types = build_type_pages(roms, updated, all_countries, all_ages)
    n_ages, ages = build_age_pages(roms, updated, all_countries, all_types)

    total = n_countries + n_types + n_ages
    print(f"   ✅ {total} kategorisider genereret:")
    print(f"      {n_countries} lande, {n_types} typer, {n_ages} aldre")

    return total


if __name__ == "__main__":
    main()
"""
generate_brand_pages.py
────────────────────────
Genererer statiske brand-hub-sider under /rom/brand/{slug}/.
Modelleret efter BeerSniffers generate_brewery_pages.py.

Hver side viser:
  - Brand-navn + antal rom + prisinterval
  - Nøgletal (antal, billigste, gennemsnit, lande, typer)
  - Grid af produktkort for brand'et
  - Links til kategorisider

Kør standalone:      python generate_brand_pages.py
Kør fra pipeline:    fra build_rom_data.py → generate_brand_pages()
"""

import json
import os
import re
import shutil
from datetime import datetime

OUTPUT_BASE = "rom/brand"
DATA_FILE = "rom_data.json"


def brand_slug(name):
    """Lav URL-slug fra brand-navn."""
    s = name.lower()
    # Erstat special chars
    replacements = {
        'æ': 'ae', 'ø': 'oe', 'å': 'aa',
        'ä': 'ae', 'ö': 'oe', 'ü': 'ue',
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'á': 'a', 'à': 'a', 'â': 'a',
        'í': 'i', 'ì': 'i', 'î': 'i',
        'ó': 'o', 'ò': 'o', 'ô': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u',
        'ñ': 'n', 'ç': 'c', 'ð': 'd', 'þ': 'th',
        "'": '', "'": '', "`": '',
    }
    for old, new in replacements.items():
        s = s.replace(old, new)
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = s.strip('-')
    return s


def flag_svg(country):
    """Returner inline flag-emoji for et land."""
    flags = {
        'Jamaica': '🇯🇲', 'Cuba': '🇨🇺', 'Barbados': '🇧🇧',
        'Guyana': '🇬🇾', 'Guatemala': '🇬🇹', 'Panama': '🇵🇦',
        'Nicaragua': '🇳🇮', 'Dominikansk': '🇩🇴', 'Trinidad': '🇹🇹',
        'Martinique': '🇲🇶', 'Haiti': '🇭🇹', 'Puerto Rico': '🇵🇷',
        'Brasilien': '🇧🇷', 'Colombia': '🇨🇴', 'Venezuela': '🇻🇪',
        'Peru': '🇵🇪', 'Mauritius': '🇲🇺', 'Filippinerne': '🇵🇭',
        'Dansk': '🇩🇰', 'Danmark': '🇩🇰', 'England': '🏴\u200d☠️',
        'Australien': '🇦🇺', 'Frankrig': '🇫🇷', 'Østrig': '🇦🇹',
        'El Salvador': '🇸🇻', 'Belize': '🇧🇿', 'Grenada': '🇬🇩',
        'Spanien': '🇪🇸', 'Guadeloupe': '🇬🇵', 'Réunion': '🇷🇪',
    }
    return flags.get(country, '🌍')


def build_brand_page(brand_name, roms, updated, all_brands):
    """Byg HTML for én brand-side."""
    slug = brand_slug(brand_name)
    roms_sorted = sorted(roms, key=lambda r: r.get('min_price', 9999))

    # Nøgletal
    count = len(roms)
    cheapest = min(r['min_price'] for r in roms)
    avg_price = sum(r['min_price'] for r in roms) / count
    countries = sorted(set(r['country'] for r in roms if r.get('country')))
    types = sorted(set(r['type'] for r in roms if r.get('type')))
    ages = sorted(set(r['age'] for r in roms if r.get('age')))
    multi = sum(1 for r in roms if r.get('shop_count', 0) > 1)
    deals = sum(1 for r in roms if r.get('max_discount_pct', 0) > 0)

    # Meta
    title = f"{brand_name} rom — sammenlign priser | RomSniffer"
    desc = f"Find den billigste {brand_name} rom. {count} produkter fra {cheapest:.0f} kr. Sammenlign priser fra danske webshops."
    canonical = f"https://romsniffer.dk/rom/brand/{slug}/"

    # Produktkort
    cards_html = ""
    for r in roms_sorted:
        best_price = r['prices'][0] if r.get('prices') else {}
        price = best_price.get('price', r.get('min_price', 0))
        shop = best_price.get('shop_name', '')
        url = best_price.get('url', '#')
        old_price = best_price.get('old_price')
        disc = r.get('max_discount_pct', 0)
        rom_slug = r.get('slug', '')

        tags = []
        if r.get('country'):
            tags.append(f'<span class="bp-tag">{flag_svg(r["country"])} {r["country"]}</span>')
        if r.get('type'):
            tags.append(f'<span class="bp-tag">{r["type"]}</span>')
        if r.get('age'):
            tags.append(f'<span class="bp-tag">🕰️ {r["age"]}</span>')
        if r.get('abv'):
            tags.append(f'<span class="bp-tag">{r["abv"]}%</span>')
        if r.get('volume_cl'):
            tags.append(f'<span class="bp-tag">{r["volume_cl"]} cl</span>')

        cards_html += f'''<a href="/rom/{rom_slug}/" class="bp-card" style="text-decoration:none;color:inherit">
            {f'<div class="bp-badge">−{disc}%</div>' if disc > 0 else ''}
            <div class="bp-img-wrap">
                {f'<img src="{r["image"]}" alt="{brand_name}" loading="lazy" decoding="async" onerror="this.style.display=&apos;none&apos;;this.nextElementSibling.style.display=&apos;flex&apos;">' if r.get('image') else ''}
                <div class="bp-placeholder" {"style=display:none" if r.get("image") else ""}>🥃</div>
            </div>
            <div class="bp-body">
                <div class="bp-tags">{''.join(tags)}</div>
                <div class="bp-name">{r["name"]}</div>
                <div class="bp-price-row">
                    <span class="bp-shop">✓ {shop}</span>
                    <span class="bp-price">{price:.0f} kr</span>
                </div>
                {f'<span class="bp-old">{old_price:.0f} kr</span>' if old_price else ''}
                {f'<div class="bp-multi">I {r["shop_count"]} butikker</div>' if r.get("shop_count", 0) > 1 else ''}
            </div>
        </a>
'''

    # Relaterede brands (navigation)
    brand_nav = ""
    for b in sorted(all_brands)[:30]:
        bs = brand_slug(b)
        active = ' class="active"' if b == brand_name else ''
        brand_nav += f'<a href="/rom/brand/{bs}/"{active}>{b}</a> '

    html = f'''<!DOCTYPE html>
<html lang="da">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
<link rel="icon" href="/logo.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Sans:wght@400;500;600&family=Playfair+Display:wght@600&display=swap" rel="stylesheet">
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  "name": "{brand_name} rom",
  "description": "{desc}",
  "url": "{canonical}",
  "numberOfItems": {count},
  "provider": {{
    "@type": "Organization",
    "name": "RomSniffer",
    "url": "https://romsniffer.dk"
  }}
}}
</script>
<style>
:root {{
    --bg: #0a0604; --surface: #1a0f08; --surface2: #251810;
    --copper: #b87333; --copper-light: #d99458;
    --text: #f5e4cf; --text-muted: #a08570; --text-dim: #5a4838;
    --border: #2e1d10; --border-light: #3d2818;
    --discount: #3dba6f; --gold: #d4a847;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: var(--bg); color: var(--text); font-family: 'DM Sans', sans-serif; min-height: 100vh; line-height: 1.6; }}
nav {{ background: rgba(10,6,4,0.97); border-bottom: 1px solid var(--border); padding: 0.85rem 2rem; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 200; }}
.nav-logo {{ display: flex; align-items: center; gap: 0.6rem; text-decoration: none; }}
.nav-logo img {{ width: 40px; height: 40px; object-fit: contain; }}
.nav-logo span {{ font-family: 'Bebas Neue', sans-serif; font-size: 1.5rem; letter-spacing: 0.06em; background: linear-gradient(135deg, var(--copper-light), var(--copper)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }}
.nav-links {{ display: flex; gap: 0.5rem; }}
.nav-links a {{ color: var(--text-muted); text-decoration: none; font-size: 0.78rem; letter-spacing: 0.15em; text-transform: uppercase; padding: 0.5rem 0.9rem; border-radius: 6px; transition: all 0.2s; }}
.nav-links a:hover {{ color: var(--copper-light); background: rgba(184,115,51,0.1); }}
.back {{ display: inline-flex; align-items: center; gap: 0.4rem; padding: 0.7rem 2rem; color: var(--copper-light); text-decoration: none; font-size: 0.82rem; border-bottom: 1px solid var(--border); }}
.back:hover {{ color: var(--text); }}
.header {{ padding: 2rem 2rem 1.5rem; border-bottom: 1px solid var(--border); background: linear-gradient(180deg, rgba(42,24,16,0.4) 0%, transparent 100%); }}
.header-inner {{ max-width: 1200px; margin: 0 auto; }}
.brand-title {{ font-family: 'Bebas Neue', sans-serif; font-size: clamp(2rem, 5vw, 3rem); letter-spacing: 0.06em; color: var(--copper-light); }}
.brand-sub {{ font-size: 0.88rem; color: var(--text-muted); margin-top: 0.3rem; }}
.stats-row {{ display: flex; gap: 1.5rem; margin-top: 1.2rem; flex-wrap: wrap; }}
.stat {{ text-align: center; }}
.stat-num {{ font-family: 'Bebas Neue', sans-serif; font-size: 1.6rem; color: var(--copper-light); line-height: 1; }}
.stat-lbl {{ font-size: 0.58rem; letter-spacing: 0.2em; text-transform: uppercase; color: var(--text-muted); }}
.grid-wrap {{ max-width: 1200px; margin: 0 auto; padding: 1.2rem; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.9rem; }}
.bp-card {{ background: linear-gradient(180deg, var(--surface) 0%, #1a0f08 100%); border: 1px solid var(--border-light); border-radius: 14px; overflow: hidden; transition: all 0.25s; position: relative; display: flex; flex-direction: column; }}
.bp-card:hover {{ transform: translateY(-3px); border-color: var(--copper); box-shadow: 0 12px 30px rgba(0,0,0,0.5); }}
.bp-badge {{ position: absolute; top: 0; right: 0; background: linear-gradient(135deg, var(--discount), #29a35a); color: #000; font-family: 'Bebas Neue', sans-serif; font-size: 0.9rem; padding: 0.25rem 0.6rem 0.25rem 0.7rem; border-radius: 0 0 0 10px; z-index: 5; }}
.bp-img-wrap {{ height: 160px; background: linear-gradient(180deg, #1a1108, #0a0604); display: flex; align-items: center; justify-content: center; padding: 0.7rem; }}
.bp-img-wrap img {{ max-width: 100%; max-height: 100%; object-fit: contain; }}
.bp-placeholder {{ font-size: 2.5rem; opacity: 0.35; display: flex; align-items: center; justify-content: center; width: 100%; height: 100%; }}
.bp-body {{ padding: 0.75rem; flex: 1; display: flex; flex-direction: column; gap: 0.3rem; }}
.bp-tags {{ display: flex; gap: 0.2rem; flex-wrap: wrap; }}
.bp-tag {{ font-size: 0.58rem; background: rgba(184,115,51,0.12); color: var(--copper-light); padding: 0.12rem 0.35rem; border-radius: 4px; border: 1px solid var(--border-light); }}
.bp-name {{ font-family: 'Playfair Display', serif; font-size: 0.85rem; font-weight: 600; line-height: 1.3; min-height: 2.2em; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }}
.bp-price-row {{ display: flex; justify-content: space-between; align-items: center; margin-top: auto; padding-top: 0.4rem; border-top: 1px solid var(--border); }}
.bp-shop {{ font-size: 0.6rem; color: var(--discount); text-transform: uppercase; letter-spacing: 0.08em; }}
.bp-price {{ font-family: 'Bebas Neue', sans-serif; font-size: 1.2rem; color: var(--copper-light); }}
.bp-old {{ font-size: 0.68rem; color: #a08070; text-decoration: line-through; text-decoration-color: #e05050; }}
.bp-multi {{ font-size: 0.6rem; color: var(--gold); margin-top: 0.15rem; }}
.brand-nav {{ padding: 1rem 2rem; border-bottom: 1px solid var(--border); display: flex; flex-wrap: wrap; gap: 0.3rem; max-width: 1200px; margin: 0 auto; }}
.brand-nav a {{ padding: 0.25rem 0.6rem; border-radius: 20px; font-size: 0.7rem; color: var(--text-muted); text-decoration: none; border: 1px solid var(--border); transition: all 0.15s; }}
.brand-nav a:hover, .brand-nav a.active {{ border-color: var(--copper); color: var(--copper-light); background: rgba(184,115,51,0.08); }}
footer {{ background: var(--surface); border-top: 1px solid var(--border); padding: 1.5rem 2rem; text-align: center; margin-top: 3rem; }}
footer a {{ color: var(--copper-light); text-decoration: none; margin: 0 0.5rem; font-size: 0.8rem; }}
footer p {{ font-size: 0.65rem; color: var(--text-dim); margin-top: 0.5rem; letter-spacing: 0.1em; text-transform: uppercase; }}
@media (max-width: 640px) {{
    .grid {{ grid-template-columns: repeat(2, 1fr); gap: 0.5rem; }}
    .bp-img-wrap {{ height: 130px; }}
    .header {{ padding: 1.2rem 1rem; }}
    .brand-title {{ font-size: 1.8rem; }}
    .stats-row {{ gap: 1rem; }}
}}
</style>
</head>
<body>
<nav>
    <a href="/" class="nav-logo">
        <img src="/logo.png" alt="RomSniffer" onerror="this.style.display='none'" decoding="async">
        <span>RomSniffer</span>
    </a>
    <div class="nav-links">
        <a href="/">Alle rom</a>
        <a href="/premium.html">Premium</a>
        <a href="/guide.html">Guide</a>
        <a href="/om.html">Om</a>
    </div>
</nav>

<a href="/" class="back">← Alle rom</a>

<div class="header">
    <div class="header-inner">
        <h1 class="brand-title">{brand_name}</h1>
        <p class="brand-sub">{count} rom{'' if count == 1 else ''} fra {cheapest:.0f} kr — opdateret {updated}</p>
        <div class="stats-row">
            <div class="stat"><div class="stat-num">{count}</div><div class="stat-lbl">Rom i alt</div></div>
            <div class="stat"><div class="stat-num">{cheapest:.0f}</div><div class="stat-lbl">Billigste (kr)</div></div>
            <div class="stat"><div class="stat-num">{avg_price:.0f}</div><div class="stat-lbl">Gns. pris</div></div>
            {f'<div class="stat"><div class="stat-num">{multi}</div><div class="stat-lbl">I flere butikker</div></div>' if multi > 0 else ''}
            {f'<div class="stat"><div class="stat-num">{deals}</div><div class="stat-lbl">Tilbud</div></div>' if deals > 0 else ''}
        </div>
    </div>
</div>

<div class="grid-wrap">
    <div class="grid">
{cards_html}
    </div>
</div>

<div class="brand-nav">
{brand_nav}
</div>

<footer>
    <div>
        <a href="/">Forsiden</a>
        <a href="/guide.html">Rom-guide</a>
        <a href="/om.html">Om RomSniffer</a>
    </div>
    <p>🥃 RomSniffer © 2026</p>
</footer>
</body>
</html>'''

    return slug, html


def main():
    print("\n🏷️  Genererer brand-sider...")

    if not os.path.exists(DATA_FILE):
        print(f"   ❌ {DATA_FILE} ikke fundet")
        return 0

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    roms = data.get("roms", [])
    updated_raw = data.get("updated", "")
    try:
        updated = datetime.fromisoformat(updated_raw).strftime("%-d. %b %Y")
    except Exception:
        try:
            updated = datetime.fromisoformat(updated_raw).strftime("%d. %b %Y")
        except Exception:
            updated = updated_raw[:10]

    if not roms:
        print("   ❌ Ingen rom i data")
        return 0

    # Gruppér efter brand
    brands = {}
    for r in roms:
        b = r.get("brand")
        if not b or len(b.strip()) < 2:
            continue
        brands.setdefault(b, []).append(r)

    # Filtrer: kun brands med 2+ rom
    brands = {k: v for k, v in brands.items() if len(v) >= 2}

    if not brands:
        print("   ⚠️  Ingen brands med 2+ rom fundet")
        return 0

    # Ryd gamle brand-sider
    if os.path.isdir(OUTPUT_BASE):
        shutil.rmtree(OUTPUT_BASE)

    all_brand_names = sorted(brands.keys())
    count = 0

    for brand_name, brand_roms in sorted(brands.items()):
        slug, html = build_brand_page(brand_name, brand_roms, updated, all_brand_names)
        out_dir = os.path.join(OUTPUT_BASE, slug)
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(html)
        count += 1

    print(f"   ✅ {count} brand-sider genereret (brands med 2+ rom)")
    return count


if __name__ == "__main__":
    n = main()
    if n:
        print(f"\n   Sider ligger i {OUTPUT_BASE}/")
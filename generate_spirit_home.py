"""Generate the category chooser at / and the RomSniffer rum listing at /rom/."""
import json
from pathlib import Path

TEMPLATE = Path("_rom_home_template.html")
ROM_PAGE = Path("rom") / "index.html"
HOME = Path("index.html")


def _count(path, key):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return int(data.get("stats", {}).get(key, 0) or 0)
    except (OSError, ValueError, TypeError):
        return 0


def _stats(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")).get("stats", {})
    except (OSError, ValueError, TypeError):
        return {}


def _make_rom_page(template):
    html = template
    html = html.replace('<link rel="canonical" href="https://www.romsniffer.dk/">',
                        '<link rel="canonical" href="https://www.romsniffer.dk/rom/">')
    html = html.replace('<meta property="og:url" content="https://www.romsniffer.dk/">',
                        '<meta property="og:url" content="https://www.romsniffer.dk/rom/">')
    html = html.replace('<a href="/">Alle rom</a>', '<a href="/rom/">Rom</a>')
    html = html.replace('<a href="/rom/">Rom</a>', '')
    html = html.replace("fetch('rom_data.json?v=' + DATA_VERSION)", "fetch('/rom_data.json?v=' + DATA_VERSION)")
    for page in ("premium.html", "guide.html", "om.html"):
        html = html.replace(f'href="{page}"', f'href="/{page}"')
    return html


def _make_home(rom_stats, whisky_stats):
    def fmt(value):
        return f"{int(value or 0):,}".replace(",", ".")

    rom_products = fmt(rom_stats.get("total"))
    whisky_products = fmt(whisky_stats.get("total"))
    rom_shops = len(rom_stats.get("shop_counts", {})) or len(rom_stats.get("shop_names", []))
    whisky_shops = len(whisky_stats.get("shop_counts", {})) or len(whisky_stats.get("shop_names", []))
    return f'''<!doctype html>
<html lang="da">
<head>
  <!-- Start cookieyes banner -->
  <script id="cookieyes" type="text/javascript" src="https://cdn-cookieyes.com/client_data/89fa8867d76958bb0adf126ff23ddbf6/script.js"></script>
  <!-- End cookieyes banner -->
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Sammenlign priser på rom og whisky fra danske webshops med RomSniffer.">
  <link rel="canonical" href="https://www.romsniffer.dk/">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="RomSniffer">
  <meta property="og:title" content="Find rom og whisky til den bedste pris | RomSniffer">
  <meta property="og:description" content="Vælg rom eller whisky og sammenlign priser fra danske webshops.">
  <meta property="og:url" content="https://www.romsniffer.dk/">
  <title>Find rom og whisky til den bedste pris | RomSniffer</title>
  <link rel="icon" type="image/png" href="/favicon.png">
  <link rel="apple-touch-icon" href="/apple-touch-icon.png">
  <link rel="preload" href="/fonts/playfair-display-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="/fonts/dm-sans-latin-wght-normal.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/fonts/fonts.css">
  <link rel="stylesheet" href="/theme.css">
  <link rel="preload" as="image" href="/hero-bottles.png">
  <script src="/theme.js?v=menu-category-3"></script>
  <style>
    * {{ box-sizing:border-box }}
    body {{ margin:0; min-height:100vh; min-height:100svh; display:flex; flex-direction:column; background:#07060a; color:#f0e8d8; font:16px/1.55 'DM Sans',system-ui,sans-serif; }}
    nav {{ min-height:58px; display:flex; align-items:center; justify-content:space-between; padding:10px max(22px,calc((100vw - 1120px)/2)); }}
    .nav-logo {{ color:#e8c868; text-decoration:none; font:500 19px Georgia,serif; letter-spacing:.3em; text-transform:uppercase; }}
    .nav-links a {{ color:#a39887; text-decoration:none; text-transform:uppercase; font-size:12px; letter-spacing:.16em; }}
    main {{ width:min(1040px,calc(100% - 36px)); flex:1; display:flex; flex-direction:column; justify-content:center; margin:8px auto; }}
    .hero {{ min-height:clamp(160px,25svh,230px); display:grid; grid-template-columns:1.15fr .85fr; align-items:center; gap:18px; padding:18px clamp(20px,4vw,44px); margin-bottom:14px; border:1px solid rgba(201,168,76,.2); background:radial-gradient(ellipse at 80% 50%,rgba(201,168,76,.12),transparent 48%),#09080b; box-shadow:0 22px 60px rgba(0,0,0,.28); }}
    .hero-copy {{ position:relative; z-index:1; }}
    .hero-image {{ display:block; width:100%; height:clamp(150px,24svh,220px); object-fit:contain; filter:drop-shadow(0 15px 22px rgba(0,0,0,.55)); }}
    .eyebrow {{ color:#c9a84c; font-size:12px; text-transform:uppercase; letter-spacing:.24em; }}
    h1 {{ margin:14px 0 12px; color:#e8c868; font:500 clamp(38px,7vw,66px)/1.08 'Playfair Display',Georgia,serif; }}
    .intro {{ max-width:620px; color:#a39887; font-size:18px; margin:0; }}
    .choices-title {{ margin:0 0 8px; color:#c9a84c; font:500 20px/1.3 'Playfair Display',Georgia,serif; }}
    .choices {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:16px; }}
    .choice {{ position:relative; display:flex; min-height:clamp(175px,25svh,220px); flex-direction:column; justify-content:space-between; padding:22px; overflow:hidden; border:1px solid rgba(201,168,76,.25); background:radial-gradient(ellipse at 100% 0,rgba(201,168,76,.13),transparent 55%),#0f0c13; color:#f0e8d8; text-decoration:none; transition:border-color .2s,transform .2s,background .2s; }}
    .choice:hover {{ border-color:#c9a84c; transform:translateY(-3px); background-color:#15111b; }}
    .choice-name {{ display:flex; align-items:center; gap:14px; color:#e8c868; font:500 clamp(32px,5vw,48px)/1.1 'Playfair Display',Georgia,serif; }}
    .drink-icon {{ width:38px; height:38px; flex:0 0 38px; color:#c9a84c; }}
    .choice-stats {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:8px; margin:16px 0 14px; }}
    .choice-stat {{ border-left:1px solid rgba(201,168,76,.3); padding-left:10px; color:#a39887; font-size:11px; line-height:1.35; }}
    .choice-stat strong {{ display:block; color:#f0e8d8; font:500 19px/1.2 'DM Sans',system-ui,sans-serif; margin-bottom:4px; }}
    .choice-cta {{ color:#d6ad62; text-transform:uppercase; font-size:12px; letter-spacing:.2em; }}
    footer {{ padding:8px 18px 12px; color:#a39887; text-align:center; font-size:12px; letter-spacing:.06em; }}
    @media(max-width:640px) {{ nav {{ min-height:50px; padding:8px 18px }} .nav-logo {{ font-size:17px }} main {{ width:calc(100% - 28px); margin:4px auto }} .hero {{ min-height:clamp(125px,22svh,170px); grid-template-columns:1.05fr .95fr; gap:2px; padding:12px 10px; margin-bottom:12px }} .hero-image {{ height:clamp(105px,20svh,155px); width:100% }} .eyebrow {{ font-size:8px; letter-spacing:.12em }} h1 {{ font-size:clamp(27px,7.6vw,36px); margin:8px 0 6px }} .intro {{ font-size:12px; line-height:1.3 }} .choices-title {{ font-size:17px; margin-bottom:6px }} .choices {{ grid-template-columns:1fr; gap:8px }} .choice {{ min-height:clamp(140px,22svh,165px); padding:14px 16px 12px }} .choice-name {{ gap:10px; font-size:30px }} .drink-icon {{ width:32px; height:32px; flex-basis:32px }} .choice-stats {{ grid-template-columns:repeat(2,minmax(0,1fr)); margin:10px 0; gap:6px 5px }} .choice-stat {{ padding-left:7px; font-size:9px }} .choice-stat strong {{ font-size:16px; margin-bottom:2px }} .choice-cta {{ font-size:11px }} footer {{ padding:6px 10px 8px; font-size:10px }} }}
    @media(max-width:640px) and (max-height:700px) {{ .hero {{ min-height:112px; padding:9px 10px; margin-bottom:8px }} .hero-image {{ height:105px }} h1 {{ font-size:27px; margin:6px 0 4px }} .intro {{ font-size:11px }} .choices-title {{ margin-bottom:4px }} .choice {{ min-height:132px; padding:11px 14px 10px }} .choice-name {{ font-size:27px }} .choice-stats {{ margin:7px 0; gap:4px }} .choice-stat strong {{ font-size:15px }} footer {{ padding-block:4px }} }}
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
      <img class="hero-image" src="/hero-bottles.png" alt="To flasker spiritus" fetchpriority="high">
    </section>
    <h2 class="choices-title">Vælg kategori</h2>
    <section class="choices" aria-label="Vælg kategori">
      <a class="choice" href="/rom/" aria-label="Se {rom_products} rom">
        <span class="choice-name"><svg class="drink-icon" viewBox="0 0 40 40" aria-hidden="true"><path d="M7 7h26l-3 27H10L7 7Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="m9 19 22-2-1.5 15h-18L9 19Z" fill="currentColor" opacity=".3"/><path d="M11 12h18" stroke="currentColor" stroke-width="1.3" opacity=".65"/></svg>Rom</span>
        <span class="choice-stats">
          <span class="choice-stat"><strong>{rom_products}</strong>produkter</span>
          <span class="choice-stat"><strong>{rom_shops}</strong>butikker</span>
          <span class="choice-stat"><strong>{fmt(rom_stats.get('multi_shop'))}</strong>findes flere steder</span>
          <span class="choice-stat"><strong>{fmt(rom_stats.get('deals'))}</strong>aktive tilbud</span>
        </span>
        <span class="choice-cta">Find rom →</span>
      </a>
      <a class="choice" href="/whisky/" aria-label="Se {whisky_products} whiskyer">
        <span class="choice-name"><svg class="drink-icon" viewBox="0 0 40 40" aria-hidden="true"><path d="M7 7h26l-3 27H10L7 7Z" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/><path d="m9 19 22-2-1.5 15h-18L9 19Z" fill="currentColor" opacity=".3"/><path d="M11 12h18" stroke="currentColor" stroke-width="1.3" opacity=".65"/></svg>Whisky</span>
        <span class="choice-stats">
          <span class="choice-stat"><strong>{whisky_products}</strong>produkter</span>
          <span class="choice-stat"><strong>{whisky_shops}</strong>butikker</span>
          <span class="choice-stat"><strong>{fmt(whisky_stats.get('multi_shop'))}</strong>findes flere steder</span>
          <span class="choice-stat"><strong>{fmt(whisky_stats.get('deals'))}</strong>aktive tilbud</span>
        </span>
        <span class="choice-cta">Find whisky →</span>
      </a>
    </section>
  </main>
  <footer>Opdateres dagligt <span aria-hidden="true">·</span> Gratis <span aria-hidden="true">·</span> Ingen reklamer</footer>
</body>
</html>
'''


def main():
    if not TEMPLATE.is_file():
        raise SystemExit(f"RomSniffer-skabelonen mangler: {TEMPLATE}")
    source = TEMPLATE.read_text(encoding="utf-8")
    ROM_PAGE.parent.mkdir(parents=True, exist_ok=True)
    ROM_PAGE.write_text(_make_rom_page(source), encoding="utf-8")
    HOME.write_text(_make_home(_stats("rom_data.json"), _stats("whisky_data.json")), encoding="utf-8")
    print(f"Kategoriforside genereret: {HOME.resolve()}; romoversigt: {ROM_PAGE.resolve()}")


if __name__ == "__main__":
    main()

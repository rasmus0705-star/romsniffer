"""Generate the category chooser at / and the RomSniffer rum listing at /rom/."""
import json
from pathlib import Path
from html import escape

TEMPLATE = Path("_rom_home_template.html")
ROM_PAGE = Path("rom") / "index.html"
HOME = Path("index.html")


def _count(path, key):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return int(data.get("stats", {}).get(key, 0) or 0)
    except (OSError, ValueError, TypeError):
        return 0


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


def _make_home(rom_count, whisky_count):
    rom_label = f"{rom_count:,}".replace(",", ".") if rom_count else "Se oversigten"
    whisky_label = f"{whisky_count:,}".replace(",", ".") if whisky_count else "Se oversigten"
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
  <script src="/theme.js"></script>
  <style>
    * {{ box-sizing:border-box }}
    body {{ margin:0; min-height:100vh; background:#07060a; color:#f0e8d8; font:16px/1.55 'DM Sans',system-ui,sans-serif; }}
    nav {{ min-height:76px; display:flex; align-items:center; justify-content:space-between; padding:14px max(22px,calc((100vw - 1120px)/2)); }}
    .nav-logo {{ color:#e8c868; text-decoration:none; font:500 19px Georgia,serif; letter-spacing:.3em; text-transform:uppercase; }}
    .nav-links a {{ color:#a39887; text-decoration:none; text-transform:uppercase; font-size:12px; letter-spacing:.16em; }}
    main {{ width:min(1040px,calc(100% - 36px)); margin:clamp(42px,9vh,100px) auto 80px; }}
    .eyebrow {{ color:#c9a84c; font-size:12px; text-transform:uppercase; letter-spacing:.24em; }}
    h1 {{ margin:14px 0 12px; color:#e8c868; font:500 clamp(38px,7vw,66px)/1.08 'Playfair Display',Georgia,serif; }}
    .intro {{ max-width:620px; color:#a39887; font-size:18px; margin:0 0 42px; }}
    .choices {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; }}
    .choice {{ position:relative; display:flex; min-height:270px; flex-direction:column; justify-content:space-between; padding:30px; overflow:hidden; border:1px solid rgba(201,168,76,.25); background:radial-gradient(ellipse at 100% 0,rgba(201,168,76,.13),transparent 55%),#0f0c13; color:#f0e8d8; text-decoration:none; transition:border-color .2s,transform .2s,background .2s; }}
    .choice:hover {{ border-color:#c9a84c; transform:translateY(-3px); background-color:#15111b; }}
    .choice-name {{ color:#e8c868; font:500 clamp(32px,5vw,48px)/1.1 'Playfair Display',Georgia,serif; }}
    .choice-count {{ color:#a39887; font-size:14px; margin-top:12px; }}
    .choice-cta {{ color:#d6ad62; text-transform:uppercase; font-size:12px; letter-spacing:.2em; }}
    footer {{ border-top:1px solid rgba(201,168,76,.15); padding:24px 18px 34px; color:#7a7064; text-align:center; font-size:12px; letter-spacing:.08em; }}
    @media(max-width:640px) {{ main {{ margin-top:46px }} .intro {{ font-size:16px; margin-bottom:28px }} .choices {{ grid-template-columns:1fr; gap:12px }} .choice {{ min-height:190px; padding:23px }} nav {{ padding-inline:18px }} }}
  </style>
</head>
<body data-cat="home">
  <nav aria-label="Hovedmenu">
    <a href="/" class="nav-logo"><span>RomSniffer</span></a>
  </nav>
  <main>
    <div class="eyebrow">Sammenlign danske webshops</div>
    <h1>Hvad leder du efter?</h1>
    <p class="intro">Vælg en type spiritus for at se priser, tilbud og butikker samlet ét sted.</p>
    <section class="choices" aria-label="Vælg kategori">
      <a class="choice" href="/rom/" aria-label="Se {rom_label} rom">
        <span><span class="choice-name">Rom</span><span class="choice-count">{escape(rom_label)} produkter · sammenlign priser på tværs af butikker</span></span>
        <span class="choice-cta">Find rom →</span>
      </a>
      <a class="choice" href="/whisky/" aria-label="Se {whisky_label} whiskyer">
        <span><span class="choice-name">Whisky</span><span class="choice-count">{escape(whisky_label)} produkter · sammenlign priser på tværs af butikker</span></span>
        <span class="choice-cta">Find whisky →</span>
      </a>
    </section>
  </main>
  <footer>RomSniffer · Priser og lagerstatus kontrolleres hos butikken</footer>
</body>
</html>
'''


def main():
    if not TEMPLATE.is_file():
        raise SystemExit(f"RomSniffer-skabelonen mangler: {TEMPLATE}")
    source = TEMPLATE.read_text(encoding="utf-8")
    ROM_PAGE.parent.mkdir(parents=True, exist_ok=True)
    ROM_PAGE.write_text(_make_rom_page(source), encoding="utf-8")
    HOME.write_text(_make_home(_count("rom_data.json", "total"), _count("whisky_data.json", "total")), encoding="utf-8")
    print(f"Kategoriforside genereret: {HOME.resolve()}; romoversigt: {ROM_PAGE.resolve()}")


if __name__ == "__main__":
    main()

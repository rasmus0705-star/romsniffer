"""Generér den statiske whisky-prissammenligning fra verificerede match."""
import json
from datetime import datetime
from html import escape
from pathlib import Path


DATA_FILE = Path("whisky_pilot_data.json")
OUTPUT_FILE = Path("whisky") / "index.html"


def main():
    if not DATA_FILE.is_file():
        raise SystemExit(f"Pilotdata mangler: {DATA_FILE}")
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    matches = data.get("matches", [])
    payload = []
    for match in matches:
        offers = sorted(match.get("prices", []), key=lambda item: item["price"])
        if not offers:
            continue
        low, high = offers[0]["price"], offers[-1]["price"]
        payload.append({
            "name": match.get("name", "Whisky"),
            "volume": match.get("volume_cl"),
            "abv": match.get("abv"),
            "prices": offers,
            "saving": round(high - low, 2),
            "saving_pct": round((high - low) / high * 100, 1) if high else 0,
            "ean_check": match.get("ean_check"),
            "whisky_dk_stock": match.get("whisky_dk_stock"),
        })

    encoded = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    updated = escape(str(data.get("updated", ""))[:16].replace("T", " "))
    html = f'''<!doctype html>
<html lang="da">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Sammenlign whiskypriser hos danske butikker, og find den laveste pris på tværs af butikkerne.">
  <link rel="canonical" href="https://www.romsniffer.dk/whisky/">
  <link rel="stylesheet" href="/theme.css">
  <script src="/theme.js"></script>
  <title>Whisky tilbud og prissammenligning | RomSniffer</title>
  <style>
    :root {{ color-scheme: dark; --bg:#0a0604; --panel:#17100b; --panel2:#21170f; --line:#3d2818; --gold:#d4a847; --text:#f5e4cf; --muted:#aa927b; --green:#8bd1a8; }}
    * {{ box-sizing:border-box }}
    body {{ margin:0; background:var(--bg); color:var(--text); font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif; }}
    header {{ border-bottom:1px solid var(--line); padding:24px max(20px,calc((100vw - 1120px)/2)); background:linear-gradient(135deg,#21170f,#0a0604 70%); }}
    .brand {{ color:var(--gold); font:600 14px/1.2 Georgia,serif; letter-spacing:.22em; text-transform:uppercase; }}
    h1 {{ margin:12px 0 4px; font:500 clamp(30px,5vw,46px)/1.1 Georgia,serif; color:var(--gold); }}
    .sub {{ color:var(--muted); margin:8px 0 0; }}
    main {{ width:min(1120px,100% - 32px); margin:24px auto 70px; }}
    .toolbar {{ display:flex; gap:12px; align-items:center; margin-bottom:18px; }}
    input,select {{ min-height:46px; border:1px solid var(--line); border-radius:8px; background:var(--panel); color:var(--text); padding:10px 13px; font:inherit; }}
    input {{ flex:1; min-width:0; }}
    .count {{ white-space:nowrap; color:var(--muted); font-size:14px; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr)); gap:14px; }}
    article {{ background:var(--panel); border:1px solid var(--line); border-radius:12px; padding:18px; min-width:0; }}
    h2 {{ font:500 22px/1.25 Georgia,serif; margin:0 0 8px; }}
    .facts {{ color:var(--muted); font-size:14px; margin-bottom:15px; }}
    .saving {{ color:var(--green); font-size:14px; margin:0 0 12px; }}
    .offers {{ display:grid; gap:8px; }}
    .offer {{ display:flex; justify-content:space-between; align-items:center; gap:12px; padding:10px 12px; border:1px solid #332419; border-radius:8px; background:var(--panel2); }}
    .offer a {{ color:var(--text); text-decoration:none; }}
    .offer a:hover {{ color:var(--gold); text-decoration:underline; }}
    .price {{ color:var(--gold); font-weight:700; white-space:nowrap; }}
    .price.lowest {{ color:var(--green); }}
    .badge {{ display:inline-block; color:var(--muted); border:1px solid var(--line); border-radius:20px; padding:2px 8px; margin-top:12px; font-size:12px; }}
    .empty {{ color:var(--muted); text-align:center; padding:50px 12px; }}
    footer {{ color:var(--muted); font-size:13px; text-align:center; padding:0 16px 28px; }}
    @media(max-width:560px) {{ header {{ padding:20px 16px }} main {{ width:calc(100% - 24px); margin-top:16px }} .toolbar {{ flex-wrap:wrap }} .toolbar input {{ flex-basis:100% }} .count {{ margin-left:auto }} article {{ padding:15px }} }}
  </style>
</head>
<body data-cat="whisky">
  <nav><a href="/" class="nav-logo"><span>RomSniffer</span></a><div class="nav-links"><a href="/">Forside</a></div></nav>
  <header>
    <div class="brand">RomSniffer · Whisky</div>
    <h1>Whisky til gode priser</h1>
    <p class="sub">{len(payload)} sammenligninger · kildedata opdateret {updated}</p>
  </header>
  <main>
    <div class="toolbar">
      <input id="search" type="search" placeholder="Søg efter whisky eller butik" aria-label="Søg">
      <select id="sort" aria-label="Sortér">
        <option value="saving">Størst besparelse</option>
        <option value="price">Laveste pris</option>
        <option value="name">Navn A–Å</option>
      </select>
      <span class="count" id="count"></span>
    </div>
    <section class="grid" id="grid" aria-live="polite"></section>
  </main>
  <footer>Priser og lagerstatus kan ændre sig; kontrollér altid oplysningerne hos butikken.</footer>
  <script>
    const products = {encoded};
    const grid = document.getElementById('grid');
    const search = document.getElementById('search');
    const sort = document.getElementById('sort');
    const count = document.getElementById('count');
    const fmt = n => new Intl.NumberFormat('da-DK', {{minimumFractionDigits:0, maximumFractionDigits:2}}).format(n) + ' kr';
    function render() {{
      const query = search.value.trim().toLocaleLowerCase('da');
      const visible = products.filter(p => (p.name + ' ' + p.prices.map(x => x.shop_name).join(' ')).toLocaleLowerCase('da').includes(query));
      visible.sort((a,b) => sort.value === 'name' ? a.name.localeCompare(b.name,'da') : sort.value === 'price' ? a.prices[0].price-b.prices[0].price : b.saving-a.saving);
      count.textContent = visible.length + ' varer';
      grid.replaceChildren();
      if (!visible.length) {{ const empty=document.createElement('p'); empty.className='empty'; empty.textContent='Ingen whisky fundet.'; grid.append(empty); return; }}
      visible.forEach(p => {{
        const card=document.createElement('article');
        const title=document.createElement('h2'); title.textContent=p.name; card.append(title);
        const facts=document.createElement('div'); facts.className='facts';
        facts.textContent=[p.volume ? Number(p.volume).toLocaleString('da-DK')+' cl' : null,p.abv ? Number(p.abv).toLocaleString('da-DK')+'%' : null].filter(Boolean).join(' · ');
        card.append(facts);
        if (p.saving > 0) {{ const save=document.createElement('p'); save.className='saving'; save.textContent='Spar '+fmt(p.saving)+' ('+p.saving_pct.toLocaleString('da-DK')+'%)'; card.append(save); }}
        const offers=document.createElement('div'); offers.className='offers';
        p.prices.forEach((offer,index) => {{
          const row=document.createElement('div'); row.className='offer';
          const link=document.createElement('a'); link.href=offer.url; link.target='_blank'; link.rel='noopener noreferrer'; link.textContent=offer.shop_name;
          const price=document.createElement('span'); price.className='price'+(index===0?' lowest':''); price.textContent=fmt(offer.price);
          row.append(link,price); offers.append(row);
        }});
        card.append(offers);
        const badge=document.createElement('span'); badge.className='badge';
        badge.textContent=p.ean_check==='verified'?'EAN bekræftet':p.whisky_dk_stock==='in_stock'?'Lager kontrolleret':'Lagerstatus fra butiksfeed';
        card.append(badge); grid.append(card);
      }});
    }}
    search.addEventListener('input',render); sort.addEventListener('change',render); render();
  </script>
</body>
</html>'''
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"Whisky-side genereret: {OUTPUT_FILE.resolve()} ({len(payload)} produkter)")


if __name__ == "__main__":
    main()

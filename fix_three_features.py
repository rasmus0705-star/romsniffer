"""
Tilfojer 3 features paa een gang:
1. Prishistorik-logning i build_rom_data.py
2. Romroulette knap i index.html
3. Dagens fund sektion i index.html
"""

# ══════════════════════════════════════════════════════════
# 1. PRISHISTORIK i build_rom_data.py
# ══════════════════════════════════════════════════════════
print("=== 1. Prishistorik ===")
with open('build_rom_data.py', encoding='utf-8') as f:
    build = f.read()

if 'price_history' not in build:
    # Tilfoej prishistorik-logning lige foer git push
    old_git = '    # ── Git push til GitHub'
    new_history = '''    # ── Gem prishistorik (daglig log) ──
    print("\\n📈 Gemmer prishistorik...")
    history_file = "price_history.json"
    try:
        with open(history_file, "r", encoding="utf-8") as hf:
            history = json.load(hf)
    except (FileNotFoundError, json.JSONDecodeError):
        history = {}

    today = datetime.now().strftime("%Y-%m-%d")
    today_data = {}
    for rom in unique_roms:
        key = rom["name"]
        shops = {}
        for p in rom["prices"]:
            shops[p["shop_name"]] = p["price"]
        today_data[key] = {
            "min": rom["min_price"],
            "shops": shops,
        }
    history[today] = today_data

    # Behold max 90 dages historik
    dates = sorted(history.keys())
    if len(dates) > 90:
        for old_date in dates[:-90]:
            del history[old_date]

    with open(history_file, "w", encoding="utf-8") as hf:
        json.dump(history, hf, ensure_ascii=False)
    print(f"   ✅ Prishistorik gemt for {len(today_data)} rom ({today})")

    # ── Git push til GitHub'''

    if old_git in build:
        build = build.replace(old_git, new_history)
        # Tilfoej price_history.json til git add
        build = build.replace(
            'subprocess.run(["git", "add", "rom_data.json"]',
            'subprocess.run(["git", "add", "rom_data.json", "price_history.json"]'
        )
        print("OK: prishistorik tilfojet til build_rom_data.py")
    else:
        print("FEJL: git-blok ikke fundet")
else:
    print("Allerede tilstede")

with open('build_rom_data.py', 'w', encoding='utf-8') as f:
    f.write(build)


# ══════════════════════════════════════════════════════════
# 2 + 3. ROMROULETTE + DAGENS FUND i index.html
# ══════════════════════════════════════════════════════════
print("\n=== 2. Romroulette + 3. Dagens fund ===")
with open('index.html', encoding='utf-8') as f:
    idx = f.read()

changes = 0

# 2a. Romroulette knap i quick-bar (efter Premium-knappen)
if 'Overrask mig' not in idx:
    old_premium_btn = """onclick="quickFilter('premium')">💎 Premium</button>"""
    new_premium_btn = """onclick="quickFilter('premium')">💎 Premium</button>
                <button class="qbtn" onclick="romRoulette()" style="background:linear-gradient(135deg,#6b2c0e,#b87333);color:#f5e4cf;border:none">🎲 Overrask mig</button>"""
    if old_premium_btn in idx:
        idx = idx.replace(old_premium_btn, new_premium_btn)
        changes += 1
        print("OK: Romroulette knap tilfojet")
    else:
        print("FEJL: Premium-knap ikke fundet")
else:
    print("Romroulette: allerede tilstede")

# 2b. Romroulette JS (tilfoej foer INIT-sektionen)
if 'function romRoulette' not in idx:
    old_init = '// ── INIT'
    new_roulette = """// ── ROMROULETTE ───────────────────────────────────────────────────
function romRoulette() {
    const cards = document.querySelectorAll('#grid .card');
    if (!cards.length) return;
    const idx = Math.floor(Math.random() * cards.length);
    const card = cards[idx];
    card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    card.style.transition = 'box-shadow 0.3s, border-color 0.3s';
    card.style.boxShadow = '0 0 40px rgba(212,168,71,0.6)';
    card.style.borderColor = '#d4a847';
    setTimeout(() => {
        card.style.boxShadow = '';
        card.style.borderColor = '';
    }, 2500);
}

// ── INIT"""
    if old_init in idx:
        idx = idx.replace(old_init, new_roulette, 1)
        changes += 1
        print("OK: Romroulette JS tilfojet")
    else:
        print("FEJL: INIT-sektion ikke fundet")
else:
    print("Romroulette JS: allerede tilstede")

# 3a. Dagens fund HTML (mellem stats-bar og top-deals)
if 'dagens-fund' not in idx:
    old_top_deals = '<!-- TOP DEALS CAROUSEL -->'
    new_fund_section = """<!-- DAGENS FUND -->
<div id="dagens-fund" style="display:none;padding:1rem 2rem;border-bottom:1px solid var(--border);background:linear-gradient(180deg,var(--surface) 0%,var(--bg) 100%)">
    <div style="max-width:700px;margin:0 auto">
        <div style="display:flex;align-items:center;gap:0.5rem;margin-bottom:0.8rem">
            <span style="font-size:1.2rem">🏆</span>
            <span style="font-family:'Bebas Neue',sans-serif;font-size:1.1rem;letter-spacing:0.1em;color:var(--gold)">Dagens fund</span>
            <span style="font-size:0.7rem;color:var(--text-dim);margin-left:auto">Stoerst besparelse mellem butikker</span>
        </div>
        <div id="fund-card" style="background:linear-gradient(135deg,var(--surface2),rgba(212,168,71,0.06));border:1px solid rgba(212,168,71,0.3);border-radius:12px;padding:1rem 1.2rem;display:flex;gap:1.2rem;align-items:center">
            <img id="fund-img" src="" alt="" style="width:80px;height:100px;object-fit:contain;border-radius:8px;background:#0a0604;padding:0.4rem;flex-shrink:0" onerror="this.style.display='none'">
            <div style="flex:1;min-width:0">
                <div id="fund-name" style="font-family:'Playfair Display',serif;font-size:1rem;font-weight:600;color:var(--text);margin-bottom:0.3rem"></div>
                <div id="fund-meta" style="font-size:0.72rem;color:var(--text-muted);margin-bottom:0.5rem"></div>
                <div style="display:flex;align-items:baseline;gap:0.8rem;flex-wrap:wrap">
                    <span id="fund-price" style="font-family:'Bebas Neue',sans-serif;font-size:1.6rem;color:var(--gold);line-height:1"></span>
                    <span id="fund-expensive" style="font-size:0.78rem;color:var(--text-dim);text-decoration:line-through"></span>
                    <span id="fund-saving" style="background:linear-gradient(135deg,rgba(61,186,111,0.15),rgba(212,168,71,0.1));border:1px solid var(--discount);color:var(--discount);padding:0.25rem 0.6rem;border-radius:6px;font-size:0.78rem;font-weight:700"></span>
                </div>
            </div>
            <a id="fund-cta" href="#" target="_blank" rel="noopener" style="background:linear-gradient(135deg,var(--gold),#e8c868);color:#0a0604;padding:0.55rem 1.2rem;border-radius:8px;text-decoration:none;font-weight:700;font-size:0.82rem;white-space:nowrap;flex-shrink:0">Koeb billigst →</a>
        </div>
    </div>
</div>

<!-- TOP DEALS CAROUSEL -->"""

    if old_top_deals in idx:
        idx = idx.replace(old_top_deals, new_fund_section)
        changes += 1
        print("OK: Dagens fund HTML tilfojet")
    else:
        print("FEJL: top-deals markering ikke fundet")
else:
    print("Dagens fund HTML: allerede tilstede")

# 3b. Dagens fund JS (tilfoej i loadData efter renderTopDeals)
if 'renderDagensFund' not in idx:
    old_render_calls = """        renderTopDeals();
        setupSpotlight();
        render();"""
    new_render_calls = """        renderTopDeals();
        renderDagensFund();
        setupSpotlight();
        render();"""

    if old_render_calls in idx:
        idx = idx.replace(old_render_calls, new_render_calls)
        changes += 1
        print("OK: renderDagensFund kald tilfojet")

    # Tilfoej funktionen foer renderActiveChips (eller foer spotlight)
    old_spotlight = '// ── SPOTLIGHT'
    new_fund_js = """// ── DAGENS FUND ───────────────────────────────────────────────────
function renderDagensFund() {
    // Find rom med stoerst besparelse mellem butikker
    const candidates = allRoms.filter(r => r.shop_count > 1 && r.prices && r.prices.length > 1);
    if (!candidates.length) return;

    candidates.sort((a, b) => {
        const sa = getSavings(a), sb = getSavings(b);
        return sb - sa;
    });

    const best = candidates[0];
    const sorted = [...best.prices].sort((a, b) => a.price - b.price);
    const cheapest = sorted[0];
    const expensive = sorted[sorted.length - 1];
    const savings = expensive.price - cheapest.price;

    document.getElementById('dagens-fund').style.display = 'block';
    if (best.image) {
        const img = document.getElementById('fund-img');
        img.src = best.image;
        img.style.display = 'block';
    }
    document.getElementById('fund-name').textContent = best.name;
    document.getElementById('fund-meta').textContent = [best.country, best.type, best.age, best.abv ? best.abv + '%' : ''].filter(Boolean).join(' · ');
    document.getElementById('fund-price').textContent = cheapest.price.toFixed(0) + ' kr';
    document.getElementById('fund-expensive').textContent = expensive.price.toFixed(0) + ' kr hos ' + expensive.shop_name;
    document.getElementById('fund-saving').textContent = 'Spar ' + savings.toFixed(0) + ' kr hos ' + cheapest.shop_name;
    document.getElementById('fund-cta').href = cheapest.url || '#';
}

// ── SPOTLIGHT"""

    if old_spotlight in idx:
        idx = idx.replace(old_spotlight, new_fund_js, 1)
        changes += 1
        print("OK: renderDagensFund JS tilfojet")
else:
    print("Dagens fund JS: allerede tilstede")

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(idx)

print(f"\nFaerdig — {changes} aendringer i index.html")
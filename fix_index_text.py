with open('index.html', encoding='utf-8') as f:
    lines = f.readlines()

fixes = 0

for i, line in enumerate(lines):
    # Fix 1: Hero subtitle - fjern butik-tal
    if 'id="hero-shops"' in line:
        lines[i] = '            <p class="hero-sub">Sammenlign <strong id="hero-count">500+</strong> rom fra danske webshops — opdateres dagligt</p>\n'
        fixes += 1
        print(f'Linje {i+1}: hero subtitle rettet')

    # Fix 2: Aged ikon
    if "quickType('Aged rom')" in line and 'Aged' in line:
        lines[i] = line.replace('🥃 Aged', '🕰️ Aged')
        if '🥃' not in lines[i] or 'Aged' in lines[i]:
            fixes += 1
            print(f'Linje {i+1}: Aged ikon rettet')

    # Fix 3: Fjern JS-reference til hero-shops (elementet eksisterer ikke laengere)
    if "getElementById('hero-shops')" in line:
        lines[i] = ''
        fixes += 1
        print(f'Linje {i+1}: hero-shops JS fjernet')

with open('index.html', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print(f'Faerdig — {fixes} rettelser')
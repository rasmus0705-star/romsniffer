with open('build_rom_data.py', encoding='utf-8') as f:
    content = f.read()

changes = 0

# 1. Tilfoej import
old_import = "from spitus_rom import scrape_spitus_rom"
new_import = "from spitus_rom import scrape_spitus_rom\nfrom rombo_rom import scrape_rombo_rom"

if 'rombo_rom' not in content:
    content = content.replace(old_import, new_import)
    changes += 1
    print('OK: import tilfojet')
else:
    print('Import: allerede tilstede')

# 2. Tilfoej scraper-kald efter Spitus-blokken
old_spitus = '''    # Spitus
    print("\\n🥃 Kører Spitus...")
    spitus_items = scrape_spitus_rom()
    all_items.extend(spitus_items)
    print(f"   ✅ {len(spitus_items)} produkter")'''

new_spitus = '''    # Spitus
    print("\\n🥃 Kører Spitus...")
    spitus_items = scrape_spitus_rom()
    all_items.extend(spitus_items)
    print(f"   ✅ {len(spitus_items)} produkter")

    # Rombo
    print("\\n🥃 Kører Rombo...")
    rombo_items = scrape_rombo_rom()
    all_items.extend(rombo_items)
    print(f"   ✅ {len(rombo_items)} produkter")'''

if 'rombo' not in content.lower() or 'scrape_rombo' not in content:
    if old_spitus in content:
        content = content.replace(old_spitus, new_spitus)
        changes += 1
        print('OK: Rombo scraper tilfojet')
    else:
        print('FEJL: Spitus-blok ikke fundet')
else:
    print('Rombo: allerede tilstede')

with open('build_rom_data.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f'Faerdig — {changes} aendringer')
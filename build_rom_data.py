"""
RomSniffer — Build rom_data.json.
Bruger smart parsing + hård gate matching + HTML enrichment.
"""
import json
import time
import subprocess
from datetime import datetime

from kokkensvinhus_rom import scrape_kokkensvinhus_rom
from spitus_rom import scrape_spitus_rom
from rombo_rom import scrape_rombo_rom
from rom_parser import enrich_from_html
from rom_matching import group_products


def enrich_missing_data(items, max_enrich=100):
    """
    For produkter hvor ABV/volume/age mangler, hent HTML siden og prøv at finde data.
    max_enrich: maks antal produkter at enriche (for at undgå at tage 30 min)
    """
    needs_enrich = [
        it for it in items
        if it.get("url") and (
            it.get("abv") is None or 
            it.get("volume_cl") is None
        )
    ]
    
    if not needs_enrich:
        print("   ✅ Ingen produkter behøver HTML enrichment")
        return
    
    # Sortér så vi tager dem med mest manglende data først
    needs_enrich.sort(key=lambda x: sum(1 for v in [
        x.get("abv"), x.get("volume_cl"), x.get("age")
    ] if v is None), reverse=True)
    
    to_enrich = needs_enrich[:max_enrich]
    print(f"   🌐 Henter HTML for {len(to_enrich)} produkter (max {max_enrich})...")
    
    cache = {}
    enriched_count = 0
    
    for i, item in enumerate(to_enrich, 1):
        if i % 20 == 0:
            print(f"      {i}/{len(to_enrich)}...")
        
        extra = enrich_from_html(item["url"], cache=cache)
        
        if extra.get("abv") and item.get("abv") is None:
            item["abv"] = extra["abv"]
            enriched_count += 1
        if extra.get("volume_cl") and item.get("volume_cl") is None:
            item["volume_cl"] = extra["volume_cl"]
            enriched_count += 1
        if extra.get("age") and item.get("age") is None:
            item["age"] = extra["age"]
            enriched_count += 1
    
    print(f"   ✅ HTML enrichment tilføjede data {enriched_count} gange")


def main():
    print("=" * 70)
    print("🥃 RomSniffer — Daglig opdatering")
    print(f"   Tidspunkt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    start = time.time()
    all_items = []

    # Kokkens Vinhus
    print("\n🥃 Kører Kokkens Vinhus...")
    kokkens_items = scrape_kokkensvinhus_rom()
    all_items.extend(kokkens_items)
    print(f"   ✅ {len(kokkens_items)} produkter")

    # Spitus
    print("\n🥃 Kører Spitus...")
    spitus_items = scrape_spitus_rom()
    all_items.extend(spitus_items)
    print(f"   ✅ {len(spitus_items)} produkter")

    # Rombo
    print("\n🥃 Kører Rombo...")
    rombo_items = scrape_rombo_rom()
    all_items.extend(rombo_items)
    print(f"   ✅ {len(rombo_items)} produkter")

    if not all_items:
        print("❌ Ingen produkter — afslutter")
        return

    # Filtrér åbenlyse ikke-rom
    print(f"\n🧹 Filtrerer ikke-rom væk...")
    before = len(all_items)
    bad_keywords = ["champagne", "vodka", "tequila", "prosecco", "gin ", "whisky", "whiskey"]
    # Kendte rom-brands/termer — behold altid selv hvis "cask"/"wine" optræder i navnet
    rom_whitelist = [
        "sbs ", "patridom", "la favorite", "dictador", "chasing casks",
        "plantation", "diplomatico", "diplomático", "foursquare", "el dorado",
        "appleton", "mount gay", "zacapa", "angostura", "doorly", "clément",
        "clement", "worthy park", "hampden", "smith & cross", "pusser",
        "compagnie des indes", "rum nation", "real mccoy", "don papa",
        "bumbu", "sailor jerry", "kraken", "brugal", "flor de caña",
        "santa teresa", "pampero", "botran", "abuelo", "a.h. riise",
        "ah riise", "riise", "santos dumont", "trois rivières",
        "chairman", "botucal", "cachaça", "cachaca", "millonario",
        "cartavio", "quorhum", "ron esclavo", "old pascas", "cobra bay",
        "saison rum", "takamaka",
    ]
    filtered = []
    for item in all_items:
        name_lower = item["name"].lower()
        # Altid behold hvis navn indeholder rom/rum/ron/rhum
        if "rom" in name_lower or "rum" in name_lower or "ron " in name_lower or "rhum" in name_lower:
            filtered.append(item)
            continue
        # Behold hvis kendt rom-brand
        if any(brand in name_lower for brand in rom_whitelist):
            filtered.append(item)
            continue
        # Behold hvis det har brand fra parser
        if item.get("brand"):
            filtered.append(item)
            continue
        # Smid kun væk hvis det rammer et tydeligt ikke-rom keyword
        if any(bad in name_lower for bad in bad_keywords):
            print(f"   🚫 Skipper: {item['name'][:60]}")
            continue
        # Ellers behold (bedre at have for mange end for få)
        filtered.append(item)
    all_items = filtered
    print(f"   Filtreret {before - len(all_items)} produkter væk")

    # HTML enrichment for manglende data
    print(f"\n🌐 HTML enrichment for produkter med manglende data...")
    enrich_missing_data(all_items, max_enrich=80)

    # Coverage statistik FØR matching
    with_brand = sum(1 for it in all_items if it.get("brand"))
    with_volume = sum(1 for it in all_items if it.get("volume_cl"))
    with_abv = sum(1 for it in all_items if it.get("abv"))
    with_age = sum(1 for it in all_items if it.get("age"))
    with_country = sum(1 for it in all_items if it.get("country"))
    print(f"\n📊 Coverage efter parsing:")
    print(f"   Brand:    {with_brand}/{len(all_items)} ({100*with_brand//len(all_items)}%)")
    print(f"   Volume:   {with_volume}/{len(all_items)} ({100*with_volume//len(all_items)}%)")
    print(f"   ABV:      {with_abv}/{len(all_items)} ({100*with_abv//len(all_items)}%)")
    print(f"   Alder:    {with_age}/{len(all_items)} ({100*with_age//len(all_items)}%)")
    print(f"   Land:     {with_country}/{len(all_items)} ({100*with_country//len(all_items)}%)")

    # Gruppér med hård gate matching
    print(f"\n🔗 Matcher rom på tværs af butikker (hård gate)...")
    groups, match_stats = group_products(all_items, verbose=True)

    # Byg final rom-objekter
    unique_roms = []
    for group in groups:
        group_sorted = sorted(group, key=lambda x: x["price"])
        first = group_sorted[0]
        
        prices = []
        for item in group_sorted:
            prices.append({
                "shop_name": item["shop_name"],
                "price": item["price"],
                "old_price": item.get("old_price"),
                "discount_pct": item.get("discount_pct"),
                "url": item["url"],
            })
        
        cheapest_price = prices[0]["price"]
        max_discount_pct = max((p.get("discount_pct") or 0 for p in prices), default=0)
        
        # Vælg bedste metadata (fra den med flest udfyldte felter)
        best_meta = max(group, key=lambda x: sum(1 for v in [
            x.get("image"), x.get("type"), x.get("country"), 
            x.get("age"), x.get("abv"), x.get("volume_cl"), x.get("brand")
        ] if v))

        unique_roms.append({
            "name": first["name"],
            "image": best_meta.get("image"),
            "type": best_meta.get("type"),
            "country": best_meta.get("country"),
            "brand": best_meta.get("brand"),
            "abv": best_meta.get("abv"),
            "volume_cl": best_meta.get("volume_cl"),
            "age": best_meta.get("age"),
            "category": "rom",
            "shop_count": len(set(p["shop_name"] for p in prices)),
            "min_price": cheapest_price,
            "cheapest_price": cheapest_price,
            "max_discount_pct": max_discount_pct,
            "prices": prices,
        })

    unique_roms.sort(key=lambda x: x["min_price"])

    # Statistik
    total = len(unique_roms)
    deals = sum(1 for r in unique_roms if r["max_discount_pct"] > 0)
    shop_names = sorted(set(item["shop_name"] for item in all_items))
    types = sorted(set(r["type"] for r in unique_roms if r.get("type")))
    countries = sorted(set(r["country"] for r in unique_roms if r.get("country")))
    ages = sorted(set(r["age"] for r in unique_roms if r.get("age")), key=lambda x: (
        (0, int(x.split()[0])) if x.endswith(" år") else (1, 0 if x == "XO" else 1 if x == "Solera" else 2)
    ))
    cheapest = min((r["min_price"] for r in unique_roms), default=0)
    multi_shop_count = sum(1 for r in unique_roms if r["shop_count"] > 1)

    output = {
        "updated": datetime.now().isoformat(),
        "stats": {
            "total": total,
            "deals": deals,
            "shops": len(shop_names),
            "shop_names": shop_names,
            "types": types,
            "countries": countries,
            "ages": ages,
            "cheapest": cheapest,
            "multi_shop": multi_shop_count,
        },
        "roms": unique_roms,
    }

    with open("rom_data.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # ── Git push til GitHub (GitHub Pages serverer rom_data.json) ──
    print("\n📤 Pusher rom_data.json til GitHub...")
    try:
        subprocess.run(["git", "add", "rom_data.json"], check=True)
        subprocess.run(
            ["git", "commit", "-m", f"Opdater rompriser {datetime.now().strftime('%Y-%m-%d %H:%M')}"],
            check=True
        )
        subprocess.run(["git", "push"], check=True)
        print("✅ rom_data.json pushet til GitHub!")
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Git push fejlede: {e}")
        print("   (Kør manuelt: git add rom_data.json && git commit -m 'opdater' && git push)")
    # ──────────────────────────────────────────────────────────────

    elapsed = time.time() - start
    print(f"\n{'=' * 70}")
    print(f"✅ FÆRDIG på {elapsed:.1f}s")
    print(f"   Skrev rom_data.json med {total} unikke rom fra {len(shop_names)} butikker")
    print(f"   Rom i flere butikker: {multi_shop_count}")
    print(f"   Aktive tilbud: {deals}")
    print(f"   Billigste: {cheapest:.0f} kr")
    print(f"   Stilarter: {len(types)}, Lande: {len(countries)}, Aldre: {len(ages)}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
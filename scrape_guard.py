"""
scrape_guard.py — Værn mod tavse scraper-fejl.

BAGGRUND: Da Rombo returnerede HTTP 403, hentede buildet 0 produkter derfra
og publicerede alligevel — 1037 rom blev 579, og 544 rom-sider blev slettet
og pushet til produktion. Ingen advarsel.

Dette modul afbryder buildet hvis:
  1. En forventet butik returnerer 0 produkter
  2. Totalen er faldet mere end MAX_DROP_PCT siden sidste build
  3. En enkelt butik er faldet mere end MAX_SHOP_DROP_PCT

Brug --force for at køre alligevel (fx når et fald er reelt).
"""
import json
import os
import sys
from collections import Counter

ROM_DATA_FILE = "rom_data.json"

# Butikker der SKAL levere produkter
EXPECTED_SHOPS = ["Kokkens Vinhus", "Spitus", "Rombo"]

MAX_DROP_PCT = 25.0        # samlet fald der udløser stop
MAX_SHOP_DROP_PCT = 40.0   # fald for én butik der udløser stop


def _previous_counts(path=ROM_DATA_FILE):
    """Læs forrige builds tal. Returnerer (total, {butik: antal}) eller (None, {})."""
    if not os.path.exists(path):
        return None, {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None, {}

    stats = data.get("stats", {})
    total = stats.get("total")

    # shop_counts findes kun i builds efter dette modul blev indført
    shop_counts = stats.get("shop_counts") or {}

    if not shop_counts:
        # Udled fra prices som fallback
        counter = Counter()
        for rom in data.get("roms", []):
            for p in rom.get("prices", []):
                if p.get("shop_name"):
                    counter[p["shop_name"]] += 1
        shop_counts = dict(counter)

    return total, shop_counts


def check(all_items, force=False, path=ROM_DATA_FILE):
    """
    Tjek scrape-sundhed. Returnerer (ok, shop_counts).
    Ved problemer printes forklaring; ok=False medmindre force=True.
    """
    counts = Counter(it.get("shop_name") for it in all_items if it.get("shop_name"))
    shop_counts = dict(counts)

    print("\n🛡️  Scrape-sundhedstjek...")
    problems = []

    # ── 1. Tomme butikker ──
    for shop in EXPECTED_SHOPS:
        n = shop_counts.get(shop, 0)
        if n == 0:
            problems.append(f"{shop} returnerede 0 produkter")

    # ── 2. Sammenlign med forrige build ──
    prev_total, prev_shops = _previous_counts(path)
    total = len(all_items)

    if prev_total:
        # prev_total er antal unikke rom EFTER matching; total er rå produkter
        # før matching. Vi sammenligner derfor pr. butik, som er æbler-til-æbler,
        # og bruger kun den samlede sum af forrige butikstal som reference.
        prev_sum = sum(prev_shops.values()) if prev_shops else None
        if prev_sum:
            drop = 100 * (prev_sum - total) / prev_sum
            if drop > MAX_DROP_PCT:
                problems.append(
                    f"total faldt {drop:.0f}% ({prev_sum} → {total}), "
                    f"grænse er {MAX_DROP_PCT:.0f}%"
                )

    for shop, prev_n in prev_shops.items():
        if prev_n < 10:
            continue  # for lille base til at vurdere
        now_n = shop_counts.get(shop, 0)
        drop = 100 * (prev_n - now_n) / prev_n
        if drop > MAX_SHOP_DROP_PCT:
            problems.append(
                f"{shop} faldt {drop:.0f}% ({prev_n} → {now_n}), "
                f"grænse er {MAX_SHOP_DROP_PCT:.0f}%"
            )

    # ── Rapport ──
    for shop in EXPECTED_SHOPS:
        now_n = shop_counts.get(shop, 0)
        prev_n = prev_shops.get(shop)
        if prev_n:
            diff = now_n - prev_n
            arrow = "→" if diff == 0 else ("↑" if diff > 0 else "↓")
            print(f"   {shop:18s} {now_n:5d}  {arrow} {diff:+d} vs sidst")
        else:
            print(f"   {shop:18s} {now_n:5d}")

    if not problems:
        print("   ✅ Alle butikker ser sunde ud")
        return True, shop_counts

    print("\n" + "=" * 70)
    print("❌ SCRAPE-PROBLEM — buildet er STOPPET før data blev skrevet")
    print("=" * 70)
    for p in problems:
        print(f"   • {p}")
    print("\n   Ingen filer er ændret, og der er ikke pushet til GitHub.")
    print("\n   Mulige årsager:")
    print("     - Butikken blokerer scraperen (403/429) — tjek User-Agent")
    print("     - Butikken har ændret API eller kategori-ID")
    print("     - Netværksfejl")
    print("\n   Undersøg med:")
    print("     python -c \"from rombo_rom import scrape_rombo_rom as s; print(len(s()))\"")
    print("\n   Er faldet reelt (butik lukket, sortiment skrumpet)? Kør så:")
    print("     python build_rom_data.py --force")
    print("=" * 70)

    if force:
        print("\n⚠️  --force angivet — fortsætter alligevel\n")
        return True, shop_counts

    return False, shop_counts


def force_requested(argv=None):
    """Er --force angivet på kommandolinjen?"""
    return "--force" in (argv if argv is not None else sys.argv)


if __name__ == "__main__":
    # Selvtest
    print("── Test: normal drift ──")
    items = (
        [{"shop_name": "Kokkens Vinhus"}] * 250
        + [{"shop_name": "Spitus"}] * 331
        + [{"shop_name": "Rombo"}] * 485
    )
    ok, counts = check(items, path="/nonexistent.json")
    assert ok

    print("\n── Test: Rombo nede (0 produkter) ──")
    items_bad = (
        [{"shop_name": "Kokkens Vinhus"}] * 250
        + [{"shop_name": "Spitus"}] * 331
    )
    ok, _ = check(items_bad, path="/nonexistent.json")
    assert not ok, "burde have stoppet buildet"

    print("\n── Test: samme, men med --force ──")
    ok, _ = check(items_bad, force=True, path="/nonexistent.json")
    assert ok

    print("\n✅ Alle tests bestået")

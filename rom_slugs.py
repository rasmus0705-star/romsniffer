"""
rom_slugs.py — Persistente slugs for RomSniffer.

PROBLEM: Slugs blev tidligere udregnet fra produktnavnet ved hver build.
Når en butik ændrede et navn (eller vi rensede HTML-entities), ændrede
slug'en sig — og hver indekseret URL blev en 404.

LØSNING: Slugs bindes til produkt-URL'er, som er stabile. Et slug tildeles
én gang og ændres aldrig, uanset hvad der siden sker med navnet.

Datafil: rom_slugs.json
{
  "version": 1,
  "entries": {
    "https://butik.dk/produkt-x": {
      "slug": "ron-zacapa-23",
      "first_seen": "2026-07-28",
      "last_seen": "2026-07-28"
    }
  }
}

Forsvundne produkter bliver IKKE slettet fra filen — det reserverer deres
slug, så et nyt produkt ikke arver en gammel URL.
"""
import json
import os
from datetime import date

from slugify_rom import slugify

SLUG_FILE = "rom_slugs.json"


# ────────────────────────────────────────────────────────────
# LOAD / SAVE
# ────────────────────────────────────────────────────────────

def load_slug_map(path=SLUG_FILE):
    """Indlæs slug-kortet. Returnerer (entries, used_slugs)."""
    if not os.path.exists(path):
        return {}, set()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"   ⚠️  Kunne ikke læse {path}: {e}")
        print("      Starter med tomt slug-kort (ALLE slugs vil blive nye!)")
        return {}, set()

    entries = data.get("entries", {})
    used = {v["slug"] for v in entries.values() if v.get("slug")}
    return entries, used


def save_slug_map(entries, path=SLUG_FILE):
    """Gem slug-kortet."""
    data = {"version": 1, "entries": entries}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    os.replace(tmp, path)  # atomisk — undgår korrupt fil ved crash


# ────────────────────────────────────────────────────────────
# SLUG-TILDELING
# ────────────────────────────────────────────────────────────

def _unique(base, used):
    """Find et ledigt slug baseret på base."""
    if not base:
        base = "rom"
    if base not in used:
        return base
    n = 2
    while f"{base}-{n}" in used:
        n += 1
    return f"{base}-{n}"


def assign_slugs(unique_roms, path=SLUG_FILE, verbose=True):
    """
    Tildel stabile slugs til alle rom i unique_roms (muterer objekterne).

    Logik pr. rom-gruppe:
      1. Saml alle produkt-URL'er i gruppen.
      2. Hvis nogen af dem allerede har et slug i kortet — genbrug det.
         (Ved flere forskellige: vælg det ældste, så det mest etablerede
          slug vinder.)
      3. Ellers: generér nyt slug fra navnet.
      4. Skriv alle gruppens URL'er tilbage til kortet med det valgte slug.

    Returnerer stats-dict.
    """
    entries, used = load_slug_map(path)
    today = date.today().isoformat()

    claimed = set()   # slugs taget i DENNE build
    reused = 0
    created = 0
    conflicts = 0

    for rom in unique_roms:
        urls = [p.get("url") for p in rom.get("prices", []) if p.get("url")]

        # Find eksisterende slug via URL'erne
        candidates = []
        for u in urls:
            e = entries.get(u)
            if e and e.get("slug"):
                candidates.append((e.get("first_seen", "9999"), e["slug"]))

        slug = None
        if candidates:
            candidates.sort()  # ældste first_seen først
            for _, cand in candidates:
                if cand not in claimed:
                    slug = cand
                    reused += 1
                    break
            else:
                # Alle kandidat-slugs er allerede taget i denne build
                # (en gruppe er splittet i to) — giv den nyeste et nyt slug
                conflicts += 1

        if slug is None:
            slug = _unique(slugify(rom["name"]), used | claimed)
            created += 1

        rom["slug"] = slug
        claimed.add(slug)
        used.add(slug)

        # Opdatér kortet for alle URL'er i gruppen
        for u in urls:
            if u in entries:
                entries[u]["slug"] = slug
                entries[u]["last_seen"] = today
            else:
                entries[u] = {
                    "slug": slug,
                    "first_seen": today,
                    "last_seen": today,
                }

    save_slug_map(entries, path)

    stats = {
        "total": len(unique_roms),
        "reused": reused,
        "created": created,
        "conflicts": conflicts,
        "map_size": len(entries),
    }

    if verbose:
        print(f"   🔗 Slugs: {reused} genbrugt, {created} nye", end="")
        if conflicts:
            print(f", {conflicts} konflikt(er) løst med nyt slug", end="")
        print(f" — kort: {len(entries)} URL'er")
        if created and reused:
            pct = 100 * created / max(len(unique_roms), 1)
            if pct > 25:
                print(f"   ⚠️  {pct:.0f}% nye slugs — usædvanligt højt.")
                print("      Tjek at rom_slugs.json ikke er gået tabt.")

    return stats


def active_slugs(unique_roms):
    """Slugs der findes i det aktuelle datasæt."""
    return {r["slug"] for r in unique_roms if r.get("slug")}


if __name__ == "__main__":
    # Selvtest med midlertidig fil
    import tempfile

    tmpdir = tempfile.mkdtemp()
    test_path = os.path.join(tmpdir, "test_slugs.json")

    print("── Test 1: første tildeling ──")
    roms = [
        {"name": "Ron Zacapa 23", "prices": [{"url": "https://a.dk/zacapa"}]},
        {"name": "Doorly's 12 YO", "prices": [{"url": "https://a.dk/doorlys"}]},
    ]
    assign_slugs(roms, test_path)
    print(f"   {roms[0]['slug']} / {roms[1]['slug']}")
    assert roms[0]["slug"] == "ron-zacapa-23"
    assert roms[1]["slug"] == "doorlys-12-yo"

    print("\n── Test 2: navn ændres, URL er den samme → slug bevares ──")
    roms2 = [
        {"name": "Ron Zacapa Centenario 23 Solera", "prices": [{"url": "https://a.dk/zacapa"}]},
        {"name": "Doorly&#8217;s 12 YO", "prices": [{"url": "https://a.dk/doorlys"}]},
    ]
    assign_slugs(roms2, test_path)
    print(f"   {roms2[0]['slug']} / {roms2[1]['slug']}")
    assert roms2[0]["slug"] == "ron-zacapa-23", "slug skiftede ved navneændring!"
    assert roms2[1]["slug"] == "doorlys-12-yo", "slug skiftede ved navneændring!"

    print("\n── Test 3: to butikker matcher → arver ældste slug ──")
    roms3 = [
        {"name": "Ron Zacapa 23", "prices": [
            {"url": "https://a.dk/zacapa"},
            {"url": "https://b.dk/zacapa-23"},
        ]},
    ]
    assign_slugs(roms3, test_path)
    print(f"   {roms3[0]['slug']}")
    assert roms3[0]["slug"] == "ron-zacapa-23"

    print("\n── Test 4: gruppen splittes igen → én beholder, én får nyt ──")
    roms4 = [
        {"name": "Ron Zacapa 23", "prices": [{"url": "https://a.dk/zacapa"}]},
        {"name": "Ron Zacapa 23", "prices": [{"url": "https://b.dk/zacapa-23"}]},
    ]
    assign_slugs(roms4, test_path)
    print(f"   {roms4[0]['slug']} / {roms4[1]['slug']}")
    assert roms4[0]["slug"] != roms4[1]["slug"], "kollision ikke håndteret!"

    print("\n── Test 5: nyt produkt får ikke et gammelt slug ──")
    roms5 = [
        {"name": "Ron Zacapa 23", "prices": [{"url": "https://c.dk/helt-ny"}]},
    ]
    assign_slugs(roms5, test_path)
    print(f"   {roms5[0]['slug']}")
    assert roms5[0]["slug"] != "ron-zacapa-23", "nyt produkt arvede gammelt slug!"

    print("\n✅ Alle tests bestået")
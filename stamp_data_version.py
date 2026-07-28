"""
stamp_data_version.py — Cache-busting med indholds-hash.

PROBLEM: index.html og premium.html henter data med
    fetch('rom_data.json?v=' + Date.now())

Date.now() er unik ved HVERT sidevisning. Det betyder at hverken browseren
eller Cloudflare nogensinde kan genbruge en hentet kopi — hver besøgende,
og hvert reload, trækker hele rom_data.json (~1,5 MB) ned forfra.

LØSNING: Stempl en version ind ved build-tid, udregnet som hash af
rom_data.json's indhold:
    fetch('rom_data.json?v=' + DATA_VERSION)

Så gælder:
  - Data uændret  → samme streng → browseren genbruger sin kopi
  - Data ændret   → ny streng    → alle henter friske data straks

Bemærk: browser-cachen er den sikre gevinst her. Om Cloudflare også cacher
filen afhænger af dine Cache Rules — JSON ligger ikke i Cloudflares
standardliste over cachede filtyper.

Køres som sidste build-step, EFTER rom_data.json er skrevet.
"""
import hashlib
import os
import re
import sys

DATA_FILE = "rom_data.json"
TARGETS = ["index.html", "premium.html"]

# Matcher et eksisterende stempel, uanset citationstegn og mellemrum
_STAMP_RE = re.compile(
    r"const\s+DATA_VERSION\s*=\s*['\"][^'\"]*['\"]\s*;"
)

# Matcher fetch-kaldet med Date.now(), med eller uden mellemrum om +
_FETCH_RE = re.compile(
    r"(fetch\(\s*['\"]" + re.escape(DATA_FILE) + r"\?v=['\"]\s*\+\s*)Date\.now\(\)"
)


def data_version(path=DATA_FILE):
    """Kort hash af datafilens indhold."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def stamp_file(path, version):
    """
    Stempl version ind i én HTML-fil.
    Returnerer (ændret, status-tekst).
    """
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    original = html

    # ── 1. Erstat Date.now() i fetch-kaldet ──
    html, n_fetch = _FETCH_RE.subn(r"\1DATA_VERSION", html)

    # ── 2. Indsæt eller opdatér stemplet ──
    stamp = f"const DATA_VERSION = '{version}';"

    if _STAMP_RE.search(html):
        html = _STAMP_RE.sub(stamp, html)
        placed = "opdateret"
    else:
        # Læg det i <head> som global, så alle senere scripts kan se det
        block = f"<script>{stamp}</script>\n</head>"
        if "</head>" not in html:
            return False, "FEJL: ingen </head> fundet"
        html = html.replace("</head>", block, 1)
        placed = "indsat"

    # ── 3. Sanity: er der Date.now() tilbage på datafilen? ──
    leftover = "Date.now()" in html and f"{DATA_FILE}?v=" in html
    if leftover and _FETCH_RE.search(html):
        return False, "FEJL: fetch med Date.now() findes stadig"

    if html == original:
        return False, "uændret"

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)

    parts = [f"stempel {placed}"]
    if n_fetch:
        parts.append(f"{n_fetch} fetch-kald bundet til DATA_VERSION")
    return True, ", ".join(parts)


def main():
    if not os.path.exists(DATA_FILE):
        print(f"   ⚠️  {DATA_FILE} findes ikke — springer cache-stempling over")
        return None

    version = data_version()
    print(f"\n🏷️  Cache-version: {version}")

    for path in TARGETS:
        if not os.path.exists(path):
            print(f"   ⏭️  {path} findes ikke")
            continue
        changed, status = stamp_file(path, version)
        icon = "✅" if changed else ("⏭️ " if "uændret" in status else "❌")
        print(f"   {icon} {path}: {status}")
        if status.startswith("FEJL"):
            sys.exit(1)

    return version


if __name__ == "__main__":
    main()
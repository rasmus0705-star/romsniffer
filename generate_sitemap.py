"""
generate_sitemap.py — Generér sitemap.xml for RomSniffer.

Inkluderer:
- Faste sider (forside, guide, premium, om)
- Alle /rom/{slug}/ produktsider
- Kategorisider (/rom/land/, /rom/type/, /rom/alder/) og brandsider (/rom/brand/)

<lastmod> er den dag, SIDEN FAKTISK ÆNDREDE SIG - ikke dagens dato. Google bruger kun lastmod, hvis den er
pålidelig; stod den på "i dag" for alle 1.200 sider hver dag, ville Google lære at ignorere den. Derfor
gemmes et fingeraftryk af hver sides indhold i sitemap_state.json (datoen "opdateret ..." og afsnittet "Relaterede rom" er
trukket fra, så de ikke ændrer fingeraftrykket hver dag). Første kørsel sætter alle til i dag.

sitemap_state.json er lokal tilstand: den skal IKKE committes (står i .gitignore).
"""
import hashlib
import json
import os
import re
from datetime import datetime

SITE_URL = "https://www.romsniffer.dk"      # samme adresse som canonical-tagsene
ROM_DIR = "rom"
OUTPUT_FILE = "sitemap.xml"
STATE_FILE = "sitemap_state.json"
CATEGORY_TYPES = ["land", "type", "alder"]

_MONTHS_DA = "januar|februar|marts|april|maj|juni|juli|august|september|oktober|november|december"
# "9. oktober 2026" (nu) og "09. Oct 2026" (gamle sider) - fjernes før fingeraftrykket
_DATE_RE = re.compile(r"\b\d{1,2}\.\s*(?:%s|[A-Za-z]{3})\s+\d{4}\b" % _MONTHS_DA)
# "Relaterede rom" viser andre produkters priser; de ændrer sig næsten hver dag og skal ikke tælle som ændring af SIDEN
_RELATED_RE = re.compile(r'<section class="related">.*?</section>', re.S)


def _fingerprint(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            html = f.read()
    except OSError:
        return None
    html = _RELATED_RE.sub("", html)
    return hashlib.sha1(_DATE_RE.sub("", html).encode("utf-8")).hexdigest()[:16]


def _load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def main():
    print("\n🗺️  Genererer sitemap.xml...")
    today = datetime.now().strftime("%Y-%m-%d")
    state = _load_state()
    new_state = {}
    changed_today = 0

    def lastmod_for(key, source_path):
        """Dato for sidens seneste ændring (i dag, hvis fingeraftrykket er nyt)."""
        nonlocal changed_today
        fp = _fingerprint(source_path)
        old = state.get(key)
        if fp is None:
            return old["d"] if old else today
        if old and old.get("h") == fp:
            new_state[key] = old
            return old["d"]
        new_state[key] = {"h": fp, "d": today}
        changed_today += 1
        return today

    urls = []

    # Faste sider
    static_pages = [
        ("", "index.html", "1.0", "daily"),
        ("guide.html", "guide.html", "0.8", "monthly"),
        ("premium.html", "premium.html", "0.7", "daily"),
        ("om.html", "om.html", "0.3", "monthly"),
    ]
    for path, source, priority, freq in static_pages:
        urls.append({
            "loc": f"{SITE_URL}/{path}",
            "lastmod": lastmod_for(path or "index.html", source),
            "changefreq": freq,
            "priority": priority,
        })

    # Kategorisider
    cat_count = 0
    for cat_type in CATEGORY_TYPES:
        cat_dir = os.path.join(ROM_DIR, cat_type)
        if os.path.isdir(cat_dir):
            for entry in sorted(os.listdir(cat_dir)):
                index_path = os.path.join(cat_dir, entry, "index.html")
                if os.path.isfile(index_path):
                    urls.append({
                        "loc": f"{SITE_URL}/rom/{cat_type}/{entry}/",
                        "lastmod": lastmod_for(f"rom/{cat_type}/{entry}/", index_path),
                        "changefreq": "daily",
                        "priority": "0.7",
                    })
                    cat_count += 1

    # Rom-sider fra /rom/ mappen (kun direkte undermapper, ikke land/type/alder)
    rom_count = 0
    if os.path.isdir(ROM_DIR):
        for entry in sorted(os.listdir(ROM_DIR)):
            if entry in CATEGORY_TYPES or entry == "brand":
                continue
            index_path = os.path.join(ROM_DIR, entry, "index.html")
            if os.path.isfile(index_path):
                urls.append({
                    "loc": f"{SITE_URL}/rom/{entry}/",
                    "lastmod": lastmod_for(f"rom/{entry}/", index_path),
                    "changefreq": "daily",
                    "priority": "0.6",
                })
                rom_count += 1

    # Brand-sider fra /rom/brand/
    brand_count = 0
    brand_dir = os.path.join(ROM_DIR, "brand")
    if os.path.isdir(brand_dir):
        for entry in sorted(os.listdir(brand_dir)):
            index_path = os.path.join(brand_dir, entry, "index.html")
            if os.path.isfile(index_path):
                urls.append({
                    "loc": f"{SITE_URL}/rom/brand/{entry}/",
                    "lastmod": lastmod_for(f"rom/brand/{entry}/", index_path),
                    "changefreq": "weekly",
                    "priority": "0.6",
                })
                brand_count += 1

    # Skriv XML
    xml_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for url in urls:
        xml_parts.append("  <url>")
        xml_parts.append(f"    <loc>{url['loc']}</loc>")
        xml_parts.append(f"    <lastmod>{url['lastmod']}</lastmod>")
        xml_parts.append(f"    <changefreq>{url['changefreq']}</changefreq>")
        xml_parts.append(f"    <priority>{url['priority']}</priority>")
        xml_parts.append("  </url>")
    xml_parts.append("</urlset>")
    xml_parts.append("")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(xml_parts))
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(new_state, f, ensure_ascii=False)

    print(f"   ✅ sitemap.xml skrevet med {len(urls)} URL'er ({rom_count} rom + {cat_count} kategorier + {len(static_pages)} faste + {brand_count} brands)")
    print(f"   🕒 lastmod ændret i dag for {changed_today} sider (resten beholder deres gamle dato)")


if __name__ == "__main__":
    main()

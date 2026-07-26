"""
generate_sitemap.py — Generér sitemap.xml for RomSniffer.

Inkluderer:
- Faste sider (forside, guide, premium, om)
- Alle /rom/{slug}/ produktsider
"""
import os
from datetime import datetime

SITE_URL = "https://www.romsniffer.dk"
ROM_DIR = "rom"
OUTPUT_FILE = "sitemap.xml"


def main():
    print("\n🗺️  Genererer sitemap.xml...")
    today = datetime.now().strftime("%Y-%m-%d")

    urls = []

    # Faste sider
    static_pages = [
        ("", "1.0", "daily"),
        ("guide.html", "0.8", "monthly"),
        ("premium.html", "0.7", "daily"),
        ("om.html", "0.3", "monthly"),
    ]
    for path, priority, freq in static_pages:
        urls.append({
            "loc": f"{SITE_URL}/{path}",
            "lastmod": today,
            "changefreq": freq,
            "priority": priority,
        })

    # Rom-sider fra /rom/ mappen
    rom_count = 0
    if os.path.isdir(ROM_DIR):
        for entry in sorted(os.listdir(ROM_DIR)):
            index_path = os.path.join(ROM_DIR, entry, "index.html")
            if os.path.isfile(index_path):
                urls.append({
                    "loc": f"{SITE_URL}/rom/{entry}/",
                    "lastmod": today,
                    "changefreq": "daily",
                    "priority": "0.6",
                })
                rom_count += 1

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

    print(f"   ✅ sitemap.xml skrevet med {len(urls)} URL'er ({rom_count} rom-sider + {len(static_pages)} faste)")


if __name__ == "__main__":
    main()
"""
rom_text.py — fælles hjælpere til generate_rom_pages / generate_category_pages / generate_brand_pages.

  clean_text(x)     afkoder dobbelt-kodede HTML-tegn ("Smith &amp;amp; Cross" -> "Smith & Cross")
  esc(x)            clean_text + HTML-escape (erstatter de lokale esc()-funktioner)
  plausible_abv(r)  alkoholprocent, hvis den er troværdig - ellers None (se reglerne nedenfor)
  fmt_abv(v)        dansk format: 45,2%
  dk_date(dt)       "9. oktober 2026" uafhængigt af styresystemets sprogindstilling
  filter_category   filtrerer data til den kategori, generatoren bygger (CATEGORY)

Tilføj en ny kategori (fx whisky) ved at kopiere de tre generatorer, sætte CATEGORY = "whisky"
og OUTPUT_DIR = "whisky", og give rom_data.json-posterne feltet "category": "whisky".
"""
import re
from html import escape, unescape

CATEGORY = "rom"

GLASS_SVG = ('<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 22h8"/><path d="M7 10h10"/>'
             '<path d="M12 15v7"/><path d="M12 15a5 5 0 0 0 5-5c0-2-.5-4-2-8H9c-1.5 4-2 6-2 8a5 5 0 0 0 5 5Z"/></svg>')

_MONTHS = ["januar", "februar", "marts", "april", "maj", "juni",
           "juli", "august", "september", "oktober", "november", "december"]


def clean_text(text):
    s = "" if text is None else str(text)
    for _ in range(3):
        u = unescape(s)
        if u == s:
            break
        s = u
    return s


def esc(text):
    """HTML-escape med fallback for None og afkodning af dobbelt-kodede tegn."""
    return escape(clean_text(text)) if text else ""


def plausible_abv(rom):
    """
    Returnerer alkoholprocenten som float, hvis den er troværdig, ellers None.
    - under 20 % eller over 85 %: ikke en spiritus-styrke -> None
    - 70, 75 og 80 % er næsten altid en fejl (flaskestørrelsen 70/75 cl eller en afrunding). De accepteres kun,
      hvis navnet selv nævner styrken (fx "75,5%", "80 %") eller siger "proof"/"151".
    - andre tal over 70 (72,0 / 73,6 / 74,9) kommer fra tekst med procent og accepteres.
    Den rigtige rettelse ligger i rom_parser.extract_abv; det her er sikkerhedsnettet for allerede gemte data.
    """
    try:
        v = float(rom.get("abv"))
    except (TypeError, ValueError):
        return None
    if v < 20 or v > 85:
        return None
    if v >= 70 and abs(v / 5 - round(v / 5)) < 1e-9:
        name = clean_text(rom.get("name")).lower().replace(",", ".")
        mentioned = re.search(r"(?<!\d)%d(\.\d+)?\s*%%" % int(v), name)
        if not (mentioned or "proof" in name or "151" in name):
            return None
    return v


def fmt_abv(v):
    s = ("%.1f" % v).rstrip("0").rstrip(".")
    return s.replace(".", ",") + "%"


def dk_date(dt):
    return "%d. %s %d" % (dt.day, _MONTHS[dt.month - 1], dt.year)


def filter_category(roms, category=None):
    cat = category or CATEGORY
    return [r for r in roms if (r.get("category") or "rom").lower() == cat]

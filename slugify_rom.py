"""
slugify_rom.py — Generér URL-sikre slugs fra rom-navne.
Håndterer accenter, specialtegn og kollisioner.
"""
import re
import unicodedata


# Eksplicitte replacements (fanger tegn NFKD ikke altid splitter rent)
_ACCENT_MAP = {
    "à": "a", "á": "a", "â": "a", "ã": "a", "ä": "a", "å": "a",
    "è": "e", "é": "e", "ê": "e", "ë": "e",
    "ì": "i", "í": "i", "î": "i", "ï": "i",
    "ò": "o", "ó": "o", "ô": "o", "õ": "o", "ö": "o",
    "ù": "u", "ú": "u", "û": "u", "ü": "u",
    "ý": "y", "ÿ": "y",
    "ñ": "n", "ç": "c", "ð": "d", "þ": "th",
    "ø": "o", "æ": "ae",
    "ā": "a", "ē": "e", "ī": "i", "ō": "o", "ū": "u",  # macrons
    "š": "s", "ž": "z", "č": "c", "ř": "r", "ď": "d", "ť": "t", "ň": "n",
    "ł": "l", "ś": "s", "ź": "z", "ż": "z", "ć": "c",
    "ă": "a", "ș": "s", "ț": "t",
    # Apostroffer og anførselstegn → fjern
    "'": "", "'": "", "'": "", "´": "", "`": "",
    "\u2018": "", "\u2019": "", "\u201c": "", "\u201d": "",
}


def strip_accents(text):
    """Fjern accenter via eksplicit map + NFKD fallback."""
    result = []
    for ch in text:
        lower = ch.lower()
        if lower in _ACCENT_MAP:
            # Bevar original case for uppercase
            replacement = _ACCENT_MAP[lower]
            if ch.isupper() and replacement:
                replacement = replacement[0].upper() + replacement[1:]
            result.append(replacement)
        else:
            result.append(ch)
    text = "".join(result)

    # NFKD fallback for alt vi ikke dækkede eksplicit
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def slugify(name):
    """
    Konverter rom-navn til URL-sikker slug.
    'Ron Zacapa Centenario 23 SISTEMA SOLERA' → 'ron-zacapa-centenario-23-sistema-solera'
    """
    if not name:
        return ""

    text = strip_accents(name.strip())
    text = text.lower()

    # & → and
    text = text.replace("&", "and")

    # Alt der ikke er alfanumerisk eller bindestreg → mellemrum
    text = re.sub(r"[^a-z0-9\-]", " ", text)

    # Saml whitespace og konverter til bindestreg
    text = re.sub(r"[\s\-]+", "-", text).strip("-")

    return text


def make_unique_slug(name, seen_slugs):
    """
    Generér slug og tilføj -2, -3 osv. ved kollision.
    Returnerer slug og opdaterer seen_slugs sættet.
    """
    base = slugify(name)
    if not base:
        base = "rom"

    slug = base
    counter = 2
    while slug in seen_slugs:
        slug = f"{base}-{counter}"
        counter += 1

    seen_slugs.add(slug)
    return slug


if __name__ == "__main__":
    tests = [
        "Ron Zacapa Centenario 23 SISTEMA SOLERA Gran Reserva",
        "Diplomático Reserva Exclusiva 40%",
        "A.H. Riise X.O. Reserve 40%",
        "Rhum Clément 10 Ans d'Âge",
        "Ārpus Brewing Co. Rum Barrel Aged",
        "Flor de Caña 18 Años",
        "Cachaça 51 Gold",
        "Foursquare Exceptional Cask 2008",
        "Smith & Cross Navy Strength",
    ]
    seen = set()
    for name in tests:
        slug = make_unique_slug(name, seen)
        print(f"  {name[:55]:55s} → {slug}")
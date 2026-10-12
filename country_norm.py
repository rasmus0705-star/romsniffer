"""
country_norm.py — Normaliserer landefeltet paa tvaers af alle butikker.

Butikkerne skriver land som fritekst ("Den Dominikanske Republik",
"Saint Catherine, Jamaica", "Guyana / England", "Barbados og Jamaica" ...).
Hver variant blev til sin egen landeside. Regler:

  1. Find alle kendte lande i teksten.
  2. Aftapper-/finish-lande (England, Danmark, Spanien ...) ignoreres, naar
     der ogsaa staar et egentligt oprindelsesland.
  3. Praecis ét land        -> det land
     To eller flere lande   -> "Flere lande"
     Intet land, men region -> regionen (fx "Caribien")
     Intet genkendt         -> None (og rapporteres, saa listen kan udvides)
"""
import re

# alias (lowercase) -> kanonisk navn
COUNTRIES = {
    "jamaica": "Jamaica", "barbados": "Barbados", "guyana": "Guyana",
    "panama": "Panama", "martinique": "Martinique", "venezuela": "Venezuela",
    "cuba": "Cuba", "trinidad": "Trinidad", "guatemala": "Guatemala",
    "colombia": "Colombia", "réunion": "Réunion", "reunion": "Réunion",
    "puerto rico": "Puerto Rico", "mauritius": "Mauritius",
    "filippinerne": "Filippinerne", "grenada": "Grenada", "haiti": "Haiti",
    "peru": "Peru", "brasilien": "Brasilien", "mexico": "Mexico",
    "østrig": "Østrig", "nicaragua": "Nicaragua", "guadeloupe": "Guadeloupe",
    "seychellerne": "Seychellerne", "australien": "Australien",
    "el salvador": "El Salvador", "japan": "Japan", "sydafrika": "Sydafrika",
    "paraguay": "Paraguay", "saint lucia": "Saint Lucia",
    "st. lucia": "Saint Lucia", "st lucia": "Saint Lucia",
    "costa rica": "Costa Rica", "belize": "Belize", "fiji": "Fiji",
    "bermuda": "Bermuda", "indien": "Indien", "bahamas": "Bahamas",
    "antigua": "Antigua", "portugal": "Portugal", "indonesien": "Indonesien",
    "thailand": "Thailand", "vietnam": "Vietnam", "ecuador": "Ecuador",
    "ghana": "Ghana", "taiwan": "Taiwan", "madagaskar": "Madagaskar",
    "amerikanske jomfruøer": "Amerikanske Jomfruøer",
    "saint croix": "Amerikanske Jomfruøer", "st. croix": "Amerikanske Jomfruøer",
    "britiske jomfruøer": "Britiske Jomfruøer",
    "dominikansk": "Dominikansk", "dominikanske republik": "Dominikansk",
    "santo domingo": "Dominikansk",
    "dansk": "Dansk", "danmark": "Dansk",
    "england": "England", "storbritannien": "Storbritannien",
    "skotland": "Skotland", "holland": "Holland", "tyskland": "Tyskland",
    "flensburg": "Tyskland", "spanien": "Spanien", "frankrig": "Frankrig",
    "usa": "USA", "oregon": "USA",
}

# Lande der typisk er aftapper/finish, ikke oprindelse, naar de staar sammen
# med et andet land ("Guyana / England", "Danmark/Jamaica", "Martinique / Frankrig")
BOTTLER = {"England", "Storbritannien", "Skotland", "Holland", "Tyskland",
           "Dansk", "Spanien", "Frankrig", "USA"}

REGIONS = {
    "caribien": "Caribien", "vestindien": "Caribien",
    "franske antiller": "Caribien", "antillske øer": "Caribien",
    "mellemamerika": "Mellemamerika", "centralamerika": "Mellemamerika",
}

MULTI = {"hele verden": "Flere lande"}

_L = r"(?<![a-zæøåé])"
_R = r"(?![a-zæøåé])"


def _find(table, text):
    hits = []
    for alias, canon in table.items():
        m = re.search(_L + re.escape(alias) + _R, text)
        if m:
            hits.append((m.start(), canon))
    seen, out = set(), []
    for _, canon in sorted(hits):
        if canon not in seen:
            seen.add(canon)
            out.append(canon)
    return out


def normalize_country(raw):
    if not raw:
        return None
    t = str(raw).strip().lower()
    if not t:
        return None

    for alias, canon in MULTI.items():
        if alias in t:
            return canon

    found = _find(COUNTRIES, t)
    origin = [c for c in found if c not in BOTTLER]

    if len(origin) == 1:
        return origin[0]
    if len(origin) >= 2:
        return "Flere lande"

    regions = _find(REGIONS, t)
    if regions:
        return regions[0]
    if len(found) == 1:
        return found[0]
    if len(found) >= 2:
        return "Flere lande"
    return None


def normalize_items(items, verbose=True):
    """Normalisér 'country' paa alle items. Returnerer ukendte raa-vaerdier."""
    unknown = {}
    for it in items:
        raw = it.get("country")
        if not raw:
            continue
        ny = normalize_country(raw)
        if ny is None:
            unknown[raw] = unknown.get(raw, 0) + 1
        it["country"] = ny
    if verbose and unknown:
        print(f"   ⚠️  {len(unknown)} ukendte landeværdier sat til tom (udvid country_norm.py):")
        for raw, n in sorted(unknown.items(), key=lambda x: -x[1])[:15]:
            print(f"      {n:3d}  {raw[:70]}")
    return unknown


if __name__ == "__main__":
    tests = {
        "Jamaica": "Jamaica", "Den Dominikanske Republik": "Dominikansk",
        "Dominikanske Republik": "Dominikansk", "Dominikansk": "Dominikansk",
        "Santo Domingo Den Dominikanske Republik": "Dominikansk",
        "Danmark": "Dansk", "Kolding, Danmark": "Dansk", "Dansk": "Dansk",
        "Trinidad og Tobago": "Trinidad", "Trinidad & Tobago": "Trinidad",
        "St. Lucia": "Saint Lucia", "St Lucia": "Saint Lucia",
        "La Réunion": "Réunion", "Reunion": "Réunion", "Réunion, Frankrig": "Réunion",
        "Saint Catherine, Jamaica": "Jamaica",
        "Cartagena de Indias, Colombia": "Colombia",
        "Bukidnon, Mindanao, Filippinerne": "Filippinerne",
        "Bahamas (Nassau)": "Bahamas", "Skotland (Islay)": "Skotland",
        "Oregon USA": "USA", "Martinique / Frankrig": "Martinique",
        "Guyana / England": "Guyana", "Jamaica / England": "Jamaica",
        "Caribien / England": "Caribien", "Danmark/Jamaica": "Jamaica",
        "Spanien & Panama": "Panama", "El Salvador og USA": "El Salvador",
        "Barbados og Guyana": "Flere lande", "Guatemala og Belize": "Flere lande",
        "Barbados/Trinidad/Jamaica/Guyana": "Flere lande",
        "Centralamerika (Nicaragua, Guatemala og Panama)": "Flere lande",
        "Caribien & Nicaragua": "Nicaragua", "Barbados / Caribien": "Barbados",
        "Saint Croix, Caribien": "Amerikanske Jomfruøer",
        "Vestindien (importeret rom), aftappet i Flensburg, Tyskland": "Caribien",
        "Franske Antiller": "Caribien", "Mellemamerika": "Mellemamerika",
        "Centralamerika": "Mellemamerika", "Rom fra hele verden": "Flere lande",
        "Produceret og tappet i Danmark, 2022 Alc. styrke: 40 % 50 cl. Andet: kun 700 flasker": "Dansk",
        "Flensburg, Tyskland": "Tyskland", "Caribien": "Caribien",
        "Norden": None, "Det Sydlige Stillehav": None, "": None, None: None,
    }
    fejl = 0
    for ind, ventet in tests.items():
        fik = normalize_country(ind)
        if fik != ventet:
            fejl += 1
            print(f"   FEJL {ind!r:60} -> {fik!r} (ventet {ventet!r})")
    print(f"{len(tests) - fejl}/{len(tests)} OK")

"""
rom_matching.py — Hård gate matching for rom på tværs af butikker.

Strategien (alle gates skal passere for at to rom matches):
1. Brand-gate: Begge skal have samme brand (eller begge mangle)
2. Alder-gate: Begge skal have samme alder-markering (eller begge mangle)
3. Volume-gate: Max 2cl forskel
4. ABV-gate: Max 1% forskel
5. Edition-keyword check: Begge skal have samme edition-keywords
6. Fuzzy score: Mindst 88% navn-overlap (lavere hvis alle gates passerer)
"""
import re
import unicodedata
from html import unescape


# Alle apostrof-varianter der skal fjernes helt (ikke blive til mellemrum)
_APOSTROPHES = dict.fromkeys(
    map(ord, "\u2019\u2018\u02bc\u00b4`'"), None
)

# Ord der ikke identificerer produktet.
# Aldersenheder er med, fordi alder tjekkes af age_gate — de skal ikke
# skabe kunstig forskel mellem "12 y.o." og "12 år".
_STOP_WORDS = {
    "rom", "rum", "spiritus", "the", "de", "la", "el", "ron", "rhum",
    "and", "og", "med", "fra",
    "\u00e5r", "\u00e5rs", "ars", "aar", "years", "year", "yo",
    "ans", "anos", "a\u00f1os", "old", "aged",
}


def clean_name(name):
    """Forbered navn til matching."""
    if not name:
        return ""

    name = unescape(name).lower()
    name = re.sub(r"<[^>]+>", " ", name)

    # Fjern apostroffer HELT, saa "doorly's" -> "doorlys" -> token "doorlys"
    name = name.translate(_APOSTROPHES)

    # Strip accenter: "barcel\u00f3" -> "barcelo"
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if unicodedata.category(c) != "Mn")

    # Fjern volumen og ABV (tjekkes af egne gates)
    name = re.sub(r"\d+(?:[.,]\d+)?\s*(ml|cl|l)\b", " ", name)
    name = re.sub(r"\d+(?:[.,]\d+)?\s*%", " ", name)

    # Separatorer -> mellemrum
    name = re.sub(r"[,\-\u2014\.()/\"&+]", " ", name)

    words = [w for w in name.split() if w not in _STOP_WORDS and len(w) > 1]
    return re.sub(r"\s+", " ", " ".join(words)).strip()


def fuzzy_overlap_score(a, b):
    """
    Beregn ord-overlap score mellem to normaliserede navne.
    Returnerer 0-100.
    """
    if not a or not b:
        return 0
    
    words_a = set(a.split())
    words_b = set(b.split())
    
    if not words_a or not words_b:
        return 0
    
    # Jaccard-lignende score med vægt på matches
    overlap = words_a & words_b
    union = words_a | words_b
    
    # Vægt: matches er værd mere end ikke-matches
    score = (len(overlap) / len(union)) * 100
    
    # Bonus hvis kortere af de to har meget overlap
    shorter = min(len(words_a), len(words_b))
    if shorter > 0:
        coverage = len(overlap) / shorter * 100
        score = (score + coverage) / 2
    
    return score


# ────────────────────────────────────────────────────────────
# HARD GATES
# ────────────────────────────────────────────────────────────

def brand_gate(a, b):
    """
    Brand skal vaere ens hvis begge har det.

    Returns (passes, reason, neutral)
    """
    ba = (a.get("brand") or "").lower().strip()
    bb = (b.get("brand") or "").lower().strip()

    if not ba and not bb:
        return True, None, True
    if not ba or not bb:
        return True, None, True

    # Normaliser apostroffer og accenter foer sammenligning, saa
    # "Gosling's" og "Goslings" er samme brand
    def _n(s):
        s = s.translate(_APOSTROPHES)
        s = unicodedata.normalize("NFKD", s)
        return "".join(c for c in s if unicodedata.category(c) != "Mn")

    na, nb = _n(ba), _n(bb)
    if na == nb or na in nb or nb in na:
        return True, None, False

    return False, f"Brand mismatch: '{a.get('brand')}' vs '{b.get('brand')}'", False


def age_gate(a, b):
    """
    Alder skal vaere ens NAAR begge har den.

    Mangler den paa én side, er det ikke en uenighed — det er manglende
    oplysning. Returnerer neutral, og try_match kompenserer ved at kraeve
    hoejere navne-lighed.

    Returns (passes, reason, neutral)
    """
    aa, ab = a.get("age"), b.get("age")

    if aa is None and ab is None:
        return True, None, False
    if aa is None or ab is None:
        return True, None, True          # neutral, ikke afvisning

    if str(aa).lower().strip() == str(ab).lower().strip():
        return True, None, False

    return False, f"Alder mismatch: '{aa}' vs '{ab}'", False


# Standardflaske. Mangler volumen paa den ene side, tillades match kun hvis
# den kendte side er en standardflaske — saa risikoen for at en 35 cl
# miniature matcher en helflaske er lille.
_STANDARD_VOLUMES = {70.0, 75.0}

# Stoerste tillade prisforhold naar volumen ikke kunne verificeres paa
# begge sider. En aegte prisforskel mellem butikker er sjaeldent over 2x;
# en 5x forskel betyder naesten altid forskellig flaskestoerrelse.
_MAX_PRICE_RATIO = 3.0


def volume_gate(a, b, max_diff=2):
    """
    Volumen skal vaere ~ens. Max 2 cl forskel.

    Returns (passes, reason, neutral)
    """
    va, vb = a.get("volume_cl"), b.get("volume_cl")

    if va is None and vb is None:
        return True, None, True          # ingen af dem kendes — neutral

    if va is None or vb is None:
        known = va if va is not None else vb
        if float(known) not in _STANDARD_VOLUMES:
            return (False,
                    f"Volume: {known}cl er ikke standard, og den anden side "
                    f"mangler volumen", False)

        # Prisvaern: stor prisforskel indikerer forskellig stoerrelse
        pa, pb = a.get("price"), b.get("price")
        try:
            if pa and pb:
                lo, hi = sorted((float(pa), float(pb)))
                if lo > 0 and hi / lo > _MAX_PRICE_RATIO:
                    return (False,
                            f"Volume ukendt og prisforhold {hi/lo:.1f}x "
                            f"for stort", False)
        except (TypeError, ValueError):
            pass

        return True, None, True          # neutral

    if abs(va - vb) > max_diff:
        return False, f"Volume mismatch: {va}cl vs {vb}cl", False

    return True, None, False


def abv_gate(a, b, max_diff=1.0):
    """
    ABV skal vaere ~ens naar begge har den.

    Returns (passes, reason, neutral)
    """
    aa, ab = a.get("abv"), b.get("abv")

    if aa is None and ab is None:
        return True, None, True
    if aa is None or ab is None:
        return True, None, True

    if abs(aa - ab) > max_diff:
        return False, f"ABV mismatch: {aa}% vs {ab}%", False

    return True, None, False


def edition_gate(a, b):
    """
    Edition-keywords skal vaere ens.

    Returns (passes, reason, neutral)
    """
    ea = a.get("editions") or set()
    eb = b.get("editions") or set()
    if isinstance(ea, list):
        ea = set(ea)
    if isinstance(eb, list):
        eb = set(eb)

    if not ea and not eb:
        return True, None, False

    if not ea or not eb:
        diff = ea or eb
        return False, f"Edition mismatch: '{list(diff)}' kun paa én side", False

    if ea == eb:
        return True, None, False

    overlap = ea & eb
    if len(overlap) >= len(ea) / 2 and len(overlap) >= len(eb) / 2:
        return True, None, False

    return False, f"Edition mismatch: {list(ea)} vs {list(eb)}", False


# ────────────────────────────────────────────────────────────
# HOVED MATCHING FUNKTION
# ────────────────────────────────────────────────────────────

def try_match(a, b, fuzzy_threshold=88):
    """
    Tjek om to rom-produkter er samme produkt.

    Gates kan nu svare "neutral": feltet manglede paa én side, saa gaten
    kunne hverken bekraefte eller afvise. For hvert neutralt gate haeves
    fuzzy-taersklen, saa navnet skal baere mere af beviset.
    """
    result = {
        "match": False,
        "score": 0,
        "reason": None,
        "gates_passed": [],
        "fuzzy_score": 0,
        "neutral_gates": [],
    }

    if a is b:
        result["reason"] = "Samme objekt"
        return result

    if a.get("shop_name") == b.get("shop_name"):
        result["reason"] = "Samme butik"
        return result

    gates = [
        ("brand", brand_gate),
        ("age", age_gate),
        ("volume", volume_gate),
        ("abv", abv_gate),
        ("edition", edition_gate),
    ]

    neutral_count = 0
    for gate_name, gate_func in gates:
        out = gate_func(a, b)
        # Bagudkompatibel: gates kan returnere 2- eller 3-tuple
        if len(out) == 3:
            passes, reason, neutral = out
        else:
            passes, reason = out
            neutral = False

        if not passes:
            result["reason"] = f"\u274c {gate_name}-gate: {reason}"
            return result

        if neutral:
            neutral_count += 1
            result["neutral_gates"].append(gate_name)
        else:
            result["gates_passed"].append(gate_name)

    # Fuzzy navne-sammenligning
    name_a = clean_name(a.get("name", ""))
    name_b = clean_name(b.get("name", ""))
    fuzzy_score = fuzzy_overlap_score(name_a, name_b)
    result["fuzzy_score"] = fuzzy_score
    result["neutral_count"] = neutral_count

    # Taerskel afhaenger ALENE af hvor mange gates der bekraeftede noget.
    # Faerre bekraeftelser -> navnet skal baere mere af beviset.
    # (Tidligere blev manglende data straffet to gange: baade via
    #  has_full_data og via neutral_count.)
    threshold = min(90, 75 + 5 * neutral_count)

    if fuzzy_score >= threshold:
        result["match"] = True
        result["score"] = fuzzy_score
        return result

    result["reason"] = (
        f"\u274c Fuzzy score for lav: {fuzzy_score:.0f}% < {threshold}%"
        + (f" ({neutral_count} neutrale gates)" if neutral_count else "")
    )
    return result


# ────────────────────────────────────────────────────────────
# GROUP MATCHING
# ────────────────────────────────────────────────────────────

def group_products(products, verbose=True):
    """
    Tag en liste af produkter og gruppér dem efter matching.
    Returnerer (groups, stats) hvor groups er liste af lister.
    """
    groups = []
    successful_matches = []
    rejected_matches = []
    
    for product in products:
        matched_group = None
        best_score = 0
        
        for group in groups:
            # Tjek om dette produkt matcher gruppen
            # Vi tjekker mod første medlem af gruppen
            primary = group[0]
            
            # Skip hvis vi allerede har dette produkt i gruppen (samme butik)
            shops_in_group = set(p.get("shop_name") for p in group)
            if product.get("shop_name") in shops_in_group:
                # Tjek om det måske er en duplikat (samme navn)
                if any(p.get("name") == product.get("name") for p in group):
                    continue
                # Ellers er det en variant fra samme butik - skip matching
                continue
            
            match_result = try_match(primary, product)
            
            if match_result["match"]:
                if match_result["score"] > best_score:
                    matched_group = group
                    best_score = match_result["score"]
                    successful_matches.append({
                        "a": primary.get("name"),
                        "shop_a": primary.get("shop_name"),
                        "b": product.get("name"),
                        "shop_b": product.get("shop_name"),
                        "score": match_result["score"],
                        "gates": match_result["gates_passed"],
                    })
            elif match_result["reason"] and "Samme" not in (match_result["reason"] or ""):
                # Log afvist match kun hvis det var "tæt på"
                # (samme brand fx)
                if "Brand mismatch" not in match_result["reason"]:
                    rejected_matches.append({
                        "a": primary.get("name"),
                        "shop_a": primary.get("shop_name"),
                        "b": product.get("name"),
                        "shop_b": product.get("shop_name"),
                        "reason": match_result["reason"],
                    })
        
        if matched_group is not None:
            matched_group.append(product)
        else:
            groups.append([product])
    
    if verbose:
        print(f"\n{'='*70}")
        print(f"📊 MATCHING RESULTAT")
        print(f"{'='*70}")
        print(f"   Total produkter: {len(products)}")
        print(f"   Total grupper:   {len(groups)}")
        print(f"   Multi-shop grupper: {sum(1 for g in groups if len(set(p.get('shop_name') for p in g)) > 1)}")
        print(f"   Vellykkede matches: {len(successful_matches)}")
        print(f"   Afviste matches (samme brand): {len(rejected_matches)}")
        
        if successful_matches:
            print(f"\n✅ VELLYKKEDE MATCHES (top 10):")
            for m in successful_matches[:10]:
                print(f"   • '{m['a'][:50]}' ({m['shop_a']})")
                print(f"     ≈ '{m['b'][:50]}' ({m['shop_b']})")
                print(f"     Score: {m['score']:.0f}% | Gates: {', '.join(m['gates'])}")
        
        if rejected_matches:
            print(f"\n❌ AFVISTE MATCHES MED SAMME BRAND (top 10):")
            for m in rejected_matches[:10]:
                print(f"   • '{m['a'][:50]}' ({m['shop_a']})")
                print(f"     vs '{m['b'][:50]}' ({m['shop_b']})")
                print(f"     {m['reason']}")
    
    stats = {
        "total_products": len(products),
        "total_groups": len(groups),
        "multi_shop_groups": sum(1 for g in groups if len(set(p.get("shop_name") for p in g)) > 1),
        "successful_matches": successful_matches,
        "rejected_matches": rejected_matches,
    }
    
    return groups, stats


# ────────────────────────────────────────────────────────────
# TEST
# ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Test 1: Skal matche - samme Zacapa 23
    a = {
        "name": "Ron Zacapa Centenario 23 SISTEMA SOLERA Gran Reserva",
        "brand": "Zacapa",
        "age": "23 år",
        "volume_cl": 70,
        "abv": 40,
        "editions": set(),
        "shop_name": "Spitus",
    }
    b = {
        "name": "Ron Zacapa Centenario 23 års 40%",
        "brand": "Zacapa",
        "age": "23 år",
        "volume_cl": 70,
        "abv": 40,
        "editions": set(),
        "shop_name": "Kokkens Vinhus",
    }
    print("\nTest 1 (skal matche): Zacapa 23 mod Zacapa 23")
    print(try_match(a, b))
    
    # Test 2: Skal IKKE matche - Zacapa 23 vs Edición Negra
    c = {
        "name": "Ron Zacapa Centenario EDICIÓN NEGRA Sistema Solera",
        "brand": "Zacapa",
        "age": None,  # Edición Negra har ikke alder
        "volume_cl": 70,
        "abv": 43,
        "editions": {"edición negra"},
        "shop_name": "Spitus",
    }
    print("\nTest 2 (skal IKKE matche): Zacapa 23 mod Edición Negra")
    print(try_match(a, c))
    
    # Test 3: Skal IKKE matche - Zacapa 23 vs XO
    d = {
        "name": "Ron Zacapa Centenario XO",
        "brand": "Zacapa",
        "age": "XO",
        "volume_cl": 70,
        "abv": 40,
        "editions": set(),
        "shop_name": "Spitus",
    }
    print("\nTest 3 (skal IKKE matche): Zacapa 23 mod Zacapa XO")
    print(try_match(a, d))
    
    # Test 4: Skal IKKE matche - 70cl vs 5cl miniature
    e = {
        "name": "Zacapa 23 års 5cl miniature",
        "brand": "Zacapa",
        "age": "23 år",
        "volume_cl": 5,
        "abv": 40,
        "editions": set(),
        "shop_name": "Kokkens Vinhus",
    }
    print("\nTest 4 (skal IKKE matche): Zacapa 23 70cl mod 5cl")
    print(try_match(a, e))
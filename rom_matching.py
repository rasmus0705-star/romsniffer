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
from html import unescape


def clean_name(name):
    """Forbered navn til matching"""
    if not name:
        return ""
    name = name.lower()
    name = unescape(name)
    # Fjern HTML
    name = re.sub(r"<[^>]+>", " ", name)
    # Fjern volume/ABV (allerede tjekket separat)
    name = re.sub(r"\d+(?:[.,]\d+)?\s*(ml|cl|l)\b", " ", name)
    name = re.sub(r"\d+(?:[.,]\d+)?\s*%", " ", name)
    # Behold tal (årgang/alder) som standalone "ord"
    # Fjern separatorer
    name = re.sub(r"[,\-—\.()/\"'&]", " ", name)
    # Fjern stop-words
    stop_words = ["rom", "rum", "spiritus", "the", "de", "la", "el", "ron", "rhum"]
    words = name.split()
    words = [w for w in words if w not in stop_words and len(w) > 1]
    name = " ".join(words)
    # Saml whitespace
    name = re.sub(r"\s+", " ", name).strip()
    return name


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
    Brand skal være ens hvis begge har det.
    Returns (passes, reason)
    """
    ba = (a.get("brand") or "").lower().strip()
    bb = (b.get("brand") or "").lower().strip()
    
    if not ba and not bb:
        return True, None  # Begge mangler — accepter, lad andre gates afgøre
    if not ba or not bb:
        return True, None  # Én mangler — accepter, lad andre gates afgøre
    
    # Strict equality
    if ba == bb:
        return True, None
    
    # Tillad delvis match: "Ron Zacapa" matches "Zacapa"
    if ba in bb or bb in ba:
        return True, None
    
    return False, f"Brand mismatch: '{a.get('brand')}' vs '{b.get('brand')}'"


def age_gate(a, b):
    """
    Alder skal være helt ens.
    'XO' ≠ '12 år' ≠ 'Solera' ≠ None
    """
    aa = a.get("age")
    ab = b.get("age")
    
    if aa is None and ab is None:
        return True, None
    
    if aa is None or ab is None:
        return False, f"Alder mismatch: '{aa}' vs '{ab}' (én mangler)"
    
    # Normaliser
    aa_clean = str(aa).lower().strip()
    ab_clean = str(ab).lower().strip()
    
    if aa_clean == ab_clean:
        return True, None
    
    return False, f"Alder mismatch: '{aa}' vs '{ab}'"


def volume_gate(a, b, max_diff=2):
    """Volume skal være ~ens. Max 2cl forskel."""
    va = a.get("volume_cl")
    vb = b.get("volume_cl")
    
    if va is None and vb is None:
        return True, None
    if va is None or vb is None:
        return True, None  # Acceptér, men noter
    
    if abs(va - vb) > max_diff:
        return False, f"Volume mismatch: {va}cl vs {vb}cl"
    
    return True, None


def abv_gate(a, b, max_diff=1.0):
    """ABV skal være ~ens. Max 1% forskel (din ønske)."""
    abva = a.get("abv")
    abvb = b.get("abv")
    
    if abva is None and abvb is None:
        return True, None
    if abva is None or abvb is None:
        return True, None  # Acceptér
    
    if abs(abva - abvb) > max_diff:
        return False, f"ABV mismatch: {abva}% vs {abvb}%"
    
    return True, None


def edition_gate(a, b):
    """
    Edition keywords skal være ens.
    Hvis A har 'edición negra' og B ikke, så er det IKKE samme produkt.
    """
    ea = a.get("editions") or set()
    eb = b.get("editions") or set()
    
    # Konverter til set hvis det er liste
    if isinstance(ea, list):
        ea = set(ea)
    if isinstance(eb, list):
        eb = set(eb)
    
    # Hvis begge er tomme: ok
    if not ea and not eb:
        return True, None
    
    # Hvis kun én har editions: NOT match
    if not ea or not eb:
        diff = ea or eb
        return False, f"Edition mismatch: '{list(diff)}' kun på én side"
    
    # Begge har editions: skal være ens (eller mindst overlap)
    if ea == eb:
        return True, None
    
    # Tillad delvis overlap (mindst halvdelen skal være ens)
    overlap = ea & eb
    if len(overlap) >= len(ea) / 2 and len(overlap) >= len(eb) / 2:
        return True, None
    
    return False, f"Edition mismatch: {list(ea)} vs {list(eb)}"


# ────────────────────────────────────────────────────────────
# HOVED MATCHING FUNKTION
# ────────────────────────────────────────────────────────────

def try_match(a, b, fuzzy_threshold=88):
    """
    Tjek om to rom-produkter er samme produkt.
    
    Returns dict:
    {
        "match": bool,
        "score": float,
        "reason": str (hvis ikke match) eller None,
        "gates_passed": list,
        "fuzzy_score": float,
    }
    """
    result = {
        "match": False,
        "score": 0,
        "reason": None,
        "gates_passed": [],
        "fuzzy_score": 0,
    }
    
    # Skal ikke matche med sig selv
    if a is b:
        result["reason"] = "Samme objekt"
        return result
    
    # Skal være forskellige butikker (vi vil have pris-sammenligning)
    if a.get("shop_name") == b.get("shop_name"):
        # Tillad samme butik hvis ID er forskelligt (måske dupletter)
        # men det er ikke pris-sammenligning
        result["reason"] = "Samme butik"
        return result
    
    # Kør gates i rækkefølge - stop ved første fejl
    gates = [
        ("brand", brand_gate),
        ("age", age_gate),
        ("volume", volume_gate),
        ("abv", abv_gate),
        ("edition", edition_gate),
    ]
    
    for gate_name, gate_func in gates:
        passes, reason = gate_func(a, b)
        if not passes:
            result["reason"] = f"❌ {gate_name}-gate: {reason}"
            return result
        result["gates_passed"].append(gate_name)
    
    # Alle gates passerede - tjek nu fuzzy navn
    name_a = clean_name(a.get("name", ""))
    name_b = clean_name(b.get("name", ""))
    
    fuzzy_score = fuzzy_overlap_score(name_a, name_b)
    result["fuzzy_score"] = fuzzy_score
    
    # Dynamisk threshold:
    # - Hvis brand+alder+volume+abv alle matcher: 80% er nok
    # - Hvis nogle data manglede: kræv 88%
    has_full_data = all([
        a.get("brand"), b.get("brand"),
        a.get("age") is not None or (a.get("age") is None and b.get("age") is None),
        a.get("volume_cl"), b.get("volume_cl"),
    ])
    
    threshold = 75 if has_full_data else fuzzy_threshold
    
    if fuzzy_score >= threshold:
        result["match"] = True
        result["score"] = fuzzy_score
        return result
    
    result["reason"] = f"❌ Fuzzy score for lav: {fuzzy_score:.0f}% < {threshold}%"
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
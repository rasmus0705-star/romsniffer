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
    name = re.sub(r"\bcasks\b", "cask", name)

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

# Samme producent, forskelligt navn i butikkernes data (mærke mod destilleri / importør). Bruges kun til at
# IKKE afvise et match på brand; selve navnet skal stadig ligne.
_BRAND_FAMILIES = [
    ("old st. croix", "st. croix", "a.h. riise", "ah riise", "riise"),
    ("foursquare", "real mccoy"),
    ("hampden", "navy island"),
]


_WORD_AGES = {"xo", "solera", "reserva"}


def _word_in_name(word, other):
    return re.search(r"\b%s\b" % re.escape(word), (other.get("name") or "").lower()) is not None


def _brand_family(s):
    for i, family in enumerate(_BRAND_FAMILIES):
        if any(alias in s for alias in family):
            return i
    return None


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
    fa, fb = _brand_family(na), _brand_family(nb)
    if fa is not None and fa == fb:
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

    wa, wb = str(aa).lower().strip(), str(ab).lower().strip()
    if wa in _WORD_AGES and wb not in _WORD_AGES and _word_in_name(wa, b):
        return True, None, False
    if wb in _WORD_AGES and wa not in _WORD_AGES and _word_in_name(wb, a):
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
    ea = set(a.get("editions") or ()) - _SOFT_EDITIONS
    eb = set(b.get("editions") or ()) - _SOFT_EDITIONS

    if not ea and not eb:
        return True, None, False

    if not ea or not eb:
        diff = ea or eb
        if diff <= _FINISH_KEYWORDS and _confirmed_same(a, b):
            return True, None, True
        return False, f"Edition mismatch: '{list(diff)}' kun paa én side", False

    if ea == eb:
        return True, None, False

    overlap = ea & eb
    if len(overlap) >= len(ea) / 2 and len(overlap) >= len(eb) / 2:
        return True, None, False

    return False, f"Edition mismatch: {list(ea)} vs {list(eb)}", False


# ────────────────────────────────────────────────────────────


def price_gate(a, b, max_pct=0.30):
    """Afvis hvis prisforskellen er over 30%."""
    pa, pb = a.get("price"), b.get("price")
    if pa is None or pb is None:
        return True, None, True
    try:
        pa, pb = float(pa), float(pb)
    except (TypeError, ValueError):
        return True, None, True
    if pa <= 0 or pb <= 0:
        return True, None, True
    lo, hi = sorted((pa, pb))
    pct = (hi - lo) / lo
    if pct > max_pct:
        return (False, f"Prisforskel for stor: {lo:.0f} vs {hi:.0f} kr ({pct:.0%} > {max_pct:.0%})", False)
    return True, None, False

# Samme produkt kan koste meget forskelligt fra butik til butik. Den almindelige prisgrænse (30 %) opgives
# derfor, når navnet er (næsten) identisk, OG begge volumener er kendte og ens. Så er en stor prisforskel
# langt mere sandsynligt en butiks-forskel end et andet produkt.
_RELAXED_PRICE_RATIO = 1.75


def _price_ok_for_identical(a, b):
    """Lempet prisgrænse (op til 1,75x) når navnet er næsten identisk OG størrelsen er sikker: begge volumener er
    kendte og ens, eller den ene mangler og den anden er en standardflaske, og begge ABV er kendte og ens."""
    va, vb = a.get("volume_cl"), b.get("volume_cl")
    if va is not None and vb is not None:
        if abs(float(va) - float(vb)) > 2:
            return False
    else:
        known = va if va is not None else vb
        if known is None or float(known) not in _STANDARD_VOLUMES:
            return False
        aa, ab = a.get("abv"), b.get("abv")
        if aa is None or ab is None or abs(aa - ab) > 0.5:
            return False
    if fuzzy_overlap_score(clean_name(a.get("name", "")), clean_name(b.get("name", ""))) < 95:
        return False
    try:
        pa, pb = float(a.get("price")), float(b.get("price"))
    except (TypeError, ValueError):
        return False
    if pa <= 0 or pb <= 0:
        return False
    return max(pa, pb) / min(pa, pb) <= _RELAXED_PRICE_RATIO


# Ord der gør et navn for generisk til at stole på alene (kalendere, smagssæt osv.)
_GENERIC_TOKENS = {"julekalender", "kalender", "adventskalender", "smagesaet", "smagesæt", "sampak",
                   "gaveaeske", "gaveæske", "miniature", "mini"}


def _same_product_by_name(a, b, max_price_ratio=1.5):
    """
    Navnet er (næsten) identisk, og volumen og pris modsiger det ikke: så er en uenighed om BRAND eller ALDER
    næsten altid en fejl i udtrækket ('20th Anniversary' læst som 20 år, 'Old St. Croix' mod 'A.H. Riise',
    destilleri mod mærke). ABV, volumen og udgave tæller stadig som hård uenighed.
    """
    na, nb = clean_name(a.get("name", "")), clean_name(b.get("name", ""))
    if fuzzy_overlap_score(na, nb) < 97:
        return False
    toks = set(na.split())
    if len(toks) < 2 or toks & _GENERIC_TOKENS:
        return False
    if not volume_gate(a, b)[0]:
        return False
    try:
        pa, pb = float(a.get("price")), float(b.get("price"))
    except (TypeError, ValueError):
        return False
    if pa <= 0 or pb <= 0 or max(pa, pb) / min(pa, pb) > max_price_ratio:
        return False
    return True


# Udgave-ord der ikke adskiller produkter ("limited edition" tilføjes frit af butikkerne), og finish-typer,
# hvor en butik kan udelade ordet, men alt andet (volumen, ABV, alder, pris) er identisk.
_SOFT_EDITIONS = {"limited edition"}
_FINISH_KEYWORDS = {"port cask", "sherry cask", "cognac cask", "wine cask"}


def _confirmed_same(a, b):
    """Fire uafhængige bekræftelser: volumen, ABV og alder er kendte og ens, og prisen er (næsten) ens."""
    va, vb = a.get("volume_cl"), b.get("volume_cl")
    aa, ab = a.get("abv"), b.get("abv")
    ga, gb = a.get("age"), b.get("age")
    if va is None or vb is None or abs(float(va) - float(vb)) > 2:
        return False
    if aa is None or ab is None or abs(aa - ab) > 0.5:
        return False
    if ga is None or gb is None or str(ga).lower().strip() != str(gb).lower().strip():
        return False
    try:
        pa, pb = float(a.get("price")), float(b.get("price"))
    except (TypeError, ValueError):
        return False
    return pa > 0 and pb > 0 and max(pa, pb) / min(pa, pb) <= 1.03


_HARD_GATES = ("brand", "age", "volume", "abv", "edition", "manuel")


def _spread_ok(group, product, loose=1.45):
    """Prisspredningen i en gruppe må ikke glide trinvist: uden kendt, ens volumen højst 1,45x mellem dyreste og
    billigste; med kendt, ens volumen højst 1,75x (samme grænse som den lempede prisregel)."""
    members = list(group) + [product]
    try:
        prices = [float(p["price"]) for p in members if p.get("price")]
    except (TypeError, ValueError):
        return True
    if len(prices) < 2 or min(prices) <= 0:
        return True
    spread = max(prices) / min(prices)
    vols = [p.get("volume_cl") for p in members]
    if all(v is not None for v in vols) and max(vols) - min(vols) <= 2:
        return spread <= _RELAXED_PRICE_RATIO
    return spread <= loose


# Facit fra fejlliste.xlsx: {(url_a, url_b): "sammen" | "adskilt"}. Sættes af build_rom_data via set_manual_pairs().
_MANUAL_PAIRS = {}


def set_manual_pairs(pairs):
    _MANUAL_PAIRS.clear()
    _MANUAL_PAIRS.update(pairs or {})


def _manual_decision(a, b):
    ua, ub = a.get("url"), b.get("url")
    if not ua or not ub:
        return None
    return _MANUAL_PAIRS.get(tuple(sorted((ua, ub))))


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

    manual = _manual_decision(a, b)
    if manual == "adskilt":
        result["reason"] = "\u274c manuel-gate: adskilt i fejllisten"
        return result
    if manual == "sammen":
        result.update({"match": True, "score": 100, "fuzzy_score": 100, "manuel": True})
        result["gates_passed"].append("manuel")
        return result

    gates = [
        ("brand", brand_gate),
        ("age", age_gate),
        ("volume", volume_gate),
        ("abv", abv_gate),
        ("edition", edition_gate),
        ("price", price_gate),
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
            if gate_name == "price" and _price_ok_for_identical(a, b):
                result["gates_passed"].append("price(lempet)")
                continue
            if gate_name in ("brand", "age") and _same_product_by_name(a, b):
                neutral_count += 1
                result["neutral_gates"].append(gate_name + "(navn)")
                continue
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

        if product.get("_solo"):           # sæt/kalendere: aldrig slået sammen med andre
            groups.append([product])
            continue
        
        for group in groups:
            # Én butik pr. gruppe
            if group[0].get("_solo"):
                continue
            shops_in_group = set(p.get("shop_name") for p in group)
            if product.get("shop_name") in shops_in_group:
                continue

            # Sammenlign med ALLE medlemmer, ikke kun det første: en butik kan mangle et felt, som en anden
            # butik i gruppen har. Hård uenighed med ét medlem (brand/alder/volumen/ABV/udgave) blokerer dog
            # hele gruppen, så to forskellige flasker ikke samles via en mellemmand.
            best_here = None
            best_member = None
            blocked = None
            for member in group:
                res = try_match(member, product)
                if res["match"]:
                    if best_here is None or res["score"] > best_here["score"]:
                        best_here, best_member = res, member
                else:
                    reason = res.get("reason") or ""
                    if any(f"{g}-gate" in reason for g in _HARD_GATES):
                        blocked = (member, res)
                        break

            if best_here is not None and blocked is None and not best_here.get("manuel") and not _spread_ok(group, product):
                best_here = None          # ville gøre prisspredningen i gruppen for stor

            if blocked is not None:
                member, res = blocked
                if "Brand mismatch" not in (res["reason"] or ""):
                    rejected_matches.append({
                        "a": member.get("name"), "shop_a": member.get("shop_name"),
                        "b": product.get("name"), "shop_b": product.get("shop_name"),
                        "reason": res["reason"],
                    })
                continue

            if best_here is not None and best_here["score"] > best_score:
                matched_group = group
                best_score = best_here["score"]
                successful_matches.append({
                    "a": best_member.get("name"), "shop_a": best_member.get("shop_name"),
                    "b": product.get("name"), "shop_b": product.get("shop_name"),
                    "score": best_here["score"], "gates": best_here["gates_passed"],
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
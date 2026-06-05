"""
Diagnose-script: viser ALLE felter for nogle rom-produkter,
så vi kan se hvor ABV, volume, alder osv. ligger gemt.
"""
import requests
import json

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

# Kig på en håndfuld Zacapa-produkter fra begge butikker
SHOPS = [
    {
        "name": "Kokkens Vinhus",
        "url": "https://www.kokkensvinhus.dk/wp-json/wc/store/v1/products?search=zacapa&per_page=5",
    },
    {
        "name": "Spitus",
        "url": "https://spitus.dk/wp-json/wc/store/v1/products?search=zacapa&per_page=5",
    },
]


def show_product_fields(product, shop_name):
    """Vis alle interessante felter for et produkt"""
    print(f"\n{'='*70}")
    print(f"🏪 {shop_name}")
    print(f"📦 {product.get('name', 'UDEN NAVN')}")
    print(f"{'='*70}")
    
    # Grundlæggende felter
    interesting_fields = [
        "id", "slug", "permalink", "sku",
        "short_description", "description",
    ]
    
    for field in interesting_fields:
        val = product.get(field)
        if val:
            # Trim lange tekster
            if isinstance(val, str) and len(val) > 200:
                val_short = val[:200].replace("\n", " ") + "..."
                print(f"\n📝 {field}: {val_short}")
            else:
                print(f"\n📝 {field}: {val}")
        else:
            print(f"\n📝 {field}: (tom)")
    
    # Attributes - meget vigtig!
    attrs = product.get("attributes", [])
    print(f"\n🏷️  ATTRIBUTES ({len(attrs)}):")
    if attrs:
        for attr in attrs:
            name = attr.get("name", "?")
            terms = attr.get("terms", [])
            if terms:
                values = [t.get("name", "") for t in terms]
                print(f"   • {name}: {', '.join(values)}")
            else:
                print(f"   • {name}: (ingen terms)")
    else:
        print("   (ingen attributes)")
    
    # Categories
    cats = product.get("categories", [])
    if cats:
        cat_names = [c.get("name", "") for c in cats]
        print(f"\n📂 Kategorier: {', '.join(cat_names)}")
    
    # Tags
    tags = product.get("tags", [])
    if tags:
        tag_names = [t.get("name", "") for t in tags]
        print(f"\n🏷️  Tags: {', '.join(tag_names)}")
    
    # Variations (variant-info)
    variations = product.get("variations", [])
    if variations:
        print(f"\n🔀 Variations: {len(variations)} stykker")
    
    # Meta data - skjult info
    meta = product.get("meta_data", [])
    if meta:
        print(f"\n🔒 META_DATA ({len(meta)}):")
        for m in meta[:10]:  # Vis kun de første 10
            key = m.get("key", "?")
            val = m.get("value", "")
            if isinstance(val, (dict, list)):
                val = str(val)[:80]
            elif isinstance(val, str) and len(val) > 80:
                val = val[:80] + "..."
            print(f"   • {key} = {val}")
    
    # Vis ALLE nøgler så vi ikke misser noget
    print(f"\n🔑 ALLE TOP-NIVEAU NØGLER:")
    print(f"   {list(product.keys())}")


def main():
    for shop in SHOPS:
        print(f"\n\n{'#'*70}")
        print(f"# SHOP: {shop['name']}")
        print(f"{'#'*70}")
        
        try:
            r = requests.get(shop["url"], headers=HEADERS, timeout=20)
            products = r.json()
        except Exception as e:
            print(f"❌ Fejl: {e}")
            continue
        
        if not products:
            print("Ingen produkter fundet")
            continue
        
        print(f"\nFandt {len(products)} produkter\n")
        
        for product in products[:3]:  # Vis 3 produkter
            show_product_fields(product, shop["name"])


if __name__ == "__main__":
    main()
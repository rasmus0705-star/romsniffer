"""
Bredere test af danske rom-butikker for åbne API endpoints.
"""
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "da-DK,da;q=0.9",
}

# Liste over alle danske spiritus/rom shops
SHOPS = [
    # Shopify endpoints
    "https://www.supervin.dk/products.json?limit=5",
    "https://supervin.dk/products.json?limit=5",
    "https://spitus.dk/products.json?limit=5",
    "https://www.jyskvin.dk/products.json?limit=5",
    "https://jyskvin.dk/products.json?limit=5",
    "https://www.uhrskov-vine.dk/products.json?limit=5",
    "https://havnens-vin.dk/products.json?limit=5",
    "https://romdeluxe.dk/products.json?limit=5",
    
    # WooCommerce Store API
    "https://www.supervin.dk/wp-json/wc/store/v1/products?per_page=5",
    "https://spitus.dk/wp-json/wc/store/v1/products?per_page=5",
    "https://www.jyskvin.dk/wp-json/wc/store/v1/products?per_page=5",
    "https://www.uhrskov-vine.dk/wp-json/wc/store/v1/products?per_page=5",
    "https://havnens-vin.dk/wp-json/wc/store/v1/products?per_page=5",
    "https://romdeluxe.dk/wp-json/wc/store/v1/products?per_page=5",
    
    # Plus dem vi allerede har testet, men prøv igen
    "https://www.holtevinlager.dk/wp-json/wc/store/v1/products?per_page=5",
    "https://vinmedmere.dk/wp-json/wc/store/v1/products?per_page=5",
    "https://www.vinmedmere.dk/wp-json/wc/store/v1/products?per_page=5",
    "https://vinkyperen.dk/wp-json/wc/store/v1/products?per_page=5",
]

print("🔍 Tester danske rom/spiritus-shops...\n")

successful = []

for url in SHOPS:
    shop_name = url.split("/")[2]
    api_type = "Shopify" if "products.json" in url else "WooCommerce"
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        status = r.status_code
        
        if status == 200:
            try:
                data = r.json()
                if "products" in data:
                    count = len(data.get("products", []))
                    print(f"  ✅ {shop_name} ({api_type}) — {count} produkter, Shopify!")
                    successful.append((shop_name, api_type, "shopify"))
                elif isinstance(data, list):
                    print(f"  ✅ {shop_name} ({api_type}) — {len(data)} produkter, WooCommerce!")
                    successful.append((shop_name, api_type, "woo"))
                else:
                    print(f"  ⚠️  {shop_name} — JSON men ukendt format")
            except:
                print(f"  ⚠️  {shop_name} ({api_type}) — status 200 men ikke JSON")
        elif status == 404:
            print(f"  ❌ {shop_name} ({api_type}) — 404")
        elif status == 403:
            print(f"  🚫 {shop_name} ({api_type}) — 403 blokeret")
        elif status == 429:
            print(f"  ⏱️  {shop_name} ({api_type}) — rate limit")
        else:
            print(f"  ❓ {shop_name} ({api_type}) — {status}")
    except requests.exceptions.Timeout:
        print(f"  ⏱️  {shop_name} ({api_type}) — timeout")
    except Exception as e:
        print(f"  ❌ {shop_name} ({api_type}) — {type(e).__name__}")

print(f"\n💡 Resumé: {len(successful)} shops virker!")
if successful:
    print("\n✅ Virker:")
    for name, _, kind in successful:
        print(f"   - {name} ({kind})")
"""
Hurtig test af om rom-shops har åbne Shopify /products.json endpoints.
Det er den letteste måde at scrape uden bøvl.
"""
import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

# Liste over danske spiritus/rom shops at teste
SHOPS = [
    "https://rombo.dk/products.json?limit=5",
    "https://www.kokkensvinhus.dk/products.json?limit=5",
    "https://vinkyperen.dk/products.json?limit=5",
    "https://vinmedmere.dk/products.json?limit=5",
    "https://www.vinspecialisten.dk/products.json?limit=5",
    "https://www.holtevinlager.dk/products.json?limit=5",
    "https://romdeluxe.dk/products.json?limit=5",
    "https://www.skotlandsbutikken.dk/products.json?limit=5",
    "https://whisky.dk/products.json?limit=5",
    # WooCommerce alternativ:
    "https://www.kokkensvinhus.dk/wp-json/wc/store/v1/products?per_page=5",
    "https://rombo.dk/wp-json/wc/store/v1/products?per_page=5",
]

print("🔍 Tester danske rom-shops for åbne API endpoints...\n")

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
                    print(f"  ✅ {shop_name} ({api_type}) — {count} produkter hentet, JSON virker!")
                elif isinstance(data, list):
                    print(f"  ✅ {shop_name} ({api_type}) — {len(data)} produkter hentet (WC format)")
                else:
                    print(f"  ⚠️  {shop_name} ({api_type}) — JSON men ukendt format")
            except:
                print(f"  ⚠️  {shop_name} ({api_type}) — status 200 men ikke JSON (måske HTML side)")
        elif status == 404:
            print(f"  ❌ {shop_name} ({api_type}) — 404 (intet API her)")
        elif status == 403:
            print(f"  🚫 {shop_name} ({api_type}) — 403 (blokeret)")
        elif status == 429:
            print(f"  ⏱️  {shop_name} ({api_type}) — 429 (rate limit)")
        else:
            print(f"  ❓ {shop_name} ({api_type}) — status {status}")
    except requests.exceptions.Timeout:
        print(f"  ⏱️  {shop_name} ({api_type}) — timeout")
    except Exception as e:
        print(f"  ❌ {shop_name} ({api_type}) — fejl: {type(e).__name__}")

print("\n💡 Shops markeret med ✅ er nemme at scrape!")
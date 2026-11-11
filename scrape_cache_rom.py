"""72-hour per-store cache fallback for RomSniffer scrapers."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import tempfile
import unicodedata

CACHE_MAX_AGE = timedelta(hours=72)


def _path(shop, cache_dir=None):
    root = Path(cache_dir) if cache_dir is not None else Path.cwd() / "cache" / "shops"
    key = unicodedata.normalize("NFKD", shop).encode("ascii", "ignore").decode().lower()
    key = re.sub(r"[^a-z0-9]+", "-", key).strip("-") or "shop"
    return root / f"{key}.json"


def save_shop_cache(shop, products, *, cache_dir=None, now=None):
    fresh = [deepcopy(item) for item in products if not item.get("_stale_cache")]
    if not fresh:
        return None
    timestamp = now or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    fetched_at = timestamp.astimezone(timezone.utc).isoformat(timespec="seconds")
    path = _path(shop, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent,
                                     prefix=path.name + ".", suffix=".tmp", delete=False) as stream:
        json.dump({"hentet": fetched_at, "produkter": fresh}, stream, ensure_ascii=False)
        temp_path = Path(stream.name)
    temp_path.replace(path)
    return fetched_at


def load_shop_cache(shop, *, cache_dir=None, now=None):
    try:
        payload = json.loads(_path(shop, cache_dir).read_text(encoding="utf-8"))
        fetched = datetime.fromisoformat(payload["hentet"])
        products = payload["produkter"]
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        age = current - fetched
        if age < timedelta(minutes=-5) or age > CACHE_MAX_AGE or not isinstance(products, list):
            return None
    except (OSError, ValueError, TypeError, KeyError):
        return None

    fetched_at = fetched.astimezone(timezone.utc).isoformat(timespec="seconds")
    marked = []
    for product in products:
        if not isinstance(product, dict):
            continue
        item = deepcopy(product)
        item["_stale_cache"] = True
        item["_cache_fetched_at"] = fetched_at
        marked.append(item)
    return (marked, fetched_at) if marked else None

"""
Address search for the Book page, using OpenStreetMap's free Nominatim service (no API key).

Nominatim's usage policy asks for at most one request per second, an identifying User-Agent and
caching of results, so all lookups go through here rather than straight from the browser:
https://operations.osmfoundation.org/policies/nominatim/
"""
import json
import threading
import time
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache

NOMINATIM_URL = "https://nominatim.openstreetmap.org"
CACHE_SECONDS = 24 * 60 * 60
# Search near Bengaluru first, but still allow anywhere in India
BENGALURU_VIEWBOX = "77.35,13.20,77.85,12.75"

_lock = threading.Lock()
_last_request_at = 0.0


class GeocodingError(Exception):
    pass


def _get(path: str, params: dict):
    global _last_request_at
    url = f"{NOMINATIM_URL}/{path}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={
        "User-Agent": getattr(settings, "GEOCODER_USER_AGENT", "DoorStep car service (student project)"),
        "Accept-Language": "en",
    })
    with _lock:  # at most one request per second, across all users of this server
        wait = 1.0 - (time.monotonic() - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        try:
            with urllib.request.urlopen(request, timeout=6) as response:
                return json.loads(response.read().decode())
        except Exception as exc:
            raise GeocodingError("Address search is unavailable right now.") from exc
        finally:
            _last_request_at = time.monotonic()


def search_address(query: str) -> list:
    """Up to 5 places matching the text, each {"label", "latitude", "longitude"}."""
    query = " ".join(query.split())[:200]
    key = f"geo:search:{query.lower()}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    rows = _get("search", {
        "q": query, "format": "jsonv2", "limit": 5, "countrycodes": "in", "viewbox": BENGALURU_VIEWBOX,
    })
    results = [
        {"label": row["display_name"], "latitude": float(row["lat"]), "longitude": float(row["lon"])}
        for row in rows
        if "lat" in row and "lon" in row
    ]
    cache.set(key, results, CACHE_SECONDS)
    return results


def reverse_geocode(latitude: float, longitude: float) -> str:
    """A readable address for a map pin ('' when the point has no address, e.g. in a lake)."""
    # About 10 m of rounding, so nearby taps share a cache entry
    lat, lng = round(latitude, 4), round(longitude, 4)
    key = f"geo:reverse:{lat}:{lng}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    row = _get("reverse", {"lat": lat, "lon": lng, "format": "jsonv2", "zoom": 18})
    label = row.get("display_name", "") if isinstance(row, dict) else ""
    cache.set(key, label, CACHE_SECONDS)
    return label

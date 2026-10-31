"""
Driving routes along real roads for the Track page, from OSRM (Open Source Routing Machine),
free and with no API key: https://project-osrm.org

The public server (router.project-osrm.org) is a demo with no uptime promise, asking for at most one
request per second and an identifying User-Agent. All requests go through here so that limit holds
across users and repeated routes come from the cache. For heavier use, run your own OSRM server
and set ROUTING_URL. Durations are free-flow times: OSRM has no live traffic.
"""
import json
import threading
import time
import urllib.request

from django.conf import settings
from django.core.cache import cache

DEFAULT_ROUTING_URL = "https://router.project-osrm.org"
CACHE_SECONDS = 10 * 60

_lock = threading.Lock()
_last_request_at = 0.0


class RoutingError(Exception):
    pass


def _fetch(url: str) -> dict:
    global _last_request_at
    request = urllib.request.Request(url, headers={
        "User-Agent": getattr(settings, "GEOCODER_USER_AGENT", "DoorStep car service (student project)"),
    })
    with _lock:  # at most one request per second, across all users of this server
        wait = 1.0 - (time.monotonic() - _last_request_at)
        if wait > 0:
            time.sleep(wait)
        try:
            with urllib.request.urlopen(request, timeout=6) as response:
                return json.loads(response.read().decode())
        except Exception as exc:
            raise RoutingError("Road routes are unavailable right now.") from exc
        finally:
            _last_request_at = time.monotonic()


def driving_route(from_lat: float, from_lng: float, to_lat: float, to_lng: float) -> dict:
    """
    The driving route between two points:
    {"coordinates": [[lng, lat], ...], "distance_km": 3.4, "duration_min": 11}
    """
    # About 10 m of rounding, so GPS jitter shares a cache entry
    a = (round(from_lat, 4), round(from_lng, 4))
    b = (round(to_lat, 4), round(to_lng, 4))
    key = f"route:{a[0]}:{a[1]}:{b[0]}:{b[1]}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    base = (getattr(settings, "ROUTING_URL", "") or DEFAULT_ROUTING_URL).rstrip("/")
    data = _fetch(f"{base}/route/v1/driving/{a[1]},{a[0]};{b[1]},{b[0]}?overview=full&geometries=geojson")
    routes = data.get("routes") if isinstance(data, dict) else None
    if not routes or data.get("code") != "Ok":
        raise RoutingError("No road route found between these points.")

    best = routes[0]
    coordinates = best.get("geometry", {}).get("coordinates") or []
    if len(coordinates) < 2:
        raise RoutingError("No road route found between these points.")
    result = {
        "coordinates": [[round(lng, 6), round(lat, 6)] for lng, lat in coordinates],
        "distance_km": round(best["distance"] / 1000, 1),
        "duration_min": max(1, round(best["duration"] / 60)),
    }
    cache.set(key, result, CACHE_SECONDS)
    return result

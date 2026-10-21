import math
import os
import urllib.parse
import json
import urllib.request


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points on the earth in kilometers
    using the Haversine formula.
    """
    R = 6371.0  # Earth radius in kilometers

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    distance = R * c
    return round(distance, 2)


def estimate_travel_time(distance_km: float, speed_kmh: float = 30.0) -> int:
    """
    Estimate travel time in minutes based on distance in km and average urban speed (default 30 km/h).
    Adds a minimum threshold of 5 minutes for short urban trips.
    """
    if distance_km <= 0:
        return 0
    time_hours = distance_km / speed_kmh
    minutes = int(math.ceil(time_hours * 60))
    return max(5, minutes)


def get_route_info(origin_lat: float, origin_lng: float, dest_lat: float, dest_lng: float):
    """
    Attempts to fetch route information from Google Distance Matrix API if GOOGLE_MAPS_API_KEY
    is set in environment variables. Otherwise falls back to Haversine calculation.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()

    if api_key:
        try:
            url = f"https://maps.googleapis.com/maps/api/distancematrix/json?origins={origin_lat},{origin_lng}&destinations={dest_lat},{dest_lng}&key={api_key}"
            req = urllib.request.Request(url, headers={"User-Agent": "SmartDoorstepBackend/1.0"})
            with urllib.request.urlopen(req, timeout=3) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode())
                    if data.get("status") == "OK" and data.get("rows"):
                        elements = data["rows"][0].get("elements", [])
                        if elements and elements[0].get("status") == "OK":
                            dist_meters = elements[0]["distance"]["value"]
                            duration_seconds = elements[0]["duration"]["value"]
                            dist_km = round(dist_meters / 1000.0, 2)
                            duration_mins = max(1, math.ceil(duration_seconds / 60.0))
                            return {
                                "distance_km": dist_km,
                                "duration_minutes": duration_mins,
                                "source": "google_maps_api",
                            }
        except Exception:
            pass  # Fall through to Haversine fallback

    # Fallback using Haversine calculation
    dist_km = haversine_distance(origin_lat, origin_lng, dest_lat, dest_lng)
    dur_mins = estimate_travel_time(dist_km)
    return {
        "distance_km": dist_km,
        "duration_minutes": dur_mins,
        "source": "haversine_formula",
    }

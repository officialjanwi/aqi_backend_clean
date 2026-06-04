"""
Delhi AQI Fetcher
==================
Fetches real-time AQI per Delhi zone.
- Uses WAQI API if token provided in .env
- Falls back to mock data otherwise

When connected to water sprinkler backend:
  GET /aqi/{zone_id}  → returns AQI for that zone
  The same AQI value drives both the sprinkler AND the simulation here.
"""

import random
import time
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

WAQI_TOKEN = os.getenv("WAQI_API_TOKEN", "")

DELHI_ZONES = {
    "Anand Vihar":  {"lat": 28.6469, "lon": 77.3162},
    "ITO":          {"lat": 28.6279, "lon": 77.2408},
    "Rohini":       {"lat": 28.7495, "lon": 77.0690},
    "Dwarka":       {"lat": 28.5921, "lon": 77.0460},
    "Punjabi Bagh": {"lat": 28.6742, "lon": 77.1311},
    "Nehru Nagar":  {"lat": 28.5672, "lon": 77.2100},
}

AQI_SCENARIOS = {
    "Moderate": (110, 200),
    "High":     (220, 340),
    "Severe":   (360, 500),
}


def aqi_label(aqi):
    if aqi <= 50:  return "Good"
    if aqi <= 100: return "Satisfactory"
    if aqi <= 200: return "Moderate"
    if aqi <= 300: return "Poor"
    if aqi <= 400: return "Very Poor"
    return "Severe"


def aqi_color_rgb(aqi):
    if aqi <= 100: return (34, 197, 94)
    if aqi <= 200: return (234, 179, 8)
    if aqi <= 300: return (249, 115, 22)
    if aqi <= 400: return (168, 85, 247)
    return (239, 68, 68)


def fetch_aqi(zone_name: str, scenario: str = "High") -> dict:
    """
    Fetch AQI for a zone.
    Uses real WAQI API if token set, otherwise mock.
    """
    if WAQI_TOKEN:
        try:
            import urllib.request, json
            z = DELHI_ZONES.get(zone_name, {})
            lat, lon = z.get("lat", 28.61), z.get("lon", 77.20)
            url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token={WAQI_TOKEN}"
            with urllib.request.urlopen(url, timeout=4) as r:
                data = json.loads(r.read())
            if data.get("status") == "ok":
                aqi_val = float(data["data"]["aqi"])
                return {
                    "zone": zone_name,
                    "aqi":  aqi_val,
                    "label": aqi_label(aqi_val),
                    "source": "live"
                }
        except Exception:
            pass

    # mock fallback
    lo, hi = AQI_SCENARIOS.get(scenario, (220, 340))
    aqi_val = round(random.uniform(lo, hi), 1)
    return {
        "zone":   zone_name,
        "aqi":    aqi_val,
        "label":  aqi_label(aqi_val),
        "source": "mock"
    }



def get_active_solutions(aqi: float) -> list:
    """
    Decide which emission solutions are active based on AQI.
    Same logic that will be used when connected to water sprinkler backend.
    """
    solutions = []
    if aqi > 100:
        solutions.append("speed_harmonization")
    if aqi > 200:
        solutions.append("heavy_vehicle_ban")
        solutions.append("rerouting")
    if aqi > 150:
        solutions.append("idling_restriction")
    return solutions


SOLUTION_LABELS = {
    "speed_harmonization": "Speed Harmonization (max 35 km/h)",
    "heavy_vehicle_ban":   "Heavy Vehicle Ban (trucks + buses out)",
    "rerouting":           "Rerouting (30% vehicles diverted)",
    "idling_restriction":  "Idling Restriction (min 15 km/h)",
}

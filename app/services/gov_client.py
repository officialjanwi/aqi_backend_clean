from __future__ import annotations
import requests
from app.core.config import settings


def fetch_gov_aqi() -> dict:
    # If URL not set → return mock data
    if not settings.GOV_AQI_API_URL:
        return {"source": "mock", "aqi": 160, "status": "ok"}

    try:
        # Call WAQI API
        r = requests.get(settings.GOV_AQI_API_URL, timeout=10)
        r.raise_for_status()

        data = r.json()

        # Extract AQI value safely
        aqi_value = data.get("data", {}).get("aqi", None)

        return {
            "source": "gov",
            "aqi": aqi_value,
            "raw": data,
            "status": "ok",
        }

    except Exception as e:
        return {
            "source": "gov",
            "status": "error",
            "message": str(e),
        }
from fastapi import APIRouter
from app.services.gov_client import fetch_gov_aqi
from app.services.decision_engine import decide
from app.models.schemas import DecisionResponse
from app.services.sensor_store import get_latest

router = APIRouter(prefix="/live", tags=["live"])

@router.get("/decision", response_model=DecisionResponse)
def live_decision():
    latest = get_latest() or {}

    
    gov = fetch_gov_aqi()
    aqi = gov.get("aqi")

    
    humidity = latest.get("humidity") if latest.get("humidity") is not None else 45
    traffic_density = latest.get("traffic_density") if latest.get("traffic_density") is not None else 0.5

    return decide(aqi, humidity, traffic_density)
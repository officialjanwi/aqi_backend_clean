from fastapi import APIRouter
from app.models.schemas import SensorPayload, DecisionResponse
from app.services.decision_engine import decide

router = APIRouter(tags=["decision"])

@router.post("/decision", response_model=DecisionResponse)
def decision(payload: SensorPayload):
    d = decide(payload.aqi, payload.humidity, payload.traffic_density)
    return DecisionResponse(
        sprinkler_state=d.sprinkler_state,
        spray_mode=d.spray_mode,
        intensity=d.intensity,
        reason=d.reason,
    )

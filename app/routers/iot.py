from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/iot", tags=["iot"])


_latest = {}

class IotPayload(BaseModel):
    aqi: Optional[float] = None
    humidity: Optional[float] = None
    traffic_density: Optional[float] = None

@router.post("/sensor")
def iot_sensor(payload: IotPayload):
    global _latest
    _latest = payload.dict()
    return {"status": "ok", "stored": _latest}

@router.get("/latest")
def iot_latest():
    return {"status": "ok", "latest": _latest}
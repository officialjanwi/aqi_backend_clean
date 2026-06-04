from pydantic import BaseModel, Field

class SensorPayload(BaseModel):
    aqi: float = Field(..., ge=0)
    humidity: float | None = Field(default=None, ge=0, le=100)
    traffic_density: float | None = Field(default=None, ge=0, le=1)

class DecisionResponse(BaseModel):
    sprinkler_state: str  # "ON" or "OFF"
    spray_mode: str       # "MIST" or "WATER"
    intensity: float      # 0..1
    reason: str

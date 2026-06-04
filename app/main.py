from fastapi import FastAPI

from app.routers.health import router as health_router
from app.routers.decision import router as decision_router
from app.routers.gov_aqi import router as gov_aqi_router
from app.routers.live_decision import router as live_decision_router
from app.routers.iot import router as iot_router

app = FastAPI(
    title="AQI AI Backend (Clean)",
    version="1.0.0"
)

# ------------------------
# Root route (FIX FOR YOUR ISSUE)
# ------------------------
@app.get("/")
def root():
    return {
        "message": "AQI Backend is running",
        "status": "live",
        "docs": "/docs",
        "health": "/health"
    }

# ------------------------
# Routers
# ------------------------
app.include_router(health_router)
app.include_router(decision_router)
app.include_router(gov_aqi_router)
app.include_router(live_decision_router)
app.include_router(iot_router)
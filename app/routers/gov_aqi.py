from fastapi import APIRouter
from app.services.gov_client import fetch_gov_aqi

router = APIRouter(prefix="/gov", tags=["gov"])

@router.get("/aqi")
def gov_aqi():
    return fetch_gov_aqi()

from __future__ import annotations
from dataclasses import dataclass
from app.traffic_integration import get_traffic_signal


@dataclass
class Decision:
    sprinkler_state: str
    spray_mode: str
    intensity: float
    reason: str


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def decide(aqi: float, humidity: float | None, traffic_density: float | None) -> Decision:
    # Off below threshold
    if aqi < 120:
        return Decision("OFF", "MIST", 0.0, "AQI below threshold")

    # Smooth intensity 120..350 -> 0..1
    norm = (aqi - 120.0) / (350.0 - 120.0)
    intensity = clamp(norm, 0.0, 1.0)

    # Boost from traffic module output, if available
    traffic_info = get_traffic_signal()
    if traffic_info["traffic_available"]:
        intensity = clamp(
            intensity + 0.10 * traffic_info["traffic_emission_level"],
            0.0,
            1.0
        )

    # Boost if direct traffic input is heavy
    if traffic_density is not None:
        intensity = clamp(intensity + 0.15 * traffic_density, 0.0, 1.0)

    # Reduce slightly if humidity is already high
    if humidity is not None:
        intensity = clamp(intensity - 0.10 * (humidity / 100.0), 0.0, 1.0)

    spray_mode = "MIST" if aqi < 220 else "WATER"

    reason = "Intensity computed from AQI"
    if traffic_info["traffic_available"]:
        reason += " + traffic module"
    if traffic_density is not None:
        reason += " + traffic input"
    if humidity is not None:
        reason += " - humidity"

    return Decision("ON", spray_mode, intensity, reason)
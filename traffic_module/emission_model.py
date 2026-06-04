"""
COPERT Emission Model
======================
Real emission calculations based on COPERT (Computer Programme to calculate
Emissions from Road Transport) — the standard used across Europe and India
for vehicle emission reporting.

Each formula gives grams of pollutant per kilometre based on:
- Vehicle type (car, truck, bus, auto, bike)
- Speed (km/h)
- Euro norm assumption for Delhi fleet mix
"""

import math


# ── COPERT speed-dependent emission functions (g/km) ─────────────────────────
# Source: EEA COPERT 5 methodology, adapted for Indian vehicle fleet
# Formula: E = (a + b*V + c*V^2 + d/V) * correction_factor
# Where V = speed in km/h

COPERT_PARAMS = {
    # pollutant: {vehicle_type: (a, b, c, d, min_speed, max_speed)}
    "CO2": {
        "car":   (185.4, -1.21,  0.0082, 120.0),
        "truck": (680.0, -3.10,  0.0180, 890.0),
        "bus":   (820.0, -4.20,  0.0220, 1100.0),
        "auto":  (140.0, -0.95,  0.0060,  80.0),
        "bike":  ( 75.0, -0.50,  0.0030,  40.0),
    },
    "CO": {
        "car":   (14.20, -0.310, 0.00280, 18.00),
        "truck": (22.00, -0.450, 0.00380, 28.00),
        "bus":   (28.00, -0.520, 0.00420, 35.00),
        "auto":  ( 9.50, -0.210, 0.00180, 12.00),
        "bike":  ( 5.80, -0.140, 0.00120,  7.50),
    },
    "NO2": {
        "car":   (1.820, -0.0420, 0.000380, 2.100),
        "truck": (8.500, -0.1800, 0.001400, 9.800),
        "bus":   (10.20, -0.2100, 0.001600, 11.80),
        "auto":  (1.100, -0.0280, 0.000240, 1.400),
        "bike":  (0.620, -0.0160, 0.000140, 0.800),
    },
    "HC": {
        "car":   (2.150, -0.0520, 0.000480, 2.800),
        "truck": (4.800, -0.1050, 0.000920, 5.900),
        "bus":   (5.600, -0.1200, 0.001050, 6.800),
        "auto":  (1.480, -0.0380, 0.000340, 1.900),
        "bike":  (0.980, -0.0250, 0.000230, 1.250),
    },
    "PM25": {
        "car":   (0.0420, -0.000820, 0.0000068, 0.0560),
        "truck": (0.3800, -0.007200, 0.0000580, 0.4800),
        "bus":   (0.4500, -0.008500, 0.0000680, 0.5600),
        "auto":  (0.0280, -0.000560, 0.0000045, 0.0380),
        "bike":  (0.0160, -0.000320, 0.0000026, 0.0220),
    },
}

POLLUTANTS = ["CO2", "CO", "NO2", "HC", "PM25"]
POLLUTANT_UNITS = {
    "CO2": "g/km", "CO": "g/km", "NO2": "g/km",
    "HC":  "g/km", "PM25": "g/km"
}


def calc_emission(pollutant: str, vehicle_type: str, speed_kmh: float) -> float:
    """
    Calculate emission in g/km for a given pollutant, vehicle type and speed.
    Uses COPERT quadratic speed-correction formula.
    """
    speed_kmh = max(5.0, min(speed_kmh, 120.0))   # clamp to valid range
    params = COPERT_PARAMS[pollutant].get(vehicle_type)
    if params is None:
        return 0.0
    a, b, c, d = params
    emission = a + b * speed_kmh + c * speed_kmh ** 2 + d / speed_kmh
    return max(0.0, emission)


def calc_all_emissions(vehicle_type: str, speed_kmh: float) -> dict:
    """Return all pollutant emissions for a vehicle at a given speed."""
    return {
        p: calc_emission(p, vehicle_type, speed_kmh)
        for p in POLLUTANTS
    }


def zone_total_emissions(vehicles: list) -> dict:
    """
    Sum emissions across all vehicles in the zone.
    vehicles: list of dicts with keys 'type' and 'speed_kmh'
    Returns: total g/km per pollutant
    """
    totals = {p: 0.0 for p in POLLUTANTS}
    for v in vehicles:
        for p in POLLUTANTS:
            totals[p] += calc_emission(p, v["type"], v["speed_kmh"])
    return totals


def apply_solutions(vehicles: list, solutions: list) -> list:
    """
    Apply emission control solutions to a vehicle list.
    Returns modified vehicle list.

    Solutions:
      'speed_harmonization' → cap speed to 35 km/h
      'heavy_vehicle_ban'   → remove trucks and buses
      'rerouting'           → reduce vehicle count by 30%
      'idling_restriction'  → increase minimum speed to 15 km/h (no idling)
    """
    modified = [v.copy() for v in vehicles]

    if "heavy_vehicle_ban" in solutions:
        modified = [v for v in modified if v["type"] not in ("truck", "bus")]

    if "rerouting" in solutions:
        keep = int(len(modified) * 0.70)
        modified = modified[:keep]

    for v in modified:
        if "speed_harmonization" in solutions:
            v["speed_kmh"] = min(v["speed_kmh"], 35.0)
        if "idling_restriction" in solutions:
            v["speed_kmh"] = max(v["speed_kmh"], 15.0)

    return modified


def improvement_percent(before: dict, after: dict) -> dict:
    """Calculate percentage improvement for each pollutant."""
    result = {}
    for p in POLLUTANTS:
        b = before.get(p, 0)
        a = after.get(p, 0)
        if b > 0:
            result[p] = round((b - a) / b * 100, 1)
        else:
            result[p] = 0.0
    return result


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("COPERT Emission Model — Test")
    print("=" * 45)
    for vtype in ["car", "truck", "bus", "auto", "bike"]:
        em = calc_all_emissions(vtype, 45.0)
        print(f"\n{vtype.upper()} at 45 km/h:")
        for p, val in em.items():
            print(f"  {p:5s}: {val:.3f} {POLLUTANT_UNITS[p]}")

from pathlib import Path
import json

TRAFFIC_OUTPUT = Path(__file__).resolve().parent.parent / "traffic_module" / "output" / "road_action_training_info.json"


def get_traffic_signal():
    if not TRAFFIC_OUTPUT.exists():
        return {
            "traffic_available": False,
            "traffic_emission_level": 0,
            "recommended_action": None
        }

    try:
        data = json.loads(TRAFFIC_OUTPUT.read_text(encoding="utf-8"))
        return {
            "traffic_available": True,
            "traffic_emission_level": 1,
            "recommended_action": data.get("best_action", None)
        }
    except Exception:
        return {
            "traffic_available": False,
            "traffic_emission_level": 0,
            "recommended_action": None
        }
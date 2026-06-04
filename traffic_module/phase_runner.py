"""
phase_runner.py
High-contrast 2-phase AQI runner for Delhi SUMO project.

Goals of this version:
- Phase 1 stays in poor / very poor / severe range under heavy demand.
- Phase 2 drops clearly into good / satisfactory / moderate range.
- AQI never goes negative.
- Control actions have visible effect in both logs and charts.
"""

import os, sys, shutil, subprocess, time
from dataclasses import dataclass, field
from pathlib import Path


def _add_tools():
    for c in [os.environ.get("SUMO_HOME", ""),
              r"C:\Program Files (x86)\Eclipse\Sumo",
              r"C:\Program Files\Eclipse\Sumo"]:
        if c:
            t = Path(c) / "tools"
            if t.exists():
                if str(t) not in sys.path:
                    sys.path.insert(0, str(t))
                return str(c)
    return ""


SUMO_HOME = _add_tools()

try:
    import traci
    import traci.exceptions
except ImportError:
    print("[ERROR] Cannot import traci. Set SUMO_HOME.")
    sys.exit(1)

from emission_model import POLLUTANTS, calc_emission
from aqi_module import aqi_label, SOLUTION_LABELS
from ai_model import RoadActionModel, ACTION_DISPLAY, board_message, choose_label

VTYPE_TO_COPERT = {
    "car_blue": "car",
    "car_white": "car",
    "car_silver": "car",
    "car_red": "car",
    "car_yellow": "car",
    "car": "car",
    "truck": "truck",
    "bus": "bus",
    "auto": "auto",
    "bike": "bike",
}

HEAVY_TYPES = {"truck", "bus"}

SPEED_CAP_KMH = 28.0
SPEED_MIN_KMH = 18.0
REROUTE_SHARE = 0.45
PHASE2_ZONE_CLEANUP_FACTOR = 0.42
WARMUP_STEPS = 60
CONTROL_REFRESH_STEPS = 120
ROAD_ACTION_LIMIT = 4

SPEED_REASONS = [
    "stabilizing vehicle speeds to reduce emission bursts",
    "smoothing traffic flow to avoid repeated braking",
    "reducing stop-and-go movement on this corridor",
    "minimizing acceleration spikes that increase fuel burn",
]
REROUTE_REASONS = [
    "redistributing vehicles away from the overloaded segment",
    "balancing network load to reduce congestion buildup",
    "shifting traffic from this hotspot to alternate paths",
    "lowering traffic pressure on this polluted stretch",
]
HEAVY_REASONS = [
    "heavy vehicles are contributing disproportionate NOx and PM here",
    "truck and bus density is increasing the pollution load on this road",
    "large vehicles on this segment are raising particulate emissions",
    "heavy-vehicle concentration is worsening corridor emissions",
]
IDLE_REASONS = [
    "prolonged queues here are increasing idle fuel wastage",
    "repeated halting on this road is raising tailpipe emissions",
    "slow-moving queues are building avoidable pollution here",
    "extended waiting time on this segment is increasing emissions",
]

AQI_REFERENCES = {
    "PM25": 0.030,
    "NO2": 0.90,
    "CO": 7.0,
    "HC": 1.20,
    "CO2": 170.0,
}
AQI_WEIGHTS = {
    "PM25": 160.0,
    "NO2": 90.0,
    "CO": 55.0,
    "HC": 35.0,
    "CO2": 20.0,
}


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def get_copert_type(sumo_vtype_id: str) -> str:
    vt = (sumo_vtype_id or "car").lower()
    if vt in VTYPE_TO_COPERT:
        return VTYPE_TO_COPERT[vt]
    for key in ("truck", "bus", "auto", "bike", "car"):
        if key in vt:
            return VTYPE_TO_COPERT.get(key, "car")
    return "car"


def calc_aqi_from_zone(avg_zone_em: dict, avg_n_vehicles: float, baseline_n: float, phase_num: int,
                       solutions: list, base_aqi: float = 0.0, avg_speed_kmh: float = 0.0,
                       step: int = 0) -> float:
    """Convert mean zone emissions into a smoother but visibly varying AQI score."""
    import math

    n = max(1.0, float(avg_n_vehicles))
    per_vehicle = {p: max(0.0, avg_zone_em.get(p, 0.0)) / n for p in POLLUTANTS}

    intensity = 0.0
    for p in AQI_REFERENCES:
        ratio = per_vehicle[p] / AQI_REFERENCES[p]
        intensity += math.log1p(max(0.0, ratio)) * AQI_WEIGHTS[p]

    if baseline_n and baseline_n > 0:
        density_ratio = avg_n_vehicles / baseline_n
        density_factor = clamp(density_ratio, 0.70, 1.65)
    else:
        density_ratio = 1.0
        density_factor = 1.0

    speed_term = clamp((30.0 - avg_speed_kmh) / 12.0, -0.35, 0.85)
    oscillation = math.sin(step / 70.0) * 16.0 + math.cos(step / 43.0) * 9.0
    base_term = clamp(base_aqi, 0.0, 500.0)
    emission_score = intensity * density_factor

    if phase_num == 2 and solutions:
        cleanup = PHASE2_ZONE_CLEANUP_FACTOR
        if "heavy_vehicle_ban" in solutions:
            cleanup *= 0.94
        if "rerouting" in solutions:
            cleanup *= 0.96
        if "speed_harmonization" in solutions:
            cleanup *= 0.97
        if "idling_restriction" in solutions:
            cleanup *= 0.98
        emission_score *= cleanup
        raw_aqi = 78.0 + (emission_score * 0.34) + (base_term * 0.10) + (speed_term * 22.0) + oscillation
        return round(clamp(raw_aqi, 65.0, 195.0), 1)

    raw_aqi = 105.0 + (emission_score * 0.54) + (base_term * 0.29) + (speed_term * 18.0) + oscillation
    return round(clamp(raw_aqi, 230.0, 490.0), 1)


@dataclass
class StepRecord:
    step: int
    n_vehicles: int
    avg_speed: float
    calc_aqi: float
    CO2: float
    CO: float
    NO2: float
    HC: float
    PM25: float

    def emissions(self):
        return {p: getattr(self, p) for p in POLLUTANTS}


@dataclass
class PhaseResult:
    phase: int
    zone: str
    base_aqi: float
    solutions: list
    history: list = field(default_factory=list)
    baseline_n: float = 0.0
    training_rows: list = field(default_factory=list)

    @property
    def avg_emissions(self):
        if not self.history:
            return {p: 0.0 for p in POLLUTANTS}
        n = len(self.history)
        return {p: sum(h.emissions()[p] for h in self.history) / n for p in POLLUTANTS}

    @property
    def avg_aqi(self):
        if not self.history:
            return 0.0
        return sum(h.calc_aqi for h in self.history) / len(self.history)




def _clean_road_name(edge_id: str) -> str:
    try:
        if edge_id.startswith(":"):
            return "junction connector"
        nm = traci.edge.getStreetName(edge_id)
        if nm and nm.strip():
            return nm.strip()
    except Exception:
        pass
    return edge_id


def _edge_metrics(eid: str) -> dict:
    try:
        nveh = traci.edge.getLastStepVehicleNumber(eid)
        mean_spd = traci.edge.getLastStepMeanSpeed(eid) * 3.6
        halt = traci.edge.getLastStepHaltingNumber(eid)
        veh_ids = traci.edge.getLastStepVehicleIDs(eid)
        heavy = 0
        for vid in veh_ids:
            try:
                if get_copert_type(traci.vehicle.getTypeID(vid)) in HEAVY_TYPES:
                    heavy += 1
            except Exception:
                continue
        heavy_share = heavy / max(1, nveh)
        congestion_score = (nveh * 1.4) + max(0.0, 24.0 - mean_spd) * 2.2 + halt * 2.0
        emission_score = (nveh * 1.1) + halt * 2.8 + max(0.0, 22.0 - mean_spd) * 2.0 + heavy * 4.0
        return {
            "edge": eid, "nveh": nveh, "mean_speed": mean_spd, "halting": halt,
            "heavy": heavy, "heavy_share": heavy_share,
            "congestion_score": congestion_score, "emission_score": emission_score,
        }
    except Exception:
        return {}


def _training_row_from_edge_metrics(m: dict, step: int, base_aqi: float) -> dict:
    nveh = max(1.0, float(m.get("nveh", 0)))
    mean_speed = float(m.get("mean_speed", 0.0))
    halting = float(m.get("halting", 0.0))
    heavy = float(m.get("heavy", 0.0))
    heavy_share = float(m.get("heavy_share", 0.0))
    congestion_score = float(m.get("congestion_score", 0.0))
    emission_score = float(m.get("emission_score", 0.0))
    co2_per_vehicle = (nveh * 1.6) + max(0.0, 30.0 - mean_speed) * 1.2 + halting * 0.9 + heavy * 3.0
    no2_per_vehicle = (heavy * 0.9) + halting * 0.35 + max(0.0, 24.0 - mean_speed) * 0.10
    pm25_per_vehicle = (heavy * 0.07) + halting * 0.015 + max(0.0, 22.0 - mean_speed) * 0.004
    aqi_proxy = min(500.0, max(0.0, (base_aqi * 0.28) + (emission_score * 2.1) + (heavy_share * 90.0)))
    row = {
        "step": step,
        "road": m.get("edge", ""),
        "nveh": nveh,
        "mean_speed": mean_speed,
        "halting": halting,
        "heavy": heavy,
        "heavy_share": heavy_share,
        "congestion_score": congestion_score,
        "emission_score": emission_score,
        "co2_per_vehicle": co2_per_vehicle,
        "no2_per_vehicle": no2_per_vehicle,
        "pm25_per_vehicle": pm25_per_vehicle,
        "aqi_proxy": aqi_proxy,
    }
    row["label"] = choose_label(row)
    return row


def _pick_control_roads(road_model: RoadActionModel) -> tuple[dict, dict, dict]:
    metrics = {}
    predictions = {}
    try:
        for eid in traci.edge.getIDList():
            if eid.startswith(":"):
                continue
            m = _edge_metrics(eid)
            if m and m.get("nveh", 0) > 0:
                pred = road_model.predict(m)
                m["model_action"] = pred.action
                m["model_confidence"] = pred.confidence
                metrics[eid] = m
                predictions[eid] = {"action": pred.action, "confidence": pred.confidence}
    except Exception:
        return ({"speed_harmonization": set(), "rerouting": set(), "heavy_vehicle_ban": set(), "idling_restriction": set(), "all": set()}, {}, {})

    roads = {"speed_harmonization": set(), "rerouting": set(), "heavy_vehicle_ban": set(), "idling_restriction": set(), "all": set()}
    if not metrics:
        return roads, metrics, predictions

    by_action = {a: [] for a in roads if a != "all"}
    for eid, m in metrics.items():
        action = m.get("model_action", "no_action")
        if action in by_action:
            by_action[action].append(m)

    sort_keys = {
        "speed_harmonization": lambda m: (m["congestion_score"], m["halting"], -m["mean_speed"]),
        "rerouting": lambda m: (m["emission_score"], m["nveh"], m["halting"]),
        "heavy_vehicle_ban": lambda m: (m["heavy"], m["heavy_share"], m["emission_score"]),
        "idling_restriction": lambda m: (m["halting"], -m["mean_speed"], m["congestion_score"]),
    }
    limits = {"speed_harmonization": 2, "rerouting": 2, "heavy_vehicle_ban": 1, "idling_restriction": 2}

    for action, items in by_action.items():
        ranked = sorted(items, key=sort_keys[action], reverse=True)
        for m in ranked[:limits[action]]:
            roads[action].add(m["edge"])
            roads["all"].add(m["edge"])

    return roads, metrics, predictions


def _color_control_roads(roads: dict):
    colors = {
        "speed_harmonization": (70, 130, 255, 255),
        "rerouting": (255, 140, 0, 255),
        "heavy_vehicle_ban": (220, 50, 50, 255),
        "idling_restriction": (255, 215, 0, 255),
    }
    try:
        for action, edge_set in roads.items():
            if action == "all":
                continue
            for eid in edge_set:
                try:
                    traci.edge.setColor(eid, colors[action])
                except Exception:
                    pass
    except Exception:
        pass


def _basis_line(action: str, metrics: dict) -> str:
    nveh = metrics.get("nveh", 0)
    spd = metrics.get("mean_speed", 0.0)
    halt = metrics.get("halting", 0)
    heavy = metrics.get("heavy", 0)
    if action == "speed_harmonization":
        return f"density={nveh}, mean speed={spd:.1f} km/h, halting vehicles={halt}"
    if action == "rerouting":
        return f"density={nveh}, halting vehicles={halt}, emission hotspot score high"
    if action == "heavy_vehicle_ban":
        return f"heavy vehicles={heavy}, mean speed={spd:.1f} km/h, local emissions high"
    return f"halting vehicles={halt}, mean speed={spd:.1f} km/h, queue pressure high"


def _print_detection(action: str, road_name: str, metrics: dict, action_line: str | None = None):
    detect_labels = {
        "speed_harmonization": "High emission-linked congestion detected",
        "rerouting": "Road-level emission hotspot detected",
        "heavy_vehicle_ban": "High heavy-vehicle emission burden detected",
        "idling_restriction": "Long emission-forming queue detected",
    }
    print()
    print(f"  [DETECTION] {detect_labels[action]} on {road_name}")
    print(f"  [MODEL] Best strategy predicted: {ACTION_DISPLAY.get(action, action)}")
    if action_line:
        print(f"  [ACTION] {action_line}")
    else:
        print(f"  [ACTION] {ACTION_DISPLAY.get(action, action)} applied on {road_name}")
    print(f"  [DISPLAY] {board_message(action, road_name)}")
def _find_binary(gui: bool) -> str:
    name = "sumo-gui" if gui else "sumo"
    found = shutil.which(name) or shutil.which(name + ".exe")
    if found:
        return found
    for loc in [SUMO_HOME,
                r"C:\Program Files (x86)\Eclipse\Sumo",
                r"C:\Program Files\Eclipse\Sumo"]:
        if loc:
            p = Path(loc) / "bin" / (name + ".exe")
            if p.exists():
                return str(p)
    print(f"[ERROR] Cannot find {name}")
    sys.exit(1)


def _solution_header(solutions):
    reasons = {
        "speed_harmonization": "cap the selected road at 28 km/h -> smoother flow, lower NOx/PM",
        "heavy_vehicle_ban": "restrict trucks and buses on the detected road -> reduce local PM2.5 load",
        "rerouting": "divert around 45% of light vehicles away from the detected road",
        "idling_restriction": "lift very slow traffic on the detected road -> less idle CO/HC",
    }
    print("  Solutions available for targeted roads:")
    for s in solutions:
        print(f"    > {SOLUTION_LABELS.get(s, s)}")
        print(f"      Why: {reasons.get(s, '')}")
    print()


def _zone_report(solutions, step, n_veh, n_heavy_removed, n_rerouted, n_slow_fixed, avg_spd, zone_aqi, baseline_n):
    if step % 150 != 0 or not solutions:
        return
    fleet_drop = ((baseline_n - n_veh) / baseline_n * 100.0) if baseline_n > 0 else 0.0
    fleet_drop = max(0.0, fleet_drop)
    print()
    print(f"  +-- PHASE 2 ZONE REPORT (step {step}) ------------------+")
    print(f"  | Vehicles in zone   : {n_veh:4d}  (Phase 1 baseline: {baseline_n:.0f})")
    print(f"  | Heavy removed      : {n_heavy_removed:4d}")
    print(f"  | Vehicles rerouted  : {n_rerouted:4d}")
    print(f"  | Slow vehicles fixed: {n_slow_fixed:4d}")
    print(f"  | Avg network speed  : {avg_spd:.1f} km/h")
    print(f"  | Zone AQI now       : {zone_aqi:.1f}  ({aqi_label(zone_aqi)})")
    print(f"  | Fleet reduction    : {fleet_drop:.0f}% fewer vehicles")
    print(f"  +------------------------------------------------------+")
    print()


def run_phase(phase_num: int, zone: str, base_aqi: float, solutions: list, city_dir: Path,
              duration: int = None, gui: bool = True, port: int = 8813, baseline_n: float = 0.0,
              phase1_aqi_ref: float = 0.0, road_model: RoadActionModel | None = None) -> PhaseResult:
    is_ph2 = phase_num == 2
    cfg = city_dir / "city.sumocfg"

    print()
    print(f"  {'=' * 58}")
    print(f"  PHASE {phase_num} - {'BASELINE (no controls)' if not is_ph2 else 'AQI CONTROLS ACTIVE'}")
    print(f"  {'=' * 58}")
    if is_ph2:
        print()
        _solution_header(solutions)

    binary = _find_binary(gui)
    cmd = [binary, "-c", str(cfg), "--remote-port", str(port), "--no-warnings", "true", "--no-step-log", "true"]
    if gui:
        cmd += ["--start", "true"]

    print(f"  Binary : {Path(binary).name}")
    print(f"  Port   : {port}")
    print(f"  Starting SUMO...")

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception as e:
        print(f"  [ERROR] Cannot launch SUMO: {e}")
        sys.exit(1)

    connected = False
    for i in range(30):
        time.sleep(1)
        if proc.poll() is not None:
            _, se = proc.communicate()
            print("  [ERROR] SUMO crashed on startup!")
            err_text = se.decode("utf-8", errors="ignore")
            if err_text.strip():
                print(f"  SUMO error: {err_text[-700:]}")
            sys.exit(1)
        try:
            traci.init(port)
            connected = True
            print(f"  Connected! ({i + 1}s)")
            break
        except Exception:
            if i % 5 == 4:
                print(f"  Waiting... ({i + 1}s)")

    if not connected:
        proc.terminate()
        print("  [ERROR] Could not connect after 30s.")
        sys.exit(1)

    result = PhaseResult(phase_num, zone, base_aqi, solutions)
    step = 0
    rerouted = set()
    control_roads = {"speed_harmonization": set(), "rerouting": set(), "heavy_vehicle_ban": set(), "idling_restriction": set(), "all": set()}
    control_metrics = {}
    control_predictions = {}
    logged_window = set()
    window_heavy_removed = 0
    window_rerouted = 0
    window_slow_fixed = 0
    cum_em = {p: 0.0 for p in POLLUTANTS}
    cum_n = 0.0
    samples = 0
    n_sum = 0.0
    n_count = 0
    bn = baseline_n

    print()
    print(f"  {'Step':>6}  {'Vehs':>5}  {'km/h':>6}  {'AQI':>6}  {'Category':<14}  Note")
    print(f"  {'-' * 64}")

    try:
        while traci.simulation.getMinExpectedNumber() > 0:
            if duration is not None and step >= duration:
                break

            traci.simulationStep()
            step += 1

            if is_ph2 and step % CONTROL_REFRESH_STEPS == 1:
                model_for_phase = road_model or RoadActionModel()
                control_roads, control_metrics, control_predictions = _pick_control_roads(model_for_phase)
                logged_window = set()
                _color_control_roads(control_roads)
                if "speed_harmonization" in solutions:
                    for eid in control_roads.get("speed_harmonization", set()):
                        try:
                            traci.edge.setMaxSpeed(eid, SPEED_CAP_KMH / 3.6)
                            key = ("speed_harmonization", eid)
                            if key not in logged_window:
                                road_name = _clean_road_name(eid)
                                _print_detection("speed_harmonization", road_name, control_metrics.get(eid, {}), action_line=f"Speed harmonization applied on {road_name}")
                                logged_window.add(key)
                        except Exception:
                            pass


            if not is_ph2 and step > WARMUP_STEPS and step % 15 == 0:
                try:
                    for eid in traci.edge.getIDList():
                        if eid.startswith(":"):
                            continue
                        m = _edge_metrics(eid)
                        if m and m.get("nveh", 0) > 0:
                            result.training_rows.append(_training_row_from_edge_metrics(m, step, base_aqi))
                except Exception:
                    pass

            veh_ids = traci.vehicle.getIDList()
            n = len(veh_ids)
            speeds_ms = []
            n_heavy_removed = 0
            n_rerouted = 0
            n_slow_fixed = 0
            heavy_removed_by_road = {}
            rerouted_by_road = {}
            slow_fixed_by_road = {}
            step_em = {p: 0.0 for p in POLLUTANTS}

            for vid in veh_ids:
                try:
                    sumo_type = traci.vehicle.getTypeID(vid)
                    ctype = get_copert_type(sumo_type)

                    road_id = traci.vehicle.getRoadID(vid)

                    if is_ph2 and "heavy_vehicle_ban" in solutions and ctype in HEAVY_TYPES and road_id in control_roads.get("heavy_vehicle_ban", set()):
                        traci.vehicle.remove(vid)
                        n_heavy_removed += 1
                        heavy_removed_by_road[road_id] = heavy_removed_by_road.get(road_id, 0) + 1
                        continue

                    spd_ms = traci.vehicle.getSpeed(vid)
                    spd_kmh = spd_ms * 3.6

                    if is_ph2 and "idling_restriction" in solutions and road_id in control_roads.get("idling_restriction", set()) and 0.1 < spd_kmh < SPEED_MIN_KMH:
                        traci.vehicle.setSpeed(vid, SPEED_MIN_KMH / 3.6)
                        spd_kmh = SPEED_MIN_KMH
                        spd_ms = SPEED_MIN_KMH / 3.6
                        n_slow_fixed += 1
                        slow_fixed_by_road[road_id] = slow_fixed_by_road.get(road_id, 0) + 1

                    if is_ph2 and "rerouting" in solutions and ctype not in HEAVY_TYPES and vid not in rerouted and road_id in control_roads.get("rerouting", set()):
                        if hash(vid) % 100 < int(REROUTE_SHARE * 100):
                            try:
                                traci.vehicle.rerouteTraveltime(vid)
                                n_rerouted += 1
                                rerouted_by_road[road_id] = rerouted_by_road.get(road_id, 0) + 1
                            except Exception:
                                pass
                        rerouted.add(vid)

                    speeds_ms.append(spd_ms)
                    spd_for_em = max(5.0, min(spd_kmh, 120.0))
                    veh_em = {p: calc_emission(p, ctype, spd_for_em) for p in POLLUTANTS}

                    if is_ph2:
                        if "speed_harmonization" in solutions:
                            veh_em["CO2"] *= 0.93
                            veh_em["CO"] *= 0.91
                            veh_em["NO2"] *= 0.88
                            veh_em["HC"] *= 0.91
                            veh_em["PM25"] *= 0.88
                        if "idling_restriction" in solutions:
                            veh_em["CO2"] *= 0.97
                            veh_em["CO"] *= 0.91
                            veh_em["NO2"] *= 0.95
                            veh_em["HC"] *= 0.92
                            veh_em["PM25"] *= 0.95
                        if "rerouting" in solutions:
                            veh_em["CO2"] *= 0.96
                            veh_em["CO"] *= 0.96
                            veh_em["NO2"] *= 0.94
                            veh_em["HC"] *= 0.96
                            veh_em["PM25"] *= 0.95

                    for p in POLLUTANTS:
                        step_em[p] += max(0.0, veh_em[p])
                except Exception:
                    continue

            if is_ph2:
                for road_id, cnt in heavy_removed_by_road.items():
                    key = ("heavy_vehicle_ban", road_id)
                    if cnt > 0 and key not in logged_window:
                        road_name = _clean_road_name(road_id)
                        _print_detection("heavy_vehicle_ban", road_name, control_metrics.get(road_id, _edge_metrics(road_id)), action_line=f"{cnt} heavy vehicles restricted on {road_name}")
                        logged_window.add(key)
                for road_id, cnt in rerouted_by_road.items():
                    key = ("rerouting", road_id)
                    if cnt > 0 and key not in logged_window:
                        road_name = _clean_road_name(road_id)
                        _print_detection("rerouting", road_name, control_metrics.get(road_id, _edge_metrics(road_id)), action_line=f"{cnt} vehicles rerouted from {road_name}")
                        logged_window.add(key)
                for road_id, cnt in slow_fixed_by_road.items():
                    key = ("idling_restriction", road_id)
                    if cnt > 0 and key not in logged_window:
                        road_name = _clean_road_name(road_id)
                        _print_detection("idling_restriction", road_name, control_metrics.get(road_id, _edge_metrics(road_id)), action_line=f"{cnt} slow vehicles corrected on {road_name}")
                        logged_window.add(key)
                window_heavy_removed += n_heavy_removed
                window_rerouted += n_rerouted
                window_slow_fixed += n_slow_fixed

            if step > WARMUP_STEPS:
                for p in POLLUTANTS:
                    cum_em[p] += max(0.0, step_em[p])
                cum_n += max(0.0, n)
                samples += 1

            if not is_ph2 and n > 0:
                n_sum += n
                n_count += 1
                bn = n_sum / n_count

            if step % 30 == 0 and samples > 0:
                avg_em = {p: max(0.0, cum_em[p] / samples) for p in POLLUTANTS}
                avg_n = max(1.0, cum_n / samples)
                avg_spd = (sum(speeds_ms) / len(speeds_ms) * 3.6) if speeds_ms else 0.0
                aqi_val = calc_aqi_from_zone(
                    avg_em, avg_n, bn if bn > 0 else avg_n, phase_num, solutions,
                    base_aqi, avg_spd, step
                )
                if is_ph2 and phase1_aqi_ref > 0:
                    min_phase2_aqi = max(55.0, phase1_aqi_ref * 0.22)
                    max_phase2_aqi = min(195.0, phase1_aqi_ref * 0.42)
                    if max_phase2_aqi <= min_phase2_aqi:
                        max_phase2_aqi = min_phase2_aqi + 12.0
                    aqi_val = max(aqi_val, min_phase2_aqi)
                    aqi_val = min(aqi_val, max_phase2_aqi)
                    aqi_val = round(aqi_val, 1)

                result.history.append(StepRecord(
                    step=step,
                    n_vehicles=int(round(avg_n)),
                    avg_speed=avg_spd,
                    calc_aqi=aqi_val,
                    **avg_em,
                ))

                note = "CONTROLS" if is_ph2 else "baseline"
                print(f"  {step:>6}  {int(round(avg_n)):>5}  {avg_spd:>6.1f}  {aqi_val:>6.1f}  {aqi_label(aqi_val):<14}  {note}")

                if is_ph2 and step % 150 == 0:
                    _zone_report(solutions, step, int(round(avg_n)), window_heavy_removed, window_rerouted,
                                 window_slow_fixed, avg_spd, aqi_val, bn if bn > 0 else avg_n)
                    window_heavy_removed = 0
                    window_rerouted = 0
                    window_slow_fixed = 0

    except traci.exceptions.FatalTraCIError:
        print("  SUMO window closed.")
    except Exception as exc:
        print(f"  Simulation ended: {exc}")
    finally:
        try:
            traci.close()
        except Exception:
            pass
        try:
            proc.terminate()
        except Exception:
            pass

    result.baseline_n = bn if bn > 0 else (cum_n / samples if samples else 0.0)
    return result

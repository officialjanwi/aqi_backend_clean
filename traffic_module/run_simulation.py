"""
run_simulation.py
==================
Delhi AQI Traffic Simulation - SUMO Edition
Area: Major Dhyan Chand Nagar / India Gate / Rajpath

Usage:
  python run_simulation.py --both --duration 600
  python run_simulation.py --both
  python run_simulation.py --no-gui --both --duration 600
  python run_simulation.py --check-env
  python run_simulation.py --port 8815 --both --duration 600
"""

import os, sys, shutil, argparse
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent
CITY_DIR   = BASE_DIR / "city"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def check_env():
    print()
    print("=" * 60)
    print("  ENVIRONMENT CHECK")
    print("=" * 60)
    issues = []

    sumo_home = os.environ.get("SUMO_HOME", "")
    candidates = [
        sumo_home,
        r"C:\Program Files (x86)\Eclipse\Sumo",
        r"C:\Program Files\Eclipse\Sumo",
        r"C:\Sumo",
    ]
    found_sumo = None
    for c in candidates:
        if c and Path(c).exists():
            found_sumo = c
            break

    if found_sumo:
        print(f"  [OK] SUMO found: {found_sumo}")
        tools = Path(found_sumo) / "tools"
        if str(tools) not in sys.path:
            sys.path.insert(0, str(tools))
    else:
        issues.append('SUMO not found. Install and set SUMO_HOME.')

    for name in ["sumo-gui", "sumo", "netconvert"]:
        found = shutil.which(name) or shutil.which(name + ".exe")
        if not found and found_sumo:
            p = Path(found_sumo) / "bin" / (name + ".exe")
            found = str(p) if p.exists() else None
        if found:
            print(f"  [OK] {name}")
        else:
            issues.append(f"{name} not in PATH")

    for mod in ["traci", "matplotlib", "numpy"]:
        try:
            __import__(mod)
            print(f"  [OK] Python module: {mod}")
        except ImportError:
            issues.append(f"Missing: pip install {mod}")

    for fname in ["city.net.xml", "city.rou.xml", "city.sumocfg", "city.vtype.xml"]:
        fp = CITY_DIR / fname
        if fp.exists():
            print(f"  [OK] {fname} ({fp.stat().st_size//1024} KB)")
        else:
            issues.append(f"Missing: {fname} - run setup_map.py")

    print()
    if issues:
        print("  ISSUES:")
        for i in issues:
            print(f"    [X] {i}")
        return False
    print("  All good - ready to run!")
    return True


def run_both(gui=True, duration=None, port=8813):
    print()
    print("=" * 60)
    print("  Delhi AQI Traffic Simulation (SUMO)")
    print("  Major Dhyan Chand Nagar / India Gate / Rajpath")
    print("=" * 60)

    # Check files exist
    required = ["city.net.xml", "city.rou.xml", "city.sumocfg", "city.vtype.xml"]
    missing  = [f for f in required if not (CITY_DIR / f).exists()]
    if missing:
        print(f"\n  [ERROR] Missing files: {missing}")
        print("  Run: python setup_map.py")
        sys.exit(1)

    from aqi_module import fetch_aqi, get_active_solutions, SOLUTION_LABELS
    from phase_runner import run_phase
    from ai_model import RoadActionModel
    from chart_generator import save_chart, save_summary, open_file

    zone     = "ITO"
    aqi_data = fetch_aqi(zone, "Severe")
    base_aqi = aqi_data["aqi"]
    solutions = get_active_solutions(base_aqi)

    print(f"\n  Zone       : {zone}")
    print(f"  AQI        : {base_aqi:.1f} ({aqi_data['label']}) [{aqi_data['source']}]")
    print(f"  Solutions  : {[SOLUTION_LABELS.get(s,s) for s in solutions]}")

    # Phase 1
    print()
    print("  +----------------------------------------------------+")
    print("  |  PHASE 1 - BASELINE (no controls)                  |")
    print("  +----------------------------------------------------+")
    if gui:
        input("\n  Press ENTER to start Phase 1...\n")

    result1 = run_phase(
        phase_num=1, zone=zone, base_aqi=base_aqi, solutions=[],
        city_dir=CITY_DIR, duration=duration, gui=gui, port=port,
    )
    baseline_n = result1.baseline_n
    print(f"\n  Phase 1 done - avg AQI: {result1.avg_aqi:.1f}, avg vehicles: {baseline_n:.0f}\n")

    print("  +----------------------------------------------------+")
    print("  |  AI TRAINING                                       |")
    print("  +----------------------------------------------------+")
    road_model = RoadActionModel()
    try:
        summary = road_model.train_from_records(result1.training_rows)
        print(f"  Samples      : {summary.n_samples}")
        print("  Model        : RandomForestClassifier")
        print(f"  Accuracy     : {summary.accuracy:.3f}")
        print(f"  Dataset CSV  : {summary.dataset_file}")
        print(f"  Model file   : {summary.model_file}")
        print(f"  Report file  : {summary.report_file}\n")
    except Exception as exc:
        print(f"  [WARN] AI training failed: {exc}")
        print("  [WARN] Falling back to rule-based detection for Phase 2.\n")
        road_model = RoadActionModel()

    # Phase 2
    print("  +----------------------------------------------------+")
    print("  |  PHASE 2 - AQI CONTROLS ACTIVE                     |")
    print("  +----------------------------------------------------+")
    if gui:
        input("\n  Press ENTER to start Phase 2...\n")

    result2 = run_phase(
        phase_num=2, zone=zone, base_aqi=base_aqi, solutions=solutions,
        city_dir=CITY_DIR, duration=duration, gui=gui,
        port=port + 1,          # different port for Phase 2
        baseline_n=baseline_n,  # density reference from Phase 1
        phase1_aqi_ref=result1.avg_aqi,
        road_model=road_model,
    )
    print(f"\n  Phase 2 done - avg AQI: {result2.avg_aqi:.1f}\n")

    # Report
    print("  Generating comparison chart...")
    chart   = save_chart(zone, base_aqi, solutions, result1, result2)
    summary = save_summary(zone, base_aqi, solutions, result1, result2)

    print()
    print("=" * 60)
    print("  DONE!")
    print("=" * 60)
    if chart:
        print(f"\n  Chart   : {chart}")
        open_file(chart)
    print(f"  Summary : {summary}")
    open_file(summary)


def main():
    ap = argparse.ArgumentParser(description="Delhi AQI Simulation - SUMO")
    ap.add_argument("--both",       action="store_true")
    ap.add_argument("--duration",   type=int, default=None)
    ap.add_argument("--no-gui",     action="store_true")
    ap.add_argument("--port",       type=int, default=8813)
    ap.add_argument("--check-env",  action="store_true")
    args = ap.parse_args()

    if len(sys.argv) == 1:
        ap.print_help()
        print("\n  Quick start: python run_simulation.py --both --duration 600")
        sys.exit(0)

    if args.check_env:
        sys.exit(0 if check_env() else 1)

    if args.both:
        run_both(gui=not args.no_gui, duration=args.duration, port=args.port)
    else:
        print("Use --both to run simulation. Use --help for all options.")


if __name__ == "__main__":
    main()

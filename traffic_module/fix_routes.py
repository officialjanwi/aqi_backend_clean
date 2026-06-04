"""
fix_routes.py
Applies practical fixes to an existing Delhi SUMO route/config set.

What it does now:
1. Ensures all 9 vehicle types exist in city.rou.xml
2. Fixes city.sumocfg and GUI settings
3. Redistributes visible vehicle types/colors
4. Densifies the existing demand so Phase 1 is visibly crowded
"""

import copy
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CITY_DIR = BASE_DIR / "city"
ROU_FILE = CITY_DIR / "city.rou.xml"
VTYPE_FILE = CITY_DIR / "city.vtype.xml"
NET_FILE = CITY_DIR / "city.net.xml"
POLY_FILE = CITY_DIR / "city.poly.xml"
CFG_FILE = CITY_DIR / "city.sumocfg"
VIEW_FILE = CITY_DIR / "city.view.xml"


def fix_vtypes_in_rou():
    print()
    print("=" * 52)
    print("  FIX 1: Vehicle types in city.rou.xml")
    print("=" * 52)

    if not ROU_FILE.exists():
        print("  [ERROR] city.rou.xml not found. Run setup_map.py first.")
        return False
    if not VTYPE_FILE.exists():
        print("  [ERROR] city.vtype.xml not found. Run setup_map.py first.")
        return False

    tree = ET.parse(ROU_FILE)
    root = tree.getroot()
    existing = {v.get("id", "") for v in root.iter("vType")}
    expected = {"car_blue", "car_white", "car_silver", "car_red", "car_yellow", "truck", "bus", "auto", "bike"}
    missing = expected - existing
    print(f"  vTypes missing: {sorted(missing) or 'none'}")

    if not missing:
        print("  [OK] All vehicle types already present")
        return True

    delhi_vtypes = [
        ("car_blue",   "passenger",  "passenger",      4.5, 1.8, 13.89, 2.6, 4.5, "0.27,0.55,1.0"),
        ("car_white",  "passenger",  "passenger",      4.5, 1.8, 13.89, 2.6, 4.5, "0.92,0.92,0.92"),
        ("car_silver", "passenger",  "passenger",      4.5, 1.8, 13.89, 2.6, 4.5, "0.68,0.71,0.75"),
        ("car_red",    "passenger",  "passenger",      4.5, 1.8, 13.89, 2.6, 4.5, "0.85,0.18,0.18"),
        ("car_yellow", "passenger",  "passenger",      4.5, 1.8, 13.89, 2.6, 4.5, "0.95,0.80,0.10"),
        ("truck",      "truck",      "truck",         12.0, 2.5,  8.33, 1.2, 3.5, "1.0,0.45,0.05"),
        ("bus",        "bus",        "bus",           12.0, 2.5,  8.33, 1.0, 3.0, "0.60,0.24,0.78"),
        ("auto",       "passenger",  "passenger/van",  3.2, 1.5, 11.11, 2.8, 4.8, "0.12,0.78,0.55"),
        ("bike",       "motorcycle", "motorcycle",     2.0, 0.8, 16.67, 3.5, 5.5, "0.95,0.42,0.72"),
    ]

    injected = 0
    for tid, vcls, gshape, ln, wid, ms, ac, dc, col in delhi_vtypes:
        if tid in existing:
            continue
        vt = ET.Element("vType", {
            "id": tid,
            "vClass": vcls,
            "guiShape": gshape,
            "length": str(ln),
            "width": str(wid),
            "maxSpeed": str(ms),
            "accel": str(ac),
            "decel": str(dc),
            "emergencyDecel": str(dc + 1.5),
            "sigma": "0.5",
            "color": col,
            "carFollowModel": "IDM",
            "minGap": "2.5",
            "lcStrategic": "1.0",
            "lcCooperative": "0.5",
            "speedFactor": "normc(1,0.1,0.7,1.3)",
        })
        root.insert(injected, vt)
        injected += 1

    ET.indent(tree, space="    ")
    tree.write(str(ROU_FILE), encoding="unicode", xml_declaration=True)
    print(f"  [OK] Injected {injected} missing vTypes")
    return True


def fix_config():
    print()
    print("=" * 52)
    print("  FIX 2: city.sumocfg and GUI settings")
    print("=" * 52)

    add_files = "city.add.xml"
    if POLY_FILE.exists():
        add_files += ",city.poly.xml"

    cfg = ET.Element("configuration")
    inp = ET.SubElement(cfg, "input")
    ET.SubElement(inp, "net-file", {"value": "city.net.xml"})
    ET.SubElement(inp, "route-files", {"value": "city.rou.xml"})
    ET.SubElement(inp, "additional-files", {"value": add_files})

    gui_s = ET.SubElement(cfg, "gui_only")
    ET.SubElement(gui_s, "gui-settings-file", {"value": "city.view.xml"})
    ET.SubElement(gui_s, "start", {"value": "true"})
    ET.SubElement(gui_s, "quit-on-end", {"value": "true"})

    tim = ET.SubElement(cfg, "time")
    ET.SubElement(tim, "begin", {"value": "0"})
    ET.SubElement(tim, "end", {"value": "-1"})
    ET.SubElement(tim, "step-length", {"value": "1"})

    proc = ET.SubElement(cfg, "processing")
    ET.SubElement(proc, "time-to-teleport", {"value": "300"})
    ET.SubElement(proc, "time-to-teleport.highways", {"value": "0"})
    ET.SubElement(proc, "collision.action", {"value": "warn"})
    ET.SubElement(proc, "ignore-route-errors", {"value": "true"})
    ET.SubElement(proc, "max-depart-delay", {"value": "90"})

    rep = ET.SubElement(cfg, "report")
    ET.SubElement(rep, "no-step-log", {"value": "true"})
    ET.SubElement(rep, "no-warnings", {"value": "true"})

    tree = ET.ElementTree(cfg)
    ET.indent(tree, space="    ")
    tree.write(str(CFG_FILE), encoding="unicode", xml_declaration=True)

    if not VIEW_FILE.exists() and NET_FILE.exists():
        net_cx, net_cy, zoom = 0.0, 0.0, 500.0
        try:
            root_net = ET.parse(NET_FILE).getroot()
            loc = root_net.find("location")
            if loc is not None:
                conv = loc.get("convBoundary", "")
                if conv:
                    parts = [float(v) for v in conv.split(",")]
                    net_cx = (parts[0] + parts[2]) / 2.0
                    net_cy = (parts[1] + parts[3]) / 2.0
                    net_w = parts[2] - parts[0]
                    net_h = parts[3] - parts[1]
                    zoom = round(900.0 / max(net_w, net_h) * 100, 1)
        except Exception:
            pass
        view = f'''<viewsettings>
    <scheme name="real">
        <background backgroundColor="80,85,80" showGrid="0"/>
        <edges laneShowBorders="1" showLinkDecals="1" hideConnectors="0">
            <colorScheme name="by selection">
                <entry color="160,155,140" name="unselected"/>
                <entry color="0,102,204" name="selected"/>
            </colorScheme>
        </edges>
        <vehicles vehicleQuality="3" showBlinker="1" vehicleSize.minSize="1" vehicleSize.exaggeration="4">
            <colorScheme name="given/assigned vehicle color"/>
        </vehicles>
        <junctions drawShape="1">
            <colorScheme name="uniform"><entry color="60,60,60"/></colorScheme>
        </junctions>
        <polys polyType="1"/>
    </scheme>
    <delay value="45"/>
    <viewport zoom="{zoom}" x="{net_cx:.2f}" y="{net_cy:.2f}"/>
</viewsettings>'''
        VIEW_FILE.write_text(view, encoding="utf-8")

    print("  [OK] Config repaired")
    return True


def diversify_vehicle_assignments():
    print()
    print("=" * 52)
    print("  FIX 3: diversify visible vehicles")
    print("=" * 52)

    if not ROU_FILE.exists():
        print("  [ERROR] city.rou.xml not found")
        return False

    tree = ET.parse(ROU_FILE)
    root = tree.getroot()
    vehicles = list(root.iter("vehicle"))
    if not vehicles:
        print("  [WARN] No vehicle entries found")
        return False

    mix = (["car_blue"] * 20 + ["car_white"] * 18 + ["car_silver"] * 16 +
           ["car_red"] * 14 + ["car_yellow"] * 10 + ["auto"] * 16 +
           ["bike"] * 18 + ["truck"] * 5 + ["bus"] * 3)

    counts = {}
    for i, veh in enumerate(vehicles):
        new_type = mix[i % len(mix)]
        veh.set("type", new_type)
        counts[new_type] = counts.get(new_type, 0) + 1

    ET.indent(tree, space="    ")
    tree.write(str(ROU_FILE), encoding="unicode", xml_declaration=True)

    print("  [OK] Vehicle mix redistributed:")
    for k in ["car_blue", "car_white", "car_silver", "car_red", "car_yellow", "auto", "bike", "truck", "bus"]:
        print(f"    - {k:<10} : {counts.get(k, 0)}")
    return True


def densify_routes(target_multiplier=2.4):
    print()
    print("=" * 52)
    print("  FIX 4: increase baseline traffic demand")
    print("=" * 52)

    if not ROU_FILE.exists():
        print("  [ERROR] city.rou.xml not found")
        return False

    tree = ET.parse(ROU_FILE)
    root = tree.getroot()
    vehicles = [v for v in root.findall("vehicle")]
    if not vehicles:
        print("  [WARN] No vehicle entries found")
        return False

    original_n = len(vehicles)
    desired_n = int(original_n * target_multiplier)
    extra_needed = max(0, desired_n - original_n)
    if extra_needed == 0:
        print(f"  [OK] Traffic already dense: {original_n} vehicles")
        return True

    insert_at = len(list(root))
    appended = 0
    for i in range(extra_needed):
        src = vehicles[i % original_n]
        dup = copy.deepcopy(src)
        old_id = dup.get("id", f"veh{i}")
        base_depart = float(dup.get("depart", "0"))
        dup.set("id", f"{old_id}_x{i+1}")
        dup.set("depart", f"{base_depart + 5 + (i % 240) * 0.9:.2f}")
        dup.set("departLane", "best")
        dup.set("departSpeed", "max")
        root.insert(insert_at + appended, dup)
        appended += 1

    ET.indent(tree, space="    ")
    tree.write(str(ROU_FILE), encoding="unicode", xml_declaration=True)
    print(f"  [OK] Vehicles increased from {original_n} to {original_n + appended}")
    return True


def main():
    print()
    print("=" * 52)
    print("  Delhi AQI SUMO - Fix Script")
    print("=" * 52)

    ok1 = fix_vtypes_in_rou()
    ok2 = fix_config()
    ok3 = diversify_vehicle_assignments()
    ok4 = densify_routes()

    print()
    if ok1 and ok2 and ok3 and ok4:
        print("=" * 52)
        print("  ALL FIXES APPLIED")
        print("=" * 52)
        print()
        print("  Run:")
        print("    python fix_routes.py")
        print("    python run_simulation.py --both --duration 600")
        print()
    else:
        print("  Some fixes failed. Check messages above.")
        print("  If city files are missing, run: python setup_map.py")


if __name__ == "__main__":
    main()

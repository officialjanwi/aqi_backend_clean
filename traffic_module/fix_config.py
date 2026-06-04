"""
fix_config.py
==============
Run this if SUMO crashes immediately on startup.

It rewrites city/city.sumocfg with the correct settings
WITHOUT re-downloading or rebuilding the network.

Usage:
    python fix_config.py
"""

import xml.etree.ElementTree as ET
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CITY_DIR = BASE_DIR / "city"

CFG_FILE  = CITY_DIR / "city.sumocfg"
NET_FILE  = CITY_DIR / "city.net.xml"
ROU_FILE  = CITY_DIR / "city.rou.xml"
ADD_FILE  = CITY_DIR / "city.add.xml"
POLY_FILE = CITY_DIR / "city.poly.xml"
VIEW_FILE = CITY_DIR / "city.view.xml"


def fix():
    print()
    print("=" * 52)
    print("  Fixing city/city.sumocfg")
    print("=" * 52)
    print()

    # Check required files exist
    for f in [NET_FILE, ROU_FILE]:
        if not f.exists():
            print(f"  [ERROR] {f.name} not found.")
            print("  Run setup_map.py first.")
            return False
        print(f"  [OK] {f.name}  ({f.stat().st_size//1024} KB)")

    # Build additional-files list
    add_files = "city.add.xml"
    if POLY_FILE.exists():
        add_files += ",city.poly.xml"
        print(f"  [OK] city.poly.xml (buildings included)")

    # Write correct config
    # KEY FIX: route-files has ONLY city.rou.xml (single file)
    # duarouter already embedded vType defs inside city.rou.xml
    cfg = ET.Element("configuration")

    inp = ET.SubElement(cfg, "input")
    ET.SubElement(inp, "net-file",         {"value": "city.net.xml"})
    ET.SubElement(inp, "route-files",      {"value": "city.rou.xml"})    # SINGLE FILE ONLY
    ET.SubElement(inp, "additional-files", {"value": add_files})

    gui_s = ET.SubElement(cfg, "gui_only")
    ET.SubElement(gui_s, "gui-settings-file", {"value": "city.view.xml"})
    ET.SubElement(gui_s, "start",             {"value": "true"})
    ET.SubElement(gui_s, "quit-on-end",       {"value": "true"})

    tim = ET.SubElement(cfg, "time")
    ET.SubElement(tim, "begin",       {"value": "0"})
    ET.SubElement(tim, "end",         {"value": "-1"})
    ET.SubElement(tim, "step-length", {"value": "1"})

    proc = ET.SubElement(cfg, "processing")
    ET.SubElement(proc, "time-to-teleport",          {"value": "300"})
    ET.SubElement(proc, "time-to-teleport.highways", {"value": "0"})
    ET.SubElement(proc, "collision.action",          {"value": "warn"})
    ET.SubElement(proc, "ignore-route-errors",       {"value": "true"})
    ET.SubElement(proc, "max-depart-delay",          {"value": "60"})

    rep = ET.SubElement(cfg, "report")
    ET.SubElement(rep, "no-step-log", {"value": "true"})
    ET.SubElement(rep, "no-warnings", {"value": "true"})

    tree = ET.ElementTree(cfg)
    ET.indent(tree, space="    ")
    tree.write(str(CFG_FILE), encoding="unicode", xml_declaration=True)
    print(f"  [OK] city.sumocfg rewritten (fixed)")

    # Also fix GUI view if needed
    if not VIEW_FILE.exists():
        # Read network bounds
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
                    net_w  = parts[2] - parts[0]
                    net_h  = parts[3] - parts[1]
                    zoom   = round(900.0 / max(net_w, net_h) * 100, 1)
        except Exception:
            pass

        view = f"""<viewsettings>
    <scheme name="real">
        <background backgroundColor="80,85,80" showGrid="0"/>
        <edges laneShowBorders="1" showLinkDecals="1" hideConnectors="0">
            <colorScheme name="by selection">
                <entry color="160,155,140" name="unselected"/>
                <entry color="0,102,204"   name="selected"/>
            </colorScheme>
        </edges>
        <vehicles vehicleQuality="2" showBlinker="1"
                  vehicleSize.minSize="1" vehicleSize.exaggeration="3">
            <colorScheme name="given/assigned vehicle color"/>
        </vehicles>
        <junctions drawShape="1">
            <colorScheme name="uniform">
                <entry color="60,60,60"/>
            </colorScheme>
        </junctions>
        <polys polyType="1"/>
    </scheme>
    <delay value="50"/>
    <viewport zoom="{zoom}" x="{net_cx:.2f}" y="{net_cy:.2f}"/>
</viewsettings>"""
        VIEW_FILE.write_text(view, encoding="utf-8")
        print(f"  [OK] city.view.xml created")
    else:
        print(f"  [OK] city.view.xml exists")

    print()
    print("  Config fixed! Now run:")
    print()
    print("    python run_simulation.py --both --duration 600")
    print()
    return True


if __name__ == "__main__":
    fix()

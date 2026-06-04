"""
setup_map.py  -  ONE-TIME SETUP
Run this ONCE before anything else.

Steps:
  1. Find SUMO installation
  2. Download OSM data for Dhyan Chand / India Gate area
  3. Build road network (no traffic lights)
  4. Build building polygons (real look)
  5. Write vehicle type file (all Delhi vehicle types + colours)
  6. Generate random trips per vehicle type
  7. Route trips with duarouter
  8. Write SUMO config and GUI settings

Usage:
    python setup_map.py
"""

import os, sys, shutil, subprocess, urllib.request, random
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_DIR  = Path(__file__).resolve().parent
CITY_DIR  = BASE_DIR / "city"
CITY_DIR.mkdir(exist_ok=True)

OSM_FILE   = CITY_DIR / "map.osm"
NET_FILE   = CITY_DIR / "city.net.xml"
POLY_FILE  = CITY_DIR / "city.poly.xml"
VTYPE_FILE = CITY_DIR / "city.vtype.xml"
TRIPS_FILE = CITY_DIR / "city.trips.xml"
ROU_FILE   = CITY_DIR / "city.rou.xml"
ADD_FILE   = CITY_DIR / "city.add.xml"
CFG_FILE   = CITY_DIR / "city.sumocfg"
VIEW_FILE  = CITY_DIR / "city.view.xml"

# Dhyan Chand / India Gate / Rajpath bounding box
BBOX = dict(south=28.6100, north=28.6260, west=77.2260, east=77.2460)


def banner(msg): print(f"\n{'='*60}\n  {msg}\n{'='*60}")
def ok(msg):     print(f"  [OK]  {msg}")
def err(msg):    print(f"  [ERR] {msg}")
def info(msg):   print(f"  ...   {msg}")


def find_sumo():
    banner("STEP 1 - Finding SUMO")
    sumo_home = os.environ.get("SUMO_HOME", "")

    # Common Windows install paths
    candidates = [
        sumo_home,
        r"C:\Program Files (x86)\Eclipse\Sumo",
        r"C:\Program Files\Eclipse\Sumo",
        r"C:\Sumo",
    ]

    found_home = None
    for c in candidates:
        if c and Path(c).exists():
            found_home = c
            break

    if not found_home:
        err("SUMO not found!")
        err('Fix: setx SUMO_HOME "C:\\Program Files (x86)\\Eclipse\\Sumo"')
        err("Then open a NEW command prompt and run again.")
        sys.exit(1)

    ok(f"SUMO found at: {found_home}")

    # Find executables
    exes = {}
    for name in ["sumo", "sumo-gui", "netconvert", "duarouter", "polyconvert"]:
        # Check PATH first
        found = shutil.which(name) or shutil.which(name + ".exe")
        if not found:
            # Check SUMO_HOME/bin
            p = Path(found_home) / "bin" / (name + ".exe")
            if p.exists():
                found = str(p)
        if found:
            exes[name] = found
            ok(f"{name}: {found}")
        else:
            err(f"{name} not found - add {found_home}\\bin to PATH")
            if name in ("sumo", "netconvert", "duarouter"):
                sys.exit(1)

    # Find randomTrips.py
    rt = Path(found_home) / "tools" / "randomTrips.py"
    if rt.exists():
        exes["randomTrips"] = str(rt)
        ok(f"randomTrips.py: {rt}")
    else:
        err(f"randomTrips.py not found at {rt}")
        sys.exit(1)

    # Add tools to Python path for traci
    tools_path = str(Path(found_home) / "tools")
    if tools_path not in sys.path:
        sys.path.insert(0, tools_path)
    ok(f"tools path: {tools_path}")

    return found_home, exes


def step_download_osm():
    banner("STEP 2 - Downloading OSM map (Dhyan Chand / India Gate)")
    if OSM_FILE.exists() and OSM_FILE.stat().st_size > 100_000:
        ok(f"Already downloaded ({OSM_FILE.stat().st_size // 1024} KB) - skipping")
        return
    url = (f"https://overpass-api.de/api/map"
           f"?bbox={BBOX['west']},{BBOX['south']},{BBOX['east']},{BBOX['north']}")
    info("Contacting Overpass API...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SUMO-Delhi-AQI/1.0"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        OSM_FILE.write_bytes(data)
        ok(f"Downloaded {len(data)//1024} KB -> {OSM_FILE.name}")
    except Exception as e:
        err(f"Download failed: {e}")
        sys.exit(1)


def step_build_network(sumo_home, exes):
    banner("STEP 3 - Building road network (no traffic lights)")
    typemap = Path(sumo_home) / "data" / "typemap" / "osmNetconvert.typ.xml"
    type_args = ["--type-files", str(typemap)] if typemap.exists() else []

    cmd = [
        exes["netconvert"],
        "--osm-files",          str(OSM_FILE),
        "--output-file",        str(NET_FILE),
        "--keep-edges.by-type",
        ("highway.motorway,highway.motorway_link,"
         "highway.trunk,highway.trunk_link,"
         "highway.primary,highway.primary_link,"
         "highway.secondary,highway.secondary_link,"
         "highway.tertiary,highway.tertiary_link,"
         "highway.residential,highway.unclassified"),
        "--tls.discard-loaded", "true",
        "--tls.discard-simple", "true",
        "--geometry.remove",    "true",
        "--roundabouts.guess",  "true",
        "--junctions.join",     "true",
        "--junctions.join-dist","15",
        "--no-turnarounds",     "true",
        "--default.lanewidth",  "3.5",
        "--default.speed",      "13.89",
        "--output.street-names","true",
        "--error-log",          str(CITY_DIR / "netconvert_log.txt"),
    ] + type_args

    info("Running netconvert...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if not NET_FILE.exists() or r.returncode != 0:
        err("netconvert failed!")
        print(r.stderr[-1000:])
        sys.exit(1)
    ok(f"Network built: {NET_FILE.stat().st_size//1024} KB")


def step_build_polygons(sumo_home, exes):
    banner("STEP 4 - Building polygons (buildings for real look)")
    if "polyconvert" not in exes:
        info("polyconvert not found - skipping buildings")
        return
    typemap = Path(sumo_home) / "data" / "typemap" / "osmPolyconvert.typ.xml"
    if not typemap.exists():
        info("osmPolyconvert.typ.xml not found - skipping buildings")
        return
    cmd = [
        exes["polyconvert"],
        "--net-file",  str(NET_FILE),
        "--osm-files", str(OSM_FILE),
        "--type-file", str(typemap),
        "-o",          str(POLY_FILE),
    ]
    info("Running polyconvert...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if POLY_FILE.exists():
        ok(f"Buildings/polygons: {POLY_FILE.stat().st_size//1024} KB")
    else:
        info("polyconvert produced no output - continuing without buildings")


def step_write_vtypes():
    banner("STEP 5 - Writing vehicle types (Delhi fleet)")
    root = ET.Element("routes")

    # Delhi vehicle types with correct colours, shapes, and explicit emission classes
    types = [
        # (id, vClass, guiShape, length, width, maxSpeed, accel, decel, color, emissionClass)
        ("car_blue",   "passenger", "passenger",      4.5, 1.8, 13.89, 2.6, 4.5, "0.27,0.55,1.0",  "HBEFA3/PC_G_EU4"),
        ("car_white",  "passenger", "passenger",      4.5, 1.8, 13.89, 2.6, 4.5, "0.92,0.92,0.92", "HBEFA3/PC_G_EU4"),
        ("car_silver", "passenger", "passenger",      4.5, 1.8, 13.89, 2.6, 4.5, "0.68,0.71,0.75", "HBEFA3/PC_G_EU4"),
        ("car_red",    "passenger", "passenger",      4.5, 1.8, 13.89, 2.6, 4.5, "0.85,0.18,0.18", "HBEFA3/PC_G_EU4"),
        ("car_yellow", "passenger", "passenger",      4.5, 1.8, 13.89, 2.6, 4.5, "0.95,0.80,0.10", "HBEFA3/PC_G_EU4"),
        ("truck",      "truck",     "truck",         12.0, 2.5,  8.33, 1.2, 3.5, "1.0,0.45,0.05", "HBEFA3/HDV_D_EU4"),
        ("bus",        "bus",       "bus",           12.0, 2.5,  8.33, 1.0, 3.0, "0.60,0.24,0.78", "HBEFA3/Bus"),
        ("auto",       "passenger", "passenger/van",  3.2, 1.5, 11.11, 2.8, 4.8, "0.12,0.78,0.55", "HBEFA3/LDV_G_EU3"),
        ("bike",       "motorcycle","motorcycle",     2.0, 0.8, 16.67, 3.5, 5.5, "0.95,0.42,0.72", "HBEFA3/MC_4S_EU3"),
    ]

    for (tid, vcls, gshape, ln, wid, ms, ac, dc, col, eclass) in types:
        ET.SubElement(root, "vType", {
            "id":             tid,
            "vClass":         vcls,
            "guiShape":       gshape,
            "length":         str(ln),
            "width":          str(wid),
            "maxSpeed":       str(ms),
            "accel":          str(ac),
            "decel":          str(dc),
            "emergencyDecel": str(dc + 1.5),
            "sigma":          "0.5",
            "color":          col,
            "carFollowModel": "IDM",
            "minGap":         "2.5",
            "lcStrategic":    "1.0",
            "lcCooperative":  "0.5",
            "speedFactor":    "normc(1,0.1,0.7,1.3)",
            "emissionClass":  eclass,
        })

    tree = ET.ElementTree(root)
    ET.indent(tree, space="    ")
    tree.write(str(VTYPE_FILE), encoding="unicode", xml_declaration=True)
    ok(f"Vehicle types: {len(types)} types written")


def step_generate_trips(exes):
    banner("STEP 6 - Generating trips (Delhi traffic demand)")

    # Remove stale files
    for f in list(CITY_DIR.glob("trips_*.xml")) + [TRIPS_FILE, ROU_FILE]:
        if Path(f).exists():
            Path(f).unlink()

    py = sys.executable
    rt = exes["randomTrips"]

    # Each vehicle type gets its own seed so all colours appear
    fleet = [
        # Smaller period = more vehicles. This version is intentionally denser
        # so Phase 1 looks polluted and crowded before controls are applied.
        # (vtype,       period, end,  fringe, seed)
        ("car_blue",    0.70,  3600,  6,     42),
        ("car_white",   0.78,  3600,  6,     43),
        ("car_silver",  0.88,  3600,  6,     44),
        ("car_red",     1.05,  3600,  6,     45),
        ("car_yellow",  1.30,  3600,  6,     46),
        ("truck",       3.20,  3600,  8,     47),
        ("bus",         4.50,  3600,  8,     48),
        ("auto",        0.95,  3600,  6,     49),
        ("bike",        1.10,  3600,  5,     50),
    ]

    trip_files = []
    for (vtype, period, end, fringe, seed) in fleet:
        out = CITY_DIR / f"trips_{vtype}.xml"
        cmd = [
            py, rt,
            "-n", str(NET_FILE),
            "-o", str(out),
            "--vtype",         vtype,
            "--prefix",        f"{vtype}.",
            "--period",        str(period),
            "--end",           str(end),
            "--fringe-factor", str(fringe),
            "--random-depart",
            "--allow-fringe",
            "--seed",          str(seed),
        ]
        info(f"Trips for {vtype}...")
        r = subprocess.run(cmd, capture_output=True, text=True)
        if out.exists() and out.stat().st_size > 100:
            ok(f"  {vtype}: {out.stat().st_size//1024} KB")
            trip_files.append(out)
        else:
            err(f"  {vtype} failed: {r.stderr[-200:]}")

    if not trip_files:
        err("No trip files generated!")
        sys.exit(1)

    # Merge all trip files
    info("Merging trip files...")
    merged = ET.Element("routes")
    for tf in trip_files:
        try:
            tree = ET.parse(tf)
            for child in tree.getroot():
                merged.append(child)
        except Exception as e:
            info(f"Warning: {tf.name}: {e}")

    tree = ET.ElementTree(merged)
    ET.indent(tree, space="    ")
    tree.write(str(TRIPS_FILE), encoding="unicode", xml_declaration=True)

    for tf in trip_files:
        tf.unlink(missing_ok=True)

    ok(f"Merged trips: {TRIPS_FILE.stat().st_size//1024} KB")


def step_build_routes(exes):
    banner("STEP 7 - Building routes (duarouter)")
    cmd = [
        exes["duarouter"],
        "--net-file",         str(NET_FILE),
        "--route-files",      str(TRIPS_FILE),
        "--additional-files", str(VTYPE_FILE),
        "--output-file",      str(ROU_FILE),
        "--ignore-errors",    "true",
        "--no-warnings",      "true",
        "--no-step-log",      "true",
        "--repair",           "true",
        "--repair.from",      "true",
        "--repair.to",        "true",
    ]
    info("Running duarouter (this takes 1-3 minutes)...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if not ROU_FILE.exists():
        err("duarouter failed!")
        print("STDOUT:", r.stdout[-500:])
        print("STDERR:", r.stderr[-500:])
        sys.exit(1)

    # Count vehicles and verify vTypes are present
    try:
        tree = ET.parse(ROU_FILE)
        root = tree.getroot()
        n = sum(1 for _ in root.iter("vehicle"))
        ok(f"Routes built: {n} vehicles, {ROU_FILE.stat().st_size//1024} KB")

        # Check if vType defs made it into the route file
        vtypes_in_rou = {v.get("id","") for v in root.iter("vType")}
        expected = {"car_blue","car_white","car_silver","car_red","car_yellow",
                    "truck","bus","auto","bike"}
        missing  = expected - vtypes_in_rou

        if missing:
            info(f"vTypes missing from rou.xml: {missing}  - injecting from vtype.xml")
            _inject_vtypes_into_rou(root, tree)
        else:
            ok(f"All 9 vehicle types present in route file: {sorted(vtypes_in_rou)}")
    except Exception as e:
        info(f"Could not verify route file: {e}")


def _inject_vtypes_into_rou(root, tree):
    """Inject vType definitions from city.vtype.xml into city.rou.xml."""
    try:
        vtype_root = ET.parse(VTYPE_FILE).getroot()
        # Insert vType elements at the start of the routes element
        existing_ids = {v.get("id","") for v in root.iter("vType")}
        inserted = 0
        # Insert before first non-vType child
        insert_idx = 0
        for vt in vtype_root.iter("vType"):
            vid = vt.get("id","")
            if vid and vid not in existing_ids:
                root.insert(insert_idx, vt)
                insert_idx += 1
                inserted += 1
        if inserted > 0:
            ET.indent(tree, space="    ")
            tree.write(str(ROU_FILE), encoding="unicode", xml_declaration=True)
            ok(f"Injected {inserted} vType definitions into city.rou.xml")
    except Exception as e:
        info(f"vType injection failed: {e}")


def step_write_config():
    banner("STEP 8 - Writing SUMO config and GUI settings")

    # Additional output file
    add = ET.Element("additional")
    ET.SubElement(add, "edgeData", {
        "id": "edge_em", "type": "emissions",
        "file": "edge_emissions.xml", "period": "60",
        "excludeEmpty": "true",
    })
    tree = ET.ElementTree(add)
    ET.indent(tree, space="    ")
    tree.write(str(ADD_FILE), encoding="unicode", xml_declaration=True)

    # SUMO config
    # IMPORTANT: vtype file listed in route-files BEFORE city.rou.xml
    additional = "city.add.xml"
    if POLY_FILE.exists():
        additional += " city.poly.xml"

    cfg = ET.Element("configuration")
    inp = ET.SubElement(cfg, "input")
    ET.SubElement(inp, "net-file",         {"value": "city.net.xml"})
    ET.SubElement(inp, "route-files",      {"value": "city.rou.xml"})
    ET.SubElement(inp, "additional-files", {"value": additional})

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
    ok(f"SUMO config written")

    # GUI view settings — read network bounds for correct viewport
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
                info(f"Network centre: ({net_cx:.1f}, {net_cy:.1f}), zoom={zoom}")
    except Exception as e:
        info(f"Could not read network bounds: {e}")

    view = f"""<viewsettings>
    <scheme name="real">
        <background backgroundColor="80,85,80" showGrid="0"/>
        <edges laneShowBorders="1" showLinkDecals="1" hideConnectors="0">
            <colorScheme name="by selection">
                <entry color="160,155,140" name="unselected"/>
                <entry color="0,102,204"   name="selected"/>
            </colorScheme>
        </edges>
        <vehicles vehicleQuality="3" showBlinker="1"
                  vehicleSize.minSize="1" vehicleSize.exaggeration="4">
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
    ok("GUI settings written")


def main():
    print()
    print("=" * 60)
    print("  Delhi AQI Simulation - SUMO Setup")
    print("  Area: Dhyan Chand Nagar / India Gate / Rajpath")
    print("=" * 60)

    sumo_home, exes = find_sumo()
    step_download_osm()
    step_build_network(sumo_home, exes)
    step_build_polygons(sumo_home, exes)
    step_write_vtypes()
    step_generate_trips(exes)
    step_build_routes(exes)
    step_write_config()

    print()
    print("=" * 60)
    print("  SETUP COMPLETE!")
    print("=" * 60)
    print()
    print("  Now run the simulation:")
    print()
    print("    python run_simulation.py --both --duration 600")
    print()


if __name__ == "__main__":
    main()

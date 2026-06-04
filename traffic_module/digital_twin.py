"""
digital_twin.py  -  Delhi AQI Digital Twin
===========================================
Connects SUMO simulation to real-world AQI sensor data
from the ITO monitoring station (nearest to Dhyan Chand area).

What makes this a Digital Twin:
  1. REAL AQI data  -> polled from WAQI API every 60 steps
  2. Vehicle density calibrated to mirror real traffic load
  3. Solutions auto-trigger when real AQI crosses threshold
  4. Terminal dashboard: real vs simulated AQI side by side
  5. Chart shows sync quality between real world and simulation

Usage:
  python digital_twin.py --duration 600
  python digital_twin.py --duration 600 --no-gui
  python digital_twin.py --duration 600 --port 8815

Connection: subprocess.Popen + traci.init (proven on Windows SUMO 1.26)
"""

import os, sys, shutil, subprocess, time, datetime
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent
CITY_DIR   = BASE_DIR / "city"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# Add SUMO tools to Python path
def _add_tools():
    for c in [os.environ.get("SUMO_HOME",""),
              r"C:\Program Files (x86)\Eclipse\Sumo",
              r"C:\Program Files\Eclipse\Sumo"]:
        if c:
            t = Path(c) / "tools"
            if t.exists():
                if str(t) not in sys.path: sys.path.insert(0, str(t))
                return str(c)
    return ""

SUMO_HOME = _add_tools()

try:
    import traci
    import traci.exceptions
except ImportError:
    print("[ERROR] Cannot import traci. Install SUMO and set SUMO_HOME.")
    sys.exit(1)

from emission_model import POLLUTANTS, calc_emission
from aqi_module import fetch_aqi, aqi_label, get_active_solutions, SOLUTION_LABELS

AQI_POLL_EVERY = 60
SOL_THRESHOLD  = 200
SPEED_CAP_MS   = 50.0 / 3.6
SPEED_MIN_MS   = 15.0 / 3.6
HEAVY = {"truck", "bus"}
VTYPE_MAP = {
    "car_blue":"car","car_white":"car","car_silver":"car",
    "car_red":"car","car_yellow":"car","car":"car",
    "truck":"truck","bus":"bus","auto":"auto","bike":"bike",
}


@dataclass
class TwinSnap:
    step:int; real_aqi:float; sim_aqi:float; n_vehicles:int
    avg_speed:float; controls_on:bool
    CO2:float; CO:float; NO2:float; HC:float; PM25:float


def _ctype(vid_str):
    vt = vid_str.lower()
    if vt in VTYPE_MAP: return VTYPE_MAP[vt]
    for k in ("truck","bus","auto","bike","car"):
        if k in vt: return VTYPE_MAP.get(k,"car")
    return "car"


def _aqi(per_veh, n_veh, baseline_n):
    pm25=per_veh.get("PM25",0); no2=per_veh.get("NO2",0)
    co=per_veh.get("CO",0); hc=per_veh.get("HC",0); co2=per_veh.get("CO2",0)
    intensity = pm25/0.06*250 + no2/2.0*120 + co/16.0*80 + hc/2.5*40 + co2/190.0*10
    density   = max(0.1, min(2.0, n_veh/baseline_n)) if baseline_n > 0 else 1.0
    return round(min(max(intensity*density,0),500),1)


def _find_bin(gui):
    name = "sumo-gui" if gui else "sumo"
    found = shutil.which(name) or shutil.which(name+".exe")
    if found: return found
    for loc in [SUMO_HOME,
                r"C:\Program Files (x86)\Eclipse\Sumo",
                r"C:\Program Files\Eclipse\Sumo"]:
        if loc:
            p = Path(loc)/"bin"/(name+".exe")
            if p.exists(): return str(p)
    print(f"[ERROR] Cannot find {name}"); sys.exit(1)


def _dashboard(step, real_aqi, sim_aqi, n_veh, avg_spd, solutions, em, trig):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    bar_r = "█" * min(int(real_aqi/20), 25)
    bar_s = "█" * min(int(sim_aqi/20),  25)
    diff  = sim_aqi - real_aqi
    print()
    print(f"  +--- DELHI AQI DIGITAL TWIN --- {'CONTROLS ON' if solutions else 'BASELINE'} --- [{now}]")
    print(f"  | Step:{step}  Vehicles:{n_veh}  Speed:{avg_spd:.1f}km/h")
    print(f"  |")
    print(f"  | REAL AQI (ITO sensor) : {real_aqi:>6.1f}  {aqi_label(real_aqi):<12}  {bar_r}")
    print(f"  | SIM  AQI (SUMO calc)  : {sim_aqi:>6.1f}  {aqi_label(sim_aqi):<12}  {bar_s}")
    print(f"  | Sync delta            : {diff:>+6.1f}")
    print(f"  | Emissions g/km/veh    : CO2={em.get('CO2',0):.1f}  CO={em.get('CO',0):.2f}  NO2={em.get('NO2',0):.3f}  PM25={em.get('PM25',0):.4f}")
    if solutions:
        print(f"  | Controls (triggered at AQI {trig:.0f}):")
        for s in solutions: print(f"  |   > {SOLUTION_LABELS.get(s,s)}")
    print(f"  +------------------------------------------------------------+")
    print()


def run_digital_twin(duration=None, gui=True, port=8813):
    cfg = CITY_DIR / "city.sumocfg"
    if not cfg.exists():
        print("[ERROR] city.sumocfg not found. Run setup_map.py first.")
        sys.exit(1)

    print()
    print("="*62)
    print("  DELHI AQI DIGITAL TWIN")
    print(f"  Controls auto-trigger when real AQI > {SOL_THRESHOLD}")
    print("="*62)

    print("\n  Fetching live AQI from ITO station...")
    aqi_data = fetch_aqi("ITO", "High")
    real_aqi = aqi_data["aqi"]
    solutions = get_active_solutions(real_aqi) if real_aqi > SOL_THRESHOLD else []
    trig_at   = real_aqi if solutions else 0.0

    print(f"  AQI: {real_aqi:.1f} ({aqi_data['label']}) [{aqi_data['source']}]")
    print(f"  Mode: {'CONTROLS ACTIVE' if solutions else 'BASELINE (until AQI > '+str(SOL_THRESHOLD)+')'}")
    print()

    binary = _find_bin(gui)
    cmd = [binary, "-c", str(cfg), "--remote-port", str(port),
           "--no-warnings", "true", "--no-step-log", "true"]
    if gui: cmd += ["--start", "true"]

    print(f"  Launching SUMO on port {port}...")
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception as e:
        print(f"  [ERROR] Cannot launch SUMO: {e}"); sys.exit(1)

    print("  Connecting (up to 30s)...")
    connected = False
    for i in range(30):
        time.sleep(1)
        if proc.poll() is not None:
            _, se = proc.communicate()
            print(f"  [ERROR] SUMO crashed: {se.decode('utf-8',errors='ignore')[-400:]}")
            sys.exit(1)
        try:
            traci.init(port); connected = True
            print(f"  Connected after {i+1}s!"); break
        except Exception:
            if i % 5 == 4: print(f"  Waiting... ({i+1}s)")

    if not connected:
        proc.terminate()
        print("  [ERROR] Could not connect. Try --port 8815")
        sys.exit(1)

    history=[]; step=0; rerouted=set()
    n_sum=0.0; n_count=0; baseline_n=0.0

    print(f"\n  {'Step':>6}  {'RealAQI':>8}  {'SimAQI':>7}  {'Vehs':>5}  {'km/h':>6}  Mode")
    print(f"  {'-'*50}")

    try:
        while traci.simulation.getMinExpectedNumber() > 0:
            if duration is not None and step >= duration: break
            traci.simulationStep(); step += 1

            # Poll real AQI
            if step % AQI_POLL_EVERY == 0:
                fresh = fetch_aqi("ITO","High"); real_aqi = fresh["aqi"]
                new_s = get_active_solutions(real_aqi) if real_aqi > SOL_THRESHOLD else []
                if new_s and not solutions:
                    solutions = new_s; trig_at = real_aqi
                    print(f"\n  *** AQI {real_aqi:.0f} - ACTIVATING CONTROLS ***")
                    for s in solutions: print(f"      > {SOLUTION_LABELS.get(s,s)}")
                    print()
                elif not new_s and solutions and real_aqi < SOL_THRESHOLD - 30:
                    print(f"\n  *** AQI {real_aqi:.0f} - DEACTIVATING controls ***\n")
                    solutions = []; trig_at = 0.0

            # Speed cap
            if solutions and "speed_harmonization" in solutions and step % 10 == 0:
                for eid in traci.edge.getIDList():
                    if not eid.startswith(":"):
                        try: traci.edge.setMaxSpeed(eid, SPEED_CAP_MS)
                        except Exception: pass

            # Calibrate density
            if step % 30 == 0:
                target  = int(real_aqi/500*150 + 30)
                current = len(traci.vehicle.getIDList())
                scale   = 1.3 if current < target*0.7 else (0.8 if current > target*1.3 else 1.0)
                try: traci.simulation.setScale(scale)
                except Exception: pass

            vids=traci.vehicle.getIDList(); n=len(vids)
            spds=[]; ems={p:[] for p in POLLUTANTS}

            for vid in vids:
                try:
                    ct = _ctype(traci.vehicle.getTypeID(vid))
                    if solutions and "heavy_vehicle_ban" in solutions and ct in HEAVY:
                        traci.vehicle.remove(vid); continue
                    spd = traci.vehicle.getSpeed(vid)
                    if solutions and "idling_restriction" in solutions and 0.1<spd<SPEED_MIN_MS:
                        traci.vehicle.setSpeed(vid, SPEED_MIN_MS); spd=SPEED_MIN_MS
                    if solutions and "rerouting" in solutions and vid not in rerouted:
                        if hash(vid)%10<3:
                            try: traci.vehicle.rerouteTraveltime(vid)
                            except Exception: pass
                        rerouted.add(vid)
                    spds.append(spd)
                    spd_kmh = max(5.0, spd*3.6)
                    for p in POLLUTANTS: ems[p].append(calc_emission(p,ct,spd_kmh))
                except Exception: continue

            if not solutions and n>0:
                n_sum+=n; n_count+=1; baseline_n=n_sum/n_count

            if step%30==0 and ems["CO2"]:
                nv=len(ems["CO2"])
                pv={p:sum(ems[p])/nv for p in POLLUTANTS}
                avg_spd=(sum(spds)/len(spds)*3.6) if spds else 0.0
                sim_aqi=_aqi(pv, nv, baseline_n)
                history.append(TwinSnap(
                    step=step, real_aqi=real_aqi, sim_aqi=sim_aqi,
                    n_vehicles=nv, avg_speed=avg_spd,
                    controls_on=bool(solutions), **pv
                ))
                mode="CTRL" if solutions else "base"
                print(f"  {step:>6}  {real_aqi:>8.1f}  {sim_aqi:>7.1f}  {nv:>5}  {avg_spd:>6.1f}  {mode}")

            if step%150==0 and ems["CO2"]:
                nv=len(ems["CO2"])
                pv={p:sum(ems[p])/nv for p in POLLUTANTS}
                avg_spd=(sum(spds)/len(spds)*3.6) if spds else 0.0
                sim_aqi=_aqi(pv, nv, baseline_n)
                _dashboard(step, real_aqi, sim_aqi, n, avg_spd, solutions, pv, trig_at)

    except traci.exceptions.FatalTraCIError:
        print("  SUMO window closed.")
    except Exception as exc:
        print(f"  Ended: {exc}")
    finally:
        try: traci.close()
        except Exception: pass
        try: proc.terminate()
        except Exception: pass

    _save_chart(history)


def _save_chart(history):
    if not history: print("  No data."); return
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
    except ImportError:
        print("  pip install matplotlib"); return

    BG="#0f0f1e"; AX="#12122a"
    def style(ax,title):
        ax.set_facecolor(AX); ax.set_title(title,color="white",fontsize=10,pad=8)
        ax.tick_params(colors="white",labelsize=9)
        ax.spines[["top","right"]].set_visible(False)
        ax.spines[["left","bottom"]].set_color("#3a3a5a")
        ax.xaxis.label.set_color("white"); ax.yaxis.label.set_color("white")
        ax.yaxis.grid(True,color="#2a2a4a",linewidth=0.6)

    steps=[h.step for h in history]; r=[h.real_aqi for h in history]
    s=[h.sim_aqi for h in history]; sp=[h.avg_speed for h in history]
    n=[h.n_vehicles for h in history]; pm=[h.PM25 for h in history]
    no2=[h.NO2 for h in history]
    ctrl=next((h.step for h in history if h.controls_on), None)

    fig=plt.figure(figsize=(16,10)); fig.patch.set_facecolor(BG)
    fig.suptitle("Delhi AQI Digital Twin — Real Sensor + SUMO Sync\nMajor Dhyan Chand Nagar / India Gate",
                 color="white",fontsize=13,fontweight="bold",y=0.99)
    gs=gridspec.GridSpec(2,2,figure=fig,hspace=0.42,wspace=0.30)

    ax1=fig.add_subplot(gs[0,0])
    ax1.plot(steps,r,color="#facc15",lw=2,label="Real AQI (ITO)")
    ax1.plot(steps,s,color="#34d399",lw=2,label="Sim AQI (SUMO)")
    ax1.fill_between(steps,r,s,alpha=0.08,color="#60a5fa")
    if ctrl: ax1.axvline(ctrl,color="#ef4444",lw=1.5,ls="--",alpha=0.8,label="Controls on")
    ax1.set_xlabel("Step"); ax1.set_ylabel("AQI")
    ax1.legend(facecolor=AX,edgecolor="#3a3a5a",labelcolor="white",fontsize=8)
    style(ax1,"Real vs Sim AQI — Digital Twin Sync")

    ax2=fig.add_subplot(gs[0,1])
    ax2.plot(steps,n,color="#60a5fa",lw=2)
    ax2.fill_between(steps,n,alpha=0.15,color="#60a5fa")
    if ctrl: ax2.axvline(ctrl,color="#ef4444",lw=1.5,ls="--",alpha=0.8)
    ax2.set_xlabel("Step"); ax2.set_ylabel("Vehicles")
    style(ax2,"Vehicle Count (calibrated to real AQI)")

    ax3=fig.add_subplot(gs[1,0])
    ax3.plot(steps,sp,color="#a78bfa",lw=2)
    ax3.fill_between(steps,sp,alpha=0.15,color="#a78bfa")
    ax3.axhline(50,color="#facc15",lw=1,ls="--",alpha=0.7,label="50km/h cap")
    if ctrl: ax3.axvline(ctrl,color="#ef4444",lw=1.5,ls="--",alpha=0.8)
    ax3.set_xlabel("Step"); ax3.set_ylabel("Avg Speed km/h")
    ax3.legend(facecolor=AX,edgecolor="#3a3a5a",labelcolor="white",fontsize=8)
    style(ax3,"Average Network Speed")

    ax4=fig.add_subplot(gs[1,1])
    ax4.plot(steps,pm, color="#ef4444",lw=1.8,label="PM2.5 g/km/veh")
    ax4.plot(steps,no2,color="#f97316",lw=1.8,label="NO2 g/km/veh")
    if ctrl: ax4.axvline(ctrl,color="#facc15",lw=1.5,ls="--",alpha=0.8,label="Controls on")
    ax4.set_xlabel("Step"); ax4.set_ylabel("g/km/vehicle")
    ax4.legend(facecolor=AX,edgecolor="#3a3a5a",labelcolor="white",fontsize=8)
    style(ax4,"PM2.5 + NO2 (key AQI drivers)")

    out=OUTPUT_DIR/"digital_twin_chart.png"
    plt.savefig(str(out),dpi=130,bbox_inches="tight",facecolor=BG); plt.close(fig)
    print(f"\n  Chart: {out}")
    try:
        import os
        if sys.platform.startswith("win"): os.startfile(str(out))
    except Exception: pass


def main():
    import argparse
    ap=argparse.ArgumentParser(description="Delhi AQI Digital Twin")
    ap.add_argument("--duration",type=int,default=None)
    ap.add_argument("--no-gui",action="store_true")
    ap.add_argument("--port",type=int,default=8813)
    args=ap.parse_args()
    run_digital_twin(duration=args.duration,gui=not args.no_gui,port=args.port)

if __name__=="__main__":
    main()

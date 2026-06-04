"""
chart_generator.py
===================
Generates the 4-panel Delhi Comparative AQI Study chart from two PhaseResults.

Panels:
  1. Pollutant emissions bar chart (Phase 1 vs Phase 2)
  2. Improvement % per pollutant
  3. AQI comparison bar + solutions annotation box
  4. AQI over simulation time + solutions legend + activation marker

Output: output/comparison_chart.png  +  output/summary.txt
"""

from pathlib import Path
from emission_model import POLLUTANTS, improvement_percent
from aqi_module     import aqi_label, aqi_color_rgb, SOLUTION_LABELS

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
def save_chart(zone: str, base_aqi: float, solutions: list,
               result1, result2) -> Path:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec
        import numpy as np
    except ImportError:
        print("  [WARNING] matplotlib not installed — chart skipped.")
        print("  pip install matplotlib numpy")
        return None

    before     = result1.avg_emissions
    after      = result2.avg_emissions
    aqi_before = result1.avg_aqi
    aqi_after  = result2.avg_aqi

    if not result1.history:
        print("  [WARNING] Phase 1 has no data — chart may be empty.")
    if not result2.history:
        print("  [WARNING] Phase 2 has no data — chart may be empty.")

    impr       = improvement_percent(before, after)
    total_b    = sum(before.values())
    total_a    = sum(after.values())
    total_impr = round((total_b - total_a) / total_b * 100, 1) if total_b > 0 else 0.0
    aqi_impr   = round((aqi_before - aqi_after) / aqi_before * 100, 1) if aqi_before > 0 else 0.0

    BG_MAIN = "#0f0f1e"
    BG_AX   = "#12122a"

    def style(ax, title):
        ax.set_facecolor(BG_AX)
        ax.set_title(title, color="white", fontsize=10, pad=8)
        ax.tick_params(colors="white", labelsize=9)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color("#3a3a5a")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.yaxis.grid(True, color="#2a2a4a", zorder=0, linewidth=0.6)

    fig = plt.figure(figsize=(16, 10))
    fig.patch.set_facecolor(BG_MAIN)
    aqi_drop  = aqi_before - aqi_after
    if aqi_drop > 0:
        headline = f"AQI ↓ {aqi_drop:.1f} pts  ({aqi_impr:.1f}% IMPROVEMENT) ✓"
        hcolor = "#34d399"
    else:
        headline = f"AQI ↑ {abs(aqi_drop):.1f} pts  (controls increased AQI — check data)"
        hcolor = "#ef4444"
    fig.suptitle(
        f"Delhi AQI Comparative Study — {zone}  (SUMO simulation)\n"
        f"Major Dhyan Chand Nagar / India Gate / Rajpath   {headline}",
        color=hcolor, fontsize=12, fontweight="bold", y=0.99
    )
    gs = gridspec.GridSpec(2, 2, figure=fig, hspace=0.42, wspace=0.30)

    polls = POLLUTANTS
    x     = np.arange(len(polls))
    bw    = 0.35

    # ── Panel 1: Pollutant emissions ─────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, 0])
    bv  = [before[p] for p in polls]
    av  = [after[p]  for p in polls]
    bars1b = ax1.bar(x - bw/2, bv, bw, color="#ef4444", label="Phase 1 — Baseline", zorder=3)
    bars1a = ax1.bar(x + bw/2, av, bw, color="#34d399", label="Phase 2 — AQI Controls", zorder=3)
    ax1.set_xticks(x)
    ax1.set_xticklabels(polls, color="white")
    ax1.set_ylabel("g/km  (fleet average)")
    ax1.legend(facecolor=BG_AX, edgecolor="#3a3a5a", labelcolor="white", fontsize=8)
    y_top = max(max(bv) if bv else 0, max(av) if av else 0, 1.0)
    label_offset = y_top * 0.015
    for bars, values in ((bars1b, bv), (bars1a, av)):
        for bar, val in zip(bars, values):
            ax1.text(bar.get_x() + bar.get_width()/2,
                     bar.get_height() + label_offset,
                     f"{val:.3f}" if val < 10 else f"{val:.1f}",
                     ha="center", va="bottom", color="white", fontsize=7,
                     rotation=90 if val >= 1000 else 0, zorder=5)
    style(ax1, "Pollutant Emissions  (g/km fleet avg)")

    # ── Panel 2: Improvement per pollutant ───────────────────────────────────
    ax2 = fig.add_subplot(gs[0, 1])
    iv  = [impr[p] for p in polls]
    colors2 = ["#34d399" if v >= 0 else "#ef4444" for v in iv]
    bars2   = ax2.bar(x, iv, color=colors2, zorder=3)
    ax2.set_xticks(x)
    ax2.set_xticklabels(polls, color="white")
    ax2.set_ylabel("Improvement (%)")
    ax2.axhline(0, color="#3a3a5a", linewidth=1)
    for bar, val in zip(bars2, iv):
        ax2.text(bar.get_x() + bar.get_width()/2,
                 val + (1 if val >= 0 else -3),
                 f"{val:.1f}%", ha="center", va="bottom",
                 color="white", fontsize=8, zorder=5)
    style(ax2, "Improvement per Pollutant (%)")

    # ── Panel 3: AQI comparison bar + solutions annotation ──────────────────
    ax3 = fig.add_subplot(gs[1, 0])
    aqi_vals = [aqi_before, aqi_after]
    aqi_cols = [(r/255, g/255, b/255)
                for r, g, b in [aqi_color_rgb(v) for v in aqi_vals]]
    ax3.bar(["Phase 1\n(Baseline)", "Phase 2\n(AQI Controls)"],
            aqi_vals, color=aqi_cols, zorder=3, width=0.5)
    ax3.set_ylabel("AQI")

    # Value labels
    for i, (val, col) in enumerate(zip(aqi_vals, ["white", "#34d399"])):
        ax3.text(i, val * 1.03, f"{val:.0f}\n{aqi_label(val)}",
                 ha="center", va="bottom", color=col,
                 fontsize=9, fontweight="bold", zorder=5)
    style(ax3, f"AQI Comparison   |   improvement {aqi_impr:.1f}%")

    # ── Panel 4: AQI over time ───────────────────────────────────────────────
    ax4 = fig.add_subplot(gs[1, 1])
    phase1_end = 0

    if result1.history:
        sb = [h.step for h in result1.history]
        ab = [h.calc_aqi for h in result1.history]
        ax4.plot(sb, ab, color="#ef4444", linewidth=2.0,
                 label="Phase 1 — Baseline", zorder=3)
        ax4.fill_between(sb, ab, alpha=0.08, color="#ef4444")
        phase1_end = sb[-1]

    if result2.history:
        off = phase1_end
        sa  = [h.step + off for h in result2.history]
        aa  = [h.calc_aqi   for h in result2.history]
        ax4.plot(sa, aa, color="#34d399", linewidth=2.0,
                 label="Phase 2 — AQI Controls", zorder=3)
        ax4.fill_between(sa, aa, alpha=0.08, color="#34d399")

        if result1.history and phase1_end > 0:
            y_top = max(max(ab), max(aa)) * 1.05
            ax4.axvline(phase1_end, color="#facc15",
                        linewidth=1.5, linestyle="--", alpha=0.8)
            ax4.text(phase1_end + max(sa[-1] - off, 30) * 0.01, y_top * 0.97,
                     "← Controls\n   Activated",
                     color="#facc15", fontsize=7.5, va="top", zorder=5)

        if solutions:
            short = {
                "speed_harmonization": "Speed Cap 35 km/h",
                "heavy_vehicle_ban":   "Heavy Vehicle Ban",
                "rerouting":           "Rerouting Active",
                "idling_restriction":  "Anti-Idling min 15",
            }
            sol_str = "\n".join("• " + short.get(s, s) for s in solutions)
            ax4.text(0.985, 0.97,
                     f"Phase 2 Solutions:\n{sol_str}",
                     transform=ax4.transAxes,
                     ha="right", va="top", color="#34d399",
                     fontsize=7.5, linespacing=1.4,
                     bbox=dict(boxstyle="round,pad=0.4",
                               facecolor="#0d1f0d", edgecolor="#34d399", alpha=0.90),
                     zorder=6)

    ax4.set_xlabel("Simulation step")
    ax4.set_ylabel("AQI")
    ax4.legend(facecolor=BG_AX, edgecolor="#3a3a5a", labelcolor="white", fontsize=8)
    style(ax4, f"AQI over Time   |   total emission Δ {total_impr:.1f}%")

    chart_path = OUTPUT_DIR / "comparison_chart.png"
    plt.savefig(str(chart_path), dpi=130, bbox_inches="tight",
                facecolor=BG_MAIN)
    plt.close(fig)
    print(f"  Chart  → {chart_path}")
    return chart_path


# ─────────────────────────────────────────────────────────────────────────────
def save_summary(zone, base_aqi, solutions, result1, result2) -> Path:
    before     = result1.avg_emissions
    after      = result2.avg_emissions
    aqi_before = result1.avg_aqi
    aqi_after  = result2.avg_aqi
    impr       = improvement_percent(before, after)
    total_b    = sum(before.values())
    total_a    = sum(after.values())
    total_impr = round((total_b - total_a) / total_b * 100, 1) if total_b > 0 else 0.0
    aqi_impr   = round((aqi_before - aqi_after) / aqi_before * 100, 1) if aqi_before > 0 else 0.0

    summary_path = OUTPUT_DIR / "summary.txt"
    sep = "=" * 50
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"Delhi AQI Simulation Report  (SUMO)\n{sep}\n")
        f.write(f"Area             : Major Dhyan Chand Nagar / India Gate\n")
        f.write(f"Zone             : {zone}\n")
        f.write(f"External AQI     : {base_aqi:.1f}  ({aqi_label(base_aqi)})\n\n")
        f.write(f"Phase 1 AQI      : {aqi_before:.1f}  ({aqi_label(aqi_before)})\n")
        f.write(f"Phase 2 AQI      : {aqi_after:.1f}  ({aqi_label(aqi_after)})\n")
        f.write(f"AQI Reduction    : {aqi_impr:.1f}%\n")
        f.write(f"Emission Reduction: {total_impr:.1f}%\n\n")
        f.write("Phase 2 Solutions:\n")
        for s in solutions:
            f.write(f"  • {SOLUTION_LABELS.get(s, s)}\n")
        f.write(f"\n{'─'*50}\n")
        f.write("Pollutant Results  (g/km fleet average):\n")
        f.write(f"{'Pollutant':<8} {'Phase 1':>10} {'Phase 2':>10} {'Reduction':>10}\n")
        f.write(f"{'─'*42}\n")
        for p in POLLUTANTS:
            f.write(f"{p:<8} {before[p]:>10.3f} {after[p]:>10.3f} {impr[p]:>9.1f}%\n")
    print(f"  Summary → {summary_path}")
    return summary_path


def open_file(path):
    import os, sys
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))
        elif sys.platform == "darwin":
            import subprocess; subprocess.Popen(["open", str(path)])
        else:
            import subprocess; subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass

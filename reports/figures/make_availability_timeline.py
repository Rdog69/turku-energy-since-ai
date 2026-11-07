"""Slide 4 diagram: what the model may see at origin Fri 2 Oct 2026 09:00 UTC (12:00 local).

Times only, no data values. Source of the times: reports/evaluation_report.md section 2.
    python reports/figures/make_availability_timeline.py
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

OUT = Path(__file__).with_name("availability_timeline.png")
ORIGIN = 9.0
H = lambda h, m=0: h + m / 60
# lane: (label, used marker (start, end, text), usable time, not-usable-yet (start, end, text), usable time)
LANES = [
    ("Imbalance price\n(package)", (H(7, 45), H(8), "quarter 07:45-08:00\nusable 09:00"), 9.0,
     (H(8), H(8, 15), "quarter 08:00-08:15\nusable 10:00"), 10.0),
    ("Fingrid surplus/deficit\n(real time, 198)", (H(8, 15), H(8, 30), "quarter 08:15-08:30\nusable 09:00 (end + 30 min)"), 9.0,
     (H(8, 30), H(8, 45), "quarter 08:30-08:45\nusable 10:00 (09:15 rounded up)"), 10.0),
    ("ECMWF IFS run", (0, 0.25, "00 UTC run\nusable 08:00 (+8 h)"), 8.0,
     (6, 6.25, "06 UTC run\nusable 14:00"), 14.0),
    ("ICON-EU run", (0, 0.25, "00 UTC run\nusable 05:00 (+5 h)"), 5.0,
     (6, 6.25, "06 UTC run\nusable 11:00"), 11.0),
]
GREEN, GREY, RED = "#1b7f4b", "#9a9a9a", "#c0392b"

fig, ax = plt.subplots(figsize=(13.33, 7), dpi=150)
n = len(LANES)
for i, (name, used, uf, nxt, nf) in enumerate(LANES):
    y = (n - 1 - i) * 1.5
    ax.axhline(y, color="#e3e3e3", lw=1, zorder=0)
    ax.text(-0.35, y, name, ha="right", va="center", fontsize=12, fontweight="bold")
    for (s, e, txt), f, col, a in ((used, uf, GREEN, 1.0), (nxt, nf, GREY, 0.9)):
        ax.add_patch(Rectangle((s, y - 0.12), max(e - s, 0.14), 0.24, color=col, alpha=a, zorder=3))
        # arrow from the data to the moment it becomes usable
        ax.annotate("", xy=(f, y), xytext=(max(e, s + 0.14), y),
                    arrowprops=dict(arrowstyle="->", color=col, lw=1.4, ls="-" if col == GREEN else "--"), zorder=2)
        ax.plot([f], [y], marker="o", ms=7, color=col, zorder=4)
        if col == GREEN:   # used row: label above, right-aligned for the late quarters
            ax.text(s if s < 1 else e + 0.1, y + 0.2, txt, fontsize=9.5, color=col,
                    ha="left" if s < 1 else "right", va="bottom", zorder=5)
        else:              # not usable yet: label below
            ax.text(s - 0.05 if s < 1 else s, y - 0.2, txt, fontsize=9.5, color=col, ha="left", va="top", zorder=5)
ax.axvline(ORIGIN, color=RED, lw=2.5, zorder=1)
ax.text(ORIGIN, 1.5 * (n - 1) + 0.65, "forecast origin\n09:00 UTC = 12:00 local", color=RED, ha="center", va="bottom",
        fontsize=12, fontweight="bold")
ax.axvspan(ORIGIN, 19.0, color=RED, alpha=0.05, zorder=0)
ax.text(16.5, -0.75, "not usable yet", color=GREY, ha="center", fontsize=11, style="italic")
ax.text(ORIGIN - 4.5, -0.75, "usable at the origin", color=GREEN, ha="center", fontsize=11, style="italic")
ax.annotate("", xy=(19.2, -1.1), xytext=(ORIGIN, -1.1), arrowprops=dict(arrowstyle="->", color=RED, lw=2))
ax.text(14.0, -1.25, "forecast horizon: 10 h (40 quarter-hours)", color=RED, ha="center", fontsize=11, va="top")
ax.set_xlim(-0.2, 19.6)
ax.set_ylim(-1.6, 1.5 * (n - 1) + 1.7)
ax.set_xticks(range(0, 20))
ax.set_xticklabels([f"{h:02d}:00" for h in range(0, 20)], fontsize=10)
ax.set_xlabel("UTC, Fri 2 Oct 2026", fontsize=11)
ax.set_yticks([])
for s in ("left", "right", "top"):
    ax.spines[s].set_visible(False)
ax.set_title("What the model may see at 12:00 local", fontsize=18, fontweight="bold", loc="left", pad=14)
fig.subplots_adjust(left=0.2, right=0.98, top=0.88, bottom=0.14)
fig.savefig(OUT)
print("wrote", OUT)

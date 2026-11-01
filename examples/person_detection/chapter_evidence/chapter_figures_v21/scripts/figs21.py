"""Figures 4, 5, 6, 7, 9, 10 and 14 of the chapter manuscript (version 21), drawn from the data files in ../data and
../../rq4_boot_kat_2026-10-29. Writes PNG and 300 dpi TIF files to ../output."""
import json, math, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
BOOT = os.path.join(HERE, "..", "..", "rq4_boot_kat_2026-10-29")
OUT = os.path.join(HERE, "..", "output"); os.makedirs(OUT, exist_ok=True)
BLUE, ORANGE, GREEN, PURPLE, GREY, INK, MUTED = "#2a78d6", "#eb6834", "#1baf7a", "#8c6bb1", "#b9b8b3", "#0b0b0b", "#52514e"
plt.rcParams.update({"font.family": "Liberation Sans", "font.size": 10, "axes.edgecolor": "#52514e", "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e4e3df", "grid.linewidth": 0.8, "axes.axisbelow": True})
W = 7.2


def header(fig, title, sub):
    fig.text(0.01, 0.985, title, fontsize=13.5, fontweight="bold", color=INK, va="top")
    fig.text(0.01, 0.915, sub, fontsize=10, color=MUTED, va="top")


def save(fig, name):
    fig.savefig(f"{OUT}/{name}.png", dpi=300, facecolor="white")
    fig.savefig(f"{OUT}/{name}.tif", dpi=300, facecolor="white", pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)


# ------------------------------------------------------------------ Fig 4: outputs on 12 images
w1 = json.load(open(os.path.join(DATA, "rq4_w1.json")))
rows = w1["rows"]
xnn_out = {r["image"]: (r["S"] if r["X_out_equals_S"] else None) for r in rows}
xnn_out[11] = -60  # README of the Arm package and the 25 Oct host run: XNNPACK -60 on image 11
fig = plt.figure(figsize=(W, 3.5))
header(fig, "Eleven builds agree; single rounding moved 7 of 12 scores",
       "Person score (raw int8) per image; the no-person score is its negative in every case")
ax = fig.add_axes([0.08, 0.17, 0.9, 0.62])
x = np.arange(12)
D = [r["D"] for r in rows]; S = [r["S"] for r in rows]; X = [xnn_out[i] for i in range(12)]
ax.axhline(0, color=MUTED, lw=1, ls="--"); ax.text(11.45, 4, "decision boundary", ha="right", va="bottom", fontsize=8.5, color=MUTED)
ax.scatter(x - 0.18, D, s=46, color=BLUE, zorder=3, label="ESP32 R1, R2A, R2, R2-SN and seven Arm or x86 double-rounding builds")
ax.scatter(x, S, s=46, marker="s", color=ORANGE, zorder=3, label="TFLM and CMSIS-NN with single rounding (Cortex-M4, QEMU)")
ax.scatter(x + 0.18, X, s=52, marker="^", color=GREEN, zorder=3, label="LiteRT 2.3.0 default (XNNPACK), host")
for i in range(12):
    if S[i] != D[i]:
        ax.annotate(f"{S[i] - D[i]:+d}", (i, S[i]), xytext=(0, -14 if S[i] > 0 else 9), textcoords="offset points", ha="center", fontsize=8, color=ORANGE)
ax.set_xticks(x); ax.set_xticklabels([str(i) for i in x]); ax.set_xlabel("Image ID (0–9 bundled; 10 person.bmp; 11 no_person.bmp)")
ax.set_ylabel("Person score (raw int8)"); ax.set_ylim(-130, 135)
ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=1, frameon=False, fontsize=8.5, handletextpad=0.3)
fig.subplots_adjust(bottom=0.3)
ax.set_position([0.1, 0.3, 0.88, 0.52])
save(fig, "fig04_outputs_12_images")

# ------------------------------------------------------------------ Fig 5: operator-level view
ops = json.load(open(os.path.join(DATA, "w1_oplevel.json")))
seq = ['DW', 'DW', 'C', 'DW', 'C', 'DW', 'C', 'DW', 'C', 'DW', 'C', 'DW', 'C', 'DW', 'C', 'DW', 'C', 'DW', 'C', 'DW', 'C', 'DW', 'C', 'DW', 'C', 'DW', 'C', 'P', 'C', 'R', 'S']
fig = plt.figure(figsize=(W, 3.6))
header(fig, "Single rounding departs at operator 0 and the gap grows with depth",
       "Single-rounding build against ESP32 R1, 12 images; every other build in Figure 4 differs in 0 of 2,781,768 values")
a1 = fig.add_axes([0.08, 0.2, 0.55, 0.58]); a2 = fig.add_axes([0.72, 0.2, 0.26, 0.58])
xs = np.arange(31)
frac = [o["S_frac_values_diff"] * 100 for o in ops]
cols = [BLUE if s == 'C' else (ORANGE if s == 'DW' else GREY) for s in seq]
a1.bar(xs, frac, color=cols, width=0.75)
a1.set_xlim(-0.8, 30.8); a1.set_ylabel("int8 values that differ (%)"); a1.set_xlabel("Operator index (execution order)")
a1.set_title("(a) Share of each operator's output that differs", fontsize=10, loc="left", color=INK)
a1.set_xticks([0, 5, 10, 15, 20, 25, 30])
from matplotlib.patches import Patch
a1.legend(handles=[Patch(color=ORANGE, label="Depthwise conv"), Patch(color=BLUE, label="Conv"), Patch(color=GREY, label="Pool, reshape, softmax")],
          frameon=False, fontsize=8, loc="upper left")
mx = [o["S_max_lsb"] for o in ops]
a2.plot(xs, mx, color=INK, lw=1.4, marker="o", ms=3)
a2.set_title("(b) Largest difference (LSB)", fontsize=10, loc="left", color=INK)
a2.set_xlabel("Operator index"); a2.set_xticks([0, 10, 20, 30]); a2.set_ylim(0, 16); a2.set_yticks([0, 5, 10, 15])
a2.annotate("15 LSB at op 25", (25, 15), xytext=(-62, -6), textcoords="offset points", fontsize=8, color=MUTED)
save(fig, "fig05_operator_level")

# ------------------------------------------------------------------ Fig 9: R2 latency by capture/build
caps = [("21 Oct\nbench 1000\n(transcript)", 401.645, "before"), ("22 Oct\nbench 100\nb13cfaa2", 401.677, "before"),
        ("22–23 Oct\ndrift 600\nn = 85,701", 412.780, "after"), ("24 Oct\nbench 1000\nc144b7ff", 412.864, "after"),
        ("25 Oct\nimages 10, 11\n342977f8, n = 20", 412.479, "after"), ("26 Oct\nmatched 1000\nf127818a", 412.500, "after")]
fig = plt.figure(figsize=(W, 3.5))
header(fig, "The same kernels ran about 11 ms slower in later builds",
       "Mean R2 Invoke latency per capture, 240 MHz; outputs identical; spread within any capture under 0.2 ms")
ax = fig.add_axes([0.1, 0.24, 0.88, 0.55])
for i, (lab, v, g) in enumerate(caps):
    ax.scatter(i, v, s=60, color=BLUE if g == "before" else ORANGE, marker="o" if g == "before" else "D", zorder=3)
    ax.annotate(f"{v:.3f}", (i, v), xytext=(9, 0), textcoords="offset points", va="center", fontsize=9)
ax.axvspan(-0.5, 1.5, color="#eaf2fb", zorder=0); ax.axvspan(1.5, 5.5, color="#fdf0ea", zorder=0)
ax.text(0.5, 408.6, "21–22 Oct builds\n96.40 M cycles per Invoke", ha="center", fontsize=8.5, color=MUTED)
ax.text(3.5, 406.4, "Builds from 22 Oct onward (drift command added)\n99.00 to 99.07 M cycles per Invoke", ha="center", fontsize=8.5, color=MUTED)
ax.set_xticks(range(len(caps))); ax.set_xticklabels([c[0] for c in caps], fontsize=8)
ax.set_xlim(-0.5, 5.5); ax.set_ylim(399.5, 415.5); ax.set_ylabel("Invoke latency (ms)")
save(fig, "fig09_r2_latency_by_build")

# ------------------------------------------------------------------ Fig 10: W2 open loop
w2 = json.load(open(os.path.join(DATA, "rq4_w2.json")))
fig = plt.figure(figsize=(W, 3.6))
header(fig, "Rounding differences appear inside W2 far more often than in its actions",
       "50,000 int8 observations per model; every difference in an action is exactly 1 LSB")
a1 = fig.add_axes([0.15, 0.2, 0.34, 0.58]); a2 = fig.add_axes([0.66, 0.2, 0.32, 0.58])
names = [("single_rounding", "Single rounding"), ("XNNPACK", "XNNPACK"), ("LiteRT_OPT", "LiteRT OPT")]
yy = np.arange(3)
for j, (m, c, off) in enumerate((("per_tensor", BLUE, -0.18), ("per_channel", ORANGE, 0.18))):
    v = [w2[m]["variants"][k]["n_disagree"] for k, _ in names]
    a1.barh(yy + off, v, height=0.34, color=c, label=m.replace("_", "-"))
    for y, val in zip(yy + off, v):
        a1.text(val + 25, y, f"{val:,}", va="center", fontsize=8.5)
a1.set_yticks(yy); a1.set_yticklabels([n for _, n in names]); a1.invert_yaxis()
a1.set_xlim(0, 1500); a1.set_xticks([0, 500, 1000, 1500]); a1.set_xticklabels(["0", "500", "1,000", "1,500"]); a1.set_xlabel("Actions that differ from double rounding")
a1.set_title("(a) Against the ESP32 and Arm builds", fontsize=10, loc="left", color=INK)
a1.legend(frameon=False, fontsize=8.5, loc="lower right")
for j, (m, c) in enumerate((("per_tensor", BLUE), ("per_channel", ORANGE))):
    fl = w2[m]["first_layer_single_vs_double"]
    vals = [fl["0"], fl["1"], fl["2"]]; left = 0
    for k, (v, shade) in enumerate(zip(vals, (1.0, 0.7, 0.4))):
        a2.barh(j, v, left=left, height=0.5, color=c, alpha=shade)
        left += v
    a2.text(left + 200, j, f"{left:,} in a layer\n{w2[m]['variants']['single_rounding']['n_disagree']:,} in the action", va="center", fontsize=8.5)
a2.set_yticks([0, 1]); a2.set_yticklabels(["per-tensor", "per-channel"])
a2.set_xlim(0, 19000); a2.set_xticks([0, 5000, 10000, 15000]); a2.set_xticklabels(["0", "5,000", "10,000", "15,000"]); a2.set_xlabel("Observations (of 50,000)")
a2.set_title("(b) First layer that differs", fontsize=10, loc="left", color=INK)
a2.text(0, 1.62, "Shade, dark to light: FC1, FC2, FC3", fontsize=8, color=MUTED, va="center")
a2.set_ylim(1.85, -0.6)
save(fig, "fig10_w2_open_loop")

# ------------------------------------------------------------------ Fig 11: W2 closed loop
fig = plt.figure(figsize=(W, 3.6))
header(fig, "Every trajectory separates, yet outcomes change only under stress",
       "Same seeds, double against single rounding; nominal: 200 episodes; stress: 1,000 episodes per model")
a1 = fig.add_axes([0.08, 0.2, 0.44, 0.58]); a2 = fig.add_axes([0.62, 0.2, 0.36, 0.58])
for m, c in (("per_tensor", BLUE), ("per_channel", ORANGE)):
    s = json.load(open(os.path.join(DATA, f"w2_eval_{m}_summary.json")))
    fs = np.sort(np.array(s["runtimes"]["TFLM_x86_reference"]["closed_loop_first_separation_steps"]) / 20.0)
    a1.step(fs, np.arange(1, len(fs) + 1) / len(fs) * 100, where="post", color=c, lw=1.8, label=f"{m.replace('_', '-')} (median {np.median(fs):.2f} s)")
a1.set_xlabel("Time to first different action (s)"); a1.set_ylabel("Episodes separated (%)"); a1.set_xlim(0, 16); a1.set_ylim(0, 102)
a1.set_title("(a) Nominal: when same-seed trajectories split", fontsize=10, loc="left", color=INK)
a1.legend(frameon=False, fontsize=8.5, loc="lower right")
st = {m: json.load(open(os.path.join(DATA, f"w2_stress_{m}.json"))) for m in ("per_tensor", "per_channel")}
labels = ["single\nrounding", "XNNPACK", "LiteRT\nOPT"]
for j, (m, c, off) in enumerate((("per_tensor", BLUE, -0.18), ("per_channel", ORANGE, 0.18))):
    lost = [st[m]["LiteRT_REF_single_rounding_family"]["vs_double_rounding"]["ref_only"], st[m]["LiteRT_XNNPACK"]["vs_double_rounding"]["ref_only"]]
    gained = [st[m]["LiteRT_REF_single_rounding_family"]["vs_double_rounding"]["this_only"], st[m]["LiteRT_XNNPACK"]["vs_double_rounding"]["this_only"]]
    o = json.load(open(os.path.join(DATA, f"stress_opt_{m}.json")))
    lost.append(o["double_only"]); gained.append(o["opt_only"])
    xx = np.arange(3) + off
    a2.bar(xx, [-v for v in lost], width=0.34, color=c)
    a2.bar(xx, gained, width=0.34, color=c, alpha=0.45)
    for x_, l_, g_ in zip(xx, lost, gained):
        a2.text(x_, -l_ - 0.35, str(l_), ha="center", va="top", fontsize=8)
        a2.text(x_, g_ + 0.2, str(g_), ha="center", va="bottom", fontsize=8)
a2.axhline(0, color=INK, lw=0.8); a2.set_xticks(range(3)); a2.set_xticklabels(labels, fontsize=8.5); a2.set_ylim(-5.8, 3.8)
a2.set_ylabel("Episodes (of 1,000)"); a2.set_title("(b) Stress: outcomes lost (below) or gained", fontsize=10, loc="left", color=INK)
a2.legend(handles=[Patch(color=BLUE, label="per-tensor"), Patch(color=ORANGE, label="per-channel")], frameon=False, fontsize=8, loc="upper right")
save(fig, "fig11_w2_closed_loop")

# ------------------------------------------------------------------ Fig 12: RQ4 detection
fig = plt.figure(figsize=(W, 3.7))
header(fig, "Vectors near rounding ties catch the rounding change sooner",
       "Probability that a K-vector known-answer test flags a variant; W2 from recorded outputs, W1 also run on the board (Figure 10)")
a1 = fig.add_axes([0.08, 0.2, 0.52, 0.56]); a2 = fig.add_axes([0.72, 0.2, 0.26, 0.56])
Ks = np.unique(np.round(np.logspace(0, math.log10(1024), 60)).astype(int))
for m, ls in (("per_tensor", "-"), ("per_channel", "--")):
    N = w2[m]["N"]
    for k, c in (("single_rounding", ORANGE), ("LiteRT_OPT", PURPLE)):
        nb = w2[m]["variants"][k]["n_disagree"]
        p = [1 - math.exp(math.lgamma(N - nb + 1) - math.lgamma(N - nb - K + 1) - math.lgamma(N + 1) + math.lgamma(N - K + 1)) for K in Ks]
        a1.plot(Ks, np.array(p) * 100, color=c, ls=ls, lw=1.6)
        r = w2[m]["variants"][k]["tie_first_hit_rank"]
        a1.scatter([r], [100], color=c, marker="v" if m == "per_tensor" else "o", s=40, zorder=4, edgecolor="white")
a1.set_xscale("log"); a1.set_xlim(0.8, 5000); a1.set_ylim(-3, 108)
a1.set_xlabel("K (stored vectors)"); a1.set_ylabel("Detection probability (%)")
a1.set_title("(a) W2: random draws (lines); tie-ranked (markers)", fontsize=10, loc="left", color=INK)
from matplotlib.lines import Line2D
a1.legend(handles=[Line2D([], [], color=ORANGE, lw=2, label="single rounding"), Line2D([], [], color=PURPLE, lw=2, label="LiteRT OPT"),
                   Line2D([], [], color=MUTED, lw=1.6, ls="-", label="per-tensor"), Line2D([], [], color=MUTED, lw=1.6, ls="--", label="per-channel"),
                   Line2D([], [], color=MUTED, marker="v", ls="", label="tie-ranked, per-tensor: first hit"), Line2D([], [], color=MUTED, marker="o", ls="", label="tie-ranked, per-channel: first hit")],
          frameon=True, framealpha=0.95, edgecolor="#e4e3df", fontsize=7.3, loc="center right", bbox_to_anchor=(1.0, 0.45))
k1 = [1, 2, 3, 4, 6]
a2.plot(k1, [w1["output_level_detect"][str(k)]["S"] * 100 for k in k1], color=ORANGE, marker="o", lw=1.6, label="output bytes")
a2.plot(k1, [100] * len(k1), color=BLUE, marker="s", lw=1.6, label="all 31 tensor hashes")
a2.set_xticks(k1); a2.set_ylim(-3, 108); a2.set_xlabel("K (of 12 images)")
a2.set_title("(b) W1: single rounding", fontsize=10, loc="left", color=INK)
a2.legend(frameon=False, fontsize=8, loc="lower right")
save(fig, "fig12_rq4_detection")
print("ok")


# ------------------------------------------------------------------ Fig 10 (v21): acceptance test on the board
import csv, re
from collections import defaultdict
rows = list(csv.DictReader(open(os.path.join(BOOT, "rq4_boot_kat_summary_20261029_203054.csv"))))
g = defaultdict(list)
for r in rows:
    g[r["build"]].append(r)
log = open(os.path.join(BOOT, "boot_r1sr_1_20261029_203054.txt"), "rb").read().decode("latin1")
sr_ops, sr_out = {}, {}
for m in re.finditer(r"RQ4_IMAGE,image=(\d+),.*?output_match=(\d),ops_match=(\d+)", log):
    sr_ops[int(m[1])] = int(m[3]); sr_out[int(m[1])] = int(m[2])
assert sum(sr_ops.values()) == 9 and sum(sr_out.values()) == 5
order = [("r1", "R1"), ("r2a", "R2A"), ("r2", "R2"), ("r2sn", "R2-SN"), ("r1sr", "R1-SR")]
for b, _ in order[:4]:
    assert all(r["ops_match"] == "372" and r["outputs_match"] == "12" for r in g[b])
fig = plt.figure(figsize=(W, 5.3))
header(fig, "The acceptance test on the board blocked single rounding at operator 0",
       "Five builds, five boots each, at 240 MHz; operator hashes compared with the R1 record of 25 October")
a = fig.add_axes([0.10, 0.47, 0.86, 0.33])
grid = np.array([[31] * 12] * 4 + [[sr_ops[i] for i in range(12)]])
a.imshow(grid == 31, cmap=matplotlib.colors.ListedColormap(["#3a3a38", "#e8e7e3"]), aspect="auto",
         extent=(-0.5, 11.5, 4.5, -0.5))
for i in range(5):
    for j in range(12):
        v = grid[i, j]
        out_ok = True if i < 4 else bool(sr_out[j])
        a.text(j, i, f"{v}" + ("" if out_ok else "*"), ha="center", va="center", fontsize=9,
               color=INK if v == 31 else "white", fontweight="bold" if v != 31 else "normal")
a.set_xticks(range(12)); a.set_yticks(range(5)); a.set_yticklabels([n for _, n in order])
a.set_xticks(np.arange(-0.5, 12, 1), minor=True); a.set_yticks(np.arange(-0.5, 5, 1), minor=True)
a.grid(which="minor", color="white", lw=1.5); a.grid(which="major", visible=False); a.tick_params(which="both", length=0)
for sp in a.spines.values():
    sp.set_visible(False)
a.set_xlabel("Stored image")
a.set_title("(a) Operator hashes equal to the record, of 31 per image (* final output also changed)", loc="left", fontsize=10, color=INK)
b2 = fig.add_axes([0.10, 0.09, 0.86, 0.25])
mean = lambda b, k: sum(int(r[k]) for r in g[b]) / len(g[b]) / 1e6
ys = np.arange(5)
mini = [mean(b, "minimal_test_us") for b, _ in order]
full = [mean(b, "kat_us") for b, _ in order]
b2.barh(ys - 0.2, mini, height=0.38, color="#9a9893", label="identity check and image 0")
b2.barh(ys + 0.2, full, height=0.38, color="#3a3a38", label="all 12 images")
for y, m_, f_ in zip(ys, mini, full):
    b2.text(m_ * 1.06, y - 0.2, f"{m_:.2f} s", va="center", fontsize=8.5, color=INK)
    b2.text(f_ * 1.06, y + 0.2, f"{f_:.2f} s", va="center", fontsize=8.5, color=INK)
b2.set_xscale("log"); b2.set_xlim(0.3, 150); b2.set_yticks(ys); b2.set_yticklabels([n for _, n in order]); b2.invert_yaxis()
b2.set_xticks([0.3, 1, 3, 10, 30, 100]); b2.set_xticklabels(["0.3", "1", "3", "10", "30", "100"])
b2.set_xlabel("Time in the test firmware (s, log scale), mean of five boots")
b2.legend(loc="lower right", bbox_to_anchor=(1.0, 1.0), ncol=2, fontsize=8.5, frameon=False)
b2.set_title("(b) Time to a verdict", loc="left", fontsize=10, color=INK)
save(fig, "fig_v21_board_test")

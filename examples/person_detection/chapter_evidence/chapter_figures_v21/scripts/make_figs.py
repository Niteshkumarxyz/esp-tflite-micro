"""Measured figures for 'Same Model, Different Robot' (v19 full rewrite).
All values are read from the evidence CSVs in ../data or typed from verified logs
(sources noted beside each constant)."""
import csv, statistics as st, math, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.lines import Line2D

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
OUT = HERE
plt.rcParams.update({"font.family": "Liberation Sans", "font.size": 9.5,
                     "axes.titlesize": 10.5, "axes.labelsize": 9.5})
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID, LIGHT = "#0b0b0b", "#52514e", "#e4e3df", "#b9b8b3"
CFG = [("R1", "reference", BLUE, "o"), ("R2A", "ESP-NN ANSI C", ORANGE, "s"),
       ("R2", "ESP-NN optimized", AQUA, "^")]


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def style(ax, ygrid=True, xgrid=False):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelcolor=INK)
    if ygrid:
        ax.yaxis.grid(True, color=GRID, lw=0.8)
    if xgrid:
        ax.xaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def headline(fig, title, sub, y=0.975):
    fig.text(0.012, y, title, fontsize=12, fontweight="bold", color=INK, va="top")
    fig.text(0.012, y - 0.075, sub, fontsize=9.5, color=MUTED, va="top")


def save(fig, name):
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=300, facecolor="white")
    fig.savefig(os.path.join(OUT, name + ".tif"), dpi=300, facecolor="white",
                pil_kwargs={"compression": "tiff_lzw"})
    plt.close(fig)


r100 = {c[0]: load(f) for c, f in zip(CFG, ["r1_100.csv", "r2a_100.csv", "r2_100.csv"])}

# ---------------------------------------------------------------- Figure 4
def fig_bundled():
    fig, ax = plt.subplots(figsize=(7.2, 3.5))
    fig.subplots_adjust(left=0.09, right=0.98, top=0.76, bottom=0.2)
    headline(fig, "Every bundled image gave the same bytes on all three configurations",
             "Raw int8 person score per image (the no-person score is its negative); 100 runs per configuration, ten images cycled")
    per = {}
    for name, _, col, mk in CFG:
        rows = r100[name]
        vals = {}
        for r in rows:
            vals.setdefault(int(r["image"]), set()).add(int(r["raw_person"]))
        per[name] = vals
    offs = {"R1": -0.22, "R2A": 0.0, "R2": 0.22}
    for name, lab, col, mk in CFG:
        xs, ys = [], []
        for img in range(10):
            (v,) = per[name][img]  # exactly one value per image in 10 repeats
            xs.append(img + offs[name]); ys.append(v)
        ax.scatter(xs, ys, s=34, marker=mk, color=col, edgecolor="white", linewidth=0.8,
                   zorder=3, label=f"{name} {lab}")
    for img in range(10):
        (v,) = per["R1"][img]
        ax.text(img, v + (9 if v >= 0 else -9), f"{v}", ha="center",
                va="bottom" if v >= 0 else "top", fontsize=8.5, color=INK)
    ax.axhline(0, color=MUTED, lw=0.9, ls=(0, (4, 3)))
    ax.text(9.55, 4, "decision boundary", fontsize=8, color=MUTED, ha="right", va="bottom")
    ax.set_xlim(-0.6, 9.6); ax.set_ylim(-135, 140)
    ax.set_xticks(range(10)); ax.set_xticklabels([str(i) for i in range(10)])
    ax.set_xlabel("Bundled image ID", color=INK)
    ax.set_ylabel("Person score (raw int8)", color=INK)
    style(ax)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.36), ncol=3, frameon=False, fontsize=8.5)
    save(fig, "fig04_bundled_outputs")


# ---------------------------------------------------------------- Figure 5
def fig_matched():
    # Host values: r0_output.txt (LiteRT 2.3.0) and 21 Oct host TFLM test; ESP32 values: repeat_25oct.csv
    rep = load("repeat_25oct.csv")
    esp = {}
    for r in rep:
        esp.setdefault((r["runtime"], r["image_id"]), set()).add(int(r["person_raw_int8"]))
    rows = [("Host TFLM (R0M)", 113, -57, "host"),
            ("LiteRT reference (R0)", 113, -57, "host"),
            ("LiteRT default, XNNPACK", 113, -60, "xnn"),
            ("ESP32 R1 reference", *[esp[("R1_REFERENCE", i)].pop() for i in ("10", "11")], "esp"),
            ("ESP32 R2A ANSI C", *[esp[("R2A_ANSI_C", i)].pop() for i in ("10", "11")], "esp"),
            ("ESP32 R2 optimized", *[esp[("R2_OPTIMIZED", i)].pop() for i in ("10", "11")], "esp")]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.3), sharey=True)
    fig.subplots_adjust(left=0.27, right=0.98, top=0.74, bottom=0.17, wspace=0.12)
    headline(fig, "Only the host's default fast path moved the score",
             "Person score (raw int8) for the two input-matched test images; each ESP32 value repeated 10 times on 25 October")
    ys = list(range(len(rows)))[::-1]
    for k, (ax, title, col_i, xlim) in enumerate([
            (axes[0], "Image 10, person.bmp", 1, (104, 120)),
            (axes[1], "Image 11, no_person.bmp", 2, (-66, -50))]):
        for y, row in zip(ys, rows):
            v = row[col_i]; kind = row[3]
            col = ORANGE if (kind == "xnn" and v != rows[1][col_i]) else BLUE
            mk = "D" if col == ORANGE else "o"
            ax.scatter([v], [y], s=46, color=col, marker=mk, edgecolor="white", linewidth=0.8, zorder=3)
            ax.text(v + 0.7, y, f"{v}", va="center", fontsize=8.5, color=INK)
        ref = rows[1][col_i]
        ax.axvline(ref, color=LIGHT, lw=1, zorder=1)
        ax.set_xlim(*xlim)
        ax.set_title(title, loc="left", color=INK)
        ax.set_xlabel("Person score (raw int8)", color=INK)
        style(ax, ygrid=False, xgrid=True)
        ax.axhspan(2.5, 5.5, color="#f4f3f0", zorder=0)
    axes[1].annotate("3 LSB from the reference", xy=(-60, ys[2]), xytext=(-65.6, ys[2] - 0.55),
                     fontsize=8.5, color=INK, arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))
    axes[0].set_yticks(ys); axes[0].set_yticklabels([r[0] for r in rows], color=INK)
    save(fig, "fig05_matched_inputs")


# ---------------------------------------------------------------- Figure 6
def fig_latency():
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 3.4), gridspec_kw={"width_ratios": [1.15, 1]})
    fig.subplots_adjust(left=0.15, right=0.98, top=0.74, bottom=0.17, wspace=0.42)
    headline(fig, "ESP-NN cut Invoke time tenfold; repeat runs differed by microseconds",
             "22 October captures at 240 MHz: 10 warm-up and 100 measured invocations per configuration")
    means = []
    for i, (name, lab, col, mk) in enumerate(CFG):
        x = [int(r["invoke_us"]) / 1000 for r in r100[name]]
        means.append(st.mean(x))
    yy = [2, 1, 0]
    a.barh(yy, means, height=0.55, color=[c[2] for c in CFG], edgecolor="white", linewidth=1.5)
    for y, m in zip(yy, means):
        a.text(m + 60, y, f"{m:,.1f} ms", va="center", fontsize=8.5, color=INK)
    a.set_yticks(yy); a.set_yticklabels([f"{c[0]}\n{c[1].replace('ESP-NN ', '')}" for c in CFG], color=INK)
    a.set_xlim(0, 5200); a.set_xlabel("Mean Invoke latency (ms)", color=INK)
    a.set_title("(a) Mean latency", loc="left", color=INK)
    a.text(1500, 0.5, f"R1/R2A {means[0]/means[1]:.2f}×\nR2A/R2 {means[1]/means[2]:.2f}×\nR1/R2 {means[0]/means[2]:.2f}×",
           fontsize=8.5, color=MUTED, va="center")
    style(a, ygrid=False, xgrid=True)
    for i, (name, lab, col, mk) in enumerate(CFG):
        x = [int(r["invoke_us"]) for r in r100[name]]
        m = st.mean(x)
        dev = [v - m for v in x]
        jitter = [((k * 37) % 17 - 8) / 40 for k in range(len(dev))]
        b.scatter(dev, [yy[i] + j for j in jitter], s=9, color=col, marker=mk, alpha=0.85, linewidth=0)
        b.text(118, yy[i], f"SD {st.stdev(x):.0f} µs", va="center", fontsize=8.5, color=INK)
    b.set_yticks(yy); b.set_yticklabels([c[0] for c in CFG], color=INK)
    b.set_xlim(-120, 170); b.set_xlabel("Deviation from configuration mean (µs)", color=INK)
    b.axvline(0, color=LIGHT, lw=1)
    b.set_title("(b) Run-to-run spread", loc="left", color=INK)
    style(b, ygrid=False, xgrid=True)
    save(fig, "fig06_latency_100run")


# ---------------------------------------------------------------- Figure 7
def fig_kernels():
    # 25 Oct serial logs: per-kernel timers (whole ms), first trial of image 10, identical in all 20 trials
    invoke_ms = {"R1": 4139.794, "R2A": 528.375, "R2": 412.519}
    conv = {"R1": 3513, "R2A": 391, "R2": 316}
    dw = {"R1": 625, "R2A": 136, "R2": 95}
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    fig.subplots_adjust(left=0.2, right=0.97, top=0.70, bottom=0.25)
    headline(fig, "Convolution takes most of every Invoke; depthwise convolution takes the rest",
             "Share of one Invoke spent in each kernel type (25 October builds, image 10; per-kernel timers in whole ms)")
    yy = [2, 1, 0]
    for y, (name, lab, col, mk) in zip(yy, CFG):
        tot = invoke_ms[name]
        c, d = conv[name], dw[name]
        o = tot - c - d
        parts = [(c, BLUE, "Convolution"), (d, ORANGE, "Depthwise"), (o, LIGHT, "Other")]
        left = 0
        for val, colr, lab2 in parts:
            w = val / tot * 100
            ax.barh(y, w, left=left, height=0.55, color=colr, edgecolor="white", linewidth=1.5)
            if w > 6:
                ax.text(left + w / 2, y, f"{val:,.0f} ms\n{w:.1f}%", ha="center", va="center", fontsize=8,
                        color="white" if colr != LIGHT else INK)
            left += w
        ax.text(101, y, f"{tot:,.1f} ms", va="center", fontsize=8.5, color=INK)
    ax.set_yticks(yy); ax.set_yticklabels([f"{c[0]} {c[1]}" for c in CFG], color=INK)
    ax.set_xlim(0, 112); ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("Share of Invoke time (%)", color=INK)
    style(ax, ygrid=False, xgrid=False)
    h = [plt.Rectangle((0, 0), 1, 1, color=c) for c in (BLUE, ORANGE, LIGHT)]
    ax.legend(h, ["Convolution (14 ops)", "Depthwise convolution (14 ops)", "Pooling, reshape, softmax and overhead"],
              loc="lower center", bbox_to_anchor=(0.45, -0.52), ncol=3, frameon=False, fontsize=8.3)
    save(fig, "fig07_kernel_share")


# ---------------------------------------------------------------- Figure 8
def fig_memory():
    # idf.py size, 21 Oct uninstrumented builds; arena values from boot logs
    code = [138744, 145832, 150040]
    arena_cfg = [163840, 102400, 163840]
    arena_used = [82292, 82308, 82300]
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 3.5), gridspec_kw={"width_ratios": [1, 1.35]})
    fig.subplots_adjust(left=0.09, right=0.98, top=0.74, bottom=0.25, wspace=0.32)
    headline(fig, "The faster builds carry more code; the arena reserve is set by a flag, not by need",
             "idf.py size of each configuration (21 October builds) and the tensor arena reported at boot")
    x = range(3)
    bars = a.bar(x, code, width=0.6, color=[c[2] for c in CFG], edgecolor="white", linewidth=1.5)
    for r, v in zip(bars, code):
        a.text(r.get_x() + r.get_width() / 2, v + 2500, f"{v:,}", ha="center", va="bottom", fontsize=8.3, color=INK)
    a.set_xticks(list(x)); a.set_xticklabels([f"{c[0]}\n{c[1].replace('ESP-NN ', '')}" for c in CFG])
    a.set_ylim(0, 175000); a.set_ylabel("Bytes (thousands)", color=INK)
    a.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v/1000:.0f}"))
    a.set_title("(a) Flash code (.text)", loc="left", color=INK)
    style(a)
    w = 0.36
    b1 = b.bar([i - w / 2 - 0.01 for i in x], arena_cfg, width=w, color=BLUE, edgecolor="white", linewidth=1.5,
               label="Arena configured")
    b2 = b.bar([i + w / 2 + 0.01 for i in x], arena_used, width=w, color=ORANGE, edgecolor="white", linewidth=1.5,
               hatch="////", label="Arena used by the model")
    for rs, vs in ((b1, arena_cfg), (b2, arena_used)):
        for r, v in zip(rs, vs):
            b.text(r.get_x() + r.get_width() / 2, v + 2500, f"{v:,}", ha="center", va="bottom", fontsize=7.8, color=INK)
    b.set_xticks(list(x)); b.set_xticklabels([f"{c[0]}\n{c[1].replace('ESP-NN ', '')}" for c in CFG])
    b.set_ylim(0, 190000); b.set_ylabel("Bytes (thousands)", color=INK)
    b.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v/1000:.0f}"))
    b.set_title("(b) Tensor arena", loc="left", color=INK)
    style(b)
    b.legend(loc="lower center", bbox_to_anchor=(0.45, -0.42), ncol=2, frameon=False, fontsize=8.5)
    save(fig, "fig08_memory")


# ---------------------------------------------------------------- Figure 9
def fig_drift():
    d = load("drift_minutes.csv")
    m = [int(r["minute"]) for r in d]
    mean = [int(r["mean_us"]) / 1000 for r in d]
    p95 = [int(r["p95_us"]) / 1000 for r in d]
    mn = [int(r["min_us"]) / 1000 for r in d]
    mx = [int(r["max_us"]) / 1000 for r in d]
    runs = [int(r["runs"]) for r in d]
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 3.4), gridspec_kw={"width_ratios": [2.3, 1]})
    fig.subplots_adjust(left=0.1, right=0.98, top=0.74, bottom=0.27, wspace=0.38)
    headline(fig, "Ten hours, 85,701 invocations: no failures, no output changes, no drift",
             "R2 drift build, one row per minute for 600 minutes; ten bundled images cycled; heap stayed at 128,496 bytes")
    a.fill_between(m, mn, mx, color="#cfe0f6", lw=0, label="Per-minute min to max")
    a.plot(m, mean, color=BLUE, lw=1.4, label="Per-minute mean")
    a.plot(m, p95, color=ORANGE, lw=1.4, ls=(0, (5, 2)), label="Per-minute P95")
    a.set_xlim(1, 600); a.set_ylim(412.66, 412.90)
    a.set_xlabel("Minute of run", color=INK); a.set_ylabel("Invoke latency (ms)", color=INK)
    a.set_title("(a) Invoke latency", loc="left", color=INK)
    style(a)
    a.legend(loc="lower center", bbox_to_anchor=(0.5, -0.45), ncol=3, frameon=False, fontsize=8)
    c142, c143 = runs.count(142), runs.count(143)
    bars = b.bar([0, 1], [c142, c143], width=0.6, color=[LIGHT, BLUE], edgecolor="white", linewidth=1.5)
    for r, v in zip(bars, (c142, c143)):
        b.text(r.get_x() + r.get_width() / 2, v + 8, f"{v}", ha="center", va="bottom", fontsize=8.5, color=INK)
    b.set_xticks([0, 1]); b.set_xticklabels(["142 runs", "143 runs"])
    b.set_ylim(0, 600); b.set_ylabel("Minutes", color=INK)
    b.set_title("(b) Runs per minute", loc="left", color=INK)
    b.text(-0.28, 330, "42 ticks × 10 ms\n= 420 ms per loop\n→ 142.86 per min", ha="left", va="top",
           fontsize=8, color=MUTED)
    style(b)
    save(fig, "fig09_ten_hour")


# ---------------------------------------------------------------- Figure 10
def fig_structure():
    k = load("w1_1000run_21oct.csv")
    v = [int(r["Invoke_us"]) for r in k]
    r2 = [int(r["invoke_us"]) for r in r100["R2"]]
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.2, 3.4), gridspec_kw={"width_ratios": [2.2, 1]})
    fig.subplots_adjust(left=0.11, right=0.98, top=0.74, bottom=0.25, wspace=0.3)
    headline(fig, "Run-to-run variation is not noise: it repeats every 20 invocations",
             "R2 Invoke time per run; 21 October 1,000-run capture (first 100 runs shown) and 22 October 100-run capture")
    n = list(range(1, 101))
    a.plot(n, [x / 1000 for x in v[:100]], color=BLUE, lw=1.1, marker="o", ms=2.6, label="21 Oct, benchmark 1000")
    a.plot(n, [x / 1000 for x in r2], color=ORANGE, lw=1.1, marker="s", ms=2.4, ls=(0, (4, 2)),
           label="22 Oct, benchmark 100 (cycle-count build)")
    for x0 in range(21, 101, 20):
        a.axvline(x0 - 0.5, color=GRID, lw=0.9)
    a.set_xlim(0, 101); a.set_ylim(401.53, 401.80)
    a.set_xlabel("Run number", color=INK); a.set_ylabel("Invoke latency (ms)", color=INK)
    a.set_title("(a) Sequence", loc="left", color=INK)
    style(a)
    a.legend(loc="lower center", bbox_to_anchor=(0.5, -0.42), ncol=2, frameon=False, fontsize=8.3)
    edges = [401.54 + 0.01 * i for i in range(21)]
    b.hist([x / 1000 for x in v], bins=edges, orientation="horizontal", color=BLUE, edgecolor="white", linewidth=0.8)
    b.set_ylim(401.53, 401.80); b.set_yticklabels([])
    b.set_xlabel("Runs (of 1,000)", color=INK)
    b.set_title("(b) Distribution", loc="left", color=INK)
    lo = sum(1 for x in v if x < 401650); hi = 1000 - lo
    b.text(5, 401.627, f"{lo} runs in the lower cluster", fontsize=8, color=INK, va="center")
    b.text(5, 401.748, f"{hi} runs in the upper cluster", fontsize=8, color=INK, va="center")
    style(b, ygrid=True)
    save(fig, "fig11_run_structure")


# ---------------------------------------------------------------- Figure 11
def fig_builds():
    k = [int(r["Invoke_us"]) for r in load("w1_1000run_21oct.csv")]
    r2 = [int(r["invoke_us"]) for r in r100["R2"]]
    d = load("drift_minutes.csv")
    dmean = sum(int(r["runs"]) * int(r["mean_us"]) for r in d) / sum(int(r["runs"]) for r in d)
    rep = [int(r["invoke_us"]) for r in load("repeat_25oct.csv") if r["runtime"] == "R2_OPTIMIZED"]
    pts = [
        ("21 Oct\nbenchmark 1000\nn = 1,000", st.mean(k), min(k), max(k), "before"),
        ("22 Oct\nbenchmark 100\nn = 100", st.mean(r2), min(r2), max(r2), "before"),
        ("22–23 Oct\ndrift 600\nn = 85,701", dmean, min(int(r["min_us"]) for r in d), max(int(r["max_us"]) for r in d), "after"),
        ("24 Oct\nbenchmark 1000\nn = 1,000", 412864, 412839, 412910, "after"),   # audit md, log C8A7DFCC...
        ("25 Oct\nimages 10, 11\nn = 20", st.mean(rep), min(rep), max(rep), "after"),
    ]
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    fig.subplots_adjust(left=0.1, right=0.98, top=0.75, bottom=0.27)
    headline(fig, "The same kernels ran 11 ms slower once a console command was added to the firmware",
             "Mean R2 Invoke latency per capture; the min–max spread in each capture is under 0.2 ms, smaller than the markers")
    for i, (lab, m, lo, hi, grp) in enumerate(pts):
        col = BLUE if grp == "before" else ORANGE
        mk = "o" if grp == "before" else "D"
        ax.errorbar([i], [m / 1000], yerr=[[m / 1000 - lo / 1000], [hi / 1000 - m / 1000]], fmt=mk, color=col,
                    ms=6.5, capsize=3, lw=1.2, mec="white", mew=0.8, zorder=3)
        ax.text(i + 0.12, m / 1000, f"{m/1000:.3f}", va="center", fontsize=8.5, color=INK)
    ax.set_xticks(range(len(pts))); ax.set_xticklabels([p[0] for p in pts], fontsize=8.2)
    ax.set_xlim(-0.5, 4.8); ax.set_ylim(400, 415)
    ax.set_ylabel("Invoke latency (ms)", color=INK)
    ax.axvspan(-0.5, 1.5, color="#eef4fc", zorder=0)
    ax.axvspan(1.5, 4.8, color="#fdf0ea", zorder=0)
    ax.text(0.5, 414.3, "Builds before the drift command\n96.40 M cycles per Invoke (22 Oct build)", ha="center", va="top", fontsize=8.3, color=INK)
    ax.text(3.15, 409.6, "Builds after the drift command\n99.07 M cycles per Invoke (drift build)", ha="center", va="top", fontsize=8.3, color=INK)
    style(ax)
    save(fig, "fig10_build_to_build")


if __name__ == "__main__":
    fig_bundled(); fig_matched(); fig_latency(); fig_kernels(); fig_memory(); fig_drift(); fig_structure(); fig_builds()
    print("done")

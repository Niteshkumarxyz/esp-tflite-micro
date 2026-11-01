import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
INK, MUTED, BLUE, ORANGE = "#0b0b0b", "#52514e", "#2a78d6", "#eb6834"
plt.rcParams.update({"font.family": "Liberation Sans"})
fig = plt.figure(figsize=(7.2, 4.3)); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 100); ax.set_ylim(0, 60); ax.axis("off")
fig.text(0.01, 0.985, "One model file, one set of input bytes, many ways to compute them", fontsize=13.5, fontweight="bold", color=INK, va="top")
fig.text(0.01, 0.925, "Only the runtime and its compiled kernels change; orange boxes are positive controls expected to differ", fontsize=10, color=MUTED, va="top")

def box(x, y, w, h, title, lines=(), fc="white", ec="#8a8984", tsize=8.6, bold=True, center=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=0.8", fc=fc, ec=ec, lw=1))
    if center:
        ax.text(x + 0.9, y + h / 2, title, fontsize=tsize, fontweight="bold" if bold else "normal", va="center", color=INK); return
    ax.text(x + 0.9, y + h - 1.0, title, fontsize=tsize, fontweight="bold" if bold else "normal", va="top", color=INK)
    for i, l in enumerate(lines):
        ax.text(x + 0.9, y + h - 3.2 - i * 2.0, l, fontsize=7.3, va="top", color=MUTED)

def group(x, y, w, h, title):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=1.0", fc="#fafaf9", ec="#b9b8b3", lw=1))
    ax.text(x + 0.8, y + h - 0.6, title, fontsize=7.8, fontweight="bold", color=MUTED, va="top")

def arrow(x1, y1, x2, y2):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=9, color="#8a8984", lw=1))

# inputs
box(0.8, 37, 20, 9.5, "W1 person_detect", ["300,568 bytes, 31 operators", "SHA-256 808cfdfc…", "12 int8 images of 9,216 B"], tsize=8.0)
box(0.8, 22.5, 20, 11.5, "W2 row-following policy", ["MLP 7→64→64→2, int8", "per-tensor and per-channel", "50,000 int8 observations", "kinematic simulator, 20 Hz"], tsize=8.0)
# ESP32 group
group(24, 34.5, 26, 15, "ESP32-D0WD-V3 at 240 MHz")
for i, (t, l) in enumerate([("R1  TFLM reference kernels", ""), ("R2A  ESP-NN ANSI C kernels", ""), ("R2  ESP-NN optimized kernels", ""), ("R2-SN  R2 with NN_SKIP_NUDGE", "")]):
    box(25, 44.3 - i * 3.2, 24, 2.4, t, tsize=6.8, center=True)
# host group
group(24, 18.5, 26, 14.2, "Host x86-64")
hosts = [("R0  LiteRT 2.3.0, reference", "white"), ("R0M  TFLM host build", "white"), ("LiteRT OPT (W2 only)", "white"), ("R0X  LiteRT default (XNNPACK)", "#fbeee8")]
for i, (t, fc) in enumerate(hosts):
    box(25, 27.6 - i * 3.0, 24, 2.3, t, fc=fc, ec=ORANGE if fc != "white" else "#8a8984", tsize=6.8, center=True)
# QEMU group
group(24, 1.5, 26, 15.2, "Arm Cortex-M on QEMU (no timing)")
qs = [("M0+ and M55: TFLM reference", "white"), ("M3: CMSIS-NN, pure C", "white"), ("M4: reference; CMSIS-NN, DSP", "white"),
      ("M55: CMSIS-NN, Helium (MVE)", "white"), ("M4: two single-rounding builds", "#fbeee8")]
for i, (t, fc) in enumerate(qs):
    box(25, 12.0 - i * 2.75, 24, 2.1, t, fc=fc, ec=ORANGE if fc != "white" else "#8a8984", tsize=6.8, center=True)
# compare box
box(56, 22, 22, 24, "Compare and record", ["Every operator output (31 per", "  W1 inference): bytes, LSB,", "  first divergent operator", "Output bytes; label change", "W2 actions; same-seed", "  trajectories; episode outcome", "Firmware identity (SHA-256)", "Invoke time and CPU cycles", "Kernels compiled (build files)"],
    fc="#eaf2fb", ec=BLUE)
box(80.5, 24, 18.8, 18, "Acceptance test", ["RQ4. Identity check first,", "then K stored vectors;", "evaluated here on the", "recorded outputs of", "the builds at left"], fc="#eef7f2", ec="#1baf7a")
ax.plot([22.4, 22.4], [9, 42], color="#8a8984", lw=1)
for y in (41.7, 28):
    ax.plot([21.3, 22.4], [y, y], color="#8a8984", lw=1)
for y in (42, 25.6, 9):
    arrow(22.4, y, 23.6, y)
for y in (42, 25, 9):
    arrow(50.5, y, 55.6, 33)
arrow(78.4, 33, 80.2, 33)
# W2 loop note
box(56, 2.6, 43, 13.6, "W2 hardware-in-the-loop (ESP32)", ["Host simulator sends the int8 observation over UART", "(115,200 baud); the board returns the int8 action;", "lockstep, so speed cannot change the outcome.", "R1, R2A, R2 × 2 models: 10,000-run benchmark,", "50,000 open-loop actions, 200 seeded episodes each"], fc="white")
fig.savefig("/home/claude/rq4/figs/fig02_bench.png", dpi=300, facecolor="white")
fig.savefig("/home/claude/rq4/figs/fig02_bench.tif", dpi=300, facecolor="white", pil_kwargs={"compression": "tiff_lzw"})
print("ok")

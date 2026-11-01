"""Conceptual diagrams (Figure 2 bench, Figure 12 acceptance test) as SVG, rendered with Playwright."""
import os, asyncio
from playwright.async_api import async_playwright
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GRAY, ACC, ACCF, GRN, GRNF, RED, REDF = "#8c8c84", "#b9791b", "#f9f3eb", "#2e7d32", "#e6f0e7", "#c62828", "#f9eaea"
INK, SEC, BLUEF, BLUE = "#1a1a1a", "#5a5a55", "#eaf2fc", "#2a78d6"
FONT = "Liberation Sans, Arial, Helvetica, sans-serif"


def box(x, y, w, h, title, lines=(), stroke=GRAY, fill="#ffffff", dash=False, tsize=30, lsize=25, sw=3):
    d = ' stroke-dasharray="12 8"' if dash else ""
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>']
    out.append(f'<text x="{x+26}" y="{y+46}" font-size="{tsize}" font-weight="bold" fill="{INK}">{title}</text>')
    for i, ln in enumerate(lines):
        out.append(f'<text x="{x+26}" y="{y+86+i*34}" font-size="{lsize}" fill="{SEC}">{ln}</text>')
    return "\n".join(out)


def arrow(x1, y1, x2, y2, label=None, lx=None, ly=None):
    s = f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{GRAY}" stroke-width="3" marker-end="url(#ah)"/>'
    if label:
        s += f'<text x="{lx}" y="{ly}" font-size="26" fill="{SEC}" text-anchor="middle">{label}</text>'
    return s


def poly(points, label=None, lx=None, ly=None):
    p = " ".join(f"{a},{b}" for a, b in points)
    s = f'<polyline points="{p}" fill="none" stroke="{GRAY}" stroke-width="3" marker-end="url(#ah)"/>'
    if label:
        s += f'<text x="{lx}" y="{ly}" font-size="26" fill="{SEC}" text-anchor="middle">{label}</text>'
    return s


def diamond(cx, cy, w, h, l1, l2):
    pts = f"{cx},{cy-h/2} {cx+w/2},{cy} {cx},{cy+h/2} {cx-w/2},{cy}"
    return (f'<polygon points="{pts}" fill="#ffffff" stroke="{GRAY}" stroke-width="3"/>'
            f'<text x="{cx}" y="{cy-6}" font-size="29" font-weight="bold" fill="{INK}" text-anchor="middle">{l1}</text>'
            f'<text x="{cx}" y="{cy+32}" font-size="29" font-weight="bold" fill="{INK}" text-anchor="middle">{l2}</text>')


def svg(w, h, body, title, sub=None):
    t = f'<text x="60" y="72" font-size="38" font-weight="bold" fill="{INK}">{title}</text>'
    if sub:
        t += f'<text x="60" y="122" font-size="28" fill="{SEC}">{sub}</text>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" font-family="{FONT}">
<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
<path d="M0,0 L10,5 L0,10 z" fill="{GRAY}"/></marker></defs>
<rect width="100%" height="100%" fill="#ffffff"/>{t}{body}</svg>'''


def bench():
    b = []
    # inputs
    b.append(box(60, 310, 400, 185, "Model file", ["person_detect.tflite", "300,568 bytes", "SHA-256 808cfdfc…"]))
    b.append(box(60, 530, 400, 185, "int8 input bytes", ["10 bundled images", "person.bmp, no_person.bmp", "9,216 bytes each, made once"]))
    # host group
    b.append(f'<rect x="560" y="175" width="660" height="355" rx="18" fill="#fbfbfa" stroke="{GRAY}" stroke-width="2"/>')
    b.append(f'<text x="584" y="215" font-size="26" font-weight="bold" fill="{SEC}">Host, x86-64</text>')
    b.append(box(584, 235, 612, 82, "R0  LiteRT reference kernels", [], tsize=27))
    b.append(box(584, 330, 612, 82, "R0M  TFLM host test (1ee5135b)", [], tsize=27))
    b.append(box(584, 425, 612, 82, "R0X  LiteRT default, XNNPACK", [], stroke=ACC, fill=ACCF, tsize=27))
    # esp32 group
    b.append(f'<rect x="560" y="565" width="660" height="355" rx="18" fill="#fbfbfa" stroke="{GRAY}" stroke-width="2"/>')
    b.append(f'<text x="584" y="605" font-size="26" font-weight="bold" fill="{SEC}">ESP32-D0WD-V3, 240 MHz, one board</text>')
    b.append(box(584, 625, 612, 82, "R1  TFLM reference kernels", [], tsize=27))
    b.append(box(584, 720, 612, 82, "R2A  ESP-NN ANSI C kernels", [], tsize=27))
    b.append(box(584, 815, 612, 82, "R2  ESP-NN optimized (conv, dw, softmax)", [], tsize=27))
    # compare
    b.append(box(1330, 330, 520, 385, "Compare and record", [
        "Output bytes: bit-exact?",
        "Distance in LSB; label change",
        "First divergent operator",
        "Firmware identity (ELF SHA-256)",
        "Invoke time and CPU cycles",
        "Kernels compiled (build files)"], stroke=BLUE, fill=BLUEF))
    # arrows
    b.append(arrow(460, 400, 556, 370))
    b.append(arrow(460, 600, 556, 760))
    b.append(arrow(1220, 370, 1326, 450))
    b.append(arrow(1220, 760, 1326, 620))
    # notes
    b.append(f'<text x="584" y="965" font-size="25" fill="{SEC}">Two comparisons on the ESP32: R1 vs R2A (two C implementations), R2A vs R2 (ANSI vs optimized variants).</text>')
    b.append(f'<text x="584" y="1003" font-size="25" fill="{SEC}">R0X is a positive control: a path known to compute differently. Corstone-300 FVP (Cortex-M55) was not built.</text>')
    b.append(f'<rect x="60" y="770" width="400" height="150" rx="16" fill="{ACCF}" stroke="{ACC}" stroke-width="3"/>')
    b.append(f'<text x="86" y="816" font-size="27" font-weight="bold" fill="{INK}">Orange = positive control</text>')
    b.append(f'<text x="86" y="856" font-size="25" fill="{SEC}">It shows the comparison can</text>')
    b.append(f'<text x="86" y="890" font-size="25" fill="{SEC}">detect a real difference</text>')
    return svg(1900, 1040, "\n".join(b), "One model file, one set of input bytes, six ways to compute them",
               "Only the runtime and its kernels change between configurations; everything that reaches them is identical")


def kat():
    b = []
    b.append(box(40, 200, 270, 140, "Boot", ["new firmware"]))
    b.append(arrow(310, 270, 368, 270))
    b.append(diamond(560, 270, 380, 230, "Identity equals", "qualified record?"))
    b.append(f'<text x="540" y="425" font-size="24" fill="{SEC}" text-anchor="end">app ELF SHA-256</text>')
    b.append(arrow(750, 270, 830, 270, "yes", 790, 252))
    b.append(box(834, 190, 470, 160, "Run K stored vectors", ["inputs from flash, through", "the build that drives the robot"]))
    b.append(arrow(1304, 270, 1386, 270))
    b.append(diamond(1580, 270, 380, 230, "Every output", "byte equal?"))
    b.append(poly([(1580, 385), (1580, 520)], "yes", 1615, 465))
    b.append(box(1380, 524, 400, 150, "Arm actuators", ["normal operation"], stroke=GRN, fill=GRNF))
    b.append(poly([(560, 385), (560, 524)], "no", 595, 465))
    b.append(poly([(1390, 270), (1390, 270)]))
    b.append(box(300, 524, 700, 190, "Stay disarmed", ["Log which check failed and the first failing", "vector; request requalification"], stroke=RED, fill=REDF))
    b.append(poly([(1580, 385), (1580, 440), (1130, 440), (1130, 600), (1004, 600)], "no", 1170, 430))
    b.append(f'<text x="40" y="790" font-size="26" fill="{SEC}">Actuators start disarmed. A firmware image the bootloader rejects never reaches these checks, so it can never arm the robot.</text>')
    b.append(f'<text x="40" y="828" font-size="26" fill="{SEC}">K = 16, 64 or 256. Storage: 9,218 bytes per W1 vector and 9 bytes per W2 vector. Identity is checked first because</text>')
    b.append(f'<text x="40" y="866" font-size="26" fill="{SEC}">two different builds can give the same output bytes.</text>')
    return svg(1900, 900, "\n".join(b), "The robot arms only if it is the qualified build and every stored output matches")


async def render(name, markup, w, h):
    html = f"<html><body style='margin:0'>{markup}</body></html>"
    async with async_playwright() as p:
        br = await p.chromium.launch()
        pg = await br.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        await pg.set_content(html)
        await pg.wait_for_timeout(200)
        png = os.path.join(HERE, name + ".png")
        await pg.screenshot(path=png, clip={"x": 0, "y": 0, "width": w, "height": h})
        await br.close()
    im = Image.open(png).convert("RGB")
    im.save(png, dpi=(300, 300))
    im.save(os.path.join(HERE, name + ".tif"), dpi=(300, 300), compression="tiff_lzw")


if __name__ == "__main__":
    asyncio.run(render("fig02_bench", bench(), 1900, 1040))
    asyncio.run(render("fig12_acceptance_test", kat(), 1900, 900))
    print("ok")

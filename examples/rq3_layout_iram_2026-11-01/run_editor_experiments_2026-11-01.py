"""Experiments asked for in the editor's e-mail of 1 November 2026, run on the ESP32 with one command.

Part A - skip-nudge requantize on the chip
  Builds examples/skipnudge_requant_test_2026-11-01, which compares ESP-NN 1.4.1's bit-exact and skip-nudge
  requantize functions on the ESP32 itself (random accumulators, exact rounding ties, the INT32_MAX boundary).
  The header it uses is copied from examples/person_detection/managed_components and checked by SHA-256.

Part B - the layout effect and the skip-nudge speed-up, with the kernels in flash and in IRAM
  Makes two new project copies of person_detection next to it:
    examples/rq3_layout_pre_2026-11-01   application files as on 21 October (before the drift command,
                                         failure guard and watchdog): esp_cli.c.before_drift_20261022,
                                         main_functions.cc.bak_invoke_failure_guard_20261024_213642,
                                         CMakeLists.txt.before_drift_20261022, esp_main.h.auto_benchmark_20261020_231641.bak
    examples/rq3_layout_post_2026-11-01  application files as they are now (the 28 October builds)
  and builds six variants, each with the original sdkconfig of the build it reproduces:
    pre_flash   pre_iram    (sdkconfig.cycle_optimized_20261021, the 401.6 ms build)
    post_flash  post_iram   (sdkconfig.b5_normal_r2_notrace_2026-10-28, the 412.5 ms build)
    sn_flash    sn_iram     (sdkconfig.b5_skip_nudge_notrace_2026-10-28, the 391.1 ms build)
  "_iram" adds iram_kernels/linker.lf, which places esp_nn_conv_opt and esp_nn_depthwise_conv_opt in IRAM.
  Each flash variant's linker map is compared with the original build it reproduces.
  Then, on the board, 'benchmark 1000' runs for: the original 21 October binary, the original 28 October binary,
  the six variants, and the two original binaries again (an A-B ... A-B swap on one board, one day).

Writes only new files: the two project copies, their build folders, and the evidence folder
  examples/person_detection/chapter_evidence/editor_experiments_2026-11-01/
Run from the ESP-IDF 6.0 PowerShell, in this folder, with idf.py monitor closed, charger connected:
    python run_editor_experiments_2026-11-01.py
Takes about 2.5 to 3 hours (seven builds, then ten board runs). The window must stay open; the script keeps
Windows awake while it runs. 'python run_editor_experiments_2026-11-01.py --build-only' builds and checks without the board.
"""
import csv
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import serial

PORT, BAUD = "COM5", 115200
RUNS = 1000
HERE = Path(__file__).resolve().parent
EX = HERE.parent
PD = EX / "person_detection"
EVID = PD / "chapter_evidence" / "editor_experiments_2026-11-01"
REQ = EX / "skipnudge_requant_test_2026-11-01"
PRE, POST = EX / "rq3_layout_pre_2026-11-01", EX / "rq3_layout_post_2026-11-01"
HEADER = PD / "managed_components" / "espressif__esp-nn" / "src" / "common" / "common_functions.h"
HEADER_SHA = "350ffcdbc3f834896c041479dcbe8b6be51900c520d68802e1ebabfbccb10efd"
ESP_NN_HASH = "3b3411b0e4ad1717a72870fde9f9b67cef6f3f97491cc64fcfc1910a8fd8a246"
PRE_FILES = {  # file in the copy's main/  <-  backup in person_detection/main/ (state of 21 October)
    "esp_cli.c": "esp_cli.c.before_drift_20261022",
    "main_functions.cc": "main_functions.cc.bak_invoke_failure_guard_20261024_213642",
    "CMakeLists.txt": "CMakeLists.txt.before_drift_20261022",
    "esp_main.h": "esp_main.h.auto_benchmark_20261020_231641.bak",
}
ORIGINALS = {  # existing build folders, used read-only
    "orig_pre": PD / "build_cycle_optimized_20261021",
    "orig_post": PD / "build_b5_normal_r2_notrace_2026-10-28",
    "orig_sn": PD / "build_b5_skip_nudge_notrace_2026-10-28",
}
VARIANTS = [  # name, project, sdkconfig source, iram, skip-nudge expected, original it reproduces
    ("pre_flash", PRE, "sdkconfig.cycle_optimized_20261021", False, False, "orig_pre"),
    ("post_flash", POST, "sdkconfig.b5_normal_r2_notrace_2026-10-28", False, False, "orig_post"),
    ("sn_flash", POST, "sdkconfig.b5_skip_nudge_notrace_2026-10-28", False, True, "orig_sn"),
    ("pre_iram", PRE, "sdkconfig.cycle_optimized_20261021", True, False, None),
    ("post_iram", POST, "sdkconfig.b5_normal_r2_notrace_2026-10-28", True, False, None),
    ("sn_iram", POST, "sdkconfig.b5_skip_nudge_notrace_2026-10-28", True, True, None),
]
BOARD_ORDER = ["orig_pre", "orig_post", "pre_flash", "post_flash", "sn_flash", "pre_iram", "post_iram", "sn_iram",
               "orig_pre", "orig_post"]
EXPECTED_PERSON = {0: 115, 1: -39, 2: 115, 3: 67, 4: 111, 5: -100, 6: 97, 7: -98, 8: 114, 9: 83}
IRAM_LO, IRAM_HI = 0x40080000, 0x400A0000
ANSI = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")
BUILD_ENV = {k: v for k, v in os.environ.items() if k != "TFLM_RQ1_TRACE_BUILD"}


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def write_with_sidecar(path, data):
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite {path}")
    path.write_bytes(data)
    Path(str(path) + ".sha256.txt").write_text(f"{sha256_bytes(data).upper()}  {path.name}\n", encoding="ascii")


def keep_awake(on):
    try:
        return bool(ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | (0x00000001 if on else 0)))
    except Exception:
        return False


LOG = None


def say(text):
    print(text, flush=True)
    LOG.write(text + "\n")
    LOG.flush()


# ------------------------------------------------------------------------------------------- building
def run_build(cmd, cwd, name):
    p = subprocess.Popen(cmd, cwd=cwd, env=BUILD_ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace")
    lines = []
    for line in p.stdout:
        lines.append(line)
        m = re.match(r"\[(\d+)/(\d+)\]", line)
        if m and int(m.group(1)) % 250 == 0:
            say(f"[{name}]   step {m.group(1)}/{m.group(2)}")
    return p.wait(), "".join(lines)


def idf_build(name, project, bdir_name, extra, run_id):
    cmd = [sys.executable, str(Path(os.environ["IDF_PATH"]) / "tools" / "idf.py"), "-B", bdir_name,
           "-D", f"SDKCONFIG={bdir_name}/sdkconfig", *extra, "build"]
    say(f"[{name}] building in {project.name}/{bdir_name} ...")
    t0 = time.time()
    code, text = run_build(cmd, project, name)
    if code != 0 and "internal compiler error" in text:
        say(f"[{name}] compiler crashed (internal compiler error); retrying once")
        write_with_sidecar(EVID / f"build_log_{name}_{run_id}_attempt1.txt", text.encode("utf-8"))
        code, text = run_build(cmd, project, name)
    write_with_sidecar(EVID / f"build_log_{name}_{run_id}.txt",
                       ("COMMAND: " + " ".join(cmd) + f"\nCWD: {project}\nRETURN_CODE: {code}\n\n" + text).encode("utf-8"))
    say(f"[{name}] build return code {code} in {time.time() - t0:.0f} s")
    return code == 0


EXTERNS = [b"extern volatile int g_benchmark_mode;", b"extern volatile int g_last_invoke_ok;",
           b"extern volatile long long g_last_invoke_us;", b"extern volatile uint32_t g_last_invoke_cycles;",
           b"extern volatile int g_last_raw_person;", b"extern volatile int g_last_raw_no_person;"]


def pre_esp_main_h():
    """esp_main.h as it must have been on 21 October.

    The backup of 20 October defines CLI_ONLY_INFERENCE for the ESP32 (the 21 October main/CMakeLists.txt does not),
    and the 21 October esp_cli.c reads the g_* benchmark variables, so the header of that day also declared them.
    Declarations and #include <stdint.h> generate no code, so this header gives the same object code as the original.
    """
    src = (PD / "main" / PRE_FILES["esp_main.h"]).read_bytes()
    nl = b"\r\n" if b"\r\n" in src else b"\n"
    anchor = b"extern void run_inference(void *ptr);"
    if src.count(anchor) != 1 or b"g_benchmark_mode" in src:
        raise RuntimeError("esp_main.h backup is not the expected 20 October version")
    src = src.replace(b'#include "sdkconfig.h"', b'#include "sdkconfig.h"' + nl + b"#include <stdint.h>", 1)
    return src.replace(anchor, anchor + nl + nl.join(EXTERNS), 1)


def copy_main(dst_main, pre):
    keep = re.compile(r"^(CMakeLists\.txt|Kconfig\.projbuild|idf_component\.yml|[^.]+\.(c|cc|h))$")
    dst_main.mkdir(parents=True)
    for f in sorted((PD / "main").iterdir()):
        if f.is_file() and keep.match(f.name):
            shutil.copy2(f, dst_main / f.name)
    if pre:
        for target, backup in PRE_FILES.items():
            if target == "esp_main.h":
                (dst_main / target).write_bytes(pre_esp_main_h())
            else:
                shutil.copy2(PD / "main" / backup, dst_main / target)


def root_cmake():
    """examples/person_detection/CMakeLists.txt with one addition: -D IRAM_KERNELS=1 adds the iram_kernels component."""
    src = (PD / "CMakeLists.txt").read_bytes()
    nl = b"\r\n" if b"\r\n" in src else b"\n"
    anchor = b"set(EXTRA_COMPONENT_DIRS static_images)"
    if src.count(anchor) != 1:
        raise RuntimeError("person_detection/CMakeLists.txt does not have the expected EXTRA_COMPONENT_DIRS line")
    block = nl.join([b"if(IRAM_KERNELS)",
                     b'    list(APPEND EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_LIST_DIR}/../rq3_layout_iram_2026-11-01/iram_kernels")',
                     b"endif()"])
    return src.replace(anchor, anchor + nl + block, 1)


def make_project(dst, pre):
    marker = dst / "MADE_BY_run_editor_experiments_2026-11-01.txt"
    if dst.exists():
        if marker.exists():
            say(f"{dst.name} already exists from an earlier run of this script; reusing it")
            return
        raise FileExistsError(f"{dst} exists and was not made by this script; not touching it")
    say(f"making {dst.name} ({'21 October application files' if pre else 'current application files'})")
    dst.mkdir()
    (dst / "CMakeLists.txt").write_bytes(root_cmake())
    shutil.copytree(PD / "static_images", dst / "static_images")
    copy_main(dst / "main", pre)
    for f in ("dependencies.lock", "sdkconfig.defaults", "partitions.csv"):
        shutil.copy2(PD / f, dst / f)
    shutil.copytree(PD / "managed_components", dst / "managed_components")
    lines = [f"Copy of examples/person_detection made {datetime.now().isoformat(timespec='seconds')} by "
             "rq3_layout_iram_2026-11-01/run_editor_experiments_2026-11-01.py.",
             "21 October application files (backups in person_detection/main) with esp_main.h rebuilt from its "
             "20 October backup plus the g_* declarations." if pre else "Application files as they are now.",
             "SHA-256 of the files used:"]
    for f in [dst / "CMakeLists.txt", dst / "partitions.csv"] + sorted((dst / "main").iterdir()):
        lines.append(f"{sha256_bytes(f.read_bytes())}  {f.relative_to(dst).as_posix()}")
    marker.write_text("\n".join(lines) + "\n", encoding="utf-8")


def map_info(bdir):
    mp = next(iter(sorted(bdir.glob("*.map"))), None)
    info = {"map": mp.name if mp else None}
    if mp is None:
        return info
    text = mp.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^\s+(0x[0-9a-f]+)\s+0x49618\s+\S*person_detect_model_data\.cc\.obj", text, re.M)
    info["model_array"] = m.group(1) if m else None
    for key, fn in (("conv_kernel", "esp_nn_conv_s8_opt"), ("depthwise_kernel", "esp_nn_depthwise_conv_s8_opt")):
        m = re.search(r"^ \.text\." + fn + r"\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)", text, re.M)
        info[key] = m.group(1) if m else None
        info[key + "_size"] = m.group(2) if m else None
    return info


def file_info(bdir):
    out = {}
    for k, f in (("bin", "person_detection.bin"), ("elf", "person_detection.elf")):
        p = bdir / f
        out[k] = sha256_bytes(p.read_bytes()) if p.is_file() else None
        out[k + "_bytes"] = p.stat().st_size if p.is_file() else None
    return out


def check_variant(name, project, bdir, iram, sn):
    problems = []
    cfg = json.loads((bdir / "config" / "sdkconfig.json").read_text(encoding="utf-8"))
    want = {"ESP_TFLITE_MICRO_USE_ESP_NN": True, "NN_OPTIMIZED": True, "NN_SKIP_NUDGE": sn,
            "COMPILER_OPTIMIZATION_PERF": True, "ESPTOOLPY_FLASHMODE_QIO": True, "ESPTOOLPY_FLASHFREQ_80M": True}
    for k, v in want.items():
        if bool(cfg.get(k, False)) != v:
            problems.append(f"{k}={cfg.get(k)} (expected {v})")
    if cfg.get("ESP_DEFAULT_CPU_FREQ_MHZ") != 240 or cfg.get("FREERTOS_HZ") != 100:
        problems.append(f"CPU {cfg.get('ESP_DEFAULT_CPU_FREQ_MHZ')} MHz, tick {cfg.get('FREERTOS_HZ')} Hz")
    if "TFLM_RQ1_TRACE" in (bdir / "compile_commands.json").read_text(encoding="utf-8", errors="replace"):
        problems.append("trace code compiled in")
    lock = (project / "dependencies.lock").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"espressif/esp-nn:\s*\n\s*component_hash:\s*([0-9a-f]+)[\s\S]*?version:\s*([0-9.]+)", lock)
    if not m or m.group(1) != ESP_NN_HASH or m.group(2) != "1.4.1":
        problems.append("esp-nn is not 1.4.1 with the expected hash")
    info = map_info(bdir)
    for key in ("conv_kernel", "depthwise_kernel"):
        a = int(info[key], 16) if info.get(key) else None
        in_iram = a is not None and IRAM_LO <= a < IRAM_HI
        if a is None:
            problems.append(f"{key} not found in the linker map")
        elif in_iram != iram:
            problems.append(f"{key} at {info[key]}: in IRAM={in_iram}, expected {iram}")
    return problems, info


# ------------------------------------------------------------------------------------------- the board
class Port:
    def __init__(self):
        self.ser = serial.Serial()
        self.ser.port, self.ser.baudrate, self.ser.timeout = PORT, BAUD, 0.1
        self.ser.dtr = False
        self.ser.rts = False
        self.ser.open()
        self.raw = bytearray()

    def pump(self):
        c = self.ser.read(8192)
        if c:
            self.raw.extend(c)

    def wait_for(self, marker, start, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            i = self.raw.find(marker, start)
            if i >= 0:
                return i + len(marker)
            self.pump()
        return None

    def reset(self):
        self.ser.dtr = False
        self.ser.rts = True
        time.sleep(0.2)
        self.ser.rts = False

    def boot(self):
        start = len(self.raw)
        self.reset()
        got = self.wait_for(b"rst:", start, 10)
        if got is None or self.raw.find(b"waiting for download", start) >= 0:
            start = len(self.raw)
            self.reset()
            got = self.wait_for(b"rst:", start, 10)
        if got is None:
            say("    automatic reset did not respond; press and release EN once (not BOOT)")
            got = self.wait_for(b"rst:", start, 120)
        if got is None:
            raise RuntimeError("no reset seen")
        return start, got


def flash(name, bdir, run_id, tag):
    cmd = [sys.executable, "-m", "esptool", "--chip", "esp32", "-p", PORT, "-b", "460800",
           "--before", "default-reset", "--after", "hard-reset", "write-flash", "@flash_args"]
    p = subprocess.run(cmd, cwd=bdir, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = "COMMAND: " + " ".join(cmd) + f"\nCWD: {bdir}\nRETURN_CODE: {p.returncode}\n\n" + p.stdout + "\n" + p.stderr
    write_with_sidecar(EVID / f"flash_log_{tag}_{run_id}.txt", out.encode("utf-8"))
    regions = sum(1 for line in (bdir / "flash_args").read_text().splitlines() if line.strip().startswith("0x"))
    ok = p.returncode == 0 and out.count("Hash of data verified") == regions
    say(f"[{name}] flash {'OK' if ok else 'FAILED'} ({out.count('Hash of data verified')}/{regions} regions verified)")
    return ok


def run_requant(run_id):
    say("\n=== Part A: skip-nudge requantize on the chip ===")
    hdr = HEADER.read_bytes()
    if sha256_bytes(hdr) != HEADER_SHA:
        say(f"ESP-NN header hash differs from the analysed one ({sha256_bytes(hdr)}); stopping Part A")
        return None
    dst = REQ / "main" / "common_functions.h"
    if dst.exists() and dst.read_bytes() != hdr:
        raise RuntimeError(f"{dst} exists and differs from the ESP-NN header")
    if not dst.exists():
        dst.write_bytes(hdr)
    if not idf_build("requant", REQ, "build", [], run_id):
        return None
    bdir = REQ / "build"
    if not flash("requant", bdir, run_id, "requant"):
        return None
    time.sleep(1.0)
    port = Port()
    try:
        start, _ = port.boot()
        done = port.wait_for(b"REQ_DONE", start, 600)
        port.wait_for(b"\n", done or start, 2)
        data = bytes(port.raw[start:])
    finally:
        port.ser.close()
    write_with_sidecar(EVID / f"requant_on_chip_{run_id}.txt", data)
    text = ANSI.sub(b"", data).decode("utf-8", errors="replace")
    res = {}
    for line in text.splitlines():
        if line.startswith("REQ_RESULT,"):
            kv = dict(p.split("=", 1) for p in line.strip().split(",")[1:] if "=" in p)
            res[kv["set"]] = kv
            say(f"  {kv['set']}: {kv['cases']} cases, {kv['differ']} differ, {kv['at_int32_max_overflow']} at the INT32_MAX overflow")
    if b"REQ_DONE" not in data:
        say("  REQ_DONE not seen - the test did not finish")
    return res


def benchmark(tag, bdir, run_id, idx):
    if not flash(tag, bdir, run_id, f"{idx:02d}_{tag}"):
        raise RuntimeError("flash failed")
    time.sleep(1.0)
    port = Port()
    try:
        start, got = port.boot()
        prompt = port.wait_for(b"esp>", got, 60)
        if prompt is None:
            port.ser.write(b"\r\n")
            prompt = port.wait_for(b"esp>", got, 20)
        if prompt is None:
            raise RuntimeError("CLI prompt not seen")
        time.sleep(0.5)
        port.ser.write(f"benchmark {RUNS}\r\n".encode("ascii"))
        port.ser.flush()
        say(f"[{tag}] benchmark {RUNS} started ({datetime.now():%H:%M:%S}); about 7 minutes")
        end = port.wait_for(b"BENCH_SUMMARY", prompt, RUNS * 0.6 + 300)
        if end is None:
            raise RuntimeError("BENCH_SUMMARY not seen")
        port.wait_for(b"esp>", end, 15)
        data = bytes(port.raw[start:])
    finally:
        port.ser.close()
    fname = f"bench_{idx:02d}_{tag}_{run_id}.txt"
    write_with_sidecar(EVID / fname, data)
    return fname, data


def parse_bench(data):
    text = ANSI.sub(b"", data).decode("utf-8", errors="replace").replace("\r", "")
    us, cyc, outs_ok, n = [], [], 0, 0
    summary, elf_banner = {}, None
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("BENCH_SAMPLE,"):
            f = line.split(",")
            if len(f) >= 8:
                n += 1
                us.append(int(f[3])); cyc.append(int(f[4]))
                img, person, ok = int(f[2]), int(f[5]), int(f[7])
                outs_ok += int(ok == 1 and EXPECTED_PERSON.get(img) == person)
        elif line.startswith("BENCH_SUMMARY,"):
            summary = dict(p.split("=", 1) for p in line.split(",")[1:] if "=" in p)
        m = re.search(r"ELF file SHA256:\s*([0-9a-f]+)", line)
        if m and elf_banner is None:
            elf_banner = m.group(1)
    r = {"samples": n, "outputs_as_expected": outs_ok, "elf_banner": elf_banner, "summary_mean_us": summary.get("mean_us")}
    if us:
        r.update(mean_us=sum(us) / len(us), min_us=min(us), max_us=max(us), mean_cycles=sum(cyc) / len(cyc))
    return r


def main():
    global LOG
    if "IDF_PATH" not in os.environ:
        print("Please run this from the ESP-IDF 6.0 PowerShell (IDF_PATH is not set).")
        return 2
    try:
        vt = (Path(os.environ["IDF_PATH"]) / "tools" / "cmake" / "version.cmake").read_text(encoding="utf-8")
        ver = ".".join(re.search(rf"set\(IDF_VERSION_{k}\s+(\d+)\)", vt).group(1) for k in ("MAJOR", "MINOR", "PATCH"))
    except Exception:
        ver = "unknown"
    if ver != "6.0.3":
        print(f"This window has ESP-IDF {ver} (IDF_PATH={os.environ['IDF_PATH']}).")
        print("All earlier builds used ESP-IDF 6.0.3, so this script runs only under 6.0.3. Nothing was built or flashed.")
        return 2
    build_only = "--build-only" in sys.argv[1:]
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    EVID.mkdir(parents=True, exist_ok=True)
    LOG = (EVID / f"run_log_{run_id}.txt").open("w", encoding="utf-8")
    awake = keep_awake(True)
    try:
        return experiments(run_id, build_only, awake)
    finally:
        keep_awake(False)
        LOG.close()


def experiments(run_id, build_only, awake):
    say(f"Editor experiments, run {run_id}; IDF_PATH={os.environ['IDF_PATH']}; keep-awake: {awake}; "
        f"{'BUILD ONLY' if build_only else 'build and board'}")
    needed = [PD / "main" / b for b in PRE_FILES.values()] + [PD / v[2] for v in VARIANTS] + [HEADER]
    if not build_only:
        needed += [d / "flash_args" for d in ORIGINALS.values()]
    for p in needed:
        if not p.exists():
            say(f"Missing input: {p}")
            return 3
    if not build_only:
        try:
            Port().ser.close()
        except Exception as exc:
            say(f"Cannot open {PORT} ({exc}). Close idf.py monitor or any serial terminal, check the cable, run again.")
            return 3

    if build_only:
        dst = REQ / "main" / "common_functions.h"
        if not dst.exists():
            dst.write_bytes(HEADER.read_bytes())
        requant = None if idf_build("requant", REQ, "build", [], run_id) else "build failed"
    else:
        requant = run_requant(run_id)

    say("\n=== Part B: builds ===")
    make_project(PRE, pre=True)
    make_project(POST, pre=False)
    builds, rows = {}, []
    for name, project, scfg, iram, sn, orig in VARIANTS:
        bname = f"build_{name}"
        bdir = project / bname
        if not bdir.exists():
            bdir.mkdir()
            shutil.copy2(PD / scfg, bdir / "sdkconfig")
        extra = ["-D", "IRAM_KERNELS=1"] if iram else []
        if not idf_build(name, project, bname, extra, run_id):
            say(f"[{name}] BUILD FAILED; stopping before the board runs")
            return 4
        problems, info = check_variant(name, project, bdir, iram, sn)
        files = file_info(bdir)
        same = None
        if orig and (ORIGINALS[orig] / "person_detection.map").exists():
            oi, of = map_info(ORIGINALS[orig]), file_info(ORIGINALS[orig])
            same = (oi.get("model_array") == info.get("model_array") and oi.get("conv_kernel") == info.get("conv_kernel")
                    and oi.get("depthwise_kernel") == info.get("depthwise_kernel") and of["bin_bytes"] == files["bin_bytes"])
            say(f"[{name}] layout reproduces {orig}: {same} (model {info.get('model_array')} vs {oi.get('model_array')}, "
                f"conv {info.get('conv_kernel')} vs {oi.get('conv_kernel')}, BIN {files['bin_bytes']} vs {of['bin_bytes']} bytes)")
        if problems:
            say(f"[{name}] CHECK FAILED: {problems}; stopping before the board runs")
            return 4
        say(f"[{name}] OK: conv {info['conv_kernel']}, depthwise {info['depthwise_kernel']}, model {info['model_array']}")
        builds[name] = {"dir": bdir, "info": info, "files": files, "reproduces": orig, "layout_reproduced": same,
                        "iram": iram, "skip_nudge": sn}
    if build_only:
        say("\nBuild-only run finished; nothing was flashed.")
        return 0
    for tag, d in ORIGINALS.items():
        builds[tag] = {"dir": d, "info": map_info(d), "files": file_info(d), "reproduces": None, "layout_reproduced": None,
                       "iram": False, "skip_nudge": tag == "orig_sn"}

    say(f"\n=== Part B: board runs, {len(BOARD_ORDER)} x benchmark {RUNS} (about 80 minutes) ===")
    for idx, tag in enumerate(BOARD_ORDER, 1):
        b = builds[tag]
        try:
            fname, data = benchmark(tag, b["dir"], run_id, idx)
            r = parse_bench(data)
            err = ""
        except Exception as exc:
            fname, r, err = "", {}, repr(exc)
        elf_ok = bool(r.get("elf_banner")) and (b["files"]["elf"] or "").startswith(r.get("elf_banner") or "x")
        row = {"order": idx, "build": tag, "log": fname, "error": err, "iram": b["iram"], "skip_nudge": b["skip_nudge"],
               "bin_sha256": b["files"]["bin"], "elf_banner": r.get("elf_banner"), "elf_banner_matches_elf": elf_ok,
               "model_array": b["info"].get("model_array"), "conv_kernel": b["info"].get("conv_kernel"),
               "depthwise_kernel": b["info"].get("depthwise_kernel"), "samples": r.get("samples"),
               "outputs_as_expected": r.get("outputs_as_expected"), "mean_us": r.get("mean_us"),
               "min_us": r.get("min_us"), "max_us": r.get("max_us"), "mean_cycles": r.get("mean_cycles"),
               "firmware_mean_us": r.get("summary_mean_us")}
        rows.append(row)
        say(f"[{tag}] mean {r.get('mean_us', 0) / 1000:.3f} ms, cycles {r.get('mean_cycles', 0) / 1e6:.3f} M, "
            f"outputs {r.get('outputs_as_expected')}/{r.get('samples')}, ELF banner matches: {elf_ok}"
            + (f"; ERROR {err}" if err else ""))

    csv_path = EVID / f"editor_experiments_summary_{run_id}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    Path(str(csv_path) + ".sha256.txt").write_text(f"{sha256_bytes(csv_path.read_bytes()).upper()}  {csv_path.name}\n",
                                                   encoding="ascii")
    meta = {"run_id": run_id, "runs_per_benchmark": RUNS, "requant_on_chip": requant,
            "builds": {k: {"dir": str(v["dir"]), "info": v["info"], "files": v["files"], "reproduces": v["reproduces"],
                           "layout_reproduced": v["layout_reproduced"]} for k, v in builds.items()}}
    write_with_sidecar(EVID / f"editor_experiments_metadata_{run_id}.json", json.dumps(meta, indent=2).encode("utf-8"))

    mean = {}
    for r in rows:
        if r["mean_us"]:
            mean.setdefault(r["build"], []).append(r["mean_us"] / 1000)
    say("\n=== RESULT (mean Invoke, ms) ===")
    for k, v in mean.items():
        say(f"  {k:10s} " + ", ".join(f"{x:.3f}" for x in v))
    g = lambda k: mean[k][0] if k in mean else float("nan")
    say(f"  layout gap, kernels in flash : post - pre = {g('post_flash') - g('pre_flash'):+.3f} ms")
    say(f"  layout gap, kernels in IRAM  : post - pre = {g('post_iram') - g('pre_iram'):+.3f} ms")
    say(f"  skip-nudge saving, flash     : {100 * (g('post_flash') - g('sn_flash')) / g('post_flash'):.2f} %")
    say(f"  skip-nudge saving, IRAM      : {100 * (g('post_iram') - g('sn_iram')) / g('post_iram'):.2f} %")
    say(f"Outputs: {EVID}")
    say("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())

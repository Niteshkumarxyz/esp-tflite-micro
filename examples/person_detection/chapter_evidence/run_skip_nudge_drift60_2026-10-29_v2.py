"""Skip-nudge R2: 60-minute drift capture on the ESP32 (COM5), 29 October 2026 - version 2.

Version 2 differs from version 1 only in two ways: it asks Windows not to sleep while it runs
(SetThreadExecutionState, released when the script ends; no setting is changed), and it records the
PC clock time at which each minute record arrives, so any pause on the PC side is visible.
Run 1 (20261029_114237) stopped after minute 59 because the PC slept; its partial log is kept as is.

What this script does, in order:
  1. Checks the existing build_b5_skip_nudge_notrace_2026-10-28 files against the
     SHA-256 values recorded on 28 October (BIN, ELF, sdkconfig snapshot) and checks
     that the build is optimized ESP-NN with SKIP_NUDGE and without trace code.
  2. Flashes those exact images with esptool (no rebuild) and keeps the flash log.
  3. Resets the board, records the boot banner, sends `drift 60`, and saves every
     serial byte until DRIFT_END in a raw log.
  4. Writes SHA-256 sidecars, a per-minute CSV, a JSON metadata file and an audit
     report that re-derives every summary value from the raw log.

Only new files are written, all inside chapter_evidence/skip_nudge_drift60_2026-10-29/.
Run it from the ESP-IDF 6.0 PowerShell (its Python has pyserial and esptool):
    python chapter_evidence\\run_skip_nudge_drift60_2026-10-29_v2.py
Close idf.py monitor and any other program using COM5 first.
"""
import csv
import ctypes
import hashlib
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import serial

PORT, BAUD = "COM5", 115200
MINUTES = 60
HERE = Path(__file__).resolve().parent              # chapter_evidence
PROJECT = HERE.parent                               # person_detection
BUILD = PROJECT / "build_b5_skip_nudge_notrace_2026-10-28"
SDKCONFIG = PROJECT / "sdkconfig.b5_skip_nudge_notrace_2026-10-28"
OUT = HERE / "skip_nudge_drift60_2026-10-29"

EXPECT = {
    "bin": "8ef30ef85a4bedd393be0891b0598857bb305c059f4d323ecb95e4bc37934c03",
    "elf": "6e944ae8299cb08fbd247a8e842d860d87e5d59242bf4cb00fefebcc8c63a694",
    "sdkconfig": "08f6a77c762fc2b005deef1baf55038cf77e16c00d7f41c7327800c31c1e8328",
}
APP_BYTES = 676464          # size of person_detection.bin in this build
FRESH_1000RUN_MEAN_US = 391103.7   # skip-nudge 1,000-run capture of 28 Oct (for reference only)

ANSI = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")


def keep_awake(on):
    """Ask Windows not to enter idle sleep while this process runs (ES_CONTINUOUS | ES_SYSTEM_REQUIRED)."""
    try:
        flags = 0x80000000 | (0x00000001 if on else 0)
        return bool(ctypes.windll.kernel32.SetThreadExecutionState(flags))
    except Exception:
        return False


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    return sha256_bytes(Path(path).read_bytes())


def write_with_sidecar(path, data):
    path = Path(path)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite existing file: {path}")
    path.write_bytes(data)
    h = sha256_bytes(data).upper()
    Path(str(path) + ".sha256.txt").write_text(f"{h}  {path.name}\n", encoding="ascii")
    return h


def preflight():
    problems = []
    files = {
        "bin": BUILD / "person_detection.bin",
        "elf": BUILD / "person_detection.elf",
        "sdkconfig": SDKCONFIG,
    }
    found = {}
    for key, path in files.items():
        if not path.is_file():
            problems.append(f"missing file: {path}")
            continue
        found[key] = sha256_file(path)
        if found[key] != EXPECT[key]:
            problems.append(f"{path.name}: SHA-256 {found[key]} differs from expected {EXPECT[key]}")
    cfg = SDKCONFIG.read_text(encoding="utf-8", errors="replace") if SDKCONFIG.is_file() else ""
    for line in ("CONFIG_NN_OPTIMIZED=y", "CONFIG_NN_SKIP_NUDGE=y",
                 "CONFIG_ESP_TFLITE_MICRO_USE_ESP_NN=y", "CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ=240"):
        if not re.search(rf"(?m)^{re.escape(line)}$", cfg):
            problems.append(f"{SDKCONFIG.name}: '{line}' not found")
    cc_path = BUILD / "compile_commands.json"
    cc = cc_path.read_text(encoding="utf-8", errors="replace") if cc_path.is_file() else ""
    if "TFLM_RQ1_TRACE" in cc:
        problems.append("trace macro TFLM_RQ1_TRACE found in compile_commands.json")
    if "-DSKIP_NUDGE" not in cc:
        problems.append("-DSKIP_NUDGE not found in compile_commands.json")
    if not (BUILD / "flash_args").is_file():
        problems.append("flash_args missing in build folder")
    return problems, found


def flash(run_id):
    cmd = [sys.executable, "-m", "esptool", "--chip", "esp32", "-p", PORT, "-b", "460800",
           "--before", "default-reset", "--after", "hard-reset", "write-flash", "@flash_args"]
    print("Flashing the existing skip-nudge images (no rebuild)...", flush=True)
    p = subprocess.run(cmd, cwd=BUILD, capture_output=True, text=True)
    log = ("COMMAND: " + " ".join(cmd) + "\nCWD: " + str(BUILD) + "\nRETURN_CODE: "
           + str(p.returncode) + "\n\n" + p.stdout + "\n" + p.stderr)
    write_with_sidecar(OUT / f"flash_log_{run_id}.txt", log.encode("utf-8"))
    verified = log.count("Hash of data verified")
    wrote_app = re.search(rf"Wrote {APP_BYTES} bytes .*? at 0x00020000", log)
    ok = p.returncode == 0 and verified == 4 and wrote_app is not None
    return ok, verified, log


class Port:
    def __init__(self):
        self.ser = serial.Serial()
        self.ser.port, self.ser.baudrate, self.ser.timeout = PORT, BAUD, 0.1
        self.ser.dtr = False   # keep GPIO0 high: never enter download mode
        self.ser.rts = False
        self.ser.open()
        self.raw = bytearray()

    def pump(self):
        chunk = self.ser.read(4096)
        if chunk:
            self.raw.extend(chunk)
        return chunk

    def wait_for(self, marker, start, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            i = self.raw.find(marker, start)
            if i >= 0:
                return i + len(marker)
            self.pump()
        i = self.raw.find(marker, start)
        return i + len(marker) if i >= 0 else None

    def reset(self):
        self.ser.dtr = False
        self.ser.rts = True    # EN low
        time.sleep(0.2)
        self.ser.rts = False   # EN high, GPIO0 high: normal boot

    def close(self):
        self.ser.close()


def capture(run_id):
    port = Port()
    try:
        port.reset()
        got = port.wait_for(b"rst:", 0, 10)
        if got is None or port.raw.find(b"waiting for download") >= 0:
            start = len(port.raw)
            port.reset()
            got = port.wait_for(b"rst:", start, 10)
        if got is None:
            print("Automatic reset did not respond. Press and release EN once (not BOOT).", flush=True)
            got = port.wait_for(b"rst:", len(port.raw), 120)
        if got is None:
            raise RuntimeError("no reset seen on COM5")
        prompt = port.wait_for(b"esp>", got, 60)
        if prompt is None:
            raise RuntimeError("CLI prompt 'esp>' not seen after reset")
        print("Board booted; CLI ready. Sending: drift 60", flush=True)
        time.sleep(0.5)
        port.ser.write(f"drift {MINUTES}\r\n".encode("ascii"))
        port.ser.flush()
        started = port.wait_for(b"DRIFT_START,", prompt, 60)
        if started is None:
            raise RuntimeError("DRIFT_START not seen")
        print("DRIFT_START seen. Do not close this window for about 61 minutes.", flush=True)
        deadline = time.monotonic() + MINUTES * 60 + 600
        reported = 0
        arrivals = []
        while time.monotonic() < deadline:
            port.pump()
            n = port.raw.count(b"DRIFT_SAMPLE,")
            if n > reported:
                reported = n
                arrivals.append((n, datetime.now().isoformat(timespec="seconds")))
                print(f"  minute {n}/{MINUTES} recorded", flush=True)
            if port.raw.find(b"DRIFT_END,", started) >= 0:
                break
        end = port.raw.find(b"DRIFT_END,", started)
        if end < 0:
            raise RuntimeError("DRIFT_END not seen before timeout")
        port.wait_for(b"esp>", end, 10)
        capture.arrivals = arrivals
        return bytes(port.raw), None
    except KeyboardInterrupt:
        capture.arrivals = arrivals if "arrivals" in locals() else []
        return bytes(port.raw), "interrupted by keyboard"
    except Exception as exc:
        capture.arrivals = arrivals if "arrivals" in locals() else []
        return bytes(port.raw), repr(exc)
    finally:
        port.close()


def parse_kv(line):
    out = {}
    for part in line.split(",")[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def audit(raw, run_id, flash_ok, flash_verified, inputs):
    text = ANSI.sub(b"", raw).decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    def banner(label):
        for ln in lines:
            m = re.search(re.escape(label) + r"\s*(.+)$", ln)
            if m:
                return m.group(1).strip()
        return ""

    elf_banner = banner("ELF file SHA256:")
    elf_prefix = elf_banner.rstrip(".").strip()
    app_version = banner("App version:")
    compile_time = banner("Compile time:")
    idf_version = banner("ESP-IDF:")

    prep = next((parse_kv(l) for l in lines if l.startswith("DRIFT_PREP,")), None)
    start = next((parse_kv(l) for l in lines if l.startswith("DRIFT_START,")), None)
    end = next((parse_kv(l) for l in lines if l.startswith("DRIFT_END,")), None)
    samples = [parse_kv(l) for l in lines if l.startswith("DRIFT_SAMPLE,")]
    num = lambda s, k: float(s[k])
    ints = lambda k: [int(s[k]) for s in samples]

    checks = {}
    checks["Flash: return code 0, 4 x 'Hash of data verified', app image written at 0x20000"] = flash_ok
    checks["Boot banner ELF SHA-256 prefix matches the skip-nudge ELF"] = bool(elf_prefix) and EXPECT["elf"].startswith(elf_prefix.lower())
    checks["DRIFT_PREP and DRIFT_START present"] = prep is not None and start is not None
    checks["Timing boundary is interpreter_Invoke_only"] = bool(start) and start.get("timing") == "interpreter_Invoke_only"
    checks[f"Exactly {MINUTES} minute samples"] = len(samples) == MINUTES
    checks["Minute and elapsed-second sequence valid"] = (
        len(samples) == MINUTES and ints("minute") == list(range(1, MINUTES + 1))
        and ints("elapsed_s") == [60 * i for i in range(1, MINUTES + 1)])
    checks["DRIFT_END completed = requested = 60, elapsed 3600 s"] = bool(end) and (
        end.get("completed_minutes") == str(MINUTES) and end.get("requested_minutes") == str(MINUTES)
        and end.get("elapsed_s") == str(MINUTES * 60))
    runs_sum = sum(ints("runs")) if samples else 0
    checks["Sum of minute runs equals DRIFT_END total_runs"] = bool(end) and str(runs_sum) == end.get("total_runs")
    checks["Zero failures"] = bool(samples) and set(ints("failures")) == {0} and bool(end) and end.get("total_failures") == "0"
    checks["Zero output mismatches"] = (bool(samples) and set(ints("output_mismatches")) == {0}
                                        and set(ints("total_output_mismatches")) == {0}
                                        and bool(end) and end.get("output_mismatches") == "0")
    checks["Zero latency-overflow minutes"] = (bool(samples) and set(ints("latency_overflow")) == {0}
                                               and bool(end) and end.get("p95_overflow_minutes") == "0")
    checks["Free and minimum internal memory constant"] = (bool(samples) and len(set(ints("free_internal"))) == 1
                                                           and len(set(ints("min_internal"))) == 1)
    passed = all(checks.values())

    stats = {}
    if samples:
        means = [num(s, "mean_us") for s in samples]
        runs = ints("runs")
        stats = {
            "samples": len(samples),
            "total_runs": runs_sum,
            "mean_of_minute_means_us": round(sum(means) / len(means), 3),
            "run_weighted_mean_us": round(sum(m * r for m, r in zip(means, runs)) / runs_sum, 3),
            "minute_mean_range_us": [min(means), max(means)],
            "mean_of_minute_p95_us": round(sum(num(s, "p95_us") for s in samples) / len(samples), 3),
            "min_of_minute_minima_us": min(num(s, "min_us") for s in samples),
            "max_of_minute_maxima_us": max(num(s, "max_us") for s in samples),
            "mean_cycles_range": [min(num(s, "mean_cycles") for s in samples), max(num(s, "mean_cycles") for s in samples)],
            "free_internal_bytes": sorted(set(ints("free_internal"))),
            "free_spiram_bytes": sorted(set(ints("free_spiram"))),
            "first10_mean_us": round(sum(means[:10]) / 10, 3) if len(means) >= 10 else None,
            "last10_mean_us": round(sum(means[-10:]) / 10, 3) if len(means) >= 10 else None,
        }

    with (OUT / f"skip_nudge_drift_60min_minutes_{run_id}.csv").open("w", newline="", encoding="utf-8") as f:
        if samples:
            w = csv.DictWriter(f, fieldnames=list(samples[0].keys()))
            w.writeheader()
            w.writerows(samples)

    raw_name = f"skip_nudge_drift_60min_serial_raw_{run_id}.txt"
    md = [
        "# Skip-nudge R2 - 60-Minute Drift Audit",
        "",
        f"- Run ID: {run_id}",
        "- Firmware: build_b5_skip_nudge_notrace_2026-10-28 (optimized ESP-NN, CONFIG_NN_SKIP_NUDGE=y, no trace code)",
        f"- BIN SHA-256: {inputs.get('bin', '').upper()}",
        f"- ELF SHA-256: {inputs.get('elf', '').upper()}",
        f"- sdkconfig snapshot SHA-256: {inputs.get('sdkconfig', '').upper()}",
        f"- Boot banner: App version {app_version}; compile time {compile_time}; ESP-IDF {idf_version}; ELF SHA256 {elf_banner}",
        f"- Flash: {flash_verified} x 'Hash of data verified'",
        f"- Command: drift {MINUTES}; timing boundary: {start.get('timing') if start else 'missing'}",
        f"- Raw log: {raw_name}",
        f"- Raw log SHA-256: {sha256_bytes(raw).upper()}",
        f"- Audit result: {'PASS' if passed else 'FAIL'}",
        "",
        "## Checks",
        "",
        "| Check | Result |",
        "|---|---|",
    ] + [f"| {k} | {'PASS' if v else 'FAIL'} |" for k, v in checks.items()] + [
        "",
        "## Values re-derived from the minute records",
        "",
        "| Quantity | Value |",
        "|---|---|",
    ] + [f"| {k} | {v} |" for k, v in stats.items()] + [
        "",
        f"For reference only: the 28 October skip-nudge 1,000-run capture had a mean of {FRESH_1000RUN_MEAN_US} us.",
        "",
        "Minute-level values are roll-ups printed by the firmware. The mean of minute P95 values is not a",
        "global P95 over all inferences, and the run-weighted mean uses rounded minute means.",
        "This audit covers one board, one build and the ten bundled images; it does not establish model",
        "accuracy, all-input equivalence, energy use or robot safety.",
        "",
    ]
    write_with_sidecar(OUT / f"skip_nudge_drift_60min_audit_{run_id}.md", "\n".join(md).encode("utf-8"))
    return passed, checks, stats


def main():
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Run ID: {run_id} (script version 2)")
    awake = keep_awake(True)
    print("Windows asked to stay awake while this runs:", awake, "(keep the lid open)")
    problems, inputs = preflight()
    if problems:
        print("PREFLIGHT FAILED - nothing was flashed:")
        for p in problems:
            print("  -", p)
        return 2
    print("Preflight OK: BIN, ELF and sdkconfig match the 28 Oct skip-nudge build.")

    try:
        flash_ok, verified, _ = flash(run_id)
    except serial.SerialException as exc:
        print("COM5 is busy or missing. Close idf.py monitor and try again.", exc)
        return 3
    if not flash_ok:
        print(f"FLASH FAILED (verified blocks: {verified}). See flash_log_{run_id}.txt")
        return 4
    print("Flash OK (4 blocks verified).")
    time.sleep(1.0)

    try:
        raw, error = capture(run_id)
    except serial.SerialException as exc:
        print("Could not open COM5. Close idf.py monitor and any other serial program.", exc)
        return 3
    keep_awake(False)
    arrivals = getattr(capture, "arrivals", [])
    gaps = []
    for (n0, t0), (n1, t1) in zip(arrivals, arrivals[1:]):
        dt = (datetime.fromisoformat(t1) - datetime.fromisoformat(t0)).total_seconds()
        if dt > 90:
            gaps.append((n0, n1, dt))
    write_with_sidecar(OUT / f"pc_arrival_times_{run_id}.csv",
                       ("minute_record,pc_time\n" + "".join(f"{n},{t}\n" for n, t in arrivals)).encode("ascii"))
    if gaps:
        print("WARNING: gaps over 90 s between minute records on the PC side:", gaps)
    suffix = "" if error is None else "_PARTIAL"
    raw_name = f"skip_nudge_drift_60min_serial_raw_{run_id}{suffix}.txt"
    raw_hash = write_with_sidecar(OUT / raw_name, raw)
    print(f"Raw log saved: {raw_name} ({len(raw)} bytes, SHA-256 {raw_hash})")
    if error is not None:
        print("CAPTURE STOPPED:", error)
        return 5

    passed, checks, stats = audit(raw, run_id, flash_ok, verified, inputs)
    meta = {"run_id": run_id, "script_version": 2, "keep_awake_requested": awake, "pc_gaps_over_90s": gaps,
            "port": PORT, "minutes": MINUTES, "inputs_sha256": inputs,
            "raw_log": raw_name, "raw_log_sha256": raw_hash.lower(), "audit_pass": passed,
            "checks": checks, "stats": stats}
    write_with_sidecar(OUT / f"run_metadata_{run_id}.json", json.dumps(meta, indent=2).encode("utf-8"))
    for k, v in checks.items():
        print(("PASS  " if v else "FAIL  ") + k)
    for k, v in stats.items():
        print(f"{k}: {v}")
    print("AUDIT:", "PASS" if passed else "FAIL")
    print("All outputs are in", OUT)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())

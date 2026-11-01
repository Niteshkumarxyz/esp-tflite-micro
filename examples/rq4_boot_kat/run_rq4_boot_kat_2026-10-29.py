"""RQ4 on the ESP32: build, flash and run the boot-time acceptance test for five builds.

Builds (all from this folder, each in its own build_rq4_<name> folder):
  r1    TFLM reference kernels (ESP-NN off)            expected verdict PASS
  r2a   ESP-NN ANSI C kernels                           expected verdict PASS
  r2    ESP-NN optimized kernels                        expected verdict PASS
  r2sn  ESP-NN optimized kernels with NN_SKIP_NUDGE     expected verdict PASS
  r1sr  R1 with TFLITE_SINGLE_ROUNDING=1 (positive control, deliberately different)
                                                        expected verdict FAIL
For every build: check its configuration, flash it with esptool (no rebuild), reset the board
BOOTS times, and save each boot's serial output. Then audit everything against the firmware
files and write a summary.

Writes only new files: build_rq4_* folders here, and everything else in
  examples/person_detection/chapter_evidence/rq4_boot_kat_2026-10-29/
Run from the ESP-IDF 6.0 PowerShell, in this folder, with idf.py monitor closed:
    python run_rq4_boot_kat_2026-10-29.py
"""
import csv
import ctypes
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import serial

PORT, BAUD = "COM5", 115200
BOOTS = 5
HERE = Path(__file__).resolve().parent
EVID = HERE.parent / "person_detection" / "chapter_evidence" / "rq4_boot_kat_2026-10-29"
ESP_NN_HASH = "3b3411b0e4ad1717a72870fde9f9b67cef6f3f97491cc64fcfc1910a8fd8a246"   # esp-nn 1.4.1, as in person_detection
VARIANTS = [
    # name,  defaults suffix, extra idf.py args,              expected sdkconfig values,                                                     expected verdict
    ("r1",   "r1",   [],                               {"ESP_TFLITE_MICRO_USE_ESP_NN": False},                                              "PASS"),
    ("r2a",  "r2a",  [],                               {"ESP_TFLITE_MICRO_USE_ESP_NN": True, "NN_ANSI_C": True},                            "PASS"),
    ("r2",   "r2",   [],                               {"ESP_TFLITE_MICRO_USE_ESP_NN": True, "NN_OPTIMIZED": True, "NN_SKIP_NUDGE": False}, "PASS"),
    ("r2sn", "r2sn", [],                               {"ESP_TFLITE_MICRO_USE_ESP_NN": True, "NN_OPTIMIZED": True, "NN_SKIP_NUDGE": True},  "PASS"),
    ("r1sr", "r1",   ["-D", "RQ4_SINGLE_ROUNDING=1"],  {"ESP_TFLITE_MICRO_USE_ESP_NN": False},                                              "FAIL"),
]
ANSI = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")


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


def say(log, text):
    print(text, flush=True)
    log.write(text + "\n")
    log.flush()


def build(name, suffix, extra, run_id, log):
    bdir = HERE / f"build_rq4_{name}"
    cmd = [sys.executable, str(Path(os.environ["IDF_PATH"]) / "tools" / "idf.py"), "-B", bdir.name,
           "-D", f"SDKCONFIG={bdir.name}/sdkconfig",
           "-D", f"SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.{suffix}", *extra, "build"]
    say(log, f"[{name}] building ... ({' '.join(cmd[2:])})")
    t0 = time.time()
    p = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = "COMMAND: " + " ".join(cmd) + f"\nRETURN_CODE: {p.returncode}\n\n" + p.stdout + "\n" + p.stderr
    write_with_sidecar(EVID / f"build_log_{name}_{run_id}.txt", out.encode("utf-8"))
    say(log, f"[{name}] build return code {p.returncode} in {time.time() - t0:.0f} s")
    return p.returncode == 0, bdir


def check_build(name, bdir, expect_cfg, single_rounding):
    problems = []
    cfg = json.loads((bdir / "config" / "sdkconfig.json").read_text(encoding="utf-8"))
    for key, want in expect_cfg.items():
        got = cfg.get(key, False)
        if bool(got) != want:
            problems.append(f"sdkconfig {key}={got}, expected {want}")
    if cfg.get("ESP_DEFAULT_CPU_FREQ_MHZ") != 240:
        problems.append(f"CPU MHz {cfg.get('ESP_DEFAULT_CPU_FREQ_MHZ')}")
    cc = (bdir / "compile_commands.json").read_text(encoding="utf-8", errors="replace")
    has_sr = "TFLITE_SINGLE_ROUNDING=1" in cc
    if has_sr != single_rounding:
        problems.append(f"TFLITE_SINGLE_ROUNDING present={has_sr}, expected {single_rounding}")
    lock = (HERE / "dependencies.lock").read_text(encoding="utf-8", errors="replace")
    m = re.search(r"espressif/esp-nn:\s*\n\s*component_hash:\s*([0-9a-f]+)[\s\S]*?version:\s*([0-9.]+)", lock)
    if not m or m.group(1) != ESP_NN_HASH or m.group(2) != "1.4.1":
        problems.append(f"esp-nn in dependencies.lock is not 1.4.1 with the expected hash ({m.groups() if m else None})")
    files = {k: bdir / f for k, f in (("bin", "rq4_boot_kat.bin"), ("elf", "rq4_boot_kat.elf"), ("sdkconfig", "sdkconfig"))}
    hashes = {k: sha256_bytes(p.read_bytes()) for k, p in files.items() if p.is_file()}
    binb = files["bin"].read_bytes() if files["bin"].is_file() else b""
    hashes["bin_appended_digest"] = binb[-32:].hex() if len(binb) > 32 else ""
    hashes["bin_digest_valid"] = len(binb) > 32 and sha256_bytes(binb[:-32]) == binb[-32:].hex()
    return problems, hashes


def flash(name, bdir, run_id, log):
    cmd = [sys.executable, "-m", "esptool", "--chip", "esp32", "-p", PORT, "-b", "460800",
           "--before", "default-reset", "--after", "hard-reset", "write-flash", "@flash_args"]
    p = subprocess.run(cmd, cwd=bdir, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = "COMMAND: " + " ".join(cmd) + f"\nCWD: {bdir}\nRETURN_CODE: {p.returncode}\n\n" + p.stdout + "\n" + p.stderr
    write_with_sidecar(EVID / f"flash_log_{name}_{run_id}.txt", out.encode("utf-8"))
    regions = sum(1 for line in (bdir / "flash_args").read_text().splitlines() if line.strip().startswith("0x"))
    ok = p.returncode == 0 and out.count("Hash of data verified") == regions
    say(log, f"[{name}] flash {'OK' if ok else 'FAILED'} ({out.count('Hash of data verified')}/{regions} regions verified)")
    return ok


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


def one_boot(port, log):
    start = len(port.raw)
    port.reset()
    if port.wait_for(b"rst:", start, 10) is None or port.raw.find(b"waiting for download", start) >= 0:
        start = len(port.raw)
        port.reset()
        if port.wait_for(b"rst:", start, 10) is None:
            say(log, "    automatic reset did not respond; press and release EN once (not BOOT)")
            if port.wait_for(b"rst:", start, 120) is None:
                raise RuntimeError("no reset seen")
    end = port.wait_for(b"RQ4_DONE", start, 300)
    if end is None:
        raise RuntimeError("RQ4_DONE not seen within 300 s")
    port.wait_for(b"\n", end, 2)
    return bytes(port.raw[start:])


def kv(line):
    out = {}
    for part in line.split(",")[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            out[k] = v
    return out


def parse_boot(data):
    text = ANSI.sub(b"", data).decode("utf-8", errors="replace").replace("\r", "")
    rec = {"images": [], "opmismatch": 0}
    for line in text.split("\n"):
        line = line.strip()
        for tag in ("RQ4_BUILD", "RQ4_IDENTITY", "RQ4_SETUP", "RQ4_RESULT", "RQ4_HEAP", "RQ4_BOOT"):
            if line.startswith(tag + ","):
                rec[tag] = kv(line)
        if line.startswith("RQ4_IMAGE,"):
            rec["images"].append(kv(line))
        if line.startswith("RQ4_OPMISMATCH,"):
            rec["opmismatch"] += 1
        if line.startswith("RQ4_ACTUATION,"):
            rec["actuation"] = line.split(",", 1)[1]
    return rec


def main():
    if "IDF_PATH" not in os.environ:
        print("Please run this from the ESP-IDF 6.0 PowerShell (IDF_PATH is not set).")
        return 2
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    EVID.mkdir(parents=True, exist_ok=True)
    awake = keep_awake(True)
    with (EVID / f"run_log_{run_id}.txt").open("w", encoding="utf-8") as log:
        say(log, f"RQ4 run {run_id}; IDF_PATH={os.environ['IDF_PATH']}; keep-awake requested: {awake}")
        built = {}
        for name, suffix, extra, expect_cfg, verdict in VARIANTS:
            ok, bdir = build(name, suffix, extra, run_id, log)
            if not ok:
                say(log, f"[{name}] BUILD FAILED - see build_log_{name}_{run_id}.txt. Stopping before any flashing.")
                return 4
            problems, hashes = check_build(name, bdir, expect_cfg, "RQ4_SINGLE_ROUNDING=1" in extra)
            if problems:
                say(log, f"[{name}] CONFIGURATION CHECK FAILED: {problems}")
                return 4
            built[name] = (bdir, hashes, verdict)
            say(log, f"[{name}] configuration OK; BIN {hashes['bin'][:16]}..., ELF {hashes['elf'][:16]}...")

        rows, all_ok = [], True
        for name, (bdir, hashes, expected) in built.items():
            if not flash(name, bdir, run_id, log):
                return 4
            time.sleep(1.0)
            port = Port()
            try:
                for boot in range(1, BOOTS + 1):
                    try:
                        data = one_boot(port, log)
                        err = None
                    except Exception as exc:
                        data, err = bytes(port.raw[-500000:]), repr(exc)
                    tag = "" if err is None else "_INCOMPLETE"
                    fname = f"boot_{name}_{boot}_{run_id}{tag}.txt"
                    write_with_sidecar(EVID / fname, data)
                    rec = parse_boot(data)
                    res, ident, b = rec.get("RQ4_RESULT", {}), rec.get("RQ4_IDENTITY", {}), rec.get("RQ4_BUILD", {})
                    row = {
                        "build": name, "boot": boot, "log": fname, "error": err or "",
                        "verdict": res.get("verdict", ""), "expected_verdict": expected,
                        "outputs_match": res.get("outputs_match", ""), "ops_match": res.get("ops_match", ""),
                        "first_fail_image": res.get("first_fail_image", ""), "first_fail_op": res.get("first_fail_op", ""),
                        "actuation": rec.get("actuation", ""),
                        "elf_matches_file": ident.get("elf_sha256", "") == hashes["elf"],
                        "app_digest_matches_bin": ident.get("app_image_digest", "") == hashes["bin_appended_digest"],
                        "single_rounding_flag": b.get("single_rounding", ""), "esp_nn": b.get("esp_nn", ""),
                        "nn_optimized": b.get("nn_optimized", ""), "nn_ansi_c": b.get("nn_ansi_c", ""),
                        "skip_nudge": b.get("skip_nudge", ""),
                        "identity_us": res.get("identity_us", ""), "kat_us": res.get("kat_us", ""),
                        "invoke_us_total": res.get("invoke_us_total", ""), "hash_us_total": res.get("hash_us_total", ""),
                        "minimal_test_us": res.get("minimal_test_us", ""),
                        "boot_to_verdict_us": res.get("boot_to_verdict_us", ""),
                        "arena_used": rec.get("RQ4_SETUP", {}).get("arena_used", ""),
                        "opmismatch_lines": rec["opmismatch"],
                    }
                    row["as_expected"] = (not err and row["verdict"] == expected and row["elf_matches_file"]
                                          and row["app_digest_matches_bin"])
                    all_ok &= row["as_expected"]
                    rows.append(row)
                    say(log, f"[{name}] boot {boot}: verdict {row['verdict'] or '-'} (expected {expected}); "
                             f"outputs {row['outputs_match']}/12, ops {row['ops_match']}/372, "
                             f"first fail image {row['first_fail_image']} op {row['first_fail_op']}; "
                             f"KAT {row['kat_us']} us; identity checks "
                             f"{row['elf_matches_file'] and row['app_digest_matches_bin']}"
                             + (f"; ERROR {err}" if err else ""))
            finally:
                port.ser.close()

        fields = list(rows[0].keys()) if rows else []
        csv_path = EVID / f"rq4_boot_kat_summary_{run_id}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        Path(str(csv_path) + ".sha256.txt").write_text(
            f"{sha256_bytes(csv_path.read_bytes()).upper()}  {csv_path.name}\n", encoding="ascii")
        meta = {"run_id": run_id, "boots_per_build": BOOTS, "port": PORT,
                "builds": {n: {"folder": b.name, "sha256": h, "expected_verdict": v} for n, (b, h, v) in built.items()},
                "all_as_expected": all_ok}
        write_with_sidecar(EVID / f"rq4_boot_kat_metadata_{run_id}.json", json.dumps(meta, indent=2).encode("utf-8"))
        say(log, "\nRQ4 OVERALL: " + ("ALL BUILDS GAVE THE EXPECTED VERDICT" if all_ok else "SOMETHING DID NOT MATCH - see summary CSV"))
        say(log, f"Outputs: {EVID}")
    keep_awake(False)
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

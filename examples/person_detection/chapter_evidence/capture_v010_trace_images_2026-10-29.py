"""Capture RQ1 board traces for the remaining images with the v0.1.0 optimized trace build.

Build: build_rq1_trace_opt_20261029 (commit 15dd18a, optimized ESP-NN, TFLM_RQ1_TRACE on).
For each image (default 5 to 11) the script resets the board, waits for the CLI, sends
`detect_image N`, and saves every serial byte from the reset to the next prompt, so the
boot banner (App version, ELF SHA256) is inside each log. Raw chunks are printed only for
the first inference after a boot, which is why every image gets its own reset.

Writes only new files:
  chapter_evidence/rq1_trace_board_capture_2026-10-29/optimized_rq1_trace_image<N>_<time>.txt (+ .sha256.txt)
  chapter_evidence/rq1_trace_board_capture_2026-10-29/capture_run_<time>.json  (+ .sha256.txt)
  chapter_evidence/rq1_trace_board_capture_2026-10-29/flash_log_trace_opt_<time>.txt (+ .sha256.txt)
Then it runs chapter_evidence/rq1_v010_trace_vs_r1_2026-10-29/compare_v010_trace_vs_r1.py.

Run from the ESP-IDF 6.0 PowerShell, in the person_detection folder, with idf.py monitor closed:
    python chapter_evidence\\capture_v010_trace_images_2026-10-29.py
Optional: give image numbers, e.g.  ... capture_v010_trace_images_2026-10-29.py 5 6 7
"""
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
HERE = Path(__file__).resolve().parent              # chapter_evidence
PROJECT = HERE.parent
BUILD = PROJECT / "build_rq1_trace_opt_20261029"
SDKCONFIG = PROJECT / "sdkconfig.rq1_trace_optimized_boardcheck_20261029"
OUT = HERE / "rq1_trace_board_capture_2026-10-29"
COMPARE = HERE / "rq1_v010_trace_vs_r1_2026-10-29" / "compare_v010_trace_vs_r1.py"
EXPECT = {
    "bin": "efa2ad1725f28db4cc2bbb44618d1c8a5def85cf3f300e8e18e5376fe086ccd4",
    "elf": "8ea80939ba9773e8b7014042bf427ea9d5669b1a224427e99691d4b77a5e1ba4",
    "sdkconfig": "ab5f97d900dd205657aa3f4eefbbe52d5c2e0381266c1f0ecd903763349277c3",
}
APP_BYTES = 678352
EXPECTED_TRACE, EXPECTED_RAW = 31, 3625
ANSI = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


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
    for key, path in (("bin", BUILD / "person_detection.bin"), ("elf", BUILD / "person_detection.elf"),
                      ("sdkconfig", SDKCONFIG)):
        if not path.is_file():
            problems.append(f"missing {path}")
        elif sha256_bytes(path.read_bytes()) != EXPECT[key]:
            problems.append(f"{path.name}: SHA-256 differs from the build checked on 29 Oct")
    cfg = SDKCONFIG.read_text(encoding="utf-8", errors="replace") if SDKCONFIG.is_file() else ""
    if not re.search(r"(?m)^CONFIG_NN_OPTIMIZED=y$", cfg):
        problems.append("CONFIG_NN_OPTIMIZED=y not found")
    if re.search(r"(?m)^CONFIG_NN_SKIP_NUDGE=y$", cfg):
        problems.append("SKIP_NUDGE is enabled; this script is for the normal optimized build")
    cc_path = BUILD / "compile_commands.json"
    cc = cc_path.read_text(encoding="utf-8", errors="replace") if cc_path.is_file() else ""
    if "TFLM_RQ1_TRACE" not in cc:
        problems.append("TFLM_RQ1_TRACE not found in compile_commands.json")
    return problems


def flash(run_id):
    cmd = [sys.executable, "-m", "esptool", "--chip", "esp32", "-p", PORT, "-b", "460800",
           "--before", "default-reset", "--after", "hard-reset", "write-flash", "@flash_args"]
    print("Flashing build_rq1_trace_opt_20261029 (no rebuild)...", flush=True)
    p = subprocess.run(cmd, cwd=BUILD, capture_output=True, text=True)
    log = ("COMMAND: " + " ".join(cmd) + "\nCWD: " + str(BUILD) + "\nRETURN_CODE: " + str(p.returncode)
           + "\n\n" + p.stdout + "\n" + p.stderr)
    write_with_sidecar(OUT / f"flash_log_trace_opt_{run_id}.txt", log.encode("utf-8"))
    ok = (p.returncode == 0 and log.count("Hash of data verified") == 4
          and re.search(rf"Wrote {APP_BYTES} bytes .*? at 0x00020000", log) is not None)
    return ok


class Port:
    def __init__(self):
        self.ser = serial.Serial()
        self.ser.port, self.ser.baudrate, self.ser.timeout = PORT, BAUD, 0.1
        self.ser.dtr = False   # GPIO0 stays high: never download mode
        self.ser.rts = False
        self.ser.open()
        self.raw = bytearray()

    def pump(self):
        chunk = self.ser.read(8192)
        if chunk:
            self.raw.extend(chunk)

    def wait_for(self, marker, start, timeout, abort=None):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            i = self.raw.find(marker, start)
            if i >= 0:
                return i + len(marker)
            if abort is not None and self.raw.find(abort, start) >= 0:
                raise RuntimeError(f"{abort!r} seen while waiting for {marker!r}")
            self.pump()
        i = self.raw.find(marker, start)
        return i + len(marker) if i >= 0 else None

    def reset(self):
        self.ser.dtr = False
        self.ser.rts = True
        time.sleep(0.2)
        self.ser.rts = False


def capture_one(port, image):
    start = len(port.raw)
    port.reset()
    got = port.wait_for(b"rst:", start, 10)
    if got is None or port.raw.find(b"waiting for download", start) >= 0:
        start = len(port.raw)
        port.reset()
        got = port.wait_for(b"rst:", start, 10)
    if got is None:
        print("  Automatic reset did not respond. Press and release EN once (not BOOT).", flush=True)
        got = port.wait_for(b"rst:", start, 120)
    if got is None:
        raise RuntimeError("no reset seen")
    prompt = port.wait_for(b"esp>", got, 60)
    if prompt is None:
        raise RuntimeError("CLI prompt not seen after reset")
    time.sleep(0.5)
    port.ser.write(f"detect_image {image}\r\n".encode("ascii"))
    port.ser.flush()
    print(f"  image {image}: inference with trace running (about 1 minute)...", flush=True)
    res = port.wait_for(f"IMAGE_RESULT,image={image},".encode("ascii"), prompt, 300, abort=b"rst:")
    if res is None:
        raise RuntimeError("IMAGE_RESULT not seen within 300 s")
    final = port.wait_for(b"esp>", res, 30)
    end = final if final is not None else len(port.raw)
    return bytes(port.raw[start:end])


def check(data, image):
    text = ANSI.sub(b"", data).decode("utf-8", errors="replace").replace("\r", "")
    lines = text.split("\n")
    trace = sum(l.startswith("RQ1_TRACE,run=1,") for l in lines)
    raw = sum(l.startswith("RQ1_RAW,run=1,") for l in lines)
    result = next((l.strip() for l in lines if l.startswith(f"IMAGE_RESULT,image={image},")), "")
    elf = next((l.split("ELF file SHA256:", 1)[1].strip().rstrip(".").strip() for l in lines
                if "ELF file SHA256:" in l), "")
    app = next((l.split("App version:", 1)[1].strip() for l in lines if "App version:" in l), "")
    complete = (trace == EXPECTED_TRACE and raw == EXPECTED_RAW and "invoke_ok=1" in result
                and bool(elf) and EXPECT["elf"].startswith(elf.lower()))
    return dict(trace=trace, raw=raw, result=result, elf_banner=elf, app_version=app, complete=complete)


def main():
    images = [int(a) for a in sys.argv[1:]] or [5, 6, 7, 8, 9, 10, 11]
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Run ID: {run_id}; images: {images}")
    problems = preflight()
    if problems:
        print("PREFLIGHT FAILED - nothing was flashed:")
        for p in problems:
            print("  -", p)
        return 2
    print("Preflight OK: BIN, ELF and sdkconfig match the 29 Oct optimized trace build.")
    try:
        if not flash(run_id):
            print(f"FLASH FAILED. See flash_log_trace_opt_{run_id}.txt")
            return 4
    except serial.SerialException as exc:
        print("COM5 busy. Close idf.py monitor and try again.", exc)
        return 3
    print("Flash OK (4 blocks verified).")
    time.sleep(1.0)

    results = []
    try:
        port = Port()
    except serial.SerialException as exc:
        print("Could not open COM5. Close idf.py monitor and any other serial program.", exc)
        return 3
    try:
        for image in images:
            for attempt in (1, 2):
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                try:
                    data = capture_one(port, image)
                    err = None
                except Exception as exc:
                    data, err = bytes(port.raw[-2_000_000:]), repr(exc)
                info = check(data, image) if err is None else dict(complete=False, error=err)
                suffix = "" if info.get("complete") else "_INCOMPLETE"
                name = f"optimized_rq1_trace_image{image}_{stamp}{suffix}.txt"
                h = write_with_sidecar(OUT / name, data)
                info.update(image=image, attempt=attempt, file=name, bytes=len(data), sha256=h)
                results.append(info)
                print(f"  image {image} attempt {attempt}: {'COMPLETE' if info.get('complete') else 'INCOMPLETE'}"
                      f" TRACE={info.get('trace')} RAW={info.get('raw')} {info.get('result', info.get('error', ''))}",
                      flush=True)
                if info.get("complete"):
                    break
    finally:
        port.ser.close()

    write_with_sidecar(OUT / f"capture_run_{run_id}.json",
                       json.dumps(dict(run_id=run_id, build=str(BUILD.name), expected=EXPECT,
                                       results=results), indent=2).encode("utf-8"))
    done = sorted({r["image"] for r in results if r.get("complete")})
    print(f"Complete images: {done}")
    if COMPARE.is_file():
        print("\nRunning the byte-for-byte comparison against the ESP32 R1 reference...\n", flush=True)
        subprocess.run([sys.executable, str(COMPARE)], cwd=COMPARE.parent)
    return 0 if set(done) == set(images) else 1


if __name__ == "__main__":
    sys.exit(main())

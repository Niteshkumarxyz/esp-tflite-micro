import csv
import hashlib
import math
import re
import statistics
import sys
import time
from pathlib import Path

import serial

PORT = "COM5"
BAUD = 115200
RUNS = 100
WARMUP = 10

base = Path(__file__).resolve().parent
raw_path = base / "cycle_benchmark_100_raw_20261022.txt"
samples_path = base / "cycle_benchmark_100_samples_20261022.csv"
summary_path = base / "cycle_benchmark_100_summary_20261022.csv"
hash_path = base / "cycle_benchmark_100_sha256_20261022.txt"

outputs = [raw_path, samples_path, summary_path, hash_path]
existing = [str(p) for p in outputs if p.exists()]
if existing:
    sys.exit("Refusing to overwrite existing evidence: " + ", ".join(existing))

sample_pattern = re.compile(
    r"(?m)^BENCH_SAMPLE,(\d+),(\d+),(\d+),(\d+),(-?\d+),(-?\d+),(\d+)\s*$"
)
summary_pattern = re.compile(r"(?m)^BENCH_SUMMARY,[^\r\n]+")

all_bytes = bytearray()

print(f"Opening {PORT} at {BAUD} baud.")
print("Waiting for the ESP-IDF console prompt...")

try:
    with serial.Serial(
        PORT, BAUD, timeout=0.25, write_timeout=3,
        dsrdtr=False, rtscts=False
    ) as ser, raw_path.open("xb") as raw:
        time.sleep(1)
        ser.write(b"\r\n")

        prompt_deadline = time.monotonic() + 30
        prompt_seen = False

        while time.monotonic() < prompt_deadline:
            chunk = ser.read(max(1, ser.in_waiting))
            if chunk:
                raw.write(chunk)
                raw.flush()
                all_bytes.extend(chunk)
                if b"esp>" in all_bytes:
                    prompt_seen = True
                    break

        if not prompt_seen:
            raise RuntimeError(
                "Console prompt not detected within 30 seconds. "
                "Raw serial data, if any, has been preserved."
            )

        print("Console prompt detected. Sending benchmark 100.")
        ser.write(b"benchmark 100\r\n")

        benchmark_deadline = time.monotonic() + 180
        benchmark_bytes = bytearray()

        while time.monotonic() < benchmark_deadline:
            chunk = ser.read(max(1, ser.in_waiting))
            if chunk:
                raw.write(chunk)
                raw.flush()
                all_bytes.extend(chunk)
                benchmark_bytes.extend(chunk)

                decoded = benchmark_bytes.decode("utf-8", errors="replace")
                if summary_pattern.search(decoded):
                    break
        else:
            raise RuntimeError(
                "Timed out waiting for BENCH_SUMMARY. "
                "Partial raw serial log has been preserved."
            )

except Exception as exc:
    print(f"CAPTURE ERROR: {exc}", file=sys.stderr)
    print(f"Raw log path: {raw_path}", file=sys.stderr)
    sys.exit(1)

text = all_bytes.decode("utf-8", errors="replace")
start_match = re.search(r"(?m)^BENCH_START,([^\r\n]+)", text)
summary_match = summary_pattern.search(text)

if not start_match or not summary_match:
    sys.exit(f"Benchmark markers incomplete. Raw log preserved: {raw_path}")

start_fields = dict(
    re.findall(r"([A-Za-z_]+)=([^,\r\n]+)", start_match.group(1))
)
if int(start_fields.get("runs", "0")) != RUNS:
    sys.exit("BENCH_START run count mismatch. Raw log preserved.")
if int(start_fields.get("warmup", "0")) != WARMUP:
    sys.exit("Warm-up count mismatch. Raw log preserved.")

samples = [
    {
        "run": int(m[0]),
        "image": int(m[1]),
        "invoke_us": int(m[2]),
        "cycles": int(m[3]),
        "raw_person": int(m[4]),
        "raw_no_person": int(m[5]),
        "ok": int(m[6]),
    }
    for m in sample_pattern.findall(text)
]

if len(samples) != RUNS:
    sys.exit(
        f"Expected {RUNS} samples; parsed {len(samples)}. "
        f"Raw log preserved: {raw_path}"
    )

if [s["run"] for s in samples] != list(range(1, RUNS + 1)):
    sys.exit("Sample run IDs missing or duplicated. Raw log preserved.")

firmware_summary = summary_match.group(0).strip()
summary_fields = dict(
    re.findall(r"([A-Za-z_]+)=([^,\r\n]+)", firmware_summary)
)

if int(summary_fields.get("runs", "-1")) != RUNS:
    sys.exit("Firmware summary run count mismatch.")
if int(summary_fields.get("failures", "-1")) != sum(
    s["ok"] != 1 for s in samples
):
    sys.exit("Failure count mismatch between samples and firmware summary.")

with samples_path.open("x", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "run", "image", "invoke_us", "cycles",
        "raw_person", "raw_no_person", "ok"
    ])
    writer.writeheader()
    writer.writerows(samples)

def stats(values):
    ordered = sorted(values)
    return {
        "mean": round(statistics.mean(values), 2),
        "median": round(statistics.median(values), 2),
        "p95_nearest_rank": ordered[math.ceil(0.95 * len(ordered)) - 1],
        "min": ordered[0],
        "max": ordered[-1],
    }

us = stats([s["invoke_us"] for s in samples])
cycles = stats([s["cycles"] for s in samples])

result = {
    "port": PORT,
    "baud": BAUD,
    "runs": len(samples),
    "warmup_runs": WARMUP,
    "images_reported_by_firmware": start_fields.get("images", ""),
    "timing_method": start_fields.get("timing", ""),
    "failures": sum(s["ok"] != 1 for s in samples),
    "mean_us": us["mean"],
    "median_us": us["median"],
    "p95_nearest_rank_us": us["p95_nearest_rank"],
    "min_us": us["min"],
    "max_us": us["max"],
    "mean_cycles": cycles["mean"],
    "median_cycles": cycles["median"],
    "p95_nearest_rank_cycles": cycles["p95_nearest_rank"],
    "min_cycles": cycles["min"],
    "max_cycles": cycles["max"],
    "firmware_summary_line": firmware_summary,
}

with summary_path.open("x", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(result.keys()))
    writer.writeheader()
    writer.writerow(result)

with hash_path.open("x", encoding="utf-8") as f:
    for p in [raw_path, samples_path, summary_path]:
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        f.write(f"{digest}  {p.name}\n")

print("\nCAPTURE STATUS: PASS")
print(f"Parsed samples: {len(samples)}")
print(f"Failures: {result['failures']}")
print(f"Mean Invoke time: {result['mean_us']} us")
print(f"Median Invoke time: {result['median_us']} us")
print(f"P95 Invoke time: {result['p95_nearest_rank_us']} us")
print(f"Mean cycles: {result['mean_cycles']}")
print(f"Median cycles: {result['median_cycles']}")
print(f"P95 cycles: {result['p95_nearest_rank_cycles']}")
print(f"\nFirmware summary: {firmware_summary}")
print("\nSaved evidence files:")
for p in [raw_path, samples_path, summary_path, hash_path]:
    print(f"{p.name}: {p.stat().st_size} bytes")
print("\nSHA-256 checksums:")
print(hash_path.read_text(encoding="utf-8"))
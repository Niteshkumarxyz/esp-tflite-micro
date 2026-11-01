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
TIMEOUT_SECONDS = 1200

base = Path(__file__).resolve().parent
project_root = base.parent.parent

raw_path = base / "r1_cycle_benchmark_100_verified_raw_20261022.txt"
samples_path = base / "r1_cycle_benchmark_100_verified_samples_20261022.csv"
summary_path = base / "r1_cycle_benchmark_100_verified_summary_20261022.csv"
note_path = base / "r1_cycle_benchmark_100_verified_note_20261022.txt"
hash_path = base / "r1_cycle_benchmark_100_verified_sha256_20261022.txt"
binary_path = project_root / "examples" / "person_detection" / "build_cycle_r1_20261022" / "person_detection.bin"

sample_re = re.compile(
    r"^BENCH_SAMPLE,(\d+),(\d+),(\d+),(\d+),(-?\d+),(-?\d+),(\d+)$"
)
summary_re = re.compile(
    r"^BENCH_SUMMARY,runs=(\d+),failures=(\d+),mean_us=(\d+),"
    r"median_us=(\d+),p95_nearest_rank_us=(\d+),min_us=(\d+),max_us=(\d+)$"
)
start_re = re.compile(r"^BENCH_START,(.*)$")

for p in (raw_path, samples_path, summary_path, note_path, hash_path):
    if p.exists():
        sys.exit(f"Refusing to overwrite existing evidence: {p}")

all_samples = []
start_line = None
summary_line = None
summary_fields = None
command_sent = False
pending = bytearray()

print(f"Opening {PORT} at {BAUD} baud.", flush=True)
print("Waiting for the ESP console prompt.", flush=True)

try:
    with serial.Serial(
        PORT, BAUD, timeout=0.25, write_timeout=3,
        dsrdtr=False, rtscts=False
    ) as ser, raw_path.open("xb") as raw:

        time.sleep(1.0)
        ser.write(b"\r\n")
        prompt_buffer = bytearray()
        prompt_deadline = time.monotonic() + 60

        while time.monotonic() < prompt_deadline:
            chunk = ser.read(max(1, ser.in_waiting))
            if not chunk:
                continue
            raw.write(chunk)
            raw.flush()
            prompt_buffer.extend(chunk)
            if b"esp>" in prompt_buffer:
                break
        else:
            raise RuntimeError("Console prompt not detected within 60 seconds.")

        print("Prompt detected. Sending benchmark 100.", flush=True)
        time.sleep(0.5)
        ser.write(b"benchmark 100\r\n")
        command_sent = True

        deadline = time.monotonic() + TIMEOUT_SECONDS
        while time.monotonic() < deadline and summary_line is None:
            chunk = ser.read(max(1, ser.in_waiting))
            if not chunk:
                continue

            raw.write(chunk)
            raw.flush()
            pending.extend(chunk)

            # Parse only complete newline-terminated lines.
            # This avoids treating a partial BENCH_SUMMARY as complete.
            while b"\n" in pending:
                raw_line, _, rest = pending.partition(b"\n")
                pending = bytearray(rest)
                line = raw_line.decode("utf-8", errors="replace").rstrip("\r")

                m = start_re.fullmatch(line)
                if m:
                    start_line = line
                    continue

                m = sample_re.fullmatch(line)
                if m:
                    sample = {
                        "run": int(m.group(1)),
                        "image": int(m.group(2)),
                        "invoke_us": int(m.group(3)),
                        "cycles": int(m.group(4)),
                        "raw_person": int(m.group(5)),
                        "raw_no_person": int(m.group(6)),
                        "ok": int(m.group(7)),
                    }
                    all_samples.append(sample)
                    if len(all_samples) % 10 == 0:
                        print(f"Captured {len(all_samples)}/{RUNS} samples.", flush=True)
                    continue

                m = summary_re.fullmatch(line)
                if m:
                    summary_line = line
                    summary_fields = {
                        "runs": int(m.group(1)),
                        "failures": int(m.group(2)),
                        "mean_us": int(m.group(3)),
                        "median_us": int(m.group(4)),
                        "p95_nearest_rank_us": int(m.group(5)),
                        "min_us": int(m.group(6)),
                        "max_us": int(m.group(7)),
                    }
                    break

except Exception as exc:
    print(f"CAPTURE ERROR: {exc}", file=sys.stderr)
    print(f"Partial raw log preserved: {raw_path}", file=sys.stderr)
    sys.exit(1)

if not command_sent:
    sys.exit("Command was not sent; inspect the raw log.")

if summary_line is None:
    print("CAPTURE STATUS: INCOMPLETE", file=sys.stderr)
    print(f"Complete summary not received within {TIMEOUT_SECONDS} seconds.", file=sys.stderr)
    print(f"Partial raw log preserved: {raw_path}", file=sys.stderr)
    sys.exit(1)

if start_line is None:
    sys.exit(f"BENCH_START missing; raw log preserved: {raw_path}")

start_fields = dict(
    re.findall(r"([A-Za-z_]+)=([^,\r\n]+)", start_line.split(",", 1)[1])
)

if int(start_fields.get("runs", "0")) != RUNS:
    sys.exit(f"Unexpected BENCH_START: {start_line}")
if int(start_fields.get("warmup", "0")) != WARMUP:
    sys.exit(f"Unexpected warm-up count: {start_line}")
if len(all_samples) != RUNS:
    sys.exit(f"Expected {RUNS} samples, found {len(all_samples)}. Raw log preserved.")

for i, sample in enumerate(all_samples):
    if sample["run"] != i + 1:
        sys.exit(f"Run sequence invalid at sample {i + 1}.")
    if sample["image"] != (i % 10):
        sys.exit(f"Unexpected image sequence at sample {i + 1}.")

failures = sum(s["ok"] != 1 for s in all_samples)
if summary_fields["runs"] != RUNS or summary_fields["failures"] != failures:
    sys.exit("Firmware summary does not agree with the parsed sample counts.")

fieldnames = [
    "run", "image", "invoke_us", "cycles",
    "raw_person", "raw_no_person", "ok"
]
with samples_path.open("x", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(all_samples)

def stats(values):
    ordered = sorted(values)
    return {
        "mean": round(statistics.mean(values), 2),
        "median": statistics.median(values),
        "p95_nearest_rank": ordered[math.ceil(0.95 * len(ordered)) - 1],
        "min": ordered[0],
        "max": ordered[-1],
    }

times = [s["invoke_us"] for s in all_samples]
cycles = [s["cycles"] for s in all_samples]
ts = stats(times)
cs = stats(cycles)

binary_sha = hashlib.sha256(binary_path.read_bytes()).hexdigest() if binary_path.exists() else "NOT_FOUND"

summary = {
    "status": "PASS",
    "port": PORT,
    "baud": BAUD,
    "runs": RUNS,
    "warmup_runs": WARMUP,
    "images_cycled": 10,
    "timing_method": "interpreter_Invoke_only",
    "failures": failures,
    "mean_us": ts["mean"],
    "median_us": ts["median"],
    "p95_nearest_rank_us": ts["p95_nearest_rank"],
    "min_us": ts["min"],
    "max_us": ts["max"],
    "mean_cycles": cs["mean"],
    "median_cycles": cs["median"],
    "p95_nearest_rank_cycles": cs["p95_nearest_rank"],
    "min_cycles": cs["min"],
    "max_cycles": cs["max"],
    "firmware_summary_line": summary_line,
    "firmware_binary_sha256": binary_sha,
}

with summary_path.open("x", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
    writer.writeheader()
    writer.writerow(summary)

raw_sha = hashlib.sha256(raw_path.read_bytes()).hexdigest()
note = (
    "R1 cycle-count benchmark capture note\n"
    "Date: 2026-10-22\n"
    "Status: PASS; complete newline-terminated BENCH_SUMMARY received\n"
    f"Port: {PORT} at {BAUD} baud\n"
    f"Firmware binary SHA256: {binary_sha}\n"
    f"Raw log SHA256: {raw_sha}\n"
    f"Measured samples: {RUNS}\n"
    f"Warm-up runs: {WARMUP}\n"
    f"Failures (ok != 1): {failures}\n"
    "Input sequence: 10 demo images cycled repeatedly; not 100 unique images\n"
    "Timing region: interpreter_Invoke_only\n"
    f"Firmware summary: {summary_line}\n"
)

note_path.write_text(note, encoding="utf-8")

hash_entries = []
for p in (raw_path, samples_path, summary_path, note_path, Path(__file__)):
    digest = hashlib.sha256(p.read_bytes()).hexdigest()
    hash_entries.append(f"{digest}  {p.name}")

hash_path.write_text("\n".join(hash_entries) + "\n", encoding="utf-8")

print("\nCAPTURE STATUS: PASS")
print(f"Parsed samples: {RUNS}")
print(f"Failures: {failures}")
print(f"Firmware summary: {summary_line}")
print(f"Mean Invoke time: {ts['mean']} us")
print(f"Median Invoke time: {ts['median']} us")
print(f"P95 Invoke time: {ts['p95_nearest_rank']} us")
print(f"Mean cycles: {cs['mean']}")
print(f"Median cycles: {cs['median']}")
print(f"P95 cycles: {cs['p95_nearest_rank']}")
print("\nSaved files:")
for p in (raw_path, samples_path, summary_path, note_path, hash_path):
    print(f"{p.name}: {p.stat().st_size} bytes")
print("\nSHA-256 manifest:")
print(hash_path.read_text(encoding="utf-8"), end="")
#!/usr/bin/env python3
"""Capture repeated detect_image outputs over serial for the ESP32 person_detection CLI.

Example (from repository root):
  python capture_runtime_repeatability.py --port COM5 --runtime R2A_ANSI_C \
    --firmware-bin examples/person_detection/chapter_evidence/r2a_ansi_c_images10_11_2026-10-24/person_detection_r2a_ansi_c.bin \
    --expected-firmware-sha256 4017A79C30E47A4FC15584617ACC5A86A7CF9511CB8D6F2500A22AE4B9B10143

The script does not flash the board or change firmware/configuration. Ensure the requested
runtime firmware is already flashed, and close ESP-IDF Monitor before running.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import re
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import serial
except ImportError:
    print("ERROR: pyserial is unavailable in this Python environment.", file=sys.stderr)
    print("Run this script with the ESP-IDF Python environment or install pyserial in your active environment.", file=sys.stderr)
    sys.exit(2)

IMAGE_RESULT_RE = re.compile(
    r"IMAGE_RESULT,image=(?P<image>\d+),invoke_ok=(?P<ok>\d+)"
    r"(?:,person_raw_int8=(?P<person>-?\d+),no_person_raw_int8=(?P<no_person>-?\d+))?"
    r",latency_ms=(?P<latency>\d+)"
)
INVOKE_RE = re.compile(r"INVOKE_US=(\d+)")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def percentile_nearest_rank(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((percentile / 100.0) * len(ordered) + 0.999999) - 1))
    return ordered[index]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM5")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--runtime", required=True, help="Runtime label, e.g. R1_REFERENCE, R2A_ANSI_C, R2_OPTIMIZED")
    parser.add_argument("--firmware-bin", required=True, help="Path to the preserved .bin for the runtime currently flashed")
    parser.add_argument("--expected-firmware-sha256", required=True)
    parser.add_argument("--runs", type=int, default=10, help="Repeats per image (default: 10)")
    parser.add_argument("--images", type=int, nargs="+", default=[10, 11])
    parser.add_argument("--timeout", type=float, default=20.0, help="Seconds allowed for each inference response")
    parser.add_argument("--output-dir", default=None)
    args = parser.parse_args()

    if args.runs < 1:
        parser.error("--runs must be at least 1")
    if any(i < 0 or i > 11 for i in args.images):
        parser.error("Image IDs must be between 0 and 11")

    firmware_path = Path(args.firmware_bin).resolve()
    if not firmware_path.is_file():
        print(f"ERROR: firmware binary not found: {firmware_path}", file=sys.stderr)
        return 2
    actual_hash = sha256(firmware_path)
    expected_hash = args.expected_firmware_sha256.strip().upper()
    if actual_hash != expected_hash:
        print("ERROR: preserved firmware hash mismatch; aborting.", file=sys.stderr)
        print(f"EXPECTED={expected_hash}\nACTUAL={actual_hash}", file=sys.stderr)
        return 2

    runtime_slug = re.sub(r"[^A-Za-z0-9_-]+", "_", args.runtime).strip("_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_dir).resolve() if args.output_dir else Path("examples/person_detection/chapter_evidence") / f"repeatability_{runtime_slug}_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=False)
    raw_path = out_dir / "serial_raw_log.txt"
    rows_path = out_dir / "trial_results.csv"
    summary_path = out_dir / "runtime_summary.csv"
    manifest_path = out_dir / "capture_manifest.txt"

    trials: list[dict[str, object]] = []
    raw_log: list[str] = []
    started = datetime.now(timezone.utc).isoformat()
    print(f"Runtime: {args.runtime}")
    print(f"Firmware SHA256: {actual_hash}")
    print(f"Serial: {args.port} at {args.baud} baud")
    print(f"Runs per image: {args.runs}; images: {args.images}")
    print("Starting serial capture. Do not type into the monitor during the test.")

    try:
        # DTR/RTS set low to reduce likelihood of resetting the board on open.
        with serial.Serial(args.port, args.baud, timeout=0.25, write_timeout=2.0, rtscts=False, dsrdtr=False) as ser:
            ser.dtr = False
            ser.rts = False
            time.sleep(3.0)
            ser.reset_input_buffer()
            for image_id in args.images:
                for trial_no in range(1, args.runs + 1):
                    ser.reset_input_buffer()
                    command = f"detect_image {image_id}\r\n"
                    sent_at = datetime.now(timezone.utc).isoformat()
                    raw_log.append(f"\n[{sent_at}] >>> detect_image {image_id}\n")
                    ser.write(command.encode("ascii"))
                    ser.flush()
                    deadline = time.monotonic() + args.timeout
                    invoke_us = None
                    result = None
                    while time.monotonic() < deadline:
                        data = ser.readline()
                        if not data:
                            continue
                        line = data.decode("utf-8", errors="replace").rstrip("\r\n")
                        raw_log.append(line + "\n")
                        m_inv = INVOKE_RE.search(line)
                        if m_inv:
                            invoke_us = int(m_inv.group(1))
                        m_result = IMAGE_RESULT_RE.search(line)
                        if m_result:
                            result = m_result.groupdict()
                            break
                    if result is None:
                        raw_path.write_text("".join(raw_log), encoding="utf-8")
                        print(f"ERROR: timeout waiting for IMAGE_RESULT for image {image_id}, trial {trial_no}.")
                        print(f"Partial raw log saved to: {raw_path}")
                        return 3
                    reported_image = int(result["image"])
                    if reported_image != image_id:
                        raw_path.write_text("".join(raw_log), encoding="utf-8")
                        print(f"ERROR: expected image {image_id}, got result for image {reported_image}.")
                        return 4
                    row = {
                        "runtime": args.runtime,
                        "image_id": image_id,
                        "trial": trial_no,
                        "invoke_ok": int(result["ok"]),
                        "person_raw_int8": result["person"] if result["person"] is not None else "",
                        "no_person_raw_int8": result["no_person"] if result["no_person"] is not None else "",
                        "invoke_us": invoke_us if invoke_us is not None else "",
                        "latency_ms": int(result["latency"]),
                        "firmware_sha256": actual_hash,
                        "capture_utc": sent_at,
                    }
                    trials.append(row)
                    print(f"image={image_id}, trial={trial_no}/{args.runs}, invoke_ok={row['invoke_ok']}, "
                          f"person_raw={row['person_raw_int8']}, no_person_raw={row['no_person_raw_int8']}, "
                          f"invoke_us={row['invoke_us']}, latency_ms={row['latency_ms']}")
    except serial.SerialException as exc:
        raw_path.write_text("".join(raw_log), encoding="utf-8")
        print(f"ERROR: serial port operation failed: {exc}", file=sys.stderr)
        print(f"Partial raw log saved to: {raw_path}", file=sys.stderr)
        return 5

    raw_path.write_text("".join(raw_log), encoding="utf-8")
    with rows_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(trials[0].keys()))
        writer.writeheader()
        writer.writerows(trials)

    summaries = []
    for image_id in args.images:
        group = [r for r in trials if r["image_id"] == image_id]
        ok_rows = [r for r in group if r["invoke_ok"] == 1]
        raw_tuples = {(r["person_raw_int8"], r["no_person_raw_int8"]) for r in ok_rows}
        latencies = [float(r["latency_ms"]) for r in ok_rows]
        invoke_values = [float(r["invoke_us"]) for r in ok_rows if r["invoke_us"] != ""]
        summaries.append({
            "runtime": args.runtime,
            "image_id": image_id,
            "requested_runs": args.runs,
            "successful_invocations": len(ok_rows),
            "failed_invocations": len(group) - len(ok_rows),
            "unique_raw_output_pairs": len(raw_tuples),
            "raw_outputs_stable": len(raw_tuples) == 1 and len(ok_rows) == len(group),
            "person_raw_int8": next(iter(raw_tuples))[0] if len(raw_tuples) == 1 else "MIXED_OR_MISSING",
            "no_person_raw_int8": next(iter(raw_tuples))[1] if len(raw_tuples) == 1 else "MIXED_OR_MISSING",
            "mean_latency_ms": round(statistics.mean(latencies), 3) if latencies else "",
            "median_latency_ms": round(statistics.median(latencies), 3) if latencies else "",
            "p95_latency_ms_nearest_rank": percentile_nearest_rank(latencies, 95) if latencies else "",
            "min_latency_ms": min(latencies) if latencies else "",
            "max_latency_ms": max(latencies) if latencies else "",
            "mean_invoke_us": round(statistics.mean(invoke_values), 3) if invoke_values else "",
            "min_invoke_us": min(invoke_values) if invoke_values else "",
            "max_invoke_us": max(invoke_values) if invoke_values else "",
            "firmware_sha256": actual_hash,
        })
    with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(summaries[0].keys()))
        writer.writeheader()
        writer.writerows(summaries)

    completed = datetime.now(timezone.utc).isoformat()
    raw_hash = sha256(raw_path)
    rows_hash = sha256(rows_path)
    summary_hash = sha256(summary_path)
    manifest = (
        f"runtime={args.runtime}\n"
        f"capture_started_utc={started}\n"
        f"capture_completed_utc={completed}\n"
        f"serial_port={args.port}\n"
        f"baud={args.baud}\n"
        f"runs_per_image={args.runs}\n"
        f"images={','.join(str(i) for i in args.images)}\n"
        f"firmware_bin={firmware_path}\n"
        f"firmware_sha256={actual_hash}\n"
        f"raw_log_sha256={raw_hash}\n"
        f"trial_results_sha256={rows_hash}\n"
        f"runtime_summary_sha256={summary_hash}\n"
    )
    manifest_path.write_text(manifest, encoding="utf-8")

    print("\n===== REPEATABILITY CAPTURE COMPLETE =====")
    print(f"OUTPUT_DIR={out_dir}")
    print(f"TRIAL_ROWS={len(trials)}")
    print(f"RAW_LOG_SHA256={raw_hash}")
    print(f"TRIAL_RESULTS_SHA256={rows_hash}")
    print(f"SUMMARY_SHA256={summary_hash}")
    print("\nSummary:")
    for row in summaries:
        print(
            f"image={row['image_id']} success={row['successful_invocations']}/{row['requested_runs']} "
            f"failed={row['failed_invocations']} outputs_stable={row['raw_outputs_stable']} "
            f"mean_latency_ms={row['mean_latency_ms']} p95_latency_ms={row['p95_latency_ms_nearest_rank']} "
            f"mean_invoke_us={row['mean_invoke_us']}"
        )
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

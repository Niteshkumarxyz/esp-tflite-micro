import re
import sys
import time
from pathlib import Path
import serial

port = "COM5"
base = Path(__file__).resolve().parent
raw_path = base / "r1_probe1_raw_20261022.txt"
data = bytearray()

def save_and_read(ser, raw, buf, duration):
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        chunk = ser.read(max(1, ser.in_waiting))
        if chunk:
            raw.write(chunk)
            raw.flush()
            buf.extend(chunk)
            data.extend(chunk)
            decoded = buf.decode("utf-8", errors="replace")
            if re.search(
                r"(?m)^BENCH_SUMMARY,runs=1,failures=\d+,mean_us=\d+,median_us=\d+,p95_nearest_rank_us=\d+,min_us=\d+,max_us=\d+",
                decoded,
            ):
                return True
    return False

print("Opening COM5; waiting for console prompt.", flush=True)

try:
    with serial.Serial(
        port, 115200, timeout=0.25, write_timeout=3,
        dsrdtr=False, rtscts=False
    ) as ser, raw_path.open("xb") as raw:

        time.sleep(1)
        ser.write(b"\r\n")
        startup = bytearray()
        deadline = time.monotonic() + 60

        while time.monotonic() < deadline:
            chunk = ser.read(max(1, ser.in_waiting))
            if chunk:
                raw.write(chunk)
                raw.flush()
                startup.extend(chunk)
                data.extend(chunk)
                if b"esp>" in startup:
                    break
        else:
            raise RuntimeError("No esp> prompt received in 60 seconds.")

        print("Prompt detected. Waiting briefly before sending command.", flush=True)
        time.sleep(1.5)

        print("Sending benchmark 1.", flush=True)
        ser.write(b"benchmark 1\r\n")

        result = bytearray()
        complete = save_and_read(ser, raw, result, 180)

        print("\n--- Captured benchmark output ---")
        decoded = data.decode("utf-8", errors="replace")
        for line in decoded.splitlines():
            if any(tag in line for tag in (
                "BENCH_START", "BENCH_SAMPLE,", "BENCH_SAMPLES_END",
                "BENCH_SUMMARY", "Guru Meditation", "rst:"
            )):
                print(line)

        if not complete:
            print("PROBE STATUS: INCOMPLETE")
            print(f"Partial raw log preserved: {raw_path}")
            sys.exit(1)

        print("PROBE STATUS: PASS")
        print(f"Raw log size: {raw_path.stat().st_size} bytes")

except Exception as exc:
    print(f"PROBE ERROR: {exc}", file=sys.stderr)
    print(f"Raw log, if created, is at: {raw_path}", file=sys.stderr)
    sys.exit(1)
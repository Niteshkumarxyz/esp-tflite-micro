import time, hashlib
from pathlib import Path
import serial

out = Path(r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro\examples\person_detection\chapter_evidence\optimized_r2_tensor_trace_image_5_retry2_2026-10-27.txt")

with serial.Serial("COM5", 115200, timeout=0.2, write_timeout=5) as ser:
    ser.dtr = False
    ser.rts = False
    buf = bytearray()

    # Wait for the existing CLI prompt; do not pulse reset.
    ser.write(b"\r\n")
    deadline = time.monotonic() + 30
    while b"esp>" not in buf and time.monotonic() < deadline:
        chunk = ser.read(4096)
        if chunk:
            buf.extend(chunk)

    if b"esp>" not in buf:
        raise SystemExit("CLI prompt not detected. Stop; do not flash.")

    buf.clear()
    ser.write(b"detect_image 5\r\n")
    deadline = time.monotonic() + 180

    while b"IMAGE_RESULT,image=5," not in buf and time.monotonic() < deadline:
        chunk = ser.read(4096)
        if chunk:
            buf.extend(chunk)

    if b"IMAGE_RESULT,image=5," not in buf:
        out.write_bytes(buf)
        raise SystemExit("Image 5 result missing; partial output saved.")

    deadline = time.monotonic() + 30
    while b"esp>" not in buf and time.monotonic() < deadline:
        chunk = ser.read(4096)
        if chunk:
            buf.extend(chunk)

    out.write_bytes(buf)
    text = buf.decode("ascii", errors="replace")
    lines = text.splitlines()
    raw = sum(x.startswith("RQ1_RAW,") for x in lines)
    traces = sum(x.startswith("RQ1_TRACE,") for x in lines)

    for line in lines:
        if line.startswith("IMAGE_RESULT,image=5,"):
            print(line)

    print(f"TRACE={traces}; RAW={raw}; bytes={len(buf)}")
    print(f"SHA256={hashlib.sha256(buf).hexdigest()}")
    print(f"Saved: {out}")

    if raw == 0:
        raise SystemExit("RAW=0: image 5 trace incomplete; stop for reset diagnosis.")
import time
import hashlib
from pathlib import Path
import serial

out = Path(r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro\examples\person_detection\chapter_evidence\optimized_r2_tensor_trace_image_2_reset_test_2026-10-27.txt")

with serial.Serial("COM5", 115200, timeout=0.2, write_timeout=5) as ser:
    ser.dtr = False
    ser.rts = False
    time.sleep(0.3)
    ser.reset_input_buffer()

    # ESP32 auto-reset pulse; do not enter download mode.
    ser.dtr = False
    ser.rts = True
    time.sleep(0.15)
    ser.dtr = True
    ser.rts = False
    time.sleep(0.15)
    ser.dtr = False

    captured = bytearray()
    deadline = time.monotonic() + 45

    while b"esp>" not in captured and time.monotonic() < deadline:
        data = ser.read(4096)
        if data:
            captured.extend(data)

    if b"esp>" not in captured:
        out.write_bytes(captured)
        raise SystemExit("Reset/CLI prompt not confirmed; partial boot log saved.")

    print("CLI prompt detected after reset.")
    captured.clear()
    ser.write(b"detect_image 2\r\n")

    deadline = time.monotonic() + 180
    while b"IMAGE_RESULT,image=2," not in captured and time.monotonic() < deadline:
        data = ser.read(4096)
        if data:
            captured.extend(data)

    if b"IMAGE_RESULT,image=2," not in captured:
        out.write_bytes(captured)
        raise SystemExit("Image 2 result not found; partial trace saved.")

    deadline = time.monotonic() + 20
    while b"esp>" not in captured and time.monotonic() < deadline:
        data = ser.read(4096)
        if data:
            captured.extend(data)

    out.write_bytes(captured)
    text = captured.decode("ascii", errors="replace")
    raw_count = sum(line.startswith("RQ1_RAW,") for line in text.splitlines())
    trace_count = sum(line.startswith("RQ1_TRACE,") for line in text.splitlines())

    print("IMAGE 2 RESULT:")
    for line in text.splitlines():
        if line.startswith("IMAGE_RESULT,image=2,"):
            print(line)
    print(f"RAW records: {raw_count}")
    print(f"TRACE records: {trace_count}")
    print(f"Bytes saved: {len(captured)}")
    print(f"SHA256: {hashlib.sha256(captured).hexdigest()}")
    print(f"Saved: {out}")

    if raw_count == 0:
        raise SystemExit("No raw data found; do not proceed to batch capture.")
import time
import serial
from pathlib import Path
from datetime import datetime

PORT, BAUD = "COM5", 115200
data = bytearray()
outdir = Path("chapter_evidence")
outdir.mkdir(exist_ok=True)

def poll(ser):
    chunk = ser.read(1024)
    if chunk:
        data.extend(chunk)

def wait_for(ser, marker, start, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pos = data.find(marker, start)
        if pos >= 0:
            return pos + len(marker)
        poll(ser)
    pos = data.find(marker, start)
    return pos + len(marker) if pos >= 0 else None

outfile = outdir / (
    "en_reset_timed_diagnostic_" +
    datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt"
)

with serial.Serial(PORT, BAUD, timeout=0.1, write_timeout=5) as ser:
    ser.dtr = False
    ser.rts = False

    print("Waiting for initial ESP32 CLI prompt...")
    initial = wait_for(ser, b"esp>", 0, 60)

    if initial is None:
        print("FAIL: Initial CLI prompt not detected.")
    else:
        print("Initial CLI detected.")
        time.sleep(0.5)
        start = len(data)

        print("\nRESET TEST ARMED FOR 15 SECONDS.")
        print("Press and release EN once during this window.")
        print("Do NOT press Enter. Do NOT press BOOT.")

        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            poll(ser)

        captured = bytes(data[start:])
        outfile.write_bytes(captured)

        reset_pos = captured.find(b"rst:")
        prompt_found = (
            reset_pos >= 0 and captured.find(b"esp>", reset_pos) >= 0
        )

        print("\nRESET_MARKER_FOUND:", reset_pos >= 0)
        print("POST_RESET_PROMPT_FOUND:", prompt_found)
        print("NEW_BYTES_AFTER_MARK:", len(captured))
        print("CAPTURE_FILE:", outfile.resolve())
        print("CAPTURE_PREVIEW:", repr(captured[:400]))

print("Diagnostic finished.")

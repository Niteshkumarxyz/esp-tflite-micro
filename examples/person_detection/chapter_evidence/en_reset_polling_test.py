import time
import msvcrt
import serial
from pathlib import Path
from datetime import datetime

PORT, BAUD = "COM5", 115200
data = bytearray()
outdir = Path("chapter_evidence")
outdir.mkdir(exist_ok=True)

def read_once(ser):
    chunk = ser.read(1024)
    if chunk:
        data.extend(chunk)

def wait_marker(ser, marker, start, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pos = data.find(marker, start)
        if pos >= 0:
            return pos + len(marker)
        read_once(ser)
    return None

outfile = outdir / (
    "en_reset_polling_test_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt"
)

with serial.Serial(PORT, BAUD, timeout=0.1, write_timeout=5) as ser:
    ser.dtr = False
    ser.rts = False

    print("Waiting for initial CLI prompt...")
    initial = wait_marker(ser, b"esp>", 0, 60)
    if initial is None:
        print("FAIL: Initial CLI prompt not detected.")
    else:
        print("Initial CLI detected.")
        time.sleep(0.5)
        start = len(data)
        print("Press and release EN once. Then press Enter here.")

        while True:
            read_once(ser)
            if msvcrt.kbhit():
                key = msvcrt.getwch()
                if key == "\r":
                    break
                if key == "\x03":
                    raise KeyboardInterrupt

        reset_end = wait_marker(ser, b"rst:", start, 12)
        prompt_end = (
            wait_marker(ser, b"esp>", reset_end, 60)
            if reset_end is not None else None
        )

        captured = bytes(data[start:])
        outfile.write_bytes(captured)
        print("RESET_MARKER_FOUND:", reset_end is not None)
        print("POST_RESET_PROMPT_FOUND:", prompt_end is not None)
        print("NEW_BYTES_AFTER_MARK:", len(captured))
        print("CAPTURE_FILE:", outfile.resolve())
        print("CAPTURE_PREVIEW:", repr(captured[:300]))

print("Diagnostic finished.")

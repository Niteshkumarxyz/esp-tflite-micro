import threading
import time
from pathlib import Path
from datetime import datetime
import serial

PORT = "COM5"
BAUD = 115200
data = bytearray()
lock = threading.Lock()
stop = threading.Event()
read_errors = []

def reader(ser):
    while not stop.is_set():
        try:
            chunk = ser.read(4096)
            if chunk:
                with lock:
                    data.extend(chunk)
        except Exception as exc:
            with lock:
                read_errors.append(repr(exc))
            return

def snapshot():
    with lock:
        return bytes(data)

def wait_for(marker, start, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        content = snapshot()
        pos = content.find(marker, start)
        if pos >= 0:
            return pos + len(marker)
        if read_errors:
            break
        time.sleep(0.1)
    return None

outdir = Path("chapter_evidence")
outdir.mkdir(exist_ok=True)
outfile = outdir / (
    "en_reset_diagnostic_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".txt"
)

try:
    with serial.Serial(PORT, BAUD, timeout=0.2, write_timeout=5) as ser:
        ser.dtr = False
        ser.rts = False
        thread = threading.Thread(target=reader, args=(ser,), daemon=True)
        thread.start()

        print("Waiting for initial ESP32 CLI prompt...")
        initial = wait_for(b"esp>", 0, 60)

        if initial is None:
            print("FAIL: Initial CLI prompt not detected.")
        else:
            print("Initial CLI detected.")
            time.sleep(1)
            with lock:
                start = len(data)

            input(
                "Press and release ESP32 EN once. Wait one second, "
                "then press Enter here. Do not press BOOT."
            )

            reset_end = wait_for(b"rst:", start, 12)
            if reset_end is not None:
                prompt_end = wait_for(b"esp>", reset_end, 60)
                print("RESET_MARKER_FOUND: True")
                print("POST_RESET_PROMPT_FOUND:", prompt_end is not None)
            else:
                print("RESET_MARKER_FOUND: False")

            captured = snapshot()[start:]
            outfile.write_bytes(captured)
            print("NEW_BYTES_AFTER_MARK:", len(captured))
            print("CAPTURE_FILE:", outfile.resolve())
            print("CAPTURE_PREVIEW:", repr(captured[:600]))

        if read_errors:
            print("SERIAL_READ_ERRORS:", read_errors)
finally:
    stop.set()
    if "thread" in locals():
        thread.join(timeout=2)

print("Diagnostic finished.")

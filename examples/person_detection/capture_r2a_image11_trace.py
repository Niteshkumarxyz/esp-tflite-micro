import hashlib
import time
from pathlib import Path

import serial

PORT = "COM5"
BAUD = 115200
OUTPUT_PATH = Path(
    "chapter_evidence/r2a_ansi_c_trace_image11_wdt30_2026-10-27.txt"
)

class SerialReader:
    def __init__(self, connection):
        self.connection = connection
        self.buffer = bytearray()
        self.all_data = bytearray()

    def read_until(self, marker, timeout_seconds):
        deadline = time.monotonic() + timeout_seconds

        while time.monotonic() < deadline:
            chunk = self.connection.read(4096)

            if not chunk:
                continue

            self.buffer.extend(chunk)
            self.all_data.extend(chunk)

            position = self.buffer.find(marker)
            if position >= 0:
                end = position + len(marker)
                result = bytes(self.buffer[:end])
                del self.buffer[:end]
                return result

        raise TimeoutError(
            f"Timed out waiting for {marker!r} "
            f"after {timeout_seconds} seconds"
        )

def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = serial.Serial()
    connection.port = PORT
    connection.baudrate = BAUD
    connection.timeout = 0.2
    connection.write_timeout = 5
    connection.dtr = False
    connection.rts = False

    reader = None
    capture_start = 0
    command_sent = False

    try:
        print(f"Opening {PORT}...")
        connection.open()
        time.sleep(1)
        connection.reset_input_buffer()

        reader = SerialReader(connection)

        print("Waiting for ESP32 CLI prompt...")
        connection.write(b"\r\n")
        reader.read_until(b"esp>", 45)
        print("CLI prompt detected.")

        capture_start = len(reader.all_data)
        command_sent = True

        print("Running detect_image 11. Please wait...")
        connection.write(b"detect_image 11\r\n")

        reader.read_until(b"IMAGE_RESULT,image=11,", 180)
        print("Image 11 result detected.")

        reader.read_until(b"esp>", 45)
        print("ESP32 returned to the CLI prompt.")

    except Exception as error:
        print(f"CAPTURE ERROR: {type(error).__name__}: {error}")

    finally:
        if reader is not None and command_sent:
            captured = bytes(reader.all_data[capture_start:])
            OUTPUT_PATH.write_bytes(captured)

            lines = captured.decode(
                "ascii", errors="replace"
            ).splitlines()

            results = [
                line for line in lines
                if line.startswith("IMAGE_RESULT,image=11,")
            ]
            trace_count = sum(
                line.startswith("RQ1_TRACE,") for line in lines
            )
            raw_count = sum(
                line.startswith("RQ1_RAW,") for line in lines
            )

            print("\nCapture verification")
            print(f"Result: {results[-1] if results else 'MISSING'}")
            print(f"TRACE records: {trace_count}")
            print(f"RAW records: {raw_count}")
            print(f"Captured bytes: {len(captured)}")
            print(
                "SHA-256:",
                hashlib.sha256(captured).hexdigest()
            )
            print(f"Saved file: {OUTPUT_PATH.resolve()}")

            if not results or trace_count != 31 or raw_count != 3625:
                print("STATUS: Capture is incomplete or needs review.")
            else:
                print("STATUS: Expected image 11 trace counts verified.")

        if connection.is_open:
            connection.close()

if __name__ == "__main__":
    main()
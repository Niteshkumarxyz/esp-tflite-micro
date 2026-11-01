import hashlib
import time
from pathlib import Path
import serial

EVIDENCE = Path(
    r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro\examples\person_detection\chapter_evidence"
)
OUTPUT = EVIDENCE / "optimized_r2_tensor_trace_image_10_verified_2026-10-27.txt"
FIRMWARE_SHA256 = (
    "F70EA1D4FF93289BB32BB3C89B20A70C3C232264B1B9B3793BEC43EB94D9F4BE"
)

class SerialReader:
    def __init__(self, connection):
        self.connection = connection
        self.buffer = bytearray()

    def read_until(self, marker, timeout):
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            position = self.buffer.find(marker)
            if position >= 0:
                end = position + len(marker)
                data = bytes(self.buffer[:end])
                del self.buffer[:end]
                return data

            chunk = self.connection.read(4096)
            if chunk:
                self.buffer.extend(chunk)

        raise TimeoutError(f"Timeout waiting for {marker!r}")

def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    ser = serial.Serial()
    ser.port = "COM5"
    ser.baudrate = 115200
    ser.timeout = 0.2
    ser.write_timeout = 5
    ser.dtr = False
    ser.rts = False

    try:
        ser.open()
        time.sleep(0.5)
        reader = SerialReader(ser)

        print("Connecting to the ESP32 CLI...")
        try:
            prompt_data = reader.read_until(b"esp>", 45)
        except TimeoutError:
            ser.write(b"\r\n")
            prompt_data = reader.read_until(b"esp>", 30)

        print("CLI prompt detected.")
        print("Running detect_image 10...")
        ser.write(b"detect_image 10\r\n")

        result_data = reader.read_until(
            b"IMAGE_RESULT,image=10,", 180
        )
        prompt_after_result = reader.read_until(b"esp>", 30)

        # Preserve every returned serial byte, including RAW tensor records.
        captured = (
            f"COMMAND=detect_image 10\r\n"
            f"FIRMWARE_SHA256={FIRMWARE_SHA256}\r\n"
        ).encode("ascii") + prompt_data + result_data + prompt_after_result

        OUTPUT.write_bytes(captured)

        lines = captured.decode("ascii", errors="replace").splitlines()
        result_line = next(
            (
                line for line in lines
                if line.startswith("IMAGE_RESULT,image=10,")
            ),
            "MISSING"
        )
        trace_count = sum(
            line.startswith("RQ1_TRACE,") for line in lines
        )
        raw_count = sum(
            line.startswith("RQ1_RAW,") for line in lines
        )

        print(result_line)
        print(f"TRACE records: {trace_count}")
        print(f"RAW records: {raw_count}")
        print(f"Captured bytes: {len(captured)}")
        print(f"SHA-256: {hashlib.sha256(captured).hexdigest()}")
        print(f"Saved file: {OUTPUT}")

        if result_line == "MISSING" or raw_count == 0:
            print("WARNING: Image 10 raw trace is not verified.")
        else:
            print("Image 10 raw trace capture verified.")

    except TimeoutError as error:
        print(f"ERROR: Capture timed out: {error}")
        print("No successful image 10 capture can be claimed.")
        raise SystemExit(2)
    finally:
        if ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()
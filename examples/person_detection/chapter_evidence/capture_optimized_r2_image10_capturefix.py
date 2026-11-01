import hashlib
import time
from pathlib import Path
import serial

EVIDENCE = Path(
    r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro\examples\person_detection\chapter_evidence"
)
OUTPUT = EVIDENCE / "optimized_r2_tensor_trace_image_10_capturefix_2026-10-27.txt"
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
                result = bytes(self.buffer[:end])
                del self.buffer[:end]
                return result

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

        input(
            "Press Enter to arm serial capture. "
            "Do not press BOOT."
        )

        reader.buffer.clear()
        ser.reset_input_buffer()

        print("Capture armed. Press and release the EN button now.")
        print("Waiting for application startup and CLI prompt...")

        try:
            boot_output = reader.read_until(b"esp>", 60)
        except TimeoutError:
            partial = bytes(reader.buffer)
            OUTPUT.write_bytes(partial)
            print("ERROR: CLI prompt not detected. Inference was not issued.")
            print(f"Partial log: {OUTPUT}")
            raise SystemExit(2)

        print("CLI prompt detected. Running detect_image 10.")
        ser.write(b"detect_image 10\r\n")

        try:
            result_output = reader.read_until(
                b"IMAGE_RESULT,image=10,", 180
            )
        except TimeoutError:
            partial = boot_output + bytes(reader.buffer)
            OUTPUT.write_bytes(partial)
            print("ERROR: Image 10 result not detected.")
            print(f"Partial log: {OUTPUT}")
            raise SystemExit(3)

        try:
            prompt_output = reader.read_until(b"esp>", 30)
        except TimeoutError:
            prompt_output = bytes(reader.buffer)

        # Preserve the returned data from every read operation.
        captured = (
            f"COMMAND=detect_image 10\r\n"
            f"FIRMWARE_SHA256={FIRMWARE_SHA256}\r\n"
        ).encode("ascii") + boot_output + result_output + prompt_output

        OUTPUT.write_bytes(captured)

        text = captured.decode("ascii", errors="replace")
        lines = text.splitlines()

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
            print("WARNING: Image 10 raw trace is not yet verified.")
        else:
            print("Image 10 raw trace capture verified.")

    finally:
        if ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()
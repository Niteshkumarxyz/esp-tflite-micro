import hashlib
import time
from pathlib import Path
import serial

EVIDENCE = Path(
    r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro\examples\person_detection\chapter_evidence"
)
FIRMWARE_SHA256 = (
    "38A2F6231F53C04524AE834ACE4770F74DE3F44E81AE988632AC2FDF1E110643"
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

def capture_image(reader, ser, image, boot_output):
    command = f"detect_image {image}"
    print(f"Running {command}...")
    ser.write((command + "\r\n").encode("ascii"))

    try:
        result_output = reader.read_until(
            f"IMAGE_RESULT,image={image},".encode("ascii"), 180
        )
        prompt_output = reader.read_until(b"esp>", 30)
    except TimeoutError as error:
        partial_path = EVIDENCE / (
            f"r2a_image_{image}_partial_2026-10-27.txt"
        )
        partial_path.write_bytes(
            boot_output + bytes(reader.buffer)
        )
        print(f"ERROR: Image {image} capture timed out: {error}")
        print(f"Partial output saved: {partial_path}")
        raise SystemExit(3)

    captured = (
        f"COMMAND={command}\r\n"
        f"FIRMWARE_SHA256={FIRMWARE_SHA256}\r\n"
    ).encode("ascii") + boot_output + result_output + prompt_output

    text = captured.decode("ascii", errors="replace")
    lines = text.splitlines()

    result = next(
        (
            line for line in lines
            if line.startswith(f"IMAGE_RESULT,image={image},")
        ),
        "MISSING"
    )
    trace_count = sum(line.startswith("RQ1_TRACE,") for line in lines)
    raw_count = sum(line.startswith("RQ1_RAW,") for line in lines)
    digest = hashlib.sha256(captured).hexdigest()

    filename = f"r2a_ansi_c_trace_image{image}_wdt30_{'2026-10-27'}.txt"
    output_path = EVIDENCE / filename
    output_path.write_bytes(captured)

    print(result)
    print(f"TRACE records: {trace_count}")
    print(f"RAW records: {raw_count}")
    print(f"Captured bytes: {len(captured)}")
    print(f"SHA-256: {digest}")
    print(f"Saved file: {output_path}")

    if result == "MISSING" or raw_count == 0:
        print("ERROR: Complete raw tensor trace was not verified.")
        raise SystemExit(4)

    print(f"Image {image} raw tensor trace verified.")
    return captured

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

        print("Waiting for the R2A application CLI...")
        ser.write(b"\r\n")

        try:
            boot0 = reader.read_until(b"esp>", 45)
        except TimeoutError:
            partial = EVIDENCE / "r2a_image0_boot_timeout_2026-10-27.txt"
            partial.write_bytes(bytes(reader.buffer))
            print(f"ERROR: CLI prompt not detected. Log: {partial}")
            raise SystemExit(2)

        print("CLI prompt detected.")
        capture_image(reader, ser, 0, boot0)

        input(
            "\nImage 0 saved. Press Enter to arm capture for image 11. "
            "Do not press BOOT."
        )

        reader.buffer.clear()
        ser.reset_input_buffer()

        print("Capture armed. Press and release the EN button now.")
        print("Waiting for the application CLI prompt...")

        try:
            boot11 = reader.read_until(b"esp>", 60)
        except TimeoutError:
            partial = EVIDENCE / "r2a_image11_boot_timeout_2026-10-27.txt"
            partial.write_bytes(bytes(reader.buffer))
            print(f"ERROR: Fresh CLI prompt not detected. Log: {partial}")
            raise SystemExit(5)

        print("Fresh CLI prompt detected.")
        capture_image(reader, ser, 11, boot11)

        print("\nBoth requested R2A traces were captured and saved.")

    finally:
        if ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()
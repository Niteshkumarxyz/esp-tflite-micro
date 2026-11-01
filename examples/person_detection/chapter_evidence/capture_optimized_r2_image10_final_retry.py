import hashlib
import time
from pathlib import Path
import serial

EVIDENCE = Path(
    r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro\examples\person_detection\chapter_evidence"
)
OUTPUT = EVIDENCE / "optimized_r2_tensor_trace_image_10_final_retry_2026-10-27.txt"
FIRMWARE_SHA256 = (
    "F70EA1D4FF93289BB32BB3C89B20A70C3C232264B1B9B3793BEC43EB94D9F4BE"
)

def read_until(ser, buffer, marker, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        position = buffer.find(marker)
        if position >= 0:
            end = position + len(marker)
            result = bytes(buffer[:end])
            del buffer[:end]
            return result

        chunk = ser.read(4096)
        if chunk:
            buffer.extend(chunk)

    raise TimeoutError(f"Timeout waiting for {marker!r}")

def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    buffer = bytearray()

    # Set modem control lines before opening the port to reduce reset risk.
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
        ser.reset_input_buffer()
        ser.write(b"\r\n")

        try:
            read_until(ser, buffer, b"esp>", 20)
        except TimeoutError:
            partial = EVIDENCE / "optimized_r2_image10_prompt_timeout.txt"
            partial.write_bytes(buffer)
            print("ERROR: CLI prompt not detected. Inference was not issued.")
            print(f"Partial log: {partial}")
            raise SystemExit(2)

        print("CLI prompt detected. Running image 10.")
        buffer.clear()
        ser.write(b"detect_image 10\r\n")

        try:
            read_until(
                ser, buffer, b"IMAGE_RESULT,image=10,", 180
            )
            read_until(ser, buffer, b"esp>", 30)
        except TimeoutError as error:
            OUTPUT.write_bytes(buffer)
            print(f"ERROR: Capture did not finish: {error}")
            print(f"Partial output saved: {OUTPUT}")
            raise SystemExit(3)

        text = buffer.decode("ascii", errors="replace")
        lines = text.splitlines()
        raw_count = sum(line.startswith("RQ1_RAW,") for line in lines)
        trace_count = sum(line.startswith("RQ1_TRACE,") for line in lines)
        result = next(
            (line for line in lines
             if line.startswith("IMAGE_RESULT,image=10,")),
            "MISSING"
        )

        data = (
            f"COMMAND=detect_image 10\r\n"
            f"FIRMWARE_SHA256={FIRMWARE_SHA256}\r\n"
        ).encode("ascii") + bytes(buffer)
        OUTPUT.write_bytes(data)

        print(result)
        print(f"TRACE records: {trace_count}")
        print(f"RAW records: {raw_count}")
        print(f"Output size: {len(data)} bytes")
        print(f"SHA-256: {hashlib.sha256(data).hexdigest()}")
        print(f"Saved: {OUTPUT}")

        if raw_count == 0:
            print("WARNING: Raw tensor records are missing.")

    finally:
        if ser.is_open:
            ser.close()

if __name__ == "__main__":
    main()
import csv
import hashlib
import time
from pathlib import Path
import serial

EVIDENCE = Path(
    r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro\examples\person_detection\chapter_evidence"
)
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

def save_summary(rows):
    if not rows:
        return

    path = EVIDENCE / "optimized_r2_raw_trace_summary_images7_to10_2026-10-27.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Summary CSV: {path}")

def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    rows = []

    with serial.Serial("COM5", 115200, timeout=0.2, write_timeout=5) as ser:
        ser.dtr = False
        ser.rts = False
        reader = SerialReader(ser)

        for image in range(7, 11):
            reader.buffer.clear()
            ser.reset_input_buffer()

            input(
                f"\nImage {image}: Press Enter to arm serial capture. "
                "Do not press BOOT."
            )

            print("Serial capture is armed. Press and release EN now.")
            print("Waiting for the ESP32 reset banner and CLI prompt...")

            try:
                boot_start = reader.read_until(b"rst:", 25)
                boot_rest = reader.read_until(b"esp>", 60)
            except TimeoutError as error:
                print(f"ERROR: Reset/boot was not confirmed: {error}")
                save_summary(rows)
                raise SystemExit(2)

            print("Reset banner and CLI prompt detected.")

            command = f"detect_image {image}"
            print(f"Running {command}...")

            ser.write((command + "\r\n").encode("ascii"))

            try:
                result_output = reader.read_until(
                    f"IMAGE_RESULT,image={image},".encode("ascii"),
                    180
                )
                prompt_output = reader.read_until(b"esp>", 30)
            except TimeoutError as error:
                print(f"ERROR: Image {image} capture timed out: {error}")
                save_summary(rows)
                raise SystemExit(3)

            data = (
                f"COMMAND={command}\r\n"
                f"FIRMWARE_SHA256={FIRMWARE_SHA256}\r\n"
                "RESET_BANNER_CONFIRMED=1\r\n"
            ).encode("ascii") + boot_start + boot_rest + result_output + prompt_output

            lines = data.decode("ascii", errors="replace").splitlines()
            result_line = next(
                (
                    line for line in lines
                    if line.startswith(f"IMAGE_RESULT,image={image},")
                ),
                "MISSING"
            )
            trace_count = sum(line.startswith("RQ1_TRACE,") for line in lines)
            raw_count = sum(line.startswith("RQ1_RAW,") for line in lines)

            filename = (
                f"optimized_r2_tensor_trace_image_{image}_"
                "resetverified_v2_2026-10-27.txt"
            )
            output_path = EVIDENCE / filename
            output_path.write_bytes(data)

            row = {
                "image": image,
                "result": result_line,
                "trace_records": trace_count,
                "raw_records": raw_count,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "firmware_sha256": FIRMWARE_SHA256,
                "reset_banner_confirmed": True,
                "file": filename,
                "raw_present": raw_count > 0,
            }
            rows.append(row)
            save_summary(rows)

            print(result_line)
            print(f"TRACE records: {trace_count}")
            print(f"RAW records: {raw_count}")
            print(f"SHA-256: {row['sha256']}")
            print(f"Saved: {output_path}")

            if raw_count == 0:
                print("ERROR: Raw tensor data is missing. Capture stopped.")
                raise SystemExit(4)

    print(f"\nRAW TRACE CAPTURES: {sum(r['raw_present'] for r in rows)}/{len(rows)}")

if __name__ == "__main__":
    main()
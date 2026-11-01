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

def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    results = []

    with serial.Serial("COM5", 115200, timeout=0.2, write_timeout=5) as ser:
        ser.dtr = False
        ser.rts = False
        reader = SerialReader(ser)

        for image in range(9, 11):
            reader.buffer.clear()
            ser.reset_input_buffer()

            input(
                f"\nImage {image}: Press Enter to arm serial capture. "
                "Do not press BOOT."
            )
            print("Capture armed. Press and release the EN button now.")
            print("Waiting for fresh application startup and CLI prompt...")

            try:
                # The input buffer was cleared before the manual reset.
                # A newly received CLI prompt therefore confirms application startup.
                boot_output = reader.read_until(b"esp>", 60)
            except TimeoutError as error:
                failure_path = EVIDENCE / (
                    f"optimized_r2_image_{image}_boot_failure_2026-10-27.txt"
                )
                failure_path.write_bytes(bytes(reader.buffer))
                print(f"ERROR: Application prompt not detected: {error}")
                print(f"Partial boot output saved: {failure_path}")
                print("Capture stopped. The image inference was not issued.")
                break

            print("Fresh CLI prompt detected.")

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
                    f"optimized_r2_image_{image}_partial_2026-10-27.txt"
                )
                partial_path.write_bytes(
                    boot_output + bytes(reader.buffer)
                )
                print(f"ERROR: Inference capture failed: {error}")
                print(f"Partial output saved: {partial_path}")
                break

            data = (
                f"COMMAND={command}\r\n"
                f"FIRMWARE_SHA256={FIRMWARE_SHA256}\r\n"
                "FRESH_APPLICATION_PROMPT_CONFIRMED=1\r\n"
            ).encode("ascii") + boot_output + result_output + prompt_output

            lines = data.decode("ascii", errors="replace").splitlines()
            result_line = next(
                (
                    line for line in lines
                    if line.startswith(f"IMAGE_RESULT,image={image},")
                ),
                "MISSING"
            )
            trace_count = sum(
                line.startswith("RQ1_TRACE,") for line in lines
            )
            raw_count = sum(
                line.startswith("RQ1_RAW,") for line in lines
            )

            filename = (
                f"optimized_r2_tensor_trace_image_{image}_"
                "freshboot_retry2_2026-10-27.txt"
            )
            output_path = EVIDENCE / filename
            output_path.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()

            row = {
                "image": image,
                "result": result_line,
                "trace_records": trace_count,
                "raw_records": raw_count,
                "bytes": len(data),
                "sha256": digest,
                "firmware_sha256": FIRMWARE_SHA256,
                "fresh_prompt_confirmed": True,
                "file": filename,
                "raw_present": raw_count > 0,
            }
            results.append(row)

            print(result_line)
            print(f"TRACE records: {trace_count}")
            print(f"RAW records: {raw_count}")
            print(f"SHA-256: {digest}")
            print(f"Saved: {output_path}")

            if raw_count == 0:
                print("ERROR: Raw tensor data is missing; stopping.")
                break

    if results:
        summary = EVIDENCE / (
            "optimized_r2_raw_trace_summary_images9_to10_retry2_2026-10-27.csv"
        )
        with summary.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)

        print(
            f"\nRAW TRACE CAPTURES: "
            f"{sum(row['raw_present'] for row in results)}/{len(results)}"
        )
        print(f"Summary CSV: {summary}")

if __name__ == "__main__":
    main()
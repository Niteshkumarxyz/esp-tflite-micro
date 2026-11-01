import csv
import hashlib
import re
import time
from pathlib import Path
import serial

EVIDENCE = Path(r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro\examples\person_detection\chapter_evidence")
PORT = "COM5"
BAUD = 115200
FIRMWARE_SHA256 = "F70EA1D4FF93289BB32BB3C89B20A70C3C232264B1B9B3793BEC43EB94D9F4BE"

class SerialReader:
    def __init__(self, ser):
        self.ser = ser
        self.buffer = bytearray()

    def until(self, marker, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pos = self.buffer.find(marker)
            if pos >= 0:
                end = pos + len(marker)
                result = bytes(self.buffer[:end])
                del self.buffer[:end]
                return result

            chunk = self.ser.read(2048)
            if chunk:
                self.buffer.extend(chunk)

        raise TimeoutError(
            f"Timeout waiting for {marker!r}; "
            f"buffer currently has {len(self.buffer)} bytes"
        )

def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    summary = []

    print(f"Opening {PORT} at {BAUD} baud...")
    with serial.Serial(PORT, BAUD, timeout=0.2, write_timeout=3) as ser:
        ser.dtr = False
        ser.rts = False
        reader = SerialReader(ser)

        # Re-prompt the CLI without issuing an inference command.
        ser.write(b"\r\n")
        reader.until(b"esp>", timeout=45)
        print("ESP32 CLI prompt detected.")

        for image in range(1, 11):
            filename = f"optimized_r2_tensor_trace_image_{image}_2026-10-27.txt"
            outfile = EVIDENCE / filename
            command = f"detect_image {image}"

            print(f"\nCapturing image {image}/10...")
            ser.write((command + "\r\n").encode("ascii"))

            first = b""
            tail = b""
            try:
                first = reader.until(
                    f"IMAGE_RESULT,image={image},".encode("ascii"),
                    timeout=180
                )
                tail = reader.until(b"esp>", timeout=20)
            except Exception as exc:
                partial = (
                    f"COMMAND={command}\n"
                    f"FIRMWARE_SHA256={FIRMWARE_SHA256}\n"
                ).encode("ascii") + first + tail + bytes(reader.buffer)
                outfile.write_bytes(partial)
                print(f"CAPTURE FAILED for image {image}: {exc}")
                print(f"Partial output saved: {outfile}")
                raise

            captured = (
                f"COMMAND={command}\r\n"
                f"FIRMWARE_SHA256={FIRMWARE_SHA256}\r\n"
            ).encode("ascii") + first + tail

            outfile.write_bytes(captured)
            decoded = captured.decode("ascii", errors="replace")

            result_match = re.search(
                rf"IMAGE_RESULT,image={image},[^\r\n]*", decoded
            )
            result_line = result_match.group(0) if result_match else "MISSING"

            trace_count = sum(
                line.startswith("RQ1_TRACE,") for line in decoded.splitlines()
            )
            raw_count = sum(
                line.startswith("RQ1_RAW,") for line in decoded.splitlines()
            )
            digest = hashlib.sha256(captured).hexdigest()

            row = {
                "image": image,
                "command": command,
                "log_file": filename,
                "result_line": result_line,
                "trace_records": trace_count,
                "raw_records": raw_count,
                "bytes": len(captured),
                "sha256": digest,
                "complete_result": result_line != "MISSING",
                "firmware_sha256": FIRMWARE_SHA256,
            }
            summary.append(row)

            print(f"Result: {result_line}")
            print(f"TRACE records: {trace_count}; RAW records: {raw_count}")
            print(f"Bytes: {len(captured)}")
            print(f"SHA256: {digest}")
            print(f"Saved: {outfile}")

    csv_path = EVIDENCE / "optimized_r2_tensor_trace_summary_2026-10-27.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        writer.writeheader()
        writer.writerows(summary)

    complete = sum(row["complete_result"] for row in summary)
    print(f"\nCAPTURED RESULTS: {complete}/10")
    print(f"SUMMARY CSV: {csv_path}")
    if complete != 10:
        raise SystemExit("Not all images completed; inspect the saved logs.")

if __name__ == "__main__":
    main()
import csv
import hashlib
import time
from pathlib import Path
import serial

E = Path(r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro\examples\person_detection\chapter_evidence")
FW = "F70EA1D4FF93289BB32BB3C89B20A70C3C232264B1B9B3793BEC43EB94D9F4BE"

class Reader:
    def __init__(self, ser):
        self.ser = ser
        self.buf = bytearray()

    def until(self, marker, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            pos = self.buf.find(marker)
            if pos >= 0:
                end = pos + len(marker)
                result = bytes(self.buf[:end])
                del self.buf[:end]
                return result
            chunk = self.ser.read(4096)
            if chunk:
                self.buf.extend(chunk)
        raise TimeoutError(f"Timeout waiting for {marker!r}")

def main():
    E.mkdir(parents=True, exist_ok=True)
    rows = []

    with serial.Serial("COM5", 115200, timeout=0.2, write_timeout=5) as ser:
        ser.dtr = False
        ser.rts = False
        reader = Reader(ser)

        for image in range(3, 11):
            # Clear prior serial bytes so an old prompt cannot prove a reset.
            reader.buf.clear()
            ser.reset_input_buffer()

            input(
                f"\nIMAGE {image}: EN button press and release karo; "
                "BOOT button mat dabao. Boot hone ke baad Enter dabao: "
            )

            # Require an actual reboot banner, not just a possibly stale prompt.
            try:
                boot_start = reader.until(b"rst:", 25)
                boot_rest = reader.until(b"esp>", 60)
            except TimeoutError as exc:
                print(f"RESET/BOOT NOT CONFIRMED: {exc}")
                print("Capture stopped. Do not continue without checking the board.")
                raise SystemExit(2)

            boot = boot_start + boot_rest
            print("Reboot confirmed; CLI prompt detected.")

            command = f"detect_image {image}"
            print(f"Running {command}...")
            ser.write((command + "\r\n").encode("ascii"))

            try:
                result_part = reader.until(
                    f"IMAGE_RESULT,image={image},".encode("ascii"), 180
                )
                prompt_part = reader.until(b"esp>", 30)
            except TimeoutError as exc:
                print(f"CAPTURE FAILED for image {image}: {exc}")
                raise SystemExit(3)

            data = (
                f"COMMAND={command}\r\n"
                f"FIRMWARE_SHA256={FW}\r\n"
                f"RESET_CONFIRMED=1\r\n"
            ).encode("ascii") + boot + result_part + prompt_part

            path = E / f"optimized_r2_tensor_trace_image_{image}_retry_2026-10-27.txt"
            path.write_bytes(data)
            text = data.decode("ascii", errors="replace")
            lines = text.splitlines()

            result = next(
                (line for line in lines
                 if line.startswith(f"IMAGE_RESULT,image={image},")),
                "MISSING"
            )
            trace_count = sum(line.startswith("RQ1_TRACE,") for line in lines)
            raw_count = sum(line.startswith("RQ1_RAW,") for line in lines)
            digest = hashlib.sha256(data).hexdigest()

            row = {
                "image": image,
                "result": result,
                "trace_records": trace_count,
                "raw_records": raw_count,
                "bytes": len(data),
                "sha256": digest,
                "firmware_sha256": FW,
                "reset_confirmed": True,
                "file": path.name,
                "raw_present": raw_count > 0,
            }
            rows.append(row)

            print(result)
            print(f"TRACE={trace_count}, RAW={raw_count}, bytes={len(data)}")
            print(f"SHA256={digest}")
            print(f"Saved: {path}")

            if raw_count == 0:
                print("No raw data after verified reboot; stopping for diagnosis.")
                break

    if rows:
        summary = E / "optimized_r2_verified_reset_trace_summary_2026-10-27.csv"
        with summary.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        print(f"\nRAW TRACES: {sum(r['raw_present'] for r in rows)}/{len(rows)}")
        print(f"SUMMARY CSV: {summary}")

if __name__ == "__main__":
    main()
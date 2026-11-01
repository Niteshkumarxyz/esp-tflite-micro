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
                out = bytes(self.buf[:end])
                del self.buf[:end]
                return out
            chunk = self.ser.read(4096)
            if chunk:
                self.buf.extend(chunk)
        raise TimeoutError(f"Timeout waiting for {marker!r}")

def main():
    rows = []
    E.mkdir(parents=True, exist_ok=True)

    with serial.Serial("COM5", 115200, timeout=0.2, write_timeout=5) as ser:
        ser.dtr = False
        ser.rts = False
        reader = Reader(ser)

        ser.write(b"\r\n")
        reader.until(b"esp>", 30)
        print("CLI prompt detected; capturing image 4 on current boot.")

        for image in range(4, 11):
            if image > 4:
                reader.buf.clear()
                ser.reset_input_buffer()
                input(
                    f"\nImage {image}: EN button press and release karo, "
                    "BOOT mat dabao. Boot ke baad Enter dabao: "
                )
                boot = reader.until(b"rst:", 25)
                prompt = reader.until(b"esp>", 60)
                print("Reset and normal CLI startup confirmed.")

            command = f"detect_image {image}"
            print(f"\nRunning {command}...")
            ser.write((command + "\r\n").encode("ascii"))

            result_part = reader.until(
                f"IMAGE_RESULT,image={image},".encode("ascii"), 180
            )
            tail = reader.until(b"esp>", 30)

            prefix = (
                f"COMMAND={command}\r\n"
                f"FIRMWARE_SHA256={FW}\r\n"
                f"RESET_CONFIRMED={'current-boot' if image == 4 else 'yes'}\r\n"
            ).encode("ascii")
            data = prefix + result_part + tail

            filename = f"optimized_r2_tensor_trace_image_{image}_retry_2026-10-27.txt"
            path = E / filename
            path.write_bytes(data)

            lines = data.decode("ascii", errors="replace").splitlines()
            result = next(
                (x for x in lines if x.startswith(f"IMAGE_RESULT,image={image},")),
                "MISSING"
            )
            traces = sum(x.startswith("RQ1_TRACE,") for x in lines)
            raws = sum(x.startswith("RQ1_RAW,") for x in lines)
            digest = hashlib.sha256(data).hexdigest()

            row = {
                "image": image,
                "result": result,
                "trace_records": traces,
                "raw_records": raws,
                "bytes": len(data),
                "sha256": digest,
                "firmware_sha256": FW,
                "file": filename,
                "raw_present": raws > 0,
            }
            rows.append(row)

            print(result)
            print(f"TRACE={traces}; RAW={raws}; bytes={len(data)}")
            print(f"SHA256={digest}")
            print(f"Saved: {path}")

            if raws == 0:
                print("No raw tensor data. Stopping to avoid invalid evidence.")
                break

    if rows:
        summary = E / "optimized_r2_raw_trace_summary_images4_to10_2026-10-27.csv"
        with summary.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

        print(f"\nRAW TRACES: {sum(x['raw_present'] for x in rows)}/{len(rows)}")
        print(f"SUMMARY CSV: {summary}")

if __name__ == "__main__":
    main()
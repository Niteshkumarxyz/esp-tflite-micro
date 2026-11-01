import csv
import hashlib
import time
from pathlib import Path
import serial

E = Path(r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro\examples\person_detection\chapter_evidence")
PORT = "COM5"
BAUD = 115200
FW = "F70EA1D4FF93289BB32BB3C89B20A70C3C232264B1B9B3793BEC43EB94D9F4BE"

class Reader:
    def __init__(self, ser):
        self.ser = ser
        self.buf = bytearray()

    def until(self, marker, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            pos = self.buf.find(marker)
            if pos >= 0:
                stop = pos + len(marker)
                out = bytes(self.buf[:stop])
                del self.buf[:stop]
                return out
            chunk = self.ser.read(4096)
            if chunk:
                self.buf.extend(chunk)
        raise TimeoutError(f"Timed out waiting for {marker!r}")

def main():
    rows = []
    E.mkdir(parents=True, exist_ok=True)

    # Do not pulse DTR/RTS or trigger an automatic reset.
    with serial.Serial(PORT, BAUD, timeout=0.2, write_timeout=5) as ser:
        ser.dtr = False
        ser.rts = False
        reader = Reader(ser)

        ser.write(b"\r\n")
        reader.until(b"esp>", 30)
        print("Current CLI prompt found. Image 2 will run first.")

        for image in range(2, 11):
            if image > 2:
                input(
                    f"\nImage {image-1} saved. Press and release the board's "
                    f"EN button (do NOT press BOOT), wait for boot, then "
                    f"press Enter here to capture image {image}: "
                )
                reader.until(b"esp>", 60)
                print("Fresh CLI prompt detected.")

            print(f"\nRunning detect_image {image}...")
            ser.write(f"detect_image {image}\r\n".encode("ascii"))

            first = reader.until(
                f"IMAGE_RESULT,image={image},".encode("ascii"), 180
            )
            tail = reader.until(b"esp>", 30)
            data = (
                f"COMMAND=detect_image {image}\r\n"
                f"FIRMWARE_SHA256={FW}\r\n"
            ).encode("ascii") + first + tail

            path = E / f"optimized_r2_tensor_trace_image_{image}_2026-10-27.txt"
            path.write_bytes(data)
            text = data.decode("ascii", errors="replace")
            lines = text.splitlines()

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
                "file": path.name,
                "raw_present": raws > 0,
            }
            rows.append(row)

            print(result)
            print(f"TRACE={traces}, RAW={raws}, bytes={len(data)}")
            print(f"SHA256={digest}")
            print(f"Saved: {path}")

            if raws == 0:
                raise SystemExit(
                    f"Image {image} has no raw data. Stopped; inspect the log."
                )

    summary = E / "optimized_r2_raw_trace_summary_images_2_to_10_2026-10-27.csv"
    with summary.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nRAW TRACES CAPTURED: {sum(r['raw_present'] for r in rows)}/9")
    print(f"SUMMARY: {summary}")

if __name__ == "__main__":
    main()
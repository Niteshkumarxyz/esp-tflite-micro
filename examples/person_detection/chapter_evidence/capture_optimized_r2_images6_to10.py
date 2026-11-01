import csv, hashlib, time
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
            data = self.ser.read(4096)
            if data:
                self.buf.extend(data)
        raise TimeoutError(f"Timeout waiting for {marker!r}")

def main():
    rows = []
    with serial.Serial("COM5", 115200, timeout=0.2, write_timeout=5) as ser:
        ser.dtr = False
        ser.rts = False
        reader = Reader(ser)

        for image in range(6, 11):
            reader.buf.clear()
            ser.reset_input_buffer()

            input(
                f"\nImage {image}: EN press/release karo, BOOT mat dabao; "
                "boot hone ke baad Enter dabao: "
            )

            try:
                boot = reader.until(b"esp>", 60)
            except TimeoutError:
                print("Fresh CLI prompt nahi mila. Capture stopped; do not flash.")
                raise SystemExit(2)

            print("CLI prompt detected. Running inference.")
            ser.write(f"detect_image {image}\r\n".encode("ascii"))

            try:
                capture = reader.until(
                    f"IMAGE_RESULT,image={image},".encode("ascii"), 180
                )
                tail = reader.until(b"esp>", 30)
            except TimeoutError as exc:
                print(f"Image {image} incomplete: {exc}")
                raise SystemExit(3)

            data = (
                f"COMMAND=detect_image {image}\r\n"
                f"FIRMWARE_SHA256={FW}\r\n"
                f"BOOT_PROMPT_CONFIRMED=1\r\n"
            ).encode("ascii") + boot + capture + tail

            text = data.decode("ascii", errors="replace")
            lines = text.splitlines()
            raw = sum(x.startswith("RQ1_RAW,") for x in lines)
            trace = sum(x.startswith("RQ1_TRACE,") for x in lines)
            result = next(
                (x for x in lines if x.startswith(f"IMAGE_RESULT,image={image},")),
                "MISSING"
            )

            filename = f"optimized_r2_tensor_trace_image_{image}_resetverified_2026-10-27.txt"
            path = E / filename
            path.write_bytes(data)
            digest = hashlib.sha256(data).hexdigest()

            row = {
                "image": image, "result": result,
                "trace_records": trace, "raw_records": raw,
                "bytes": len(data), "sha256": digest,
                "firmware_sha256": FW, "file": filename,
                "raw_present": raw > 0,
            }
            rows.append(row)

            print(result)
            print(f"TRACE={trace}; RAW={raw}; bytes={len(data)}")
            print(f"SHA256={digest}")
            print(f"Saved: {path}")

            if raw == 0:
                print("Raw tensor data missing. Stopping for diagnosis.")
                break

    if rows:
        summary = E / "optimized_r2_raw_trace_summary_images6_to10_2026-10-27.csv"
        with summary.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"\nRAW TRACES: {sum(r['raw_present'] for r in rows)}/{len(rows)}")
        print(f"SUMMARY: {summary}")

if __name__ == "__main__":
    main()
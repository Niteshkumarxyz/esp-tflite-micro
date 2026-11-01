import csv
import hashlib
import re
import time
from pathlib import Path
import serial

PROJECT = Path(r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro\examples\person_detection")
EVIDENCE = PROJECT / "chapter_evidence"
BUILD = PROJECT / "build_rq1_skip_nudge_wdt30_20261027"
FIRMWARE = BUILD / "person_detection.bin"
ELF = BUILD / "person_detection.elf"
SDKCONFIG = PROJECT / "sdkconfig.rq1_skip_nudge_2026-10-27"
GENERATED_CONFIG = BUILD / "config" / "sdkconfig.h"
PORT, BAUD = "COM5", 115200
EXPECTED_TRACE, EXPECTED_RAW = 31, 3625

def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

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
            chunk = self.ser.read(4096)
            if chunk:
                self.buffer.extend(chunk)
        raise TimeoutError(f"Timeout waiting for {marker!r}; buffered={len(self.buffer)} bytes")

def open_serial():
    ser = serial.Serial()
    ser.port = PORT
    ser.baudrate = BAUD
    ser.timeout = 0.2
    ser.write_timeout = 5
    ser.dtr = False
    ser.rts = False
    ser.open()
    time.sleep(0.25)
    return ser

def main():
    for p in (FIRMWARE, ELF, SDKCONFIG, GENERATED_CONFIG):
        if not p.is_file():
            raise FileNotFoundError(p)

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    fw_sha = sha256_file(FIRMWARE)
    elf_sha = sha256_file(ELF)
    cfg_sha = sha256_file(SDKCONFIG)
    gen_cfg_sha = sha256_file(GENERATED_CONFIG)
    run_id = time.strftime("%Y%m%d_%H%M%S")
    summary_path = EVIDENCE / f"r2_skip_nudge_raw_images2to11_summary_{run_id}.csv"
    fields = [
        "image", "result_line", "trace_records", "raw_records", "bytes",
        "sha256", "log_file", "prompt_seen", "raw_trace_complete",
        "firmware_bin_sha256", "firmware_elf_sha256",
        "sdkconfig_sha256", "generated_config_sha256"
    ]
    rows = []

    def save_summary():
        with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)

    print(f"Run ID: {run_id}")
    print(f"Firmware BIN SHA256: {fw_sha}")
    print(f"Firmware ELF SHA256: {elf_sha}")
    print("Images 2-11. Image 2 will use the current fresh boot; images 3-11 require manual EN resets.")
    print("Close idf.py monitor first.")

    for image in range(2, 12):
        outfile = EVIDENCE / f"r2_skip_nudge_raw_reopen_{run_id}_image_{image:02d}.txt"
        if image >= 3:
            input(
                f"\nImage {image}: with COM5 closed, press and release EN once, "
                "then press Enter here. Do not press BOOT."
            )

        ser = None
        try:
            ser = open_serial()
            reader = SerialReader(ser)
            # The console might have printed its boot prompt while COM5 was closed.
            # Sending a newline requests a fresh CLI prompt without running inference.
            ser.write(b"\r\n")
            sync = reader.until(b"esp>", timeout=60)

            command = f"detect_image {image}"
            print(f"\nConsole synchronized; capturing image {image}: {command}")
            ser.write((command + "\r\n").encode("ascii"))
            result_bytes = reader.until(
                f"IMAGE_RESULT,image={image},".encode("ascii"), timeout=180
            )
            prompt_bytes = reader.until(b"esp>", timeout=40)
            captured = (
                f"RUN_ID={run_id}\r\nIMAGE_NUMBER={image}\r\n"
                f"COMMAND={command}\r\n"
                f"FIRMWARE_BIN_SHA256={fw_sha}\r\n"
                f"FIRMWARE_ELF_SHA256={elf_sha}\r\n"
                f"SDKCONFIG_SHA256={cfg_sha}\r\n"
                f"GENERATED_SDKCONFIG_SHA256={gen_cfg_sha}\r\n"
            ).encode("ascii") + sync + result_bytes + prompt_bytes

            outfile.write_bytes(captured)
            decoded = captured.decode("ascii", errors="replace")
            lines = decoded.splitlines()
            result_match = re.search(
                rf"IMAGE_RESULT,image={image},[^\r\n]*", decoded
            )
            result_line = result_match.group(0) if result_match else "MISSING"
            trace_count = sum(x.startswith("RQ1_TRACE,") for x in lines)
            raw_lines = [x for x in lines if x.startswith("RQ1_RAW,")]
            raw_count = len(raw_lines)
            first_run_raw = all("run=1," in x for x in raw_lines)
            complete = (
                result_line != "MISSING"
                and trace_count == EXPECTED_TRACE
                and raw_count == EXPECTED_RAW
                and first_run_raw
            )

            row = {
                "image": image,
                "result_line": result_line,
                "trace_records": trace_count,
                "raw_records": raw_count,
                "bytes": len(captured),
                "sha256": hashlib.sha256(captured).hexdigest(),
                "log_file": outfile.name,
                "prompt_seen": True,
                "raw_trace_complete": complete,
                "firmware_bin_sha256": fw_sha,
                "firmware_elf_sha256": elf_sha,
                "sdkconfig_sha256": cfg_sha,
                "generated_config_sha256": gen_cfg_sha,
            }
            rows.append(row)
            save_summary()
            print(result_line)
            print(f"TRACE={trace_count}; RAW={raw_count}; complete={complete}")
            print(f"Bytes={len(captured)}; SHA256={row['sha256']}")
            print(f"Saved: {outfile}")
            print(f"Summary: {summary_path}")

            if not complete:
                raise RuntimeError(
                    f"Image {image} did not pass trace-count validation; log preserved."
                )
        except Exception as exc:
            if ser is not None and ser.is_open:
                ser.close()
            if outfile.exists():
                print(f"Partial/final log preserved: {outfile}")
            raise RuntimeError(f"Stopping at image {image}; do not restart full capture yet.") from exc
        finally:
            if ser is not None and ser.is_open:
                ser.close()

    complete_count = sum(r["raw_trace_complete"] for r in rows)
    print(f"\nRAW-COMPLETE IMAGES: {complete_count}/10")
    print(f"SUMMARY CSV: {summary_path}")

if __name__ == "__main__":
    main()

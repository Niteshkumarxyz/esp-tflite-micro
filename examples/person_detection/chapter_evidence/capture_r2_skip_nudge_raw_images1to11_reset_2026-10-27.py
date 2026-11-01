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

PORT = "COM5"
BAUD = 115200
EXPECTED_TRACE_RECORDS = 31
EXPECTED_RAW_RECORDS = 3625


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
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

        raise TimeoutError(
            f"Timeout waiting for {marker!r}; buffered={len(self.buffer)} bytes"
        )


def main():
    for path in (FIRMWARE, ELF, SDKCONFIG, GENERATED_CONFIG):
        if not path.is_file():
            raise FileNotFoundError(f"Required artifact missing: {path}")

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    firmware_sha = sha256_file(FIRMWARE)
    elf_sha = sha256_file(ELF)
    sdkconfig_sha = sha256_file(SDKCONFIG)
    generated_config_sha = sha256_file(GENERATED_CONFIG)
    run_id = time.strftime("%Y%m%d_%H%M%S")

    summary_path = EVIDENCE / f"r2_skip_nudge_raw_images1to11_summary_{run_id}.csv"
    fields = [
        "image", "result_line", "trace_records", "raw_records",
        "bytes", "sha256", "log_file", "prompt_seen",
        "raw_trace_complete", "firmware_bin_sha256", "firmware_elf_sha256",
        "sdkconfig_sha256", "generated_config_sha256"
    ]
    summary = []

    def save_summary():
        with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(summary)

    print(f"Run ID: {run_id}")
    print(f"Firmware BIN SHA256: {firmware_sha}")
    print(f"Firmware ELF SHA256: {elf_sha}")
    print(f"Experimental sdkconfig SHA256: {sdkconfig_sha}")
    print(f"Generated sdkconfig.h SHA256: {generated_config_sha}")
    print("Images 1-11 will be captured. Image 0 already has a complete raw trace.")
    print("Close idf.py monitor before continuing.")
    input("Press Enter to open COM5 and begin...")

    with serial.Serial(PORT, BAUD, timeout=0.2, write_timeout=5) as ser:
        ser.dtr = False
        ser.rts = False
        reader = SerialReader(ser)

        for image in range(1, 12):
            outfile = EVIDENCE / f"r2_skip_nudge_raw_{run_id}_image_{image:02d}.txt"
            command = f"detect_image {image}"
            result_marker = f"IMAGE_RESULT,image={image},".encode("ascii")

            reader.buffer.clear()
            ser.reset_input_buffer()
            input(
                f"\nImage {image}: press and release the ESP32 EN button "
                "once, then press Enter here. Do not press BOOT."
            )

            try:
                boot_output = reader.until(b"esp>", timeout=60)
            except Exception as exc:
                partial = (
                    f"RUN_ID={run_id}\nIMAGE={image}\n"
                    f"FIRMWARE_BIN_SHA256={firmware_sha}\n"
                    f"BOOT_SYNC_ERROR={exc}\n"
                ).encode("ascii", errors="replace") + bytes(reader.buffer)
                outfile.write_bytes(partial)
                raise RuntimeError(
                    f"Image {image}: boot prompt not detected; partial saved to {outfile}"
                ) from exc

            print(f"Fresh CLI prompt received for image {image}.")
            metadata = (
                f"RUN_ID={run_id}\r\n"
                f"COMMAND={command}\r\n"
                f"IMAGE_NUMBER={image}\r\n"
                f"TRACE_MODE=ESP-NN optimized with CONFIG_NN_SKIP_NUDGE=y\r\n"
                f"FIRMWARE_BIN_SHA256={firmware_sha}\r\n"
                f"FIRMWARE_ELF_SHA256={elf_sha}\r\n"
                f"SDKCONFIG_SHA256={sdkconfig_sha}\r\n"
                f"GENERATED_SDKCONFIG_SHA256={generated_config_sha}\r\n"
            ).encode("ascii")

            ser.write((command + "\r\n").encode("ascii"))

            try:
                result_output = reader.until(result_marker, timeout=180)
                prompt_output = reader.until(b"esp>", timeout=30)
            except Exception as exc:
                partial = (
                    metadata + boot_output + bytes(reader.buffer)
                    + b"\r\nCAPTURE_ERROR="
                    + str(exc).encode("ascii", errors="replace")
                )
                outfile.write_bytes(partial)
                raise RuntimeError(
                    f"Image {image}: result/prompt timeout; partial saved to {outfile}"
                ) from exc

            captured = metadata + boot_output + result_output + prompt_output
            outfile.write_bytes(captured)
            decoded = captured.decode("ascii", errors="replace")
            lines = decoded.splitlines()

            match = re.search(
                rf"IMAGE_RESULT,image={image},[^\r\n]*", decoded
            )
            result_line = match.group(0) if match else "MISSING"
            trace_count = sum(line.startswith("RQ1_TRACE,") for line in lines)
            raw_lines = [line for line in lines if line.startswith("RQ1_RAW,")]
            raw_count = len(raw_lines)
            run_one_raw = all("run=1," in line for line in raw_lines)
            complete = (
                result_line != "MISSING"
                and trace_count == EXPECTED_TRACE_RECORDS
                and raw_count == EXPECTED_RAW_RECORDS
                and run_one_raw
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
                "firmware_bin_sha256": firmware_sha,
                "firmware_elf_sha256": elf_sha,
                "sdkconfig_sha256": sdkconfig_sha,
                "generated_config_sha256": generated_config_sha,
            }
            summary.append(row)
            save_summary()

            print(result_line)
            print(f"TRACE records: {trace_count}; RAW records: {raw_count}")
            print(f"Raw trace complete: {complete}")
            print(f"Bytes: {len(captured)}; SHA256: {row['sha256']}")
            print(f"Saved: {outfile}")
            print(f"Summary updated: {summary_path}")

            if not complete:
                raise RuntimeError(
                    f"Image {image} did not meet expected trace counts. "
                    "The log is preserved; stopping for inspection."
                )

    completed = sum(row["raw_trace_complete"] for row in summary)
    print(f"\nRECAPTURED RAW TRACES: {completed}/11")
    print(f"SUMMARY CSV: {summary_path}")
    if completed != 11:
        raise SystemExit("Not all images 1-11 have complete raw traces.")


if __name__ == "__main__":
    main()

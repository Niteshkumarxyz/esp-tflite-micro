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
IMAGE_COUNT = 12


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class SerialReader:
    def __init__(self, connection):
        self.connection = connection
        self.buffer = bytearray()

    def until(self, marker, timeout):
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

        raise TimeoutError(
            f"Timeout waiting for {marker!r}; "
            f"{len(self.buffer)} bytes remain buffered"
        )


def main():
    required = [FIRMWARE, ELF, SDKCONFIG, GENERATED_CONFIG]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing required artifact(s): " + "; ".join(missing))

    EVIDENCE.mkdir(parents=True, exist_ok=True)

    firmware_sha = sha256_file(FIRMWARE)
    elf_sha = sha256_file(ELF)
    config_sha = sha256_file(SDKCONFIG)
    generated_config_sha = sha256_file(GENERATED_CONFIG)

    run_id = time.strftime("%Y%m%d_%H%M%S")
    summary_path = EVIDENCE / f"r2_skip_nudge_12_image_summary_{run_id}.csv"
    sync_path = EVIDENCE / f"r2_skip_nudge_console_sync_{run_id}.txt"

    fieldnames = [
        "image", "command", "log_file", "result_line",
        "trace_records", "raw_records", "bytes", "sha256",
        "firmware_bin_sha256", "firmware_elf_sha256",
        "sdkconfig_sha256", "generated_sdkconfig_sha256",
        "prompt_seen", "complete_result", "complete_trace"
    ]
    summary = []

    def save_summary():
        with summary_path.open("w", newline="", encoding="utf-8-sig") as stream:
            writer = csv.DictWriter(stream, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(summary)

    print(f"Run ID: {run_id}")
    print(f"Firmware BIN SHA256: {firmware_sha}")
    print(f"Firmware ELF SHA256: {elf_sha}")
    print(f"Experimental sdkconfig SHA256: {config_sha}")
    print(f"Generated sdkconfig.h SHA256: {generated_config_sha}")
    print(f"Opening {PORT} at {BAUD} baud. Close idf.py monitor first.")

    with serial.Serial(PORT, BAUD, timeout=0.2, write_timeout=5) as ser:
        ser.dtr = False
        ser.rts = False
        time.sleep(0.3)
        reader = SerialReader(ser)

        ser.write(b"\r\n")
        try:
            sync = reader.until(b"esp>", timeout=45)
        except TimeoutError:
            sync_path.write_bytes(bytes(reader.buffer))
            raise RuntimeError(
                f"CLI prompt not detected. Partial sync saved to {sync_path}"
            )

        sync_path.write_bytes(sync)
        print(f"CLI prompt detected. Console sync saved: {sync_path}")

        for image in range(IMAGE_COUNT):
            command = f"detect_image {image}"
            marker = f"IMAGE_RESULT,image={image},".encode("ascii")
            filename = f"r2_skip_nudge_trace_{run_id}_image_{image:02d}.txt"
            outfile = EVIDENCE / filename

            metadata = (
                f"RUN_ID={run_id}\r\n"
                f"COMMAND={command}\r\n"
                f"IMAGE_NUMBER={image}\r\n"
                f"RUNTIME=ESP-NN optimized with skip-nudge enabled\r\n"
                f"FIRMWARE_BIN_SHA256={firmware_sha}\r\n"
                f"FIRMWARE_ELF_SHA256={elf_sha}\r\n"
                f"SDKCONFIG_SHA256={config_sha}\r\n"
                f"GENERATED_SDKCONFIG_SHA256={generated_config_sha}\r\n"
            ).encode("ascii")

            print(f"\nCapturing image {image}/{IMAGE_COUNT - 1}: {command}")
            ser.write((command + "\r\n").encode("ascii"))

            try:
                result_output = reader.until(marker, timeout=180)
            except Exception as exc:
                partial = metadata + b"\r\nCAPTURE_ERROR=" + str(exc).encode(
                    "ascii", errors="replace"
                ) + b"\r\n" + bytes(reader.buffer)
                outfile.write_bytes(partial)
                print(f"Partial log saved: {outfile}")
                raise RuntimeError(
                    f"Image {image} result marker was not detected; stopping safely."
                ) from exc

            prompt_seen = False
            tail = b""
            try:
                tail = reader.until(b"esp>", timeout=60)
                prompt_seen = True
            except TimeoutError:
                tail = bytes(reader.buffer)
                reader.buffer.clear()
                print("Prompt not seen after result; attempting newline resynchronization.")
                ser.write(b"\r\n")
                try:
                    recovered = reader.until(b"esp>", timeout=30)
                    tail += b"\r\nPROMPT_RESYNCHRONIZED\r\n" + recovered
                    prompt_seen = True
                except TimeoutError as exc:
                    tail += (
                        b"\r\nPROMPT_RECOVERY_FAILED="
                        + str(exc).encode("ascii", errors="replace")
                        + b"\r\n"
                        + bytes(reader.buffer)
                    )
                    reader.buffer.clear()

            captured = metadata + result_output + tail
            outfile.write_bytes(captured)
            decoded = captured.decode("ascii", errors="replace")
            lines = decoded.splitlines()

            result_match = re.search(
                rf"IMAGE_RESULT,image={image},[^\r\n]*", decoded
            )
            result_line = result_match.group(0) if result_match else "MISSING"
            trace_count = sum(line.startswith("RQ1_TRACE,") for line in lines)
            raw_count = sum(line.startswith("RQ1_RAW,") for line in lines)
            complete_result = result_line != "MISSING"
            complete_trace = complete_result and trace_count > 0 and raw_count > 0

            row = {
                "image": image,
                "command": command,
                "log_file": filename,
                "result_line": result_line,
                "trace_records": trace_count,
                "raw_records": raw_count,
                "bytes": len(captured),
                "sha256": hashlib.sha256(captured).hexdigest(),
                "firmware_bin_sha256": firmware_sha,
                "firmware_elf_sha256": elf_sha,
                "sdkconfig_sha256": config_sha,
                "generated_sdkconfig_sha256": generated_config_sha,
                "prompt_seen": prompt_seen,
                "complete_result": complete_result,
                "complete_trace": complete_trace,
            }
            summary.append(row)
            save_summary()

            print(f"Result: {result_line}")
            print(f"TRACE records: {trace_count}; RAW records: {raw_count}")
            print(f"Bytes: {len(captured)}; SHA256: {row['sha256']}")
            print(f"Prompt synchronized: {prompt_seen}")
            print(f"Saved: {outfile}")
            print(f"Updated summary: {summary_path}")

            if not prompt_seen:
                raise RuntimeError(
                    f"Image {image} captured but console could not be resynchronized. "
                    "Stopping before sending another image command."
                )

        complete = sum(row["complete_trace"] for row in summary)
        print(f"\nCOMPLETE IMAGE TRACES: {complete}/{IMAGE_COUNT}")
        print(f"SUMMARY CSV: {summary_path}")

        if complete != IMAGE_COUNT:
            raise SystemExit("Some images lack a result or trace records; inspect logs.")


if __name__ == "__main__":
    main()

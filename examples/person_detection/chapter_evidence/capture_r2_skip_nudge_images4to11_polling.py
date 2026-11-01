import csv
import hashlib
import msvcrt
import re
import time
import serial
from pathlib import Path
from datetime import datetime

PROJECT = Path(r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro\examples\person_detection")
EVIDENCE = PROJECT / "chapter_evidence"
BUILD = PROJECT / "build_rq1_skip_nudge_wdt30_20261027"
PORT, BAUD = "COM5", 115200
EXPECTED_TRACE, EXPECTED_RAW = 31, 3625

def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()

class PollingReader:
    """Single-threaded serial reader; keeps reading during keyboard waits."""
    def __init__(self, ser):
        self.ser = ser
        self.data = bytearray()

    def poll(self):
        chunk = self.ser.read(1024)
        if chunk:
            self.data.extend(chunk)

    def mark(self):
        return len(self.data)

    def wait_marker(self, marker, start, timeout):
        deadline = time.monotonic() + timeout
        last_report = time.monotonic()
        is_inference = marker.startswith(b"IMAGE_RESULT,")

        while time.monotonic() < deadline:
            pos = self.data.find(marker, start)
            if pos >= 0:
                return pos + len(marker)

            segment = bytes(self.data[start:])

            if is_inference:
                if b"rst:" in segment:
                    raise RuntimeError(
                        "ESP32 reset detected during inference; "
                        f"captured {len(segment)} bytes before reset."
                    )

                now = time.monotonic()
                if now - last_report >= 5:
                    decoded = segment.decode("utf-8", errors="replace")
                    lines = decoded.replace("\r\n", "\n").splitlines()
                    trace_count = sum(
                        line.startswith("RQ1_TRACE,") for line in lines
                    )
                    raw_count = sum(
                        line.startswith("RQ1_RAW,") for line in lines
                    )
                    print(
                        f"Inference progress: elapsed_s={int(now - (deadline - timeout))}, "
                        f"bytes={len(segment)}, TRACE={trace_count}, RAW={raw_count}",
                        flush=True,
                    )
                    last_report = now

            self.poll()

        pos = self.data.find(marker, start)
        if pos >= 0:
            return pos + len(marker)

        raise TimeoutError(
            f"Timeout waiting for {marker!r}; start={start}, "
            f"buffered={len(self.data)} bytes"
        )
    def wait_for_enter(self, prompt):
        print(prompt, flush=True)
        while True:
            # Crucially, serial is polled while waiting for keyboard input.
            self.poll()
            if msvcrt.kbhit():
                key = msvcrt.getwch()
                if key in ("\r", "\n"):
                    return
                if key == "\x03":
                    raise KeyboardInterrupt

    def snapshot(self, start, end=None):
        if end is None:
            end = len(self.data)
        return bytes(self.data[start:end])

def save_log(outfile, metadata, captured):
    header = (
        "\r\n".join(f"{k}={v}" for k, v in metadata.items())
        + "\r\n--- SERIAL CAPTURE ---\r\n"
    ).encode("utf-8")
    outfile.write_bytes(header + captured)

def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    fw = BUILD / "person_detection.bin"
    elf = BUILD / "person_detection.elf"
    cfg = PROJECT / "sdkconfig.rq1_skip_nudge_2026-10-27"
    gen_cfg = BUILD / "config" / "sdkconfig.h"

    for path in (fw, elf, cfg, gen_cfg):
        if not path.is_file():
            raise FileNotFoundError(f"Required evidence/build file missing: {path}")

    hashes = {
        "firmware_bin_sha256": sha256_file(fw),
        "firmware_elf_sha256": sha256_file(elf),
        "sdkconfig_sha256": sha256_file(cfg),
        "generated_config_sha256": sha256_file(gen_cfg),
    }
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = EVIDENCE / f"r2_skip_nudge_images4to11_polling_{run_id}.csv"
    fields = [
        "image", "result_line", "trace_records", "raw_records",
        "bytes", "sha256", "log_file", "fresh_reset_marker",
        "fresh_cli_prompt", "raw_trace_complete",
        "firmware_bin_sha256", "firmware_elf_sha256",
        "sdkconfig_sha256", "generated_config_sha256",
    ]
    rows = []

    def persist_csv():
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    print(f"Run ID: {run_id}")
    print(f"Firmware BIN SHA256: {hashes['firmware_bin_sha256']}")
    print(f"Firmware ELF SHA256: {hashes['firmware_elf_sha256']}")
    print(f"Images 4-11; polling reader; COM5 stays open during resets.")
    print("Close idf.py monitor and every other serial application first.")

    with serial.Serial(PORT, BAUD, timeout=0.1, write_timeout=5) as ser:
        ser.dtr = False
        ser.rts = False
        reader = PollingReader(ser)

        print("Waiting for initial ESP32 CLI prompt...", flush=True)
        reader.wait_marker(b"esp>", 0, 60)
        print("Initial CLI confirmed.")

        for image in range(4, 12):
            filename = f"r2_skip_nudge_raw_polling_{run_id}_image_{image:02d}.txt"
            outfile = EVIDENCE / filename

            time.sleep(0.3)
            start = reader.mark()

            try:
                reader.wait_for_enter(
                    f"\nImage {image}: press and release EN once, "
                    "then press Enter here. Do not press BOOT."
                )

                reset_end = reader.wait_marker(b"rst:", start, 20)
                prompt_end = reader.wait_marker(b"esp>", reset_end, 60)
                print(f"Fresh reset and CLI confirmed for image {image}.")

                ser.write(f"detect_image {image}\r\n".encode("ascii"))
                ser.flush()

                result_end = reader.wait_marker(
                    f"IMAGE_RESULT,image={image},".encode("ascii"),
                    prompt_end, 180
                )
                final_end = reader.wait_marker(b"esp>", result_end, 60)
                captured = reader.snapshot(start, final_end)
                decoded = captured.decode("utf-8", errors="replace")
                lines = decoded.replace("\r\n", "\n").splitlines()

                result_match = re.search(
                    rf"IMAGE_RESULT,image={image},[^\r\n]*", decoded
                )
                result_line = result_match.group(0) if result_match else "MISSING"
                trace_lines = [x for x in lines if x.startswith("RQ1_TRACE,")]
                raw_lines = [x for x in lines if x.startswith("RQ1_RAW,")]
                run_one = (
                    len(raw_lines) == EXPECTED_RAW
                    and all("run=1," in x for x in raw_lines)
                )
                complete = (
                    result_line != "MISSING"
                    and len(trace_lines) == EXPECTED_TRACE
                    and len(raw_lines) == EXPECTED_RAW
                    and run_one
                )

                meta = {
                    "RUN_ID": run_id,
                    "IMAGE_NUMBER": image,
                    "COMMAND": f"detect_image {image}",
                    **{k.upper(): v for k, v in hashes.items()},
                    "CAPTURE_SHA256": sha256_bytes(captured),
                    "TRACE_RECORDS": len(trace_lines),
                    "RAW_RECORDS": len(raw_lines),
                    "ALL_RAW_RUN_ONE": run_one,
                    "RAW_TRACE_COMPLETE": complete,
                }
                save_log(outfile, meta, captured)

                row = {
                    "image": image,
                    "result_line": result_line,
                    "trace_records": len(trace_lines),
                    "raw_records": len(raw_lines),
                    "bytes": len(captured),
                    "sha256": sha256_bytes(captured),
                    "log_file": filename,
                    "fresh_reset_marker": True,
                    "fresh_cli_prompt": True,
                    "raw_trace_complete": complete,
                    **hashes,
                }
                rows.append(row)
                persist_csv()

                print(
                    f"Image {image}: result={result_line}; "
                    f"TRACE={len(trace_lines)}/{EXPECTED_TRACE}; "
                    f"RAW={len(raw_lines)}/{EXPECTED_RAW}; "
                    f"run_one={run_one}; COMPLETE={complete}"
                )
                print(f"Saved: {outfile}")

            except Exception as exc:
                partial = reader.snapshot(start)
                meta = {
                    "RUN_ID": run_id,
                    "IMAGE_NUMBER": image,
                    "ERROR": repr(exc),
                    **{k.upper(): v for k, v in hashes.items()},
                    "PARTIAL_CAPTURE_SHA256": sha256_bytes(partial),
                }
                save_log(outfile, meta, partial)
                print(f"CAPTURE STOPPED at image {image}: {exc}")
                print(f"Partial evidence saved: {outfile}")
                print(f"Completed-image summary (if any): {csv_path}")
                raise

    persist_csv()
    complete_count = sum(1 for row in rows if row["raw_trace_complete"])
    print(f"\nFinished images: {len(rows)}")
    print(f"Complete raw traces: {complete_count}/{len(rows)}")
    print(f"CSV summary: {csv_path}")

if __name__ == "__main__":
    main()

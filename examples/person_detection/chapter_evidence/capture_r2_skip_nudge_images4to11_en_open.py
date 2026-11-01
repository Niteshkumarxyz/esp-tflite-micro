import csv
import hashlib
import re
import threading
import time
from pathlib import Path

import serial

PROJECT = Path(r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro\examples\person_detection")
EVIDENCE = PROJECT / "chapter_evidence"
BUILD = PROJECT / "build_rq1_skip_nudge_wdt30_20261027"
PORT, BAUD = "COM5", 115200
EXPECTED_TRACE, EXPECTED_RAW = 31, 3625


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BackgroundReader:
    def __init__(self, ser):
        self.ser = ser
        self.data = bytearray()
        self.cv = threading.Condition()
        self.stop = False
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()

    def _read_loop(self):
        while True:
            with self.cv:
                if self.stop:
                    return
            try:
                chunk = self.ser.read(4096)
            except Exception:
                return
            if chunk:
                with self.cv:
                    self.data.extend(chunk)
                    self.cv.notify_all()

    def mark(self):
        with self.cv:
            return len(self.data)

    def wait_marker(self, marker, start, timeout):
        deadline = time.monotonic() + timeout
        with self.cv:
            while True:
                pos = self.data.find(marker, start)
                if pos >= 0:
                    return pos + len(marker)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(
                        f"Timeout waiting for {marker!r}; start={start}, "
                        f"buffered={len(self.data)} bytes"
                    )
                self.cv.wait(min(remaining, 0.25))

    def snapshot(self, start, end):
        with self.cv:
            return bytes(self.data[start:end])

    def close(self):
        with self.cv:
            self.stop = True
            self.cv.notify_all()
        self.thread.join(timeout=2)


def main():
    fw = BUILD / "person_detection.bin"
    elf = BUILD / "person_detection.elf"
    cfg = PROJECT / "sdkconfig.rq1_skip_nudge_2026-10-27"
    gen_cfg = BUILD / "config" / "sdkconfig.h"
    for path in (fw, elf, cfg, gen_cfg):
        if not path.is_file():
            raise FileNotFoundError(path)

    fw_sha, elf_sha = sha256_file(fw), sha256_file(elf)
    cfg_sha, gen_sha = sha256_file(cfg), sha256_file(gen_cfg)
    run_id = time.strftime("%Y%m%d_%H%M%S")
    summary_path = EVIDENCE / f"r2_skip_nudge_images4to11_summary_{run_id}.csv"
    fields = [
        "image", "result_line", "trace_records", "raw_records", "bytes",
        "sha256", "log_file", "fresh_reset_marker", "fresh_cli_prompt",
        "raw_trace_complete", "firmware_bin_sha256", "firmware_elf_sha256",
        "sdkconfig_sha256", "generated_config_sha256"
    ]
    rows = []

    def save_summary():
        with summary_path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    print(f"Run ID: {run_id}")
    print(f"Firmware BIN SHA256: {fw_sha}")
    print(f"Firmware ELF SHA256: {elf_sha}")
    print("Images 4-11. COM5 will remain open during each physical reset.")
    print("Close idf.py monitor and other serial applications first.")

    with serial.Serial(PORT, BAUD, timeout=0.2, write_timeout=5) as ser:
        ser.dtr = False
        ser.rts = False
        reader = BackgroundReader(ser)
        try:
            print("Waiting for the initial CLI prompt after opening COM5...")
            try:
                reader.wait_marker(b"esp>", 0, 60)
            except Exception as exc:
                raise RuntimeError(
                    "Initial CLI prompt not detected before per-image reset loop."
                ) from exc
            print("Initial CLI confirmed; beginning fresh-reset capture loop.")
            time.sleep(0.5)
            for image in range(4, 12):
                filename = f"r2_skip_nudge_raw_enopen_{run_id}_image_{image:02d}.txt"
                outfile = EVIDENCE / filename

                # Allow the previous image's prompt bytes to drain, then
                # record a marker so stale prompts cannot count as fresh.
                time.sleep(0.5)
                start = reader.mark()

                input(
                    f"\nImage {image}: while COM5 stays open, press and release "
                    "EN once. Then press Enter here. Do not press BOOT."
                )

                try:
                    reset_end = reader.wait_marker(b"rst:", start, 20)
                    prompt_end = reader.wait_marker(b"esp>", reset_end, 60)
                except Exception as exc:
                    partial = (
                        f"RUN_ID={run_id}\nIMAGE={image}\n"
                        f"FIRMWARE_BIN_SHA256={fw_sha}\nRESET_SYNC_ERROR={exc}\n"
                    ).encode("ascii", errors="replace") + reader.snapshot(start, reader.mark())
                    outfile.write_bytes(partial)
                    raise RuntimeError(
                        f"Fresh reset/CLI not verified for image {image}; "
                        f"partial log saved: {outfile}"
                    ) from exc

                print(f"Fresh reset and CLI confirmed for image {image}.")
                ser.write(f"detect_image {image}\r\n".encode("ascii"))
                result_end = reader.wait_marker(
                    f"IMAGE_RESULT,image={image},".encode("ascii"),
                    prompt_end, 180
                )
                final_end = reader.wait_marker(b"esp>", result_end, 60)

                metadata = (
                    f"RUN_ID={run_id}\r\nIMAGE_NUMBER={image}\r\n"
                    f"COMMAND=detect_image {image}\r\n"
                    f"FIRMWARE_BIN_SHA256={fw_sha}\r\n"
                    f"FIRMWARE_ELF_SHA256={elf_sha}\r\n"
                    f"SDKCONFIG_SHA256={cfg_sha}\r\n"
                    f"GENERATED_SDKCONFIG_SHA256={gen_sha}\r\n"
                ).encode("ascii")
                captured = metadata + reader.snapshot(start, final_end)
                outfile.write_bytes(captured)

                text = captured.decode("ascii", errors="replace")
                lines = text.splitlines()
                match = re.search(
                    rf"IMAGE_RESULT,image={image},[^\r\n]*", text
                )
                result_line = match.group(0) if match else "MISSING"
                trace_count = sum(x.startswith("RQ1_TRACE,") for x in lines)
                raw_lines = [x for x in lines if x.startswith("RQ1_RAW,")]
                raw_count = len(raw_lines)
                run_one = all("run=1," in x for x in raw_lines)
                complete = (
                    result_line != "MISSING"
                    and trace_count == EXPECTED_TRACE
                    and raw_count == EXPECTED_RAW
                    and run_one
                )

                row = {
                    "image": image,
                    "result_line": result_line,
                    "trace_records": trace_count,
                    "raw_records": raw_count,
                    "bytes": len(captured),
                    "sha256": hashlib.sha256(captured).hexdigest(),
                    "log_file": filename,
                    "fresh_reset_marker": True,
                    "fresh_cli_prompt": True,
                    "raw_trace_complete": complete,
                    "firmware_bin_sha256": fw_sha,
                    "firmware_elf_sha256": elf_sha,
                    "sdkconfig_sha256": cfg_sha,
                    "generated_config_sha256": gen_sha,
                }
                rows.append(row)
                save_summary()
                print(result_line)
                print(f"TRACE={trace_count}; RAW={raw_count}; run=1={run_one}")
                print(f"Complete: {complete}")
                print(f"Bytes={len(captured)}; SHA256={row['sha256']}")
                print(f"Saved: {outfile}")
                print(f"Summary: {summary_path}")

                if not complete:
                    raise RuntimeError(
                        f"Image {image} failed validation. Log preserved; stopping."
                    )
        finally:
            reader.close()

    completed = sum(x["raw_trace_complete"] for x in rows)
    print(f"\nCOMPLETE RAW TRACES: {completed}/8")
    print(f"SUMMARY CSV: {summary_path}")


if __name__ == "__main__":
    main()

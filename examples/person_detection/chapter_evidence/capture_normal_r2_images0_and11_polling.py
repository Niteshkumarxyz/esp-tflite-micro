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
BUILD = PROJECT / "build_rq1_tensor_trace_r2_optimized_wdt30_20261027"
PORT, BAUD = "COM5", 115200
EXPECTED_TRACE, EXPECTED_RAW = 31, 3625
IMAGES = (0, 11)

def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()

class PollingReader:
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
        inference_wait = marker.startswith(b"IMAGE_RESULT,")

        while time.monotonic() < deadline:
            pos = self.data.find(marker, start)
            if pos >= 0:
                return pos + len(marker)

            segment = bytes(self.data[start:])

            if inference_wait:
                if b"rst:" in segment:
                    raise RuntimeError(
                        "ESP32 reset detected during inference; "
                        f"{len(segment)} bytes captured before reset."
                    )

                now = time.monotonic()
                if now - last_report >= 5:
                    decoded = segment.decode("utf-8", errors="replace")
                    lines = decoded.replace("\r\n", "\n").splitlines()
                    trace_count = sum(x.startswith("RQ1_TRACE,") for x in lines)
                    raw_count = sum(x.startswith("RQ1_RAW,") for x in lines)
                    print(
                        f"Progress: elapsed_s={int(timeout - (deadline-now))}, "
                        f"bytes={len(segment)}, TRACE={trace_count}, RAW={raw_count}",
                        flush=True
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

def save_log(path, metadata, captured):
    header = (
        "\r\n".join(f"{key}={value}" for key, value in metadata.items())
        + "\r\n--- SERIAL CAPTURE ---\r\n"
    ).encode("utf-8")
    path.write_bytes(header + captured)

def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    firmware = BUILD / "person_detection.bin"
    elf = BUILD / "person_detection.elf"
    cfg = BUILD / "sdkconfig"
    generated_cfg = BUILD / "config" / "sdkconfig.h"
    compile_commands = BUILD / "compile_commands.json"

    for path in (firmware, elf, cfg, generated_cfg, compile_commands):
        if not path.is_file():
            raise FileNotFoundError(f"Required normal-R2 build file missing: {path}")

    cfg_text = cfg.read_text(encoding="utf-8", errors="replace")
    generated_text = generated_cfg.read_text(encoding="utf-8", errors="replace")
    commands_text = compile_commands.read_text(encoding="utf-8", errors="replace")

    if not re.search(r"(?m)^CONFIG_NN_OPTIMIZED=y$", cfg_text):
        raise RuntimeError("Normal R2 check failed: CONFIG_NN_OPTIMIZED=y not found.")
    if not re.search(r"(?m)^CONFIG_ESP_TFLITE_MICRO_USE_ESP_NN=y$", cfg_text):
        raise RuntimeError("Normal R2 check failed: ESP-NN is not enabled.")
    if re.search(r"(?m)^CONFIG_NN_SKIP_NUDGE=y$", cfg_text):
        raise RuntimeError("Wrong build: sdkconfig enables SKIP_NUDGE.")
    if re.search(r"(?m)^#define\s+CONFIG_NN_SKIP_NUDGE\s+1\b", generated_text):
        raise RuntimeError("Wrong build: generated config enables SKIP_NUDGE.")
    if re.search(r"(?<![A-Za-z0-9_])-DSKIP_NUDGE(?:\s|[\"'])", commands_text):
        raise RuntimeError("Wrong build: compile commands include -DSKIP_NUDGE.")
    if "TFLM_RQ1_TRACE" not in commands_text:
        raise RuntimeError("RQ1 trace instrumentation not found in compile commands.")

    hashes = {
        "firmware_bin_sha256": sha256_file(firmware),
        "firmware_elf_sha256": sha256_file(elf),
        "sdkconfig_sha256": sha256_file(cfg),
        "generated_config_sha256": sha256_file(generated_cfg),
    }

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = EVIDENCE / f"normal_r2_images0_11_raw_trace_summary_{run_id}.csv"
    fields = [
        "image", "result_line", "trace_records", "raw_records",
        "run1_raw_records", "bytes", "sha256", "log_file",
        "raw_trace_complete", "firmware_bin_sha256", "firmware_elf_sha256",
        "sdkconfig_sha256", "generated_config_sha256"
    ]
    rows = []

    def write_summary():
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    print(f"Run ID: {run_id}")
    print(f"Normal R2 BIN SHA256: {hashes['firmware_bin_sha256']}")
    print(f"Normal R2 ELF SHA256: {hashes['firmware_elf_sha256']}")
    print("Build check: optimized ESP-NN enabled; SKIP_NUDGE not enabled.")
    print("Capture targets: images 0 and 11.")
    print("Close idf.py monitor and all other serial applications first.")

    with serial.Serial(PORT, BAUD, timeout=0.1, write_timeout=5) as ser:
        ser.dtr = False
        ser.rts = False
        reader = PollingReader(ser)

        print("Waiting for initial CLI prompt...")
        reader.wait_marker(b"esp>", 0, 60)
        print("Initial CLI confirmed.")

        for image in IMAGES:
            filename = f"optimized_r2_tensor_trace_image_{image}_endpoint_raw_{run_id}.txt"
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
                run1_raw = sum(x.startswith("RQ1_RAW,run=1,") for x in raw_lines)

                complete = (
                    "invoke_ok=1" in result_line
                    and len(trace_lines) == EXPECTED_TRACE
                    and len(raw_lines) == EXPECTED_RAW
                    and run1_raw == EXPECTED_RAW
                )

                metadata = {
                    "RUN_ID": run_id,
                    "IMAGE_NUMBER": image,
                    "BUILD_TYPE": "normal_optimized_r2_skip_nudge_disabled",
                    **{k.upper(): v for k, v in hashes.items()},
                    "TRACE_RECORDS": len(trace_lines),
                    "RAW_RECORDS": len(raw_lines),
                    "RUN1_RAW_RECORDS": run1_raw,
                    "RAW_TRACE_COMPLETE": complete,
                    "CAPTURE_SHA256": sha256_bytes(captured),
                }
                save_log(outfile, metadata, captured)

                row = {
                    "image": image,
                    "result_line": result_line,
                    "trace_records": len(trace_lines),
                    "raw_records": len(raw_lines),
                    "run1_raw_records": run1_raw,
                    "bytes": len(captured),
                    "sha256": sha256_bytes(captured),
                    "log_file": filename,
                    "raw_trace_complete": complete,
                    **hashes,
                }
                rows.append(row)
                write_summary()

                print(
                    f"Image {image}: TRACE={len(trace_lines)}/{EXPECTED_TRACE}; "
                    f"RAW={len(raw_lines)}/{EXPECTED_RAW}; "
                    f"run1_raw={run1_raw}/{EXPECTED_RAW}; COMPLETE={complete}"
                )
                print(f"Result: {result_line}")
                print(f"Saved: {outfile}")

            except Exception as exc:
                partial = reader.snapshot(start)
                metadata = {
                    "RUN_ID": run_id,
                    "IMAGE_NUMBER": image,
                    "ERROR": repr(exc),
                    **{k.upper(): v for k, v in hashes.items()},
                    "PARTIAL_SHA256": sha256_bytes(partial),
                }
                save_log(outfile, metadata, partial)
                print(f"CAPTURE STOPPED at image {image}: {exc}")
                print(f"Partial log: {outfile}")
                print(f"Summary CSV: {csv_path}")
                raise

    write_summary()
    passed = sum(1 for row in rows if row["raw_trace_complete"])
    print(f"\nCompleted endpoint captures: {len(rows)}")
    print(f"Complete raw traces: {passed}/{len(IMAGES)}")
    print(f"Summary CSV: {csv_path}")

if __name__ == "__main__":
    main()

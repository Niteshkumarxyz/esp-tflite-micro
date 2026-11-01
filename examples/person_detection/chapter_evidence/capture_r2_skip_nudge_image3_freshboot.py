import csv
import hashlib
import re
import time
from pathlib import Path
import serial

P = Path(r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro\examples\person_detection")
E = P / "chapter_evidence"
BUILD = P / "build_rq1_skip_nudge_wdt30_20261027"
PORT, BAUD, IMAGE = "COM5", 115200, 3

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

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
        raise TimeoutError(f"Waiting for {marker!r} timed out; buffered={len(self.buf)}")

def main():
    fw = BUILD / "person_detection.bin"
    elf = BUILD / "person_detection.elf"
    config = P / "sdkconfig.rq1_skip_nudge_2026-10-27"
    generated = BUILD / "config" / "sdkconfig.h"
    for x in (fw, elf, config, generated):
        if not x.is_file():
            raise FileNotFoundError(x)

    fw_sha, elf_sha = sha(fw), sha(elf)
    cfg_sha, gen_sha = sha(config), sha(generated)
    run_id = time.strftime("%Y%m%d_%H%M%S")
    out = E / f"r2_skip_nudge_raw_recovery_image_03_{run_id}.txt"

    print(f"Firmware BIN SHA256: {fw_sha}")
    print(f"Firmware ELF SHA256: {elf_sha}")
    print("Using the current fresh boot. Do not press EN or BOOT.")

    with serial.Serial(PORT, BAUD, timeout=0.2, write_timeout=5) as ser:
        ser.dtr = False
        ser.rts = False
        time.sleep(0.3)
        reader = Reader(ser)
        ser.write(b"\r\n")
        sync = reader.until(b"esp>", 45)
        ser.write(b"detect_image 3\r\n")
        result = reader.until(b"IMAGE_RESULT,image=3,", 180)
        prompt = reader.until(b"esp>", 60)

    data = (
        f"RUN_ID={run_id}\r\nIMAGE_NUMBER=3\r\nCOMMAND=detect_image 3\r\n"
        f"FIRMWARE_BIN_SHA256={fw_sha}\r\nFIRMWARE_ELF_SHA256={elf_sha}\r\n"
        f"SDKCONFIG_SHA256={cfg_sha}\r\nGENERATED_SDKCONFIG_SHA256={gen_sha}\r\n"
    ).encode("ascii") + sync + result + prompt
    out.write_bytes(data)

    text = data.decode("ascii", errors="replace")
    lines = text.splitlines()
    match = re.search(r"IMAGE_RESULT,image=3,[^\r\n]*", text)
    trace = sum(line.startswith("RQ1_TRACE,") for line in lines)
    raw = [line for line in lines if line.startswith("RQ1_RAW,")]
    complete = (
        bool(match) and trace == 31 and len(raw) == 3625
        and all("run=1," in line for line in raw)
    )
    print(match.group(0) if match else "IMAGE_RESULT MISSING")
    print(f"TRACE records: {trace}")
    print(f"RAW records: {len(raw)}")
    print(f"Raw trace complete (run=1): {complete}")
    print(f"Bytes: {len(data)}")
    print(f"Log SHA256: {hashlib.sha256(data).hexdigest()}")
    print(f"Saved: {out}")
    if not complete:
        raise SystemExit("Image 3 validation failed; preserve log and stop.")

if __name__ == "__main__":
    main()

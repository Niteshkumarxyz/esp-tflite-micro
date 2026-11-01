"""Run every pending ESP32 board experiment for the chapter, one after the other, unattended.

  Step 1  RQ1 traces, images 5-11, v0.1.0 optimized build, then byte-for-byte comparison
          with the ESP32 R1 reference     (capture_v010_trace_images_2026-10-29.py, ~12 min)
  Step 2  Skip-nudge 60-minute drift with raw log and audit
                                          (run_skip_nudge_drift60_2026-10-29.py, ~62 min)

Everything printed is also saved to chapter_evidence/run_all_board_experiments_<time>.log.
Only new files are written. Run once, from the ESP-IDF 6.0 PowerShell in the
person_detection folder, with idf.py monitor closed, charger connected and sleep off:
    python chapter_evidence\\run_all_board_experiments_2026-10-29.py
"""
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
STEPS = [
    ("RQ1 traces images 5-11 + comparison", HERE / "capture_v010_trace_images_2026-10-29.py"),
    ("Skip-nudge 60-minute drift + audit", HERE / "run_skip_nudge_drift60_2026-10-29.py"),
]
STOP_CODES = {2, 3, 4}   # preflight failed, COM5 busy/missing, flash failed


def main():
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = HERE / f"run_all_board_experiments_{stamp}.log"
    summary = []
    with log_path.open("w", encoding="utf-8") as log:
        def say(text):
            print(text, flush=True)
            log.write(text + "\n")
            log.flush()

        for title, script in STEPS:
            say(f"\n===== {title} : {datetime.now():%H:%M:%S} =====")
            if not script.is_file():
                say(f"Missing script: {script}")
                summary.append((title, "missing"))
                continue
            p = subprocess.Popen([sys.executable, "-u", str(script)], cwd=HERE.parent,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                 encoding="utf-8", errors="replace")
            for line in p.stdout:
                say(line.rstrip("\n"))
            code = p.wait()
            summary.append((title, code))
            say(f"----- exit code {code} -----")
            if code in STOP_CODES:
                say("Stopping: the board or port was not usable, so the next step would fail too.")
                break

        say("\n===== SUMMARY =====")
        for title, code in summary:
            say(f"{title}: {'OK' if code == 0 else 'exit code ' + str(code)}")
        say(f"Full log: {log_path}")
    return 0 if all(c == 0 for _, c in summary) and len(summary) == len(STEPS) else 1


if __name__ == "__main__":
    sys.exit(main())

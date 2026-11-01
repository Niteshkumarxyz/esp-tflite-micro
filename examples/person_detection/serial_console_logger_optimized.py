import sys
import threading
from pathlib import Path
import serial

PORT = "COM5"
BAUD = 115200
LOG_PATH = Path(__file__).resolve().parent / "w1_optimized_esp_nn_benchmark_1000_2026-10-26.txt"
stop_event = threading.Event()

def read_serial(ser, logfile):
    while not stop_event.is_set():
        try:
            data = ser.read(2048)
            if data:
                logfile.write(data)
                logfile.flush()
                sys.stdout.write(data.decode("utf-8", errors="replace"))
                sys.stdout.flush()
        except Exception as exc:
            if not stop_event.is_set():
                print(f"\nSERIAL_READ_ERROR: {exc}")
            break

def main():
    print(f"Connecting to {PORT} at {BAUD} baud...")
    print(f"Log file: {LOG_PATH}")

    try:
        with serial.Serial(PORT, BAUD, timeout=0.1) as ser:
            with open(LOG_PATH, "wb") as logfile:
                print("Serial connected. Wait for the ESP32 prompt.")
                print("Type the command at CMD> and press Enter.")
                print("Type :quit after the benchmark finishes to save and exit.")

                thread = threading.Thread(
                    target=read_serial,
                    args=(ser, logfile),
                    daemon=True
                )
                thread.start()

                try:
                    while True:
                        line = input("\nCMD> ")
                        if line.strip().lower() == ":quit":
                            break
                        if line.strip():
                            ser.write((line + "\r\n").encode("utf-8"))
                except (KeyboardInterrupt, EOFError):
                    print("\nStopping serial logger...")
                finally:
                    stop_event.set()
                    thread.join(timeout=1)

        print(f"Log saved: {LOG_PATH}")

    except Exception as exc:
        stop_event.set()
        print(f"ERROR: {exc}")
        print("Check that COM5 is available and no other serial monitor is open.")

if __name__ == "__main__":
    main()


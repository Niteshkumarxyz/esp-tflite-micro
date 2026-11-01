# W2 hardware-in-the-loop run on the ESP32 (RQ2)

This folder holds the W2 row-following policy firmware and the Windows host script. The board runs the int8 policy, and the PC runs the simulator. They step in lockstep over the console UART, so an episode depends only on the numbers the board returns, not on its speed. Both int8 models are inside one firmware: per-tensor (`M 0`) and per-channel (`M 1`).

## 1. Build the three firmware variants

Open the ESP-IDF v6.0.3 PowerShell and go to this folder:

```
cd C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro\examples\w2_row_policy
idf.py -B build_w2_r1  -D SDKCONFIG=build_w2_r1\sdkconfig  -D "SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.r1"  build
idf.py -B build_w2_r2a -D SDKCONFIG=build_w2_r2a\sdkconfig -D "SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.r2a" build
idf.py -B build_w2_r2  -D SDKCONFIG=build_w2_r2\sdkconfig  -D "SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.r2"  build
```

If a build fails, send the error text. The firmware was written for ESP-IDF v6.0.3 and esp-tflite-micro 1.4.1, but it could not be compiled before delivery.

## 2. Prepare the Python environment once

```
py -m venv w2venv
w2venv\Scripts\pip install numpy pyserial
```

## 3. For each build: flash, then run both models

```
idf.py -B build_w2_r1 -D SDKCONFIG=build_w2_r1\sdkconfig -p COM5 flash
cd host
..\w2venv\Scripts\python w2_hil_esp32.py --port COM5 --label R1 --model per_tensor
..\w2venv\Scripts\python w2_hil_esp32.py --port COM5 --label R1 --model per_channel
cd ..
```

Repeat with `build_w2_r2a` and `--label R2A`, then `build_w2_r2` and `--label R2`. Do not open the serial monitor while the script runs.

Before it starts, the script checks two things and stops if either is wrong:
- the model hash on the board, and
- the kernel configuration the board reports (`ID` line, with the app ELF SHA-256), which must match `--label`.

A wrong or stale flash is therefore caught before any data is taken.

Each run then does three things:
1. Times 10,000 Invokes on the board (`BENCH` line: microseconds and cycles).
2. Sends 50,000 open-loop observations and prints which host/Arm group the board's actions match.
3. Runs 200 seeded closed-loop episodes (seeds 3000-3199).

Results go to `host\hil_<label>_<model>\` (`summary.json`, `openloop_actions.npy`, `closed_loop_episodes.csv`, `closed_loop_trajectories.npz`). Expect roughly 15-40 minutes per model, depending on the USB-serial latency.

## What the host side already shows

The host and Arm (QEMU) results for the same models, observations and seeds are in `w2_host_arm_results_20261027.zip`. Every TFLM reference and CMSIS-NN build (x86, Cortex-M0+/M3/M4/M55) gives identical actions on all 50,000 observations. The ESP32 builds are expected to join this group, and the HIL run tests that expectation.

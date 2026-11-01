# RQ4: boot-time acceptance test on the ESP32 (person_detection model)

This example answers RQ4 on the board: can a short test run at boot tell whether the firmware
computes the qualified model exactly, before the robot is allowed to move?

At every boot the firmware:

1. prints its identity: the ELF SHA-256 and the SHA-256 digest of the running app image;
2. runs the 12 stored test images of `../person_detection/static_images` through the
   `person_detect` model (300,568 bytes, SHA-256 808cfdfc...502e9d);
3. for each image compares the two int8 outputs and an FNV-1a hash of each of the 31 operator
   outputs with the answers recorded from the qualified reference build (ESP32 R1, TFLM reference
   kernels, trace logs of 25 October 2026); the answers are in `main/rq4_expected.h`;
4. prints `RQ4_RESULT,verdict=PASS|FAIL,...` with the first failing image and operator and the time
   taken, and `RQ4_ACTUATION,ENABLED|BLOCKED`.

Operator outputs are hashed by wrapping each kernel's invoke function in the op resolver, so the
TFLM sources are not changed. The model data and images are taken from `../person_detection`.

## Builds

| Name | Kernels | Expected verdict |
|---|---|---|
| r1 | TFLM reference (ESP-NN off) | PASS |
| r2a | ESP-NN ANSI C | PASS |
| r2 | ESP-NN optimized | PASS |
| r2sn | ESP-NN optimized with NN_SKIP_NUDGE | PASS |
| r1sr | TFLM reference with TFLITE_SINGLE_ROUNDING=1 (positive control) | FAIL |

`esp-nn` is pinned to 1.4.1 (`main/idf_component.yml`, `dependencies.lock`), the version used by
every person_detection build in this study.

## Run

From the ESP-IDF 6.0 PowerShell, in this folder, with idf.py monitor closed:

```
python run_rq4_boot_kat_2026-10-29_v3.py
```

The script builds the five variants, checks each configuration, flashes each one with esptool,
resets the board five times per build, saves every boot's serial output with a SHA-256 sidecar,
and writes a summary to `../person_detection/chapter_evidence/rq4_boot_kat_2026-10-29/`.

Manual build of one variant, for reference:

```
idf.py -B build_rq4_r2 -D SDKCONFIG=build_rq4_r2/sdkconfig -D "SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.r2" build
idf.py -B build_rq4_r1sr -D SDKCONFIG=build_rq4_r1sr/sdkconfig -D "SDKCONFIG_DEFAULTS=sdkconfig.defaults;sdkconfig.defaults.r1" -D RQ4_SINGLE_ROUNDING=1 build
```

## Change history

- Run 20261029_190542 (runner v1): stopped before flashing; the PowerShell window still had
  `TFLM_RQ1_TRACE_BUILD=1`, which put trace code into the builds, and the r1sr build hit a compiler crash.
- Run 20261029_194250 (runner v2, trace removed): r2a gave PASS on all 5 boots; r1, r2, r2sn and r1sr stopped at
  setup because the 160 KB arena could not be allocated after two 8 KB task stacks (`arena=0`), and the ELF
  identity check failed because ESP-IDF keeps only 9 characters of the ELF SHA-256 by default.
- Version 3 (current): the arena is allocated in `app_main` before the test task is created, the main task
  keeps the default 3,584-byte stack, and `CONFIG_APP_RETRIEVE_LEN_ELF_SHA=64`. Builds go to `build_rq4v3_<name>`.

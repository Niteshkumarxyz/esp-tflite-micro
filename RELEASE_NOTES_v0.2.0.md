# Release v0.2.0 (1 November 2026)

Research fork of esp-tflite-micro for the chapter "Same Model, Different Robot: Checking Int8 Runtimes Before the Robot Moves" by Nitesh Kumar, Vikash Kumar and Pinkee Kumari, Amity University Patna.

Release v0.1.0 (commit 15dd18a, DOI 10.5281/zenodo.23752911) holds the benchmark, long-run and operator-trace instrumentation. This release adds the firmware, scripts and raw logs behind the rest of the chapter: the acceptance test, the W2 policy, the Arm builds, the two experiments of 1 November 2026, and the figures.

All board results come from one ESP32-D0WD-V3 (revision 3.1) at 240 MHz, built with ESP-IDF v6.0.3, xtensa-esp-elf-gcc 15.2.0 at -O2, and ESP-NN 1.4.1 (component hash 3b3411b0…a246). Only one chip was tested.

## Firmware and code

| Path | What it is |
|---|---|
| examples/rq4_boot_kat/ | Boot-time acceptance test. At every boot it checks the ELF and app-image SHA-256, then runs 12 stored images and compares the FNV-1a hash of each of the 31 operator outputs with the reference build. Run scripts v1 to v3 included. |
| examples/w2_row_policy/ | W2 row-following policy firmware for R1, R2A and R2, the host simulator and hardware-in-the-loop script (host/), both int8 models, and the closed-loop results. |
| examples/rq3_layout_iram_2026-11-01/ | One-command runner for the editor's experiments of 1 November 2026, plus the `iram_kernels` component, whose linker fragment moves the ESP-NN conv and depthwise kernels into IRAM. |
| examples/skipnudge_requant_test_2026-11-01/ | On-chip comparison of ESP-NN's bit-exact and skip-nudge requantize functions. |
| examples/person_detection/main/ (backup copies) | Source snapshots from 19 to 24 October. The runner rebuilds the 21 October build from four of them. |
| examples/person_detection/sdkconfig.* | Configuration snapshots of the measured builds, including the three used on 1 November. |
| examples/person_detection/chapter_evidence/chapter_figures_v21/ | The 14 manuscript figures with the scripts and data that drew them. |
| examples/person_detection/chapter_evidence/rq4_host_harness_2026-10-29/ | The acceptance test built for x86 with TFLM. |
| examples/person_detection/chapter_evidence/arm_qemu_rq1_20261027/ | Arm Cortex-M0+, M3, M4 and M55 and x86 trace builds: harness, build scripts, pinned dependency commits, logs and binaries, in one verified zip. |
| examples/person_detection/chapter_evidence/w2_host_arm_20261027/ | W2 on the Arm and host builds: harness, training and conversion scripts, models and results. |
| examples/person_detection/chapter_evidence/rq4_w2_analysis_archive_2026-10-29/ | RQ4 and W2 analysis scripts and their outputs. |

## Results added on 1 November 2026

Evidence: `examples/person_detection/chapter_evidence/editor_experiments_2026-11-01/`.

**Skip-nudge requantization on the chip.**

| Set | Cases | Differ |
|---|---|---|
| Random accumulators below 2^26 | 1,000,000 | 0 |
| Random accumulators below 2^29 | 1,000,000 | 0 |
| Exact multiply ties | 3,328,000 | 0 |
| Exact shift ties | 600,000 | 0 |
| Any int32 value | 1,000,000 | 6,126 |
| Values next to INT32_MAX | 120 | 115 |

Every difference occurs where the value before the shift lies within 2^(e-1) of INT32_MAX. The worst-case accumulator bounds of W1 and W2 (`skip_nudge_requantize_analysis_2026-11-01/`) are far below that region. The scope is the C path of ESP-NN 1.4.1 on the classic ESP32; the ESP32-S3 assembly path was not tested.

**Code layout, kernels in flash and in IRAM.** Mean Invoke time over 1,000 runs per build:

| Build | Kernels in flash | Kernels in IRAM |
|---|---|---|
| 21 October application | 401.676 ms | 375.261 ms |
| 28 October application | 412.500 ms | 375.272 ms |
| 28 October, skip-nudge | 391.103 ms | 356.459 ms |

- **The layout gap closes in IRAM.** The 10.824 ms gap (2.69%) between the two applications falls to 0.011 ms.
- **The skip-nudge saving stays.** It is 5.19% with the kernels in flash and 5.01% in IRAM.
- **The board did not drift.** The original binaries, run at the start and again at the end, gave 401.677 / 401.677 ms and 412.501 / 412.500 ms.
- **All builds were correct.** Every run had 1,000 of 1,000 outputs as expected and a matching ELF banner.

**The rebuild matches the originals.** The rebuilt flash variants match the original builds in BIN size, model-array address and kernel addresses. The 21 October application files used by the runner are byte-identical to the snapshot taken that day in `evidence/cycle_count/instrumented_source_fix1_20261021/` (esp_cli.c and main_functions.cc), and esp_main.h is identical apart from line endings.

## Raw logs

The serial logs, traces, benchmark captures, manifests and capture scripts from 19 October to 1 November 2026 are included, apart from the items under "Left out":

- `evidence/`
- `examples/person_detection/` (top-level files)
- `examples/person_detection/chapter_evidence/`
- `examples/hello_world/`

Most logs have a `.sha256.txt` sidecar or a manifest beside them. `final_runtime_evidence_2026-10-29_v5.zip` is the evidence package attached to the GitHub release of v0.1.0, so it is now archived with a DOI.

## Left out

- **Build folders, managed components and the Python virtual environment.** The two project copies that the runner makes are also left out; it makes them again.
- **Earlier staging and verification copies of evidence packages.** The final packages that superseded them are included: `final_runtime_evidence_2026-10-29_v5.zip` and `r2_normal_vs_skip_nudge_final_evidence_2026-10-28_v4.zip`.
- **Uncommitted edits to two tracked files in examples/hello_world.** They are the reason some version strings end in "-dirty".
- **Chapter manuscripts.**

## Integrity

`SHA256SUMS_v0.2.0.txt` lists the SHA-256 of every file added in this release. `release_v0.2.0_files.txt` is the exact list that was committed.

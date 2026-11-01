# Editor experiments, 1 November 2026

Two checks asked for in the editor's e-mail of 30 October 2026, run on 1 November 2026 on the same ESP32-D0WD-V3 board (COM5) with one command.

## How to run

In a Command Prompt with ESP-IDF 6.0.3 active (`set IDF_TOOLS_PATH=C:\Espressif` then `C:\esp\v6.0.3\esp-idf\export.bat`), with `idf.py monitor` closed and the charger connected. The script stops at once under any other ESP-IDF version.

```
cd C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro\examples\rq3_layout_iram_2026-11-01
python run_editor_experiments_2026-11-01.py
```

It takes about 2.5 to 3 hours: seven builds (about 70 minutes), then ten `benchmark 1000` runs on the board (about 80 minutes). The window must stay open. The script keeps Windows awake while it runs.

## Part A: skip-nudge requantize on the chip

`examples/skipnudge_requant_test_2026-11-01` compiles ESP-NN 1.4.1's `common_functions.h` for the classic ESP32 and compares `esp_nn_multiply_by_quantized_mult` (bit-exact) with `esp_nn_multiply_by_quantized_mult_fast` (skip-nudge). The sets are random accumulators below 2^26, below 2^29 and over all int32 values, exact multiply ties, exact shift ties, and values next to INT32_MAX. The header is copied from `examples/person_detection/managed_components` only after its SHA-256 matches `350ffcdb…0efd`, the copy analysed on the host.

## Part B: layout effect and skip-nudge speed-up, kernels in flash and in IRAM

Two new project copies sit next to `person_detection`. Neither changes `person_detection`.

| Copy | Application files |
|---|---|
| `rq3_layout_pre_2026-11-01` | As built on 21 October: `esp_cli.c.before_drift_20261022`, `main_functions.cc.bak_invoke_failure_guard_20261024_213642`, `CMakeLists.txt.before_drift_20261022`. `esp_main.h` is the 20 October backup plus the six `g_*` declarations that the 21 October `esp_cli.c` needs. Declarations produce no code. |
| `rq3_layout_post_2026-11-01` | As they are now, the same files as the 28 October builds. |

Six variants are built, each with the original sdkconfig of the build it reproduces:

| Variant | sdkconfig | Kernels |
|---|---|---|
| `pre_flash`, `pre_iram` | `sdkconfig.cycle_optimized_20261021` (401.6 ms build) | flash / IRAM |
| `post_flash`, `post_iram` | `sdkconfig.b5_normal_r2_notrace_2026-10-28` (412.5 ms build) | flash / IRAM |
| `sn_flash`, `sn_iram` | `sdkconfig.b5_skip_nudge_notrace_2026-10-28` (391.1 ms build) | flash / IRAM |

The `_iram` variants add `iram_kernels/linker.lf`, which moves `esp_nn_conv_opt` and `esp_nn_depthwise_conv_opt` (the conv and depthwise kernels with their helpers) into IRAM. Nothing else changes.

Before any board run, each build is checked for: 240 MHz, 100 Hz tick, -O2 (PERF), QIO at 80 MHz, ESP-NN optimized, the expected skip-nudge setting, no trace code, and ESP-NN 1.4.1 with component hash `3b3411b0…a246`. The script also confirms that both kernels sit in IRAM (0x40080000 to 0x400A0000) only in the `_iram` variants. Each flash variant's model array address, kernel addresses and BIN size are compared with the original build it reproduces.

Board order, all on one board and one day: original 21 October binary, original 28 October binary, `pre_flash`, `post_flash`, `sn_flash`, `pre_iram`, `post_iram`, `sn_iram`, then the two original binaries again. Each run flashes with `esptool write-flash @flash_args`, resets, sends `benchmark 1000`, and keeps the full serial log. It also checks the ELF SHA-256 banner against the build and checks every sample's raw person score against the reference for its image.

## What the result means

If the 2.7% gap between the 21 October and 28 October builds disappears when both have the kernels in IRAM, it came from where the kernels sit in flash, so it is a cache and layout effect, not a code effect. If part of the gap remains, the other candidates are the model array, which moved 896 bytes and is still read through the flash cache, and the rest of the flash code. If the skip-nudge saving stays about the same in IRAM, it comes from the shorter requantize code, not from layout.

The two original binaries run at the start and again at the end. If they agree, the board and its temperature did not drift during the run.

## Output

Everything goes to `examples/person_detection/chapter_evidence/editor_experiments_2026-11-01/`, and no file there is overwritten:

- raw serial logs, each with a `.sha256.txt` sidecar
- build and flash logs
- `editor_experiments_summary_<run>.csv`
- `editor_experiments_metadata_<run>.json`
- `run_log_<run>.txt`

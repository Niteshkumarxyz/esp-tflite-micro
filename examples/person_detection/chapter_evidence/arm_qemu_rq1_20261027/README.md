# RQ1 on Arm Cortex-M under QEMU (27 October 2026)

This folder extends RQ1 from the ESP32 to Arm Cortex-M kernels. No physical Arm board was used. Every build ran under QEMU user-mode emulation, so the results speak to the numbers computed (RQ1), not to timing (RQ3).

## What was compared

- **Model.** The ESP32 `person_detect` model, 300,568 bytes, SHA-256 `808cfdfc0cf3a6fa6f6fa26bfa379ea97c16d5db7334637766e39c3408502e9d`. The bytes were taken from the ESP32 `person_detect_model_data.cc`, and `scripts/gen_rq1_data.py` checks the hash.
- **Inputs.** The same 12 inputs as the ESP32 traces (`static_images/sample_images/image0..11`), converted to int8 by XOR 0x80, exactly as the ESP32 `run_inference()` does.
- **Interpreter.** The same five-operator resolver as the ESP32 build: AveragePool2D, Conv2D, DepthwiseConv2D, Reshape and Softmax.
- **Trace code.** Copied unchanged from the ESP32 patch, `micro_interpreter_graph.cc` under `TFLM_RQ1_TRACE` (see `harness/micro_interpreter_graph_trace.diff`). One change was made: raw tensor bytes are printed for every run instead of only the first, because one emulator process runs all 12 images.
- **Reference.** The 12 ESP32 R1 full-dump logs of 25 October (`log.person_detection.20261025*.txt`). Their file names and SHA-256 are listed in `compare_summary.json`.

Every tensor was rebuilt from its raw chunks and checked against the element count, min, max, sum and FNV-1a hash that the target itself printed. There were no structural errors in any run.

## Results: 12 images × 31 operators = 372 tensors, 2,781,768 int8 values per configuration

| Configuration | CPU (QEMU) | Kernels and code path | Tensors equal to ESP32 R1 | Values differing | Max LSB | Outputs equal | Arena used (B) |
|---|---|---|---|---|---|---|---|
| m4_reference | Cortex-M4 | TFLM reference | 372/372 | 0 | 0 | 12/12 | 82,292 |
| m4_cmsis_nn | Cortex-M4 | CMSIS-NN, DSP path (284 `smlad`, 342 `sxtb16`) | 372/372 | 0 | 0 | 12/12 | 82,308 |
| m3_cmsis_nn_scalar | Cortex-M3 | CMSIS-NN, pure C (no DSP instructions) | 372/372 | 0 | 0 | 12/12 | 82,308 |
| m55_cmsis_nn_mve | Cortex-M55 | CMSIS-NN, Helium/MVE path (`wlstp`/`letp` loops, `vqrdmulh.s32`, 528 instructions on MVE Q registers) | 372/372 | 0 | 0 | 12/12 | 82,356 |
| m55_reference | Cortex-M55 | TFLM reference | 372/372 | 0 | 0 | 12/12 | 82,292 |
| m0plus_reference | Cortex-M0+ (run as cortex-m0) | TFLM reference | 372/372 | 0 | 0 | 12/12 | 82,292 |
| x86_reference_host | x86-64 | TFLM reference, same TFLM commit | 372/372 | 0 | 0 | 12/12 | 85,024 |
| m4_reference_SINGLE_ROUNDING | Cortex-M4 | TFLM reference with `TFLITE_SINGLE_ROUNDING=1` | 9/372 | 416,778 | 15 | 5/12 | 82,292 |
| m4_cmsis_nn_SINGLE_ROUNDING | Cortex-M4 | CMSIS-NN with `CMSIS_NN_USE_SINGLE_ROUNDING` (and `TFLITE_SINGLE_ROUNDING=1`) | 9/372 | 416,778 | 15 | 5/12 | 82,308 |

The arena sizes match the ESP32. The reference builds use 82,292 B, the same as ESP32 R1. CMSIS-NN on M3/M4 uses 82,308 B, the same as ESP32 R2.

**Positive controls.** Single rounding is a documented build option in both TFLM and CMSIS-NN. Both single-rounding builds first diverge from ESP32 R1 at operator 0 on all 12 images. They change 7 of the 12 final outputs (image 1: −39 to −31; image 3: 67 to 57; image 5: −100 to −101; image 6: 97 to 98; image 7: −98 to −97; image 9: 83 to 81; image 11: −57 to −59), and no label changes. The two single-rounding builds are byte-identical to each other in all 372 tensors.

**Link to the host XNNPACK result of 25 October.** LiteRT 2.3.0 with XNNPACK was hashed per operator on the laptop VM (`xnn_hashes_litert230.txt`, SHA-256 prefixes of each tensor). XNNPACK equals the single-rounding builds in 348 of 372 tensors:

- On 9 of the 12 images it is byte-identical at every operator.
- On images 1 and 2 it differs at a single operator (operator 9 and operator 8), and the next operator absorbs the difference.
- On image 11 it differs from operator 9 to the output (−60 against −59).

Almost all of the XNNPACK divergence from the ESP32 is therefore explained by single rounding. A second, much smaller effect appears on 3 images and has not yet been explained.

## Limits

- **Emulation, not hardware.** QEMU executes the Arm instruction sets functionally. No timing, energy or memory-bus effect is measured, and the physical NUCLEO-L4R5ZI (R3) and RP2040 (R5) of the proposal were not used.
- **Toolchain.** The Arm toolchain is xPack GCC 14.2.1 (`arm-none-eabi`); TFLM pins Arm GNU Toolchain 14.3.rel1, which could not be downloaded here. The host build used Ubuntu g++ 13.3.
- **Dependencies.** Third-party code (CMSIS 6, Cortex_DFP, CMSIS-NN, flatbuffers, kissfft, printf) was cloned with git at the exact commits pinned by TFLM (`scripts/deps_commits.json`), because archive downloads were blocked.
- **TFLM version.** TFLM is upstream commit `1ee5135b769bb1270f40e9b14137920d82ea111e`, not the esp-tflite-micro copy used on the ESP32. Agreement is therefore across versions as well as targets.
- **Inputs.** The results cover 12 inputs and one model.

## Reproduce

1. Run `scripts/setup_deps.py`, then link the toolchain to `downloads/gcc_embedded`.
2. Apply `harness/micro_interpreter_graph_trace.diff`.
3. Put `harness/rq1_arm_main.cc` and the generated `rq1_data.{cc,h}` in `tensorflow/lite/micro/examples/rq1_arm/`.
4. Run `scripts/build_all.sh`, `scripts/build_single_rounding.sh` and `scripts/run_all.sh`.
5. Run `python3 scripts/compare.py`.

Binaries and logs are hashed in `MANIFEST_SHA256.csv`.

# RQ4 acceptance test on the host (TFLM x86 build)

The host-side version of the boot-time acceptance test: the same 12 stored images and the same per-operator FNV-1a hashes as the ESP32 firmware in `examples/rq4_boot_kat`, built with TensorFlow Lite Micro for x86.

| File | What it is |
|---|---|
| rq4_host_main.cc | Test program. It runs the 12 images and checks every operator hash against the expected table. |
| rq4.mk | Make fragment that adds the `rq4_host_kat` target to the TFLM build. |
| build_rq4_host.log | Build log from 29 October 2026. |

The expected table `rq4_expected.h` is byte-identical to `examples/rq4_boot_kat/main/rq4_expected.h`. The model and image data come from `rq1_data.cc`, which `gen_rq1_data.py` writes. That script, `setup_deps.py` and the rest of the Arm and host harness are inside `../arm_qemu_rq1_20261027/arm_qemu_rq1_20261027.zip`.

To build it, put the two source files under `tensorflow/lite/micro/examples/rq4_host/` in a TFLM checkout at commit 1ee5135b769bb1270f40e9b14137920d82ea111e, add `rq1_data.cc`, `rq1_data.h` and `rq4_expected.h`, and run:

```
make -f tensorflow/lite/micro/tools/make/Makefile -f rq4.mk rq4_host_kat
```

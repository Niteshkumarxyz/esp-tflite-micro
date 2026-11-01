# RQ4 and W2 analysis archive (29 October 2026)

These files were produced in Claude's cloud workspace between 26 and 28 October and copied here so the
chapter's RQ4 and W2 numbers can be checked and re-run. `MANIFEST_SHA256.csv` lists every file with its size and SHA-256.

## rq4/ - acceptance-test (RQ4) analysis on recorded outputs
- `rq4_w1.py` -> `rq4_w1.json`: W1 (person_detect). How often a stored known-answer set catches a deviant build
  (positive controls: single-rounding TFLM and CMSIS-NN builds, and LiteRT XNNPACK). With K random images whose
  final outputs are stored: 58.3% (K=1), 84.8% (K=2), 95.5% (K=3), 99.0% (K=4), 100% (K>=6). With per-operator
  tensor hashes: 100% with a single image, because those builds diverge at operator 0 on every image.
- `w1_oplevel.py` -> `w1_oplevel.json`: per-operator share of differing values and maximum LSB for the deviant builds.
- `w2_int8_ref.py`: bit-exact numpy reimplementation of the W2 int8 fully connected layers (double and single rounding),
  checked equal to the TFLM x86 reference and the single-rounding builds on all 50,000 observations.
- `rq4_w2.py` -> `rq4_w2.json`: W2 detection by random and by rounding-tie-ranked test vectors, first-layer divergence,
  and negative controls (all QEMU Arm builds and TFLM x86 identical to the reference).
- `stress_opt.py` -> `stress_opt_per_tensor.json`, `stress_opt_per_channel.json`: closed-loop stress episodes, reference vs
  LiteRT OPT (outcome changes, identical trajectories, exact McNemar p).
- `figs_v20.py`, `fig02_bench.py`, `figs/`: chapter v20 figures (PNG and 300 dpi TIFF).

## w2/ - W2 row-following policy
- `train_w2.py` (stable-baselines3 PPO, 2,000,000 steps; `train.log`, `out/train_log.json`, `out/ppo_w2.zip`),
  `w2_sim.py` (kinematic simulator), `convert_w2.py` (int8 conversion, per-tensor and per-channel),
  `w2_runtime.py`, `w2_eval.py`, `w2_stress.py`, `diag_w2.py`.
- `out/`: int8 models, calibration states, expected open-loop outputs, and `eval_per_tensor/`, `eval_per_channel/`
  with open-loop and closed-loop CSVs for LiteRT REF/OPT/XNNPACK, TFLM x86 and the QEMU Arm builds.
- `fw/`, `bins/`, `gen_fw_models.py`, `gen_w2_model_data.py`: model data for the ESP32 and Arm firmware.
  The ESP32 hardware-in-the-loop firmware and its six run logs are in `examples/w2_row_policy/`.

## arm_w2_and_rq1_harness/
Build scripts, logs and the comparison script for the QEMU Arm runs (W1 RQ1 and W2). The full W1 RQ1 Arm evidence
(binaries and run logs) is in `chapter_evidence/arm_qemu_rq1_20261027/`.

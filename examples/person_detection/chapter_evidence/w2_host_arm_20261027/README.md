# W2 row-following policy: open-loop (RQ1) and closed-loop (RQ2) results on host and Arm (27 October 2026)

## Workload

**Simulator.** `scripts/w2_sim.py` is a 2D differential-drive robot following a 12 m crop row at 20 Hz.
- Observations (7): a five-channel IR line array plus left and right ultrasonic ranges.
- Disturbances: IR noise, ultrasonic noise, 25% ultrasonic dropouts (gaps between plants), 3–6 gaps in the line tape, and 10% wheel slip.
- Episode rules: an episode fails if the robot leaves the row by more than 0.25 m or has not finished in 30 s.
- Baseline: a hand-tuned proportional controller succeeds on about 69% of seeds.

**Policy.** An MLP 7→64→64→2 with ReLU, trained with PPO (stable-baselines3 2.9.2) for 2 million steps (`scripts/train_w2.py`, log in `scripts/train.log`).

**Quantization.** The policy was converted to full int8 (`scripts/convert_w2.py`) twice:
- Per-tensor: 7,392 B, SHA-256 `3f449cb3…`.
- Per-channel: 10,448 B, SHA-256 `097181e6…`.

Both models contain only FULLY_CONNECTED operators. Calibration used 105,796 states from seeds 2000–2199.

**Comparison method.** Every runtime receives the same int8 observation bytes. The host quantizes observations and dequantizes actions identically for all runtimes.

## Runtimes

| Group | Runtimes |
|---|---|
| LiteRT 2.3.0 | REF, OPT (built-ins without delegates), XNNPACK (default) |
| TFLM `1ee5135`, x86 | reference; reference built with `TFLITE_SINGLE_ROUNDING=1` |
| TFLM under QEMU | Cortex-M4 reference; M4 CMSIS-NN (DSP); M4 CMSIS-NN single rounding; M3 CMSIS-NN (pure C); M55 CMSIS-NN (Helium/MVE); M0+ reference |

## Open loop: 50,000 observations

The set (`eval_*/openloop_obs_int8.npy`) has four parts:
- 25,000 states from float-policy rollouts.
- 10,000 states pushed by ±2 input quantization steps.
- 10,000 uniform states.
- 5,000 states with saturated sensors.

The runtimes fall into four groups. Within each group, the actions are byte-identical on all 50,000 observations.

| Group | Members |
|---|---|
| Double rounding (D) | TFLM reference (x86, M0+, M4), CMSIS-NN (M3 pure C, M4 DSP, M55 MVE) |
| Single rounding (S) | LiteRT REF, TFLM with `TFLITE_SINGLE_ROUNDING`, CMSIS-NN with `CMSIS_NN_USE_SINGLE_ROUNDING` |
| LiteRT OPT | differs from D on 2 observations |
| LiteRT XNNPACK | differs from S on 3 (per-tensor) or 1 (per-channel) observations |

Between D and S, the actions differ on 1,189 observations (2.38%) for the per-tensor model and on 883 (1.77%) for the per-channel model. Every difference is exactly 1 LSB.

The two reference implementations disagree here. For FULLY_CONNECTED, LiteRT's reference kernel gives the same bytes as TFLM built with single rounding, while TFLM's own reference gives double-rounding results. For the W1 convolutions on 25 October, the LiteRT reference matched TFLM and the ESP32 exactly.

## Closed loop, nominal conditions

There were 200 seeded episodes (seeds 3000–3199) for each runtime.

| Model | Success, every runtime | Episodes whose D and S trajectories separate | Median first separation | Episodes with a different outcome |
|---|---|---|---|---|
| Per-tensor | 199/200 (same failing seed) | 200/200 | step 28 (1.4 s) | 0 |
| Per-channel | 198/200 (same failing seeds) | 200/200 | step 46 (2.3 s) | 0 |

The mean paired RMS cross-track difference is 0.01–0.03 mm.

## Closed loop, stress conditions

There were 1,000 seeds (5000–5999), with wheel slip 0.15, ultrasonic dropout 0.40 and IR noise 0.05 (`model/stress_*.json`). Single rounding was compared with double rounding.

| Model | Success (D / S) | Seeds that failed only with S | Seeds that failed only with D | McNemar p | Changed seeds |
|---|---|---|---|---|---|
| Per-tensor | 946 / 944 | 4 | 2 | 0.69 | 5305, 5457, 5465, 5507, 5863, 5964 |
| Per-channel | 947 / 944 | 4 | 1 | 0.38 | 5361, 5572, 5900, 5909, 5974 |

XNNPACK gave the same outcomes as S.

## Reading for RQ2

A 1-LSB difference on about 2% of observations makes every episode's trajectory separate within a few seconds. Under nominal conditions the loop absorbs it, and no outcome changes. Under stress it changes the outcome of 5–6 episodes per 1,000, in both directions, so the success rate does not reveal it. The effect therefore shows in single episodes, not in the averages. Only bit-exact identity keeps a qualified episode reproducible.

## Limits

- The simulator is kinematic, and no physical rover was used. Training used the same simulator as testing.
- QEMU emulation gives no timing; see the W1 Arm package for the toolchain notes.
- The ESP32 hardware-in-the-loop run is pending. The firmware and host script are in `esp-tflite-micro/examples/w2_row_policy`.

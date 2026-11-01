# Research Status Summary
Date: 2026-10-21
Project: Same Model, Different Robot — ESP32/TFLM runtime comparison

## 1. Platform and model
- Target: ESP32-D0WD-V3, revision 3.1
- CPU: 240 MHz
- ESP-IDF: v6.0.3
- Input tensor: INT8, shape 1x96x96x1
- Input scale: 0.0078431377
- Input zero point: -1
- Output tensor: INT8, shape 1x2
- Output scale: 0.00390625
- Output zero point: -128
- Configured tensor arena: 163840 bytes
- Reported tensor arena used: 82300 bytes

## 2. ESP-NN versus reference kernels
Source files:
- w1_esp_nn_retest_validation_2026-10-20.csv
- w1_reference_kernels_validation_2026-10-20.csv

Each timing CSV contains 10 observations.
- ESP-NN mean: 403682.6 us
- ESP-NN median: 403674 us
- ESP-NN min/max: 403492 / 403892 us
- Reference mean: 4142992.8 us
- Reference median: 4142996.5 us
- Reference min/max: 4142924 / 4143068 us
- Calculated mean speedup: approximately 10.263x
- Calculated mean latency reduction: approximately 90.26%

An older w1_timing_summary.csv has different values. It was preserved; the validated retest comparison is calculated directly from the two raw timing CSVs.

## 3. INT8 correctness checks
- Independent raw-output comparison: 10 images compared.
- Exact matches: 10.
- Mismatches: 0.
- Scope: only these 10 tested images; not a full-dataset claim.

After the signed INT8 accessor edit, board tests reported:
- detect_image 10: raw output 113,-113; person score 94%; no-person score 6%.
- detect_image 11: raw output -57,57; person score 28%; no-person score 72%.

## 4. Updated 100-run Person Detection benchmark
Raw monitor log:
log.person_detection.20261021202454.txt

Sample CSV:
w1_benchmark_100run_samples_2026-10-21.csv

- Warm-up runs: 10
- Measured runs: 100
- Images: 10, repeated cyclically
- Failed invocations: 0
- Independently calculated mean: 401644.1 us
- Independently calculated median: 401641 us
- P95 nearest-rank: 401722 us
- Min/max: 401561 / 401727 us

Timing measures interpreter_Invoke_only, not full camera-to-result latency.

## 5. Separate hello_world cycle-count evidence
- Raw log: examples/hello_world/cycle_count_raw_log.txt
- Extracted samples: 830
- All-sample mean: 12247.98 cycles
- All-sample median: 12242 cycles
- All-sample min/max: 11858 / 23685 cycles
- Excluding first sample for comparison: 829 samples, mean 12234.19 cycles, median 12242, min/max 11858 / 12610 cycles.

This is a hello_world benchmark, not Person Detection evidence.

## 6. Build and evidence integrity
- Person Detection build completed successfully.
- Firmware flash completed with written-data hash verification.
- Current source, backup, object, ELF and BIN hashes/sizes/timestamps are recorded in:
  w1_build_identity_audit_2026-10-21.csv
- Final local manifest:
  w1_evidence_sha256_final_2026-10-21.csv
- Manifest verification result: 7 entries PASS, 0 failures.

Current main_functions.cc SHA-256:
C7BD0D0974A7FA456F8A30E35848B0A5E4C7413F845C988E8DCFBE3B9C730707

Current object SHA-256:
FD6C15F77F700ECA02743BBF2F01F3867455229C7FBEC1D2D7E488164CC265B8

Current ELF SHA-256:
767211C114A14F001C27E95C1EC050008313EC6B7A6FE0E9F6C233CAB7A76C9B

Current BIN SHA-256:
23EAF001780A025F390F522E277ADB9FA972529B4A5C272A9ACB1D5D75F349DE

## 7. Remaining work
1. Investigate why the current ELF hash matches the earlier recorded ELF hash despite the source accessor edit. Build and flash succeeded and board outputs matched expected examples, but timestamps and hashes alone do not prove the exact source-to-binary machine-code relationship.
2. Add the 1000-run benchmark deliverables to the local project evidence package and manifest; they are separate from the current 7-entry local manifest.
3. Reconcile and document the old timing-summary discrepancy without overwriting historical evidence.
4. Complete the final evidence audit before making broader correctness or performance claims.

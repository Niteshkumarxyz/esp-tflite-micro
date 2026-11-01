# Skip-nudge R2 - 60-Minute Drift Audit

- Run ID: 20261029_174934
- Firmware: build_b5_skip_nudge_notrace_2026-10-28 (optimized ESP-NN, CONFIG_NN_SKIP_NUDGE=y, no trace code)
- BIN SHA-256: 8EF30EF85A4BEDD393BE0891B0598857BB305C059F4D323ECB95E4BC37934C03
- ELF SHA-256: 6E944AE8299CB08FBD247A8E842D860D87E5D59242BF4CB00FEFEBCC8C63A694
- sdkconfig snapshot SHA-256: 08F6A77C762FC2B005DEEF1BAF55038CF77E16C00D7F41C7327800C31C1E8328
- Boot banner: App version v1.4.1-4-g461cb12-dirty; compile time Oct 28 2026 09:01:16; ESP-IDF v6.0.3; ELF SHA256 6e944ae82...
- Flash: 4 x 'Hash of data verified'
- Command: drift 60; timing boundary: interpreter_Invoke_only
- Raw log: skip_nudge_drift_60min_serial_raw_20261029_174934.txt
- Raw log SHA-256: A45E12E8A85B94508F3931692966A0F2B9B3CD311C9149A7F63D81BA15A25BF6
- Audit result: PASS

## Checks

| Check | Result |
|---|---|
| Flash: return code 0, 4 x 'Hash of data verified', app image written at 0x20000 | PASS |
| Boot banner ELF SHA-256 prefix matches the skip-nudge ELF | PASS |
| DRIFT_PREP and DRIFT_START present | PASS |
| Timing boundary is interpreter_Invoke_only | PASS |
| Exactly 60 minute samples | PASS |
| Minute and elapsed-second sequence valid | PASS |
| DRIFT_END completed = requested = 60, elapsed 3600 s | PASS |
| Sum of minute runs equals DRIFT_END total_runs | PASS |
| Zero failures | PASS |
| Zero output mismatches | PASS |
| Zero latency-overflow minutes | PASS |
| Free and minimum internal memory constant | PASS |

## Values re-derived from the minute records

| Quantity | Value |
|---|---|
| samples | 60 |
| total_runs | 8999 |
| mean_of_minute_means_us | 391104.317 |
| run_weighted_mean_us | 391104.317 |
| minute_mean_range_us | [391103.0, 391105.0] |
| mean_of_minute_p95_us | 391191.5 |
| min_of_minute_minima_us | 391015.0 |
| max_of_minute_maxima_us | 391197.0 |
| mean_cycles_range | [93864487.0, 93864910.0] |
| free_internal_bytes | [128720] |
| free_spiram_bytes | [0] |
| first10_mean_us | 391104.4 |
| last10_mean_us | 391104.0 |

For reference only: the 28 October skip-nudge 1,000-run capture had a mean of 391103.7 us.

Minute-level values are roll-ups printed by the firmware. The mean of minute P95 values is not a
global P95 over all inferences, and the run-weighted mean uses rounded minute means.
This audit covers one board, one build and the ten bundled images; it does not establish model
accuracy, all-input equivalence, energy use or robot safety.

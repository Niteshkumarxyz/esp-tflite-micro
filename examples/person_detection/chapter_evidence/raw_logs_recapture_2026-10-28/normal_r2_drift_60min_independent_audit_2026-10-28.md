# Normal R2 — 60-Minute Drift Independent Audit

- Audit date: 28 October 2026
- Firmware/configuration: Normal R2 no-trace build
- Test command: \drift 60\
- Timing boundary: \interpreter_Invoke_only\
- Raw log: \
ormal_r2_drift_60min_idf_monitor_20261028_224705.txt\
- Raw log SHA-256: B2868504977217FB079407F879733D71D7F26679ABDFFB728DB8E4FC8617FA14
- Audit result: PASS

## Duration and run accounting

| Check | Independently parsed result |
|---|---:|
| Parsed minute samples | 60 |
| Completed / requested minutes | 60 / 60 |
| Elapsed seconds | 3600 |
| Sum of per-minute runs | 8571 |
| Firmware-reported total runs | 8571 |
| Run total reconciliation | PASS |

## Failures and stability indicators

- Summed per-minute failures: 0
- Firmware-reported total failures: 0
- Summed per-minute output mismatches: 0
- Firmware-reported total output mismatches: 0
- Per-minute latency-overflow indicators: 0
- Firmware-reported P95-overflow minutes: 0
- Free internal memory across minute samples: 128720
- Minimum internal memory fields across minute samples: 128720
- Free SPIRAM across minute samples: 0

## Latency statistics from minute summaries

- Mean of the 60 reported minute means: 412502.55 us
- Run-weighted mean of rounded minute means (approximate): 412502.55 us
- Mean of the 60 reported minute P95 values: 412586.517 us
- Minimum of reported minute minima: 412408 us
- Maximum of reported minute maxima: 412607 us
- Mean-cycle values across minute summaries ranged from 98999956 to 99000426.

Important: the mean and P95 calculations above are derived from minute-level summaries. The mean of minute P95 values is not a global P95 of all individual inference latencies, and the weighted mean is approximate because minute-level means are rounded.

## Audit conclusion

All 60 expected minute records were parsed in sequence; the minute elapsed-time sequence and 3,600-second duration match the firmware summary. The summed per-minute run count reconciles to the reported total. The log reports no inference failures, output mismatches, or latency-overflow minutes. Internal-memory readings were stable across the recorded samples.

This audit validates the supplied raw log and its reported summaries. It does not prove model accuracy, all-input runtime equivalence, energy efficiency, or robot-level safety.

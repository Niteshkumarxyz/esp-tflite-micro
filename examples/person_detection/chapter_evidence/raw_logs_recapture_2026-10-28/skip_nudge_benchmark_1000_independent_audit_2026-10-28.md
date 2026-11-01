# Skip-nudge — Independent 1000-Run Benchmark Audit

Date: 2026-10-28
Target: ESP32-D0WD-V3, revision 3.1
Configuration: Skip-nudge, no-trace build
Timing scope: interpreter_Invoke_only

## Raw log provenance

File: skip_nudge_benchmark_1000_idf_monitor_20261028_221239.txt
SHA-256: 5DFB172A7D76E0F1E381A2FB300E531FE861FBD889D72016832ABE301893557C

## Independent verification

- Sample records: 1000
- Sample sequence from 1 through 1000: PASS
- 10-image cycle: PASS
- Failed samples: 0
- Firmware successful runs: 1000
- Firmware failures: 0

## Latency statistics

- Exact arithmetic mean: 391103.7 us
- Truncated integer mean: 391103 us
- Firmware-reported mean: 391103 us
- Exact median from the two middle samples: 391107 us
- Truncated integer median: 391107 us
- Firmware-reported median: 391107 us
- P95 nearest-rank: 391188 us
- Firmware-reported P95: 391188 us
- Minimum: 391015 us
- Maximum: 391191 us

## Reconciliation

The raw samples give an exact mean of 391103.7 us. Truncating it to an
integer gives 391103 us, matching the firmware summary.
The exact median is 391107 us; truncating it gives
391107 us, also matching the firmware summary.
P95, minimum, maximum, run count, and failure count match the summary.

## Interpretation and limitations

The benchmark measures interpreter Invoke only, not complete application
or end-to-end system latency. Results apply to this specific ESP32,
model, firmware configuration, and input workload.

This report documents the fresh Skip-nudge benchmark capture only.
The dedicated raw logs for the two 60-minute drift runs remain
not located and are not represented as archived in this report.

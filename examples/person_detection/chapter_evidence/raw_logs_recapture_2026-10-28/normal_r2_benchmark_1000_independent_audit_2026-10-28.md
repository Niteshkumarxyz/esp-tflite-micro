# Normal R2 — Independent 1000-Run Benchmark Audit

Date: 2026-10-28
Target: ESP32-D0WD-V3, revision 3.1
Configuration: Normal R2, no-trace build
Timing scope: interpreter_Invoke_only

## Raw log

File: normal_r2_benchmark_1000_idf_monitor_20261028_215556.txt
SHA-256: 83253740BB30B718B21F8878749E8671C052894006C6F927EE8BDB6F6235F072

## Independently verified results

- Sample records: 1000
- Sample sequence: 1 through 1000, valid
- Image cycle: image indices 0 through 9, repeated in sequence
- Failed runs: 0
- Mean latency: 412500 us
- Exact median from middle two samples: 412501.5 us
- Integer median using truncation: 412501 us
- Firmware-reported median: 412501 us
- P95 nearest-rank latency: 412582 us
- Minimum latency: 412407 us
- Maximum latency: 412583 us

## Median reconciliation

The 500th sorted sample is 412466 us and the 501st is 412537 us.
Their arithmetic mean is 412501.5 us. Truncating to an integer gives
412501 us, matching the firmware-reported median.

## Interpretation and limitations

The firmware summary and independently recalculated median agree when
the firmware's integer-truncation convention is applied. The benchmark
measures interpreter Invoke only, not complete application latency.

This report documents the fresh Normal R2 capture only. Dedicated
Skip-nudge benchmark and both configurations' 60-minute drift raw logs
remain not located unless separately recovered and verified.

# B.5-B.8 No-Trace Runtime Comparison and Drift Evidence

Date: 2026-10-28
Platform: ESP32-D0WD-V3, silicon revision 3.1
Application: person_detection
Timing scope: interpreter_Invoke_only
Trace mode: Disabled for B.5 benchmark builds

## 1. 1000-run benchmark results

| Metric | Normal R2 | Skip-nudge |
|---|---:|---:|
| Runs | 1000 | 1000 |
| Successful runs | 1000 | 1000 |
| Failures | 0 | 0 |
| Mean latency (us) | 412500 | 391103 |
| Median latency (us) | 412502 | 391106 |
| P95 nearest-rank (us) | 412582 | 391188 |
| Minimum latency (us) | 412406 | 391021 |
| Maximum latency (us) | 412583 | 391193 |

Reported mean-latency reduction with skip-nudge:
approximately 5.187% relative to Normal R2.

The shared benchmark results report matching outputs for all
1000 corresponding runs. These timings measure interpreter Invoke
only, not complete application or end-to-end system latency.

## 2. 60-minute drift results

| Metric | Normal R2 | Skip-nudge |
|---|---:|---:|
| Requested duration | 60 minutes | 60 minutes |
| Completed duration | 60 minutes | 60 minutes |
| Elapsed time | 3600 seconds | 3600 seconds |
| Total runs | 8571 | 8999 |
| Total failures | 0 | 0 |
| Output mismatches | 0 | 0 |
| P95 overflow minutes | 0 | 0 |

These are reported results for the tested ESP32, model, firmware,
and workload. They do not establish performance on other boards
or runtimes.

## 3. Firmware and configuration SHA-256

| Artifact | SHA-256 |
|---|---|
| Normal R2 firmware | B553E691EEC17E8E3DC1B1B39B4ACAB686AA90FAFFA6A6C1A6A0271F8FEE2DF0 |
| Skip-nudge firmware | 8EF30EF85A4BEDD393BE0891B0598857BB305C059F4D323ECB95E4BC37934C03 |
| Normal R2 sdkconfig | 3C1ECC3310A7EB9CFBBA435C0EC7B2B487CE637D4B9719B58B56B5C8DA9B62E3 |
| Skip-nudge sdkconfig | 08F6A77C762FC2B005DEEF1BAF55038CF77E16C00D7F41C7327800C31C1E8328 |

## 4. Raw-log availability and provenance

This summary records results reported in the serial-console outputs
shared during the research session.

A recursive search under the person_detection example located older
W1 benchmark logs and a 2026-10-22 drift log with a 600-minute
request. It did not locate dedicated raw log files for the
2026-10-28 Normal R2 and Skip-nudge 1000-run benchmarks or their
60-minute drift runs.

Therefore, this file is a summary record, NOT a substitute for the
original raw serial logs. The missing raw logs should be recovered
or exported if available and separately hashed before claiming that
the complete raw evidence package is archived.

## 5. Current conclusion

Both configurations reportedly completed their 60-minute tests with
zero failures and zero output mismatches. The 1000-run benchmark
summaries also report zero failures and matching corresponding
outputs. Skip-nudge showed a lower reported mean Invoke-only latency
in these measurements.

Interpret findings within this specific test setup. Preserve raw
logs, firmware binaries, configuration snapshots, and hashes together
for reproducibility.

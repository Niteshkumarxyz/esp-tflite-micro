# Fresh Paired Benchmark Audit — 28 October 2026

## Scope

Independent sample-level comparison of the fresh Normal R2 and Skip-nudge no-trace IDF Monitor captures. The timing boundary in the firmware logs is \interpreter_Invoke_only\.

## Paired validation

- Normal R2 parsed samples: 1000
- Skip-nudge parsed samples: 1000
- Sample sequence mismatches: 0
- Image-order mismatches: 0
- Non-success status pairs: 0
- Matching final raw INT8 output pairs: 1000 / 1000
- Final raw INT8 output mismatches: 0
- Audit result: PASS

The output comparison covers the two logged final output fields, \Person\ and \NoPerson\; it is not a comparison of all intermediate layer tensors.

## Latency

| Metric | Normal R2 | Skip-nudge |
|---|---:|---:|
| Samples | 1,000 | 1,000 |
| Truncated arithmetic mean (us) | 412500 | 391103 |
| P95 nearest-rank (us) | 412582 | 391188 |
| Minimum (us) | 412407 | 391015 |
| Maximum (us) | 412583 | 391191 |

- Exact mean paired latency difference (Normal minus Skip-nudge): 21396.652 us
- Mean latency reduction relative to Normal R2: 5.187%
- P95 difference (Normal minus Skip-nudge): 21394 us

## Input artifacts

- Normal R2 raw log: \
ormal_r2_benchmark_1000_idf_monitor_20261028_215556.txt\
- Normal R2 SHA-256: 83253740BB30B718B21F8878749E8671C052894006C6F927EE8BDB6F6235F072
- Skip-nudge raw log: \skip_nudge_benchmark_1000_idf_monitor_20261028_221239.txt\
- Skip-nudge SHA-256: 5DFB172A7D76E0F1E381A2FB300E531FE861FBD889D72016832ABE301893557C
- Paired CSV: \
ormal_r2_vs_skip_nudge_paired_1000run_2026-10-28.csv\

## Interpretation and limitations

These are two sequential captures for one ESP32-D0WD-V3 rev. 3.1, using the repeated ten-image sequence. The measured Skip-nudge latency was lower in this particular paired comparison, while the two recorded final output fields matched on all aligned runs. This is not a randomized multi-trial study and does not establish performance for all inputs, target variants, or operating conditions. Latency excludes the rest of the application path according to the firmware's timing label. The separately reported 60-minute drift summaries still lack their dedicated raw logs in the current evidence package.

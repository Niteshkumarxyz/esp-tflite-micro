# Research Milestone — 28 October 2026

## Result
Normal optimized R2 vs. R2 with CONFIG_NN_SKIP_NUDGE=y.

- Images compared: 12/12 passed.
- RQ1_TRACE summary records: 31 per image in each build.
- RQ1_RAW records: 3,625 per image in each build.
- Total raw records compared per build: 43,500.
- Differing raw record lines: 0.
- Final INT8 output values: matched for all 12 images.
- Corrected raw-trace integrity audit: 12/12 passed.
- Evidence ZIP verification: PASS.
- ZIP entries: 39.
- SHA-256 manifest entries: 38.
- Manifest file size/hash mismatches: 0.

## Firmware identities
Normal R2 BIN SHA-256:
F70EA1D4FF93289BB32BB3C89B20A70C3C232264B1B9B3793BEC43EB94D9F4BE

Skip-nudge R2 BIN SHA-256:
F8957C85437CA1AF1293447058CAABAEDAB3C0280EA580AE8397B9CAC33F2994

Evidence ZIP SHA-256:
0C0572858A8B99FE9B340276F77E1905E11ADB195F339DDDF906841CB08E5251

## Comparison report
r2_normal_vs_skip_nudge_12_image_final_comparison_2026-10-28.csv

## Evidence package
r2_normal_vs_skip_nudge_final_evidence_2026-10-28.zip

## Scope and limitations
The findings apply to the tested 12 static images, ESP32 hardware, model,
and recorded runtime configurations. They do not establish equivalence
for every possible input or demonstrate a performance improvement.

Raw-trace logging latencies must not be reported as normal inference
latencies because of the large serial trace dump.

## Status
Normal R2 vs. skip-nudge static-image tensor-equivalence evidence is
captured, compared, independently checked, and packaged.

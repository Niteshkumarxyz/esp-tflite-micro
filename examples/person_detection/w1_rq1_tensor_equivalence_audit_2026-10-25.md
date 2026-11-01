# RQ1 INT8 Tensor-Equivalence Audit

**Audit date:** 25 October 2026  
**Platform:** ESP32-D0WD-V3, revision 3.1  
**Runtime comparison:** R1 reference vs. R2 optimized ESP-NN  
**Model/task:** INT8 person detection  
**Test scope:** Static input images 0–11

## Results

- Images passed: 12/12
- Identical tensor instances: 372/372
- Different tensors: 0
- Incomplete tensors: 0
- Missing evidence artifacts: 0
- Evidence manifest entries: 39

## Per-image results

| Image | Equal tensors | Different | Incomplete | Status |
|---:|---:|---:|---:|---|
| 0 | 31/31 | 0 | 0 | PASS |
| 1 | 31/31 | 0 | 0 | PASS |
| 2 | 31/31 | 0 | 0 | PASS |
| 3 | 31/31 | 0 | 0 | PASS |
| 4 | 31/31 | 0 | 0 | PASS |
| 5 | 31/31 | 0 | 0 | PASS |
| 6 | 31/31 | 0 | 0 | PASS |
| 7 | 31/31 | 0 | 0 | PASS |
| 8 | 31/31 | 0 | 0 | PASS |
| 9 | 31/31 | 0 | 0 | PASS |
| 10 | 31/31 | 0 | 0 | PASS |
| 11 | 31/31 | 0 | 0 | PASS |

## Firmware and evidence integrity

- R1 firmware SHA-256: F950CCCAABF997C9EDA95FDB6CF511DA829B0026095A09421B06AFB02781BC20
- R2 firmware SHA-256: 5A203D09CE34978158C6D3032FB7142BF2559756C5D088D8E6B9BBEF45468CB4
- Summary CSV SHA-256: 0FD8D1BEF96A9E989664ACA99877C5B5B69C8E14E75D483EE92CB952188A7FD1
- Evidence manifest SHA-256: Recorded separately after finalizing the manifest to avoid a circular hash dependency.

## Interpretation

For each of the 12 tested static images, the captured raw INT8 bytes for all 31 traced tensors were identical between the R1 reference runtime and R2 optimized ESP-NN runtime. Across the corpus, all 372 image–tensor comparisons passed.

This establishes bitwise tensor equivalence for the tested images and recorded builds. It does not establish equivalence for every possible input, every hardware platform, or a closed-loop robotic system.

The diagnostic tracing runs introduce substantial logging overhead. Their reported inference times must not be treated as normal runtime benchmark measurements.

## Reproducibility artifacts

The evidence manifest lists the raw R1 and R2 logs, per-image tensor-comparison CSVs, firmware binaries, and consolidated summary CSV, together with file sizes and SHA-256 hashes.

**Final audit validation: PASS**


# W1 1000-Run Statistical Audit

Audit date: 2026-10-25

## Source
Log: examples/person_detection/log.person_detection.20261024224848.txt

Log SHA-256:
C8A7DFCC60D66A07C3F8A95ACCA629CD27FC36A9AE22D17D3DD0DBC6BE7C1109

## Independently recalculated results
Samples: 1000
Successful runs: 1000
Failures: 0
Invalid sample sequence: 0
Mean latency: 412864 us
Median latency: 412866 us
P95 nearest-rank latency: 412887 us
Minimum latency: 412839 us
Maximum latency: 412910 us

Image coverage: IDs 0-9, 100 samples per image.

All recalculated statistics match the recorded BENCH_SUMMARY
and the benchmark manifest.

## Provenance limitation
The manifest records firmware SHA-256:
C144B7FF33139E2C12810430893F5016EBCF53B0030669EAAB65E0B2BFFB3B48

The original benchmark binary was not found in the scanned locations.
The current binary and three other artifacts have hashes that differ
from the manifest. Therefore, exact historical firmware identity
remains partially unverified.

## Interpretation
These results characterize 1000 invocations over the bundled
10-image set, with each image used 100 times. They are not evidence
of testing 1000 distinct images or of generalization accuracy.

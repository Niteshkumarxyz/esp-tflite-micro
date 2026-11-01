# Evidence Package Release Record — V5

- Release date: 29 October 2026
- Package: final_runtime_evidence_2026-10-29_v5.zip
- Package size: 14503729 bytes
- Package SHA-256: 4763817F6B780D8C967EC84367A93F0B9200EA90CB5BA88C51B591E42D7BDDE5
- Manifest records: 28
- ZIP entries: 29
- Extraction verification: PASS — all 28 manifest-listed files matched their recorded sizes and SHA-256 hashes.
- Extracted manifest: matches the staging manifest.
- ZIP checksum sidecar: written to final_runtime_evidence_2026-10-29_v5.zip.sha256.txt.

## Newly included drift evidence

- Normal R2 drift raw log SHA-256: B2868504977217FB079407F879733D71D7F26679ABDFFB728DB8E4FC8617FA14
- Normal R2 drift independent audit SHA-256: 095C321FED620BAFE40B9D51CD780934C2494B3E3F57E3D1F2A63C6EB9FE33D8
- Duration: 60/60 minute samples, 3600 seconds.
- Recorded runs: 8571; failures: 0; output mismatches: 0; latency overflow minutes: 0.
- Mean of minute-level mean latency summaries: approximately 412502.55 us.
- Mean of minute-level P95 summaries: approximately 412586.517 us; this is not a global P95.
- Skip-nudge 60-minute raw drift log and independent audit remain absent from this package.

The benchmark and equivalence findings remain limited to the documented inputs, firmware builds, and timing boundaries in README.md. This package does not establish end-to-end robot latency or robot safety.

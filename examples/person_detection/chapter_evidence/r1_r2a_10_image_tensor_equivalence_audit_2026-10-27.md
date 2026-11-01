# R1 vs R2A ? 10-image tensor-equivalence audit

Date: 2026-10-27

Scope: R1 reference diagnostic firmware vs R2A ANSI C diagnostic firmware
on the same ESP32 board, comparing the captured INT8 tensor bytes for
images 1 through 10.

The report uses the verified Image 4 R2A retry capture.
Trace-mode latency is diagnostic and is not used as a normal inference benchmark.

| Image | R1 audit | R2A audit | Identical groups | Different groups | Output match | Comparison |
|---:|---|---|---:|---:|---|---|
| 1 | PASS | PASS | 31/31 | 0 | PASS | PASS |
| 2 | PASS | PASS | 31/31 | 0 | PASS | PASS |
| 3 | PASS | PASS | 31/31 | 0 | PASS | PASS |
| 4 | PASS | PASS | 31/31 | 0 | PASS | PASS |
| 5 | PASS | PASS | 31/31 | 0 | PASS | PASS |
| 6 | PASS | PASS | 31/31 | 0 | PASS | PASS |
| 7 | PASS | PASS | 31/31 | 0 | PASS | PASS |
| 8 | PASS | PASS | 31/31 | 0 | PASS | PASS |
| 9 | PASS | PASS | 31/31 | 0 | PASS | PASS |
| 10 | PASS | PASS | 31/31 | 0 | PASS | PASS |

## Aggregate result

- Images processed: 10/10
- Tensor groups compared: 310
- Byte-identical tensor groups: 310
- Differing tensor groups: 0
- All image comparisons passed: YES

## Interpretation and limitations

A PASS means the two captured traces had structurally valid raw tensor records,
their common tensor groups were byte-identical, and their final INT8 result
fields matched for that tested image. The finding is limited to these 10 images
and these two captured configurations; it does not establish equivalence for all
possible inputs, boards, compiler versions, or hardware runtimes.

The trace-mode latency values are diagnostic measurements with extensive raw
tensor serial logging. They must not be interpreted as normal inference latency
or substituted for the separately captured benchmark measurements.

## Source trace files and integrity

### Image 1

- R1 file: `r1_reference_trace_image1_2026-10-27.txt`
- R1 SHA-256: `19375e38e4e7b9ff26a5f5bce49f933fd3f8f8f5ae73cb024528f49a1a021196`
- R2A file: `r2a_ansi_c_trace_image1_2026-10-27.txt`
- R2A SHA-256: `91cbd7a43cb74371979074369e3327b52e77a7ce548e705d3cf779687ed3dcc7`
- R1 structural audit errors: 0
- R2A structural audit errors: 0
- Person INT8: `-39`
- No-person INT8: `39`
- R1 diagnostic latency: `62212 ms`
- R2A diagnostic latency: `58595 ms`
- Comparison: **PASS**

### Image 2

- R1 file: `r1_reference_trace_image2_2026-10-27.txt`
- R1 SHA-256: `d19ab04f07a42fd0556f7a61664e630cd6bc128a15dbf4289de643e13ec98ab8`
- R2A file: `r2a_ansi_c_trace_image2_2026-10-27.txt`
- R2A SHA-256: `611a71dda1ef661ae6d0026e26af2afd4a3e567cf8179de54b6ef4bb47ce4d40`
- R1 structural audit errors: 0
- R2A structural audit errors: 0
- Person INT8: `115`
- No-person INT8: `-115`
- R1 diagnostic latency: `62213 ms`
- R2A diagnostic latency: `58599 ms`
- Comparison: **PASS**

### Image 3

- R1 file: `r1_reference_trace_image3_2026-10-27.txt`
- R1 SHA-256: `c0ecfc335b5a8f1fbe99220b2be96806f9b02f32c56af9979265715ba74eab3d`
- R2A file: `r2a_ansi_c_trace_image3_2026-10-27.txt`
- R2A SHA-256: `7e5812a49a16049cca0838071b6bc39317af9c0397742e22d6cf4e25743c6544`
- R1 structural audit errors: 0
- R2A structural audit errors: 0
- Person INT8: `67`
- No-person INT8: `-67`
- R1 diagnostic latency: `62212 ms`
- R2A diagnostic latency: `58595 ms`
- Comparison: **PASS**

### Image 4

- R1 file: `r1_reference_trace_image4_2026-10-27.txt`
- R1 SHA-256: `6397eec6354a98bb10b4b025aac0cd86f65be365a3e97f8eb3a7874aab581321`
- R2A file: `r2a_ansi_c_trace_image4_retry1_2026-10-27.txt`
- R2A SHA-256: `516ec9006dab1cbc48e4ca47d0cdf196f1f2028dbaf883c1388f5988226d0b94`
- R1 structural audit errors: 0
- R2A structural audit errors: 0
- Person INT8: `111`
- No-person INT8: `-111`
- R1 diagnostic latency: `62213 ms`
- R2A diagnostic latency: `58598 ms`
- Comparison: **PASS**

### Image 5

- R1 file: `r1_reference_trace_image5_2026-10-27.txt`
- R1 SHA-256: `759e43ed0067bed8ae86bc2230775ae591f476d1af44204a0976e659e74bb49a`
- R2A file: `r2a_ansi_c_trace_image5_2026-10-27.txt`
- R2A SHA-256: `d8f30a60cbeb289ab72a9eb8c162561e9bbdf2c865932770777c3f9bc12ec1be`
- R1 structural audit errors: 0
- R2A structural audit errors: 0
- Person INT8: `-100`
- No-person INT8: `100`
- R1 diagnostic latency: `62213 ms`
- R2A diagnostic latency: `58595 ms`
- Comparison: **PASS**

### Image 6

- R1 file: `r1_reference_trace_image6_2026-10-27.txt`
- R1 SHA-256: `08b9999ecbe5d475108bb3a51d698a0f3a2eac2c5817616b46b889bb1b155950`
- R2A file: `r2a_ansi_c_trace_image6_2026-10-27.txt`
- R2A SHA-256: `1a4312b87aeee2fbd9f11f372c81cc2ec9e5c432e73647dd05f5adc0f4a39a3e`
- R1 structural audit errors: 0
- R2A structural audit errors: 0
- Person INT8: `97`
- No-person INT8: `-97`
- R1 diagnostic latency: `62213 ms`
- R2A diagnostic latency: `58598 ms`
- Comparison: **PASS**

### Image 7

- R1 file: `r1_reference_trace_image7_2026-10-27.txt`
- R1 SHA-256: `606bf46db37250c0a21547c84c83e88c557fbe33f923e07c63b07b6a89094982`
- R2A file: `r2a_ansi_c_trace_image7_2026-10-27.txt`
- R2A SHA-256: `7d59eb5b984d0113d5864408b9631d0328692c02fecd85628c303ebba9c87a35`
- R1 structural audit errors: 0
- R2A structural audit errors: 0
- Person INT8: `-98`
- No-person INT8: `98`
- R1 diagnostic latency: `62212 ms`
- R2A diagnostic latency: `58596 ms`
- Comparison: **PASS**

### Image 8

- R1 file: `r1_reference_trace_image8_2026-10-27.txt`
- R1 SHA-256: `b1b5fabd5dc906e509047a68bcaca43a9e81a0f9e20a8f7b27b0e6a6f13bbcba`
- R2A file: `r2a_ansi_c_trace_image8_2026-10-27.txt`
- R2A SHA-256: `4a3a44ba09cf2b18e301c648dc39e4df494d893fde2fc774f69eee964d74e5f4`
- R1 structural audit errors: 0
- R2A structural audit errors: 0
- Person INT8: `114`
- No-person INT8: `-114`
- R1 diagnostic latency: `62212 ms`
- R2A diagnostic latency: `58595 ms`
- Comparison: **PASS**

### Image 9

- R1 file: `r1_reference_trace_image9_2026-10-27.txt`
- R1 SHA-256: `88c6d315a43ef67646c5327dd44a1ddff47a80a4d4ae640c43b77096d8541478`
- R2A file: `r2a_ansi_c_trace_image9_2026-10-27.txt`
- R2A SHA-256: `92667e4cde8b1a6b0d9e56636e5a5a48b9f89714a3193bf795622fb9d7cca691`
- R1 structural audit errors: 0
- R2A structural audit errors: 0
- Person INT8: `83`
- No-person INT8: `-83`
- R1 diagnostic latency: `62211 ms`
- R2A diagnostic latency: `58598 ms`
- Comparison: **PASS**

### Image 10

- R1 file: `r1_reference_trace_image10_2026-10-27.txt`
- R1 SHA-256: `a600a751dfd093ef19f8af0494f939c50cb9c1812c6a9fe6724ff53a7652d470`
- R2A file: `r2a_ansi_c_trace_image10_2026-10-27.txt`
- R2A SHA-256: `66360908c2da82b31f0a74ee639cd5b4d06badbb85e75590c8b8f20e9f77ab9d`
- R1 structural audit errors: 0
- R2A structural audit errors: 0
- Person INT8: `113`
- No-person INT8: `-113`
- R1 diagnostic latency: `62212 ms`
- R2A diagnostic latency: `58595 ms`
- Comparison: **PASS**


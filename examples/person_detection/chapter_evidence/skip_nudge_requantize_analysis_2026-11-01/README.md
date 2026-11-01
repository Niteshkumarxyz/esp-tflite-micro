# Skip-nudge requantize analysis (1 November 2026)

Question from the editor (30 Oct): ESP-NN's NN_SKIP_NUDGE is documented as "fast (non-bit-exact)", "may differ from the
TFLite reference by +/-1 LSB at half-shift boundaries", yet the R2-SN build matched R1 at all 372 operator hashes and
1,000 paired runs. Why?

Source compared: ESP-NN 1.4.1 `src/common/common_functions.h` from the person_detection managed component
(SHA-256 350ffcdbc3f834896c041479dcbe8b6be51900c520d68802e1ebabfbccb10efd). On the classic ESP32 the optimized kernels
call `esp_nn_requantize`, which maps to `esp_nn_multiply_by_quantized_mult_fast` when CONFIG_NN_SKIP_NUDGE is set and to
`esp_nn_multiply_by_quantized_mult` otherwise. The ESP32-S3 assembly file is not compiled for the classic ESP32.

Files
- test.c, test2.c: host tests that include the unmodified header and compare the two functions (gcc -O2 -fwrapv).
- test2_output.txt: 100,000,000 random cases in three ranges and 166,400,000 exact multiply ties.
- bound.py, bound_w1_output.txt, bound_w2_output.txt: upper bound on |acc| for every conv, depthwise and FC layer.

Result
- |acc| < 2^26 and |acc| < 2^29: 0 differences in 66,666,667 random cases; 0 differences in 166,400,000 exact ties
  of the doubling high multiply; 0 differences in 6,000,000 exact ties of the rounding right shift.
- Any int32: every difference (206,842 of 33,333,333) is a value before the right shift within 2^(e-1) of INT32_MAX,
  where the fast division overflows and flips the sign of a saturated result.
- W1: largest possible |acc| is 3,424,134 (2^21.7), every multiplier is below 1 (no left shift), so no W1 input can reach
  the overflow region. W2: 815,991 (2^19.6).
- Conclusion (for this library version, this chip's C path and these models): the skip-nudge path is bit-identical to the
  reference for every value the models can produce; the documented +/-1 LSB difference does not occur in the classic
  ESP32 C path.

/* Compare ESP-NN 1.4.1 bit-exact and skip-nudge (fast) requantize, exactly as compiled for the classic ESP32 (C path). */
#include <stdio.h>
#include <stdint.h>
#include <limits.h>
#include "common_functions.h"

static uint64_t s = 0x9E3779B97F4A7C15ull;
static inline uint64_t rnd(void) { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return s; }

static long long n_total = 0, n_diff = 0;
static void check(int32_t x, int32_t m, int32_t sh, const char *tag, int print) {
    int32_t a = esp_nn_multiply_by_quantized_mult(x, m, sh);
    int32_t b = esp_nn_multiply_by_quantized_mult_fast(x, m, sh);
    n_total++;
    if (a != b) { n_diff++; if (print) printf("  %s: x=%d m=%d shift=%d ref=%d fast=%d\n", tag, x, m, sh, a, b); }
}

int main(void) {
    /* 1. random accumulators in the int8 range of a real layer and in the full int32 range */
    for (long i = 0; i < 50000000; i++) {
        int32_t m = (int32_t)(0x40000000u + (rnd() % 0x40000000u));     /* Q31 multiplier in [0.5, 1) */
        int32_t sh = -(int32_t)(rnd() % 32);                            /* right shifts 0..31 */
        int32_t x = (i & 1) ? (int32_t)(rnd() % (1u << 27)) - (1 << 26)  /* |acc| < 2^26 */
                            : (int32_t)rnd();                            /* any int32 */
        check(x, m, sh, "random", n_diff < 5);
    }
    long long d1 = n_diff; printf("random: %lld cases, %lld differ\n", n_total, d1);

    /* 2. exact ties in the doubling high multiply: x*m = odd * 2^30, both signs */
    long long t0 = n_total; n_diff = 0;
    for (int a = 0; a <= 30; a++) for (int k = 0; k < 20000; k++) {
        int b = 30 - a;
        int64_t u = (int64_t)(rnd() % (1u << (31 - a > 30 ? 30 : 31 - a))) | 1;  /* odd */
        int64_t w = (int64_t)(rnd() % (1u << (31 - b > 30 ? 30 : 31 - b))) | 1;
        int64_t x = u << a, m = w << b;
        if (x > INT32_MAX || m > INT32_MAX || m <= 0) continue;
        int32_t sh = -(int32_t)(rnd() % 32);
        check((int32_t)x, (int32_t)m, sh, "tie-mult+", n_diff < 5);
        check((int32_t)-x, (int32_t)m, sh, "tie-mult-", n_diff < 5);
    }
    printf("ties in the multiply: %lld cases, %lld differ\n", n_total - t0, n_diff);

    /* 3. exact ties in the right shift: value before the shift = q*2^e +/- 2^(e-1), m = 2^31-1 is not exact,
          so test the division helpers directly over every exponent */
    long long dd = 0, dn = 0;
    for (int e = 1; e <= 30; e++) for (int k = 0; k < 200000; k++) {
        int32_t q = (int32_t)(rnd() % (1u << (31 - e))) - (1 << (30 - e));
        int32_t v = (int32_t)((int64_t)q * (1LL << e) + ((k & 1) ? (1 << (e - 1)) : -(1 << (e - 1))));
        int32_t r1 = esp_nn_div_by_power_of_two(v, e), r2 = esp_nn_div_by_power_of_two_fast(v, e);
        dn++; if (r1 != r2) { dd++; if (dd < 5) printf("  tie-shift: v=%d e=%d ref=%d fast=%d\n", v, e, r1, r2); }
    }
    printf("ties in the shift: %lld cases, %lld differ\n", dn, dd);

    /* 4. the overflow boundary: value before the shift within 2^(e-1) of INT32_MAX */
    long long od = 0, on = 0;
    for (int e = 1; e <= 30; e++) for (int32_t off = 0; off < 4; off++) {
        int32_t v = INT32_MAX - off;
        int32_t r1 = esp_nn_div_by_power_of_two(v, e), r2 = esp_nn_div_by_power_of_two_fast(v, e);
        on++; if (r1 != r2) { od++; if (od <= 3) printf("  overflow: v=%d e=%d ref=%d fast=%d\n", v, e, r1, r2); }
    }
    printf("near INT32_MAX: %lld cases, %lld differ\n", on, od);
    return 0;
}

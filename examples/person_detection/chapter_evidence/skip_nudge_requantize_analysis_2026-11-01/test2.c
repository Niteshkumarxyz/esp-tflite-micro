#include <stdio.h>
#include <stdint.h>
#include <limits.h>
#include "common_functions.h"
static uint64_t s = 0x9E3779B97F4A7C15ull;
static inline uint64_t rnd(void) { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return s; }
/* classify a mismatch: is the value before the shift within 2^(e-1) of INT32_MAX (the fast division overflows)? */
static long long tot[3], dif[3], ovf[3];
static void check(int c, int32_t x, int32_t m, int32_t sh) {
    int32_t a = esp_nn_multiply_by_quantized_mult(x, m, sh), b = esp_nn_multiply_by_quantized_mult_fast(x, m, sh);
    tot[c]++;
    if (a != b) {
        dif[c]++;
        int32_t e = -sh;
        int32_t pre = esp_nn_sat_round_doubling_high_mul(x, m);
        if (e > 0 && (int64_t)pre + ((1LL << (e - 1)) - (pre < 0)) > INT32_MAX) ovf[c]++;
    }
}
int main(void) {
    for (long i = 0; i < 100000000; i++) {
        int32_t m = (int32_t)(0x40000000u + (rnd() % 0x40000000u));
        int32_t sh = -(int32_t)(rnd() % 32);
        int32_t x;
        int c = i % 3;
        if (c == 0) x = (int32_t)(rnd() % (1u << 27)) - (1 << 26);     /* |acc| < 2^26 */
        else if (c == 1) x = (int32_t)(rnd() % (1u << 30)) - (1 << 29); /* |acc| < 2^29 */
        else x = (int32_t)rnd();                                         /* any int32 */
        check(c, x, m, sh);
    }
    /* exact ties with small accumulators: x*m = odd*2^30, |x| < 2^26 */
    long long tt = 0, td = 0;
    for (int a = 0; a <= 25; a++) for (int k = 0; k < 100000; k++) {
        int b = 30 - a;
        int64_t u = (int64_t)(rnd() % (1u << (26 - a))) | 1;
        int64_t w = 1;
        while (1) { w = (int64_t)(rnd() % (1u << (31 - b))) | 1; if ((w << b) >= 0x40000000LL && (w << b) <= INT32_MAX) break; if (b == 30) { w = 1; break; } }
        int64_t x = u << a, m = w << b;
        if (x >= (1 << 26) || m > INT32_MAX) continue;
        for (int sgn = -1; sgn <= 1; sgn += 2) for (int sh = 0; sh <= 31; sh += 1) {
            tt++; if (esp_nn_multiply_by_quantized_mult((int32_t)(sgn * x), (int32_t)m, -sh) != esp_nn_multiply_by_quantized_mult_fast((int32_t)(sgn * x), (int32_t)m, -sh)) td++;
        }
    }
    const char *nm[3] = {"|acc| < 2^26", "|acc| < 2^29", "any int32"};
    for (int c = 0; c < 3; c++) printf("%-13s %lld cases, %lld differ, of which %lld at the INT32_MAX overflow\n", nm[c], tot[c], dif[c], ovf[c]);
    printf("exact multiply ties, |acc| < 2^26, all 32 shifts: %lld cases, %lld differ\n", tt, td);
    return 0;
}

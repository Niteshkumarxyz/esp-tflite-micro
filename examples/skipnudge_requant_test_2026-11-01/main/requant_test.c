/*
 * On-chip comparison of ESP-NN 1.4.1's bit-exact requantize (esp_nn_multiply_by_quantized_mult) and its
 * skip-nudge requantize (esp_nn_multiply_by_quantized_mult_fast), compiled for the classic ESP32 with the
 * same header the optimized kernels use. Prints REQ_RESULT lines and REQ_DONE.
 */
#include <stdio.h>
#include <stdint.h>
#include <limits.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_timer.h"
#include "common_functions.h"

static uint64_t s = 0x9E3779B97F4A7C15ull;
static inline uint64_t rnd(void) { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return s; }

typedef struct { long long cases, differ, overflow; } tally_t;

static void check(tally_t *t, int32_t x, int32_t m, int32_t sh)
{
    int32_t a = esp_nn_multiply_by_quantized_mult(x, m, sh);
    int32_t b = esp_nn_multiply_by_quantized_mult_fast(x, m, sh);
    t->cases++;
    if (a != b) {
        t->differ++;
        int32_t e = -sh;
        int32_t pre = esp_nn_sat_round_doubling_high_mul(x, m);
        if (e > 0 && (int64_t)pre + ((1LL << (e - 1)) - (pre < 0)) > INT32_MAX) {
            t->overflow++;
        }
        if (t->differ <= 3) {
            printf("REQ_EXAMPLE,x=%ld,m=%ld,shift=%ld,ref=%ld,fast=%ld\n", (long)x, (long)m, (long)sh, (long)a, (long)b);
        }
    }
}

static void report(const char *name, const tally_t *t)
{
    printf("REQ_RESULT,set=%s,cases=%lld,differ=%lld,at_int32_max_overflow=%lld\n", name, t->cases, t->differ, t->overflow);
}

void app_main(void)
{
    vTaskDelay(pdMS_TO_TICKS(500));
    printf("REQ_BEGIN,header=esp-nn-1.4.1-common_functions.h,cpu_mhz=%d\n", CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ);
    int64_t t0 = esp_timer_get_time();
    tally_t r26 = {0}, r29 = {0}, rall = {0}, ties = {0};
    for (long i = 0; i < 3000000; i++) {
        int32_t m = (int32_t)(0x40000000u + (uint32_t)(rnd() % 0x40000000u));
        int32_t sh = -(int32_t)(rnd() % 32);
        int c = i % 3;
        if (c == 0) check(&r26, (int32_t)(rnd() % (1u << 27)) - (1 << 26), m, sh);
        else if (c == 1) check(&r29, (int32_t)(rnd() % (1u << 30)) - (1 << 29), m, sh);
        else check(&rall, (int32_t)rnd(), m, sh);
        if ((i & 0xFFFF) == 0) vTaskDelay(1);
    }
    report("random_acc_below_2^26", &r26);
    report("random_acc_below_2^29", &r29);
    report("random_any_int32", &rall);

    /* exact ties of the doubling high multiply: x*m = odd * 2^30 with |x| < 2^26, both signs, every right shift */
    for (int a = 0; a <= 25; a++) {
        for (int k = 0; k < 2000; k++) {
            int b = 30 - a;
            int64_t u = (int64_t)(rnd() % (1u << (26 - a))) | 1;
            int64_t w = 1;
            for (int tries = 0; tries < 64; tries++) {
                w = (int64_t)(rnd() % (1u << (31 - b))) | 1;
                if ((w << b) >= 0x40000000LL && (w << b) <= INT32_MAX) break;
                if (b == 30) { w = 1; break; }
            }
            int64_t x = u << a, m = w << b;
            if (x >= (1 << 26) || m > INT32_MAX) continue;
            for (int sgn = -1; sgn <= 1; sgn += 2)
                for (int sh = 0; sh <= 31; sh++) check(&ties, (int32_t)(sgn * x), (int32_t)m, -sh);
        }
        vTaskDelay(1);
    }
    report("exact_multiply_ties_acc_below_2^26", &ties);

    /* exact ties of the rounding right shift, every exponent, both signs */
    long long sd = 0, sn = 0;
    for (int e = 1; e <= 30; e++) {
        for (int k = 0; k < 20000; k++) {
            int32_t q = (int32_t)(rnd() % (1u << (31 - e))) - (1 << (30 - e));
            int32_t v = (int32_t)((int64_t)q * (1LL << e) + ((k & 1) ? (1 << (e - 1)) : -(1 << (e - 1))));
            sn++;
            if (esp_nn_div_by_power_of_two(v, e) != esp_nn_div_by_power_of_two_fast(v, e)) sd++;
        }
        vTaskDelay(1);
    }
    printf("REQ_RESULT,set=exact_shift_ties,cases=%lld,differ=%lld,at_int32_max_overflow=0\n", sn, sd);

    /* the overflow boundary: value before the shift within 2^(e-1) of INT32_MAX */
    long long od = 0, on = 0;
    for (int e = 1; e <= 30; e++) {
        for (int off = 0; off < 4; off++) {
            volatile int32_t v = INT32_MAX - off;
            on++;
            if (esp_nn_div_by_power_of_two(v, e) != esp_nn_div_by_power_of_two_fast(v, e)) od++;
        }
    }
    printf("REQ_RESULT,set=near_int32_max,cases=%lld,differ=%lld,at_int32_max_overflow=%lld\n", on, od, od);
    printf("REQ_DONE,elapsed_us=%lld\n", (long long)(esp_timer_get_time() - t0));
    while (1) vTaskDelay(pdMS_TO_TICKS(1000));
}

from pathlib import Path
from datetime import datetime
import shutil

files = [Path('main/esp_main.h'), Path('main/main_functions.cc'), Path('main/esp_cli.c')]
if any(not p.is_file() for p in files):
    raise SystemExit('Run from the person_detection project directory; required source file missing.')
header_path, mf_path, cli_path = files
header, mf, cli = [p.read_text(encoding='utf-8') for p in files]
if 'g_benchmark_mode' in header or 'benchmark_cli_handler' in cli:
    raise SystemExit('Benchmark markers already exist; refusing to apply twice.')

header_anchor = 'extern void run_inference(void *ptr);'
if header.count(header_anchor) != 1:
    raise SystemExit('Unexpected esp_main.h layout; no files changed.')
new_header = header.replace(header_anchor, header_anchor + '''\nextern volatile int g_benchmark_mode;\nextern volatile int g_last_invoke_ok;\nextern volatile long long g_last_invoke_us;\nextern volatile int g_last_raw_person;\nextern volatile int g_last_raw_no_person;''', 1)

include_anchor = '#include "esp_main.h"'
if mf.count(include_anchor) != 1:
    raise SystemExit('Unexpected main_functions.cc includes; no files changed.')
new_mf = mf.replace(include_anchor, include_anchor + '''\n\nextern "C" {\nvolatile int g_benchmark_mode = 0;\nvolatile int g_last_invoke_ok = 1;\nvolatile long long g_last_invoke_us = 0;\nvolatile int g_last_raw_person = 0;\nvolatile int g_last_raw_no_person = 0;\n}\n''', 1)
start = '''#if defined(COLLECT_CPU_STATS)
  long long start_time = esp_timer_get_time();
#endif
  // Run the model on this input and make sure it succeeds.
  TfLiteStatus invoke_status = interpreter->Invoke();
  if (invoke_status != kTfLiteOk) {
    MicroPrintf("Invoke failed.");
  }

#if defined(COLLECT_CPU_STATS)
  long long total_time = (esp_timer_get_time() - start_time);
  if (invoke_status == kTfLiteOk) {
    printf("INVOKE_US=%lld\\n", total_time);
  } else {
    printf("INVOKE_FAILED=1\\n");
  }
  //printf("Softmax time = %lld\\n", softmax_total_time / 1000);
  printf("FC time = %lld\\n", fc_total_time / 1000);
  printf("DC time = %lld\\n", dc_total_time / 1000);
  printf("conv time = %lld\\n", conv_total_time / 1000);
  printf("Pooling time = %lld\\n", pooling_total_time / 1000);
  printf("add time = %lld\\n", add_total_time / 1000);
  printf("mul time = %lld\\n", mul_total_time / 1000);

  /* Reset times */
  total_time = 0;
  //softmax_total_time = 0;
  dc_total_time = 0;
  conv_total_time = 0;
  fc_total_time = 0;
  pooling_total_time = 0;
  add_total_time = 0;
  mul_total_time = 0;
#endif

  TfLiteTensor* output = interpreter->output(0);
  if (invoke_status == kTfLiteOk) {
    printf("RAW_OUTPUT_INT8=%d,%d\\n", (int)output->data.int8[kPersonIndex], (int)output->data.int8[kNotAPersonIndex]);
  }'''
# The current source contains backslash-n sequences in C string literals.
start = start.replace('\\\\n', '\\n')
if new_mf.count(start) != 1:
    raise SystemExit('Inference timing block did not match exactly; no files changed.')
replacement = '''#if defined(COLLECT_CPU_STATS)
  long long start_time = esp_timer_get_time();
#endif
  TfLiteStatus invoke_status = interpreter->Invoke();
  g_last_invoke_ok = (invoke_status == kTfLiteOk) ? 1 : 0;
  if (invoke_status != kTfLiteOk && !g_benchmark_mode) {
    MicroPrintf("Invoke failed.");
  }

#if defined(COLLECT_CPU_STATS)
  long long total_time = (esp_timer_get_time() - start_time);
  g_last_invoke_us = total_time;
  if (!g_benchmark_mode) {
    if (invoke_status == kTfLiteOk) printf("INVOKE_US=%lld\\n", total_time);
    else printf("INVOKE_FAILED=1\\n");
    printf("FC time = %lld\\n", fc_total_time / 1000);
    printf("DC time = %lld\\n", dc_total_time / 1000);
    printf("conv time = %lld\\n", conv_total_time / 1000);
    printf("Pooling time = %lld\\n", pooling_total_time / 1000);
    printf("add time = %lld\\n", add_total_time / 1000);
    printf("mul time = %lld\\n", mul_total_time / 1000);
  }
  dc_total_time = 0;
  conv_total_time = 0;
  fc_total_time = 0;
  pooling_total_time = 0;
  add_total_time = 0;
  mul_total_time = 0;
#endif

  TfLiteTensor* output = interpreter->output(0);
  if (invoke_status == kTfLiteOk) {
    g_last_raw_person = (int)output->data.int8[kPersonIndex];
    g_last_raw_no_person = (int)output->data.int8[kNotAPersonIndex];
    if (!g_benchmark_mode) {
      printf("RAW_OUTPUT_INT8=%d,%d\\n", g_last_raw_person, g_last_raw_no_person);
    }
  }'''
if new_mf.count(replacement) != 0:
    raise SystemExit('Internal patch error; no files changed.')
new_mf = new_mf.replace(start, replacement, 1)
respond = '  RespondToDetection(person_score_f, no_person_score_f);'
idx = new_mf.rfind(respond)
if idx < 0 or new_mf.find(respond) == idx:
    raise SystemExit('Could not uniquely identify run_inference RespondToDetection call; no files changed.')
new_mf = new_mf[:idx] + '  if (!g_benchmark_mode) {\n    RespondToDetection(person_score_f, no_person_score_f);\n  }' + new_mf[idx+len(respond):]

reg = '''int esp_cli_register_inference_command() {
    esp_console_cmd_t command = {
        .command = "detect_image",
        .help = "detect_image <image_number>"
                "Note: image numbers ranging from 0 - 9 only are valid",
        .func = inference_cli_handler,
    };
    esp_console_cmd_register(&command);
    return 0;
}'''
if cli.count(reg) != 1:
    raise SystemExit('CLI registration block did not match exactly; no files changed.')
if '#include <stdlib.h>' not in cli:
    cli = cli.replace('#include <stdio.h>', '#include <stdio.h>\n#include <stdlib.h>', 1)
bench = r'''
typedef struct {
    long long us;
    int image;
    int raw_person;
    int raw_no_person;
    int ok;
} benchmark_sample_t;

static int compare_long_long(const void *a, const void *b)
{
    long long x = *(const long long *)a;
    long long y = *(const long long *)b;
    return (x > y) - (x < y);
}

static int benchmark_cli_handler(int argc, char *argv[])
{
    if (argc != 2) {
        printf("Usage: benchmark <measured_runs 1..10000>\n");
        return 1;
    }
    char *end = NULL;
    long requested = strtol(argv[1], &end, 10);
    if (end == argv[1] || *end != '\0' || requested < 1 || requested > 10000) {
        printf("ERROR: measured_runs must be between 1 and 10000\n");
        return 1;
    }
    const int runs = (int)requested;
    const int warmup_runs = 10;
    benchmark_sample_t *samples = (benchmark_sample_t *)calloc((size_t)runs, sizeof(*samples));
    long long *sorted = (long long *)calloc((size_t)runs, sizeof(*sorted));
    if (samples == NULL || sorted == NULL) {
        free(samples); free(sorted);
        printf("ERROR: benchmark sample allocation failed\n");
        return 1;
    }
    printf("BENCH_START,runs=%d,warmup=%d,images=%d,timing=interpreter_Invoke_only\n",
           runs, warmup_runs, IMAGE_COUNT);
    g_benchmark_mode = 1;
    for (int i = 0; i < warmup_runs; ++i) {
        run_inference((void *)image_database[i % IMAGE_COUNT]);
    }
    int failures = 0;
    long long sum = 0;
    for (int i = 0; i < runs; ++i) {
        int image = i % IMAGE_COUNT;
        run_inference((void *)image_database[image]);
        samples[i].us = g_last_invoke_us;
        samples[i].image = image;
        samples[i].raw_person = g_last_raw_person;
        samples[i].raw_no_person = g_last_raw_no_person;
        samples[i].ok = g_last_invoke_ok;
        sorted[i] = samples[i].us;
        if (!samples[i].ok) failures++;
        sum += samples[i].us;
    }
    g_benchmark_mode = 0;
    qsort(sorted, (size_t)runs, sizeof(*sorted), compare_long_long);
    long long median = (runs % 2) ? sorted[runs / 2]
        : sorted[runs / 2 - 1] / 2 + sorted[runs / 2] / 2
          + ((sorted[runs / 2 - 1] % 2 + sorted[runs / 2] % 2) / 2);
    int p95_index = (int)(((long long)95 * runs + 99) / 100) - 1;
    if (p95_index < 0) p95_index = 0;
    printf("BENCH_SAMPLES_BEGIN\n");
    for (int i = 0; i < runs; ++i) {
        printf("BENCH_SAMPLE,%d,%d,%lld,%d,%d,%d\n", i + 1, samples[i].image,
               samples[i].us, samples[i].raw_person, samples[i].raw_no_person, samples[i].ok);
    }
    printf("BENCH_SAMPLES_END\n");
    printf("BENCH_SUMMARY,runs=%d,failures=%d,mean_us=%lld,median_us=%lld,p95_nearest_rank_us=%lld,min_us=%lld,max_us=%lld\n",
           runs, failures, sum / runs, median, sorted[p95_index], sorted[0], sorted[runs - 1]);
    free(sorted); free(samples);
    return failures == 0 ? 0 : 1;
}
'''
cli = cli.replace(reg, bench + '\n' + reg, 1)
# Add benchmark command after registering detect_image.
old = '''    esp_console_cmd_register(&command);
    return 0;
}'''
new = '''    esp_console_cmd_register(&command);
    esp_console_cmd_t benchmark_command = {
        .command = "benchmark",
        .help = "benchmark <measured_runs 1..10000>",
        .func = benchmark_cli_handler,
    };
    esp_console_cmd_register(&benchmark_command);
    return 0;
}'''
if cli.count(old) != 1:
    raise SystemExit('Could not identify command-registration tail; no files changed.')
cli = cli.replace(old, new, 1)

stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
for p in files:
    shutil.copy2(p, Path(str(p) + f'.auto_benchmark_{stamp}.bak'))
header_path.write_text(new_header, encoding='utf-8', newline='')
mf_path.write_text(new_mf, encoding='utf-8', newline='')
cli_path.write_text(cli, encoding='utf-8', newline='')
print('Benchmark patch applied to esp_main.h, main_functions.cc, and esp_cli.c.')
print(f'Timestamped backups created with suffix .auto_benchmark_{stamp}.bak')
print('Next: git diff --check, then idf.py build. Do not flash unless build passes.')

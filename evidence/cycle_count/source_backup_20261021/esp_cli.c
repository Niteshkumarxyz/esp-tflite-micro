// Copyright 2020-2021 Espressif Systems (Shanghai) PTE LTD
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <esp_log.h>
#include <esp_console.h>
#include <esp_heap_caps.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include "esp_main.h"
#include "esp_cli.h"
#include "esp_timer.h"

#if CLI_ONLY_INFERENCE
#define IMAGE_COUNT 12
#define BENCHMARK_IMAGE_COUNT 10
static uint8_t *image_database[IMAGE_COUNT];


extern const uint8_t image0_start[]   asm("_binary_image0_start");
extern const uint8_t image1_start[]   asm("_binary_image1_start");
extern const uint8_t image2_start[]   asm("_binary_image2_start");
extern const uint8_t image3_start[]   asm("_binary_image3_start");
extern const uint8_t image4_start[]   asm("_binary_image4_start");
extern const uint8_t image5_start[]   asm("_binary_image5_start");
extern const uint8_t image6_start[]   asm("_binary_image6_start");
extern const uint8_t image7_start[]   asm("_binary_image7_start");
extern const uint8_t image8_start[]   asm("_binary_image8_start");
extern const uint8_t image9_start[]   asm("_binary_image9_start");
extern const uint8_t image10_start[]  asm("_binary_image10_start");
extern const uint8_t image11_start[]  asm("_binary_image11_start");
#endif

static const char *TAG = "[esp_cli]";

static int task_dump_cli_handler(int argc, char *argv[])
{
    int num_of_tasks = uxTaskGetNumberOfTasks();
    TaskStatus_t *task_array = calloc(1, num_of_tasks * sizeof(TaskStatus_t));
    /* Just to go to the next line */
    printf("\n");
    if (!task_array) {
        ESP_LOGE(TAG, "Memory not allocated for task list.");
        return 0;
    }
    num_of_tasks = uxTaskGetSystemState(task_array, num_of_tasks, NULL);
    printf("\tName\tNumber\tPriority\tStackWaterMark\n");
    for (int i = 0; i < num_of_tasks; i++) {
        printf("%16s\t%u\t%u\t%u\n",
               task_array[i].pcTaskName,
               (unsigned) task_array[i].xTaskNumber,
               (unsigned) task_array[i].uxCurrentPriority,
               (unsigned) task_array[i].usStackHighWaterMark);
    }
    free(task_array);
    return 0;
}

static int cpu_dump_cli_handler(int argc, char *argv[])
{
    /* Just to go to the next line */
    printf("\n");
#ifndef CONFIG_FREERTOS_GENERATE_RUN_TIME_STATS
    printf("%s: To use this utility enable: Component config --> FreeRTOS --> Enable FreeRTOS to collect run time stats\n", TAG);
#else
    char *buf = calloc(1, 2 * 1024);
    vTaskGetRunTimeStats(buf);
    printf("%s: Run Time Stats:\n%s\n", TAG, buf);
    free(buf);
#endif
    return 0;
}

static int mem_dump_cli_handler(int argc, char *argv[])
{
    /* Just to go to the next line */
    printf("\n");
    printf("\tDescription\tInternal\tSPIRAM\n");
    printf("Current Free Memory\t%d\t\t%d\n",
           heap_caps_get_free_size(MALLOC_CAP_8BIT) - heap_caps_get_free_size(MALLOC_CAP_SPIRAM),
           heap_caps_get_free_size(MALLOC_CAP_SPIRAM));
    printf("Largest Free Block\t%d\t\t%d\n",
           heap_caps_get_largest_free_block(MALLOC_CAP_8BIT | MALLOC_CAP_INTERNAL),
           heap_caps_get_largest_free_block(MALLOC_CAP_SPIRAM));
    printf("Min. Ever Free Size\t%d\t\t%d\n",
           heap_caps_get_minimum_free_size(MALLOC_CAP_8BIT | MALLOC_CAP_INTERNAL),
           heap_caps_get_minimum_free_size(MALLOC_CAP_SPIRAM));
    return 0;
}

#if CLI_ONLY_INFERENCE
static int inference_cli_handler(int argc, char *argv[])
{
    /* Just to go to the next line */
    printf("\n");
    if (argc != 2) {
        printf("%s: Incorrect arguments\n", TAG);
        return 0;
    }
    int image_number = atoi(argv[1]);

    if((image_number < 0) || (image_number >= IMAGE_COUNT)) {
        ESP_LOGE(TAG, "Please Enter a valid Number ( 0 - %d)", IMAGE_COUNT-1);
        return -1;
    }
   // char file_name[30];
   // sprintf(file_name, "image%d.raw", image_number);
    unsigned detect_time;
    detect_time = esp_timer_get_time();
    run_inference((void *)image_database[image_number]);
    detect_time = (esp_timer_get_time() - detect_time)/1000;
    ESP_LOGI(TAG,"Time required for the inference is %u ms", detect_time);

    return 0;
}


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
           runs, warmup_runs, BENCHMARK_IMAGE_COUNT);
    g_benchmark_mode = 1;
    for (int i = 0; i < warmup_runs; ++i) {
        run_inference((void *)image_database[i % BENCHMARK_IMAGE_COUNT]);
        vTaskDelay(1);
    }
    int failures = 0;
    long long sum = 0;
    for (int i = 0; i < runs; ++i) {
        int image = i % BENCHMARK_IMAGE_COUNT;
        run_inference((void *)image_database[image]);
        vTaskDelay(1);
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

int esp_cli_register_inference_command() {
    esp_console_cmd_t command = {
        .command = "detect_image",
        .help = "detect_image <image_number>"
                "Images 0-9: demo; 10: host person; 11: host no-person",
        .func = inference_cli_handler,
    };
    esp_console_cmd_register(&command);
    esp_console_cmd_t benchmark_command = {
        .command = "benchmark",
        .help = "benchmark <measured_runs 1..10000>",
        .func = benchmark_cli_handler,
    };
    esp_console_cmd_register(&benchmark_command);
    return 0;
}
#endif

static esp_console_cmd_t diag_cmds[] = {
    {
        .command = "mem-dump",
        .help = "",
        .func = mem_dump_cli_handler,
    },
    {
        .command = "task-dump",
        .help = "",
        .func = task_dump_cli_handler,
    },
    {
        .command = "cpu-dump",
        .help = "",
        .func = cpu_dump_cli_handler,
    },
};

int esp_cli_register_cmds()
{
    int cmds_num = sizeof(diag_cmds) / sizeof(esp_console_cmd_t);
    int i;
    for (i = 0; i < cmds_num; i++) {
        ESP_LOGI(TAG, "Registering command: %s", diag_cmds[i].command);
        esp_console_cmd_register(&diag_cmds[i]);
    }
    return 0;
}

static void image_database_init()
{
#if CLI_ONLY_INFERENCE
    image_database[0] = (uint8_t *) image0_start;
    image_database[1] = (uint8_t *) image1_start;
    image_database[2] = (uint8_t *) image2_start;
    image_database[3] = (uint8_t *) image3_start;
    image_database[4] = (uint8_t *) image4_start;
    image_database[5] = (uint8_t *) image5_start;
    image_database[6] = (uint8_t *) image6_start;
    image_database[7] = (uint8_t *) image7_start;
    image_database[8] = (uint8_t *) image8_start;
    image_database[9] = (uint8_t *) image9_start;
    image_database[10] = (uint8_t *) image10_start;
    image_database[11] = (uint8_t *) image11_start;
#endif
}

int esp_cli_start()
{
    image_database_init();
    static int cli_started;
    if (cli_started) {
        return 0;
    }

    esp_console_repl_t *repl = NULL;
    esp_console_repl_config_t repl_config = ESP_CONSOLE_REPL_CONFIG_DEFAULT();

    esp_console_register_help_command();
    esp_cli_register_cmds();
#if defined(CONFIG_ESP_CONSOLE_UART_DEFAULT) || defined(CONFIG_ESP_CONSOLE_UART_CUSTOM)
    esp_console_dev_uart_config_t hw_config = ESP_CONSOLE_DEV_UART_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_console_new_repl_uart(&hw_config, &repl_config, &repl));

#elif defined(CONFIG_ESP_CONSOLE_USB_CDC)
    esp_console_dev_usb_cdc_config_t hw_config = ESP_CONSOLE_DEV_CDC_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_console_new_repl_usb_cdc(&hw_config, &repl_config, &repl));

#elif defined(CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG)
    esp_console_dev_usb_serial_jtag_config_t hw_config = ESP_CONSOLE_DEV_USB_SERIAL_JTAG_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_console_new_repl_usb_serial_jtag(&hw_config, &repl_config, &repl));

#else
#error Unsupported console type
#endif
    ESP_ERROR_CHECK(esp_console_start_repl(repl));
    cli_started = 1;
    return 0;
}

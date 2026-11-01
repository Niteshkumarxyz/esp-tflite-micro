// W2 row-following policy: line protocol over the console UART for lockstep hardware-in-the-loop runs.
// Same protocol as the host and Arm (QEMU) harnesses:
//   "W2 o0 o1 o2 o3 o4 o5 o6"  (7 int8 observation values)  ->  "A a0 a1"  (2 int8 action values)
//   "ID"                        ->  identity line (app ELF SHA-256, model, kernel configuration)
//   "M 0" / "M 1"               ->  select model 0 = per-tensor, 1 = per-channel (re-initialises the interpreter)
//   "B n"                       ->  n timed Invoke calls on a fixed observation: mean microseconds and cycles
#include <inttypes.h>
#include <new>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "driver/uart.h"
#include "esp_app_desc.h"
#include "esp_cpu.h"
#include "esp_idf_version.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/schema/schema_generated.h"
#include "w2_models.h"

#if defined(CONFIG_ESP_TFLITE_MICRO_USE_ESP_NN)
#if defined(CONFIG_NN_OPTIMIZED)
#define W2_KERNELS "R2_ESP_NN_OPTIMIZED"
#else
#define W2_KERNELS "R2A_ESP_NN_ANSI_C"
#endif
#else
#define W2_KERNELS "R1_TFLM_REFERENCE"
#endif

namespace {
constexpr uart_port_t kUart = UART_NUM_0;
constexpr int kArenaSize = 16 * 1024;
alignas(16) uint8_t g_arena[kArenaSize];
tflite::MicroMutableOpResolver<1> g_resolver;
tflite::MicroInterpreter* g_interp = nullptr;
alignas(tflite::MicroInterpreter) uint8_t g_interp_mem[sizeof(tflite::MicroInterpreter)];
int g_model = 0;

uint32_t fnv1a(const unsigned char* p, int n) {
  uint32_t h = 2166136261u;
  for (int i = 0; i < n; ++i) h = (h ^ p[i]) * 16777619u;
  return h;
}

void say(const char* s) { uart_write_bytes(kUart, s, strlen(s)); }

bool load_model(int which) {
  if (g_interp != nullptr) g_interp->~MicroInterpreter();
  const unsigned char* data = which == 1 ? g_w2_model_pc : g_w2_model_pt;
  g_interp = new (g_interp_mem) tflite::MicroInterpreter(tflite::GetModel(data), g_resolver, g_arena, kArenaSize);
  g_model = which;
  return g_interp->AllocateTensors() == kTfLiteOk;
}

void identity() {
  char elf[65] = {0};
  esp_app_get_elf_sha256(elf, sizeof(elf));
  const unsigned char* data = g_model == 1 ? g_w2_model_pc : g_w2_model_pt;
  const int len = g_model == 1 ? g_w2_model_pc_len : g_w2_model_pt_len;
  char buf[400];
  snprintf(buf, sizeof(buf),
           "ID app_elf_sha256=%s kernels=%s idf=%s model=%s model_len=%d model_fnv1a=%08" PRIx32
           " model_sha256=%s arena_used=%d cpu_mhz=%d\n",
           elf, W2_KERNELS, esp_get_idf_version(), g_model == 1 ? "per_channel" : "per_tensor", len,
           fnv1a(data, len), g_model == 1 ? g_w2_model_pc_sha256 : g_w2_model_pt_sha256,
           (int)g_interp->arena_used_bytes(), CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ);
  say(buf);
}

int read_line(char* out, int cap) {
  int n = 0;
  while (true) {
    uint8_t c;
    if (uart_read_bytes(kUart, &c, 1, portMAX_DELAY) != 1) continue;
    if (c == '\n' || c == '\r') {
      if (n == 0) continue;
      out[n] = 0;
      return n;
    }
    if (n < cap - 1) out[n++] = (char)c;
  }
}
}  // namespace

extern "C" void app_main(void) {
  g_resolver.AddFullyConnected();
  bool ok = load_model(0);
  uart_driver_install(kUart, 2048, 2048, 0, nullptr, 0);
  identity();
  say(ok ? "W2_READY\n" : "W2_ERROR allocate\n");
  char line[160];
  char buf[96];
  while (true) {
    read_line(line, sizeof(line));
    if (line[0] == 'W' && line[1] == '2') {
      TfLiteTensor* in = g_interp->input(0);
      char* p = line + 2;
      for (int i = 0; i < 7; ++i) in->data.int8[i] = (int8_t)strtol(p, &p, 10);
      if (g_interp->Invoke() != kTfLiteOk) { say("A_ERROR\n"); continue; }
      TfLiteTensor* out = g_interp->output(0);
      snprintf(buf, sizeof(buf), "A %d %d\n", (int)out->data.int8[0], (int)out->data.int8[1]);
      say(buf);
    } else if (line[0] == 'I' && line[1] == 'D') {
      identity();
    } else if (line[0] == 'M') {
      int which = atoi(line + 1) == 1 ? 1 : 0;
      say(load_model(which) ? "M_OK\n" : "M_ERROR\n");
    } else if (line[0] == 'B') {
      int n = atoi(line + 1);
      if (n < 1) n = 1;
      if (n > 100000) n = 100000;
      TfLiteTensor* in = g_interp->input(0);
      for (int i = 0; i < 7; ++i) in->data.int8[i] = (int8_t)(i * 30 - 90);
      int64_t us = 0;
      uint64_t cyc = 0;
      for (int k = 0; k < n; ++k) {
        int64_t t0 = esp_timer_get_time();
        uint32_t c0 = esp_cpu_get_cycle_count();
        g_interp->Invoke();
        uint32_t c1 = esp_cpu_get_cycle_count();
        us += esp_timer_get_time() - t0;
        cyc += (uint32_t)(c1 - c0);
        if ((k & 255) == 255) vTaskDelay(1);
      }
      snprintf(buf, sizeof(buf), "BENCH n=%d mean_us=%.3f mean_cycles=%.1f\n", n, (double)us / n, (double)cyc / n);
      say(buf);
    }
  }
}

/* RQ4 boot-time acceptance test for the person_detection model (W1) on the ESP32.
 *
 * At every boot, before anything else runs, the firmware:
 *   1. reports its own identity: ELF SHA-256 and the SHA-256 digest of the running app image;
 *   2. runs the 12 stored test images through the model and compares, for each image,
 *      (a) the two int8 outputs and (b) an FNV-1a hash of every one of the 31 operator outputs
 *      with the answers recorded from the qualified reference build (ESP32 R1, 25 October);
 *   3. prints PASS or FAIL, the first failing image and operator, and how long each part took;
 *   4. reports whether actuation would be enabled (PASS) or blocked (FAIL).
 *
 * The operator outputs are hashed by wrapping each kernel's invoke function in the op resolver,
 * so TFLM itself is not modified. Expected answers are in rq4_expected.h.
 */
#include <inttypes.h>
#include <stdio.h>
#include <string.h>

#include "esp_app_desc.h"
#include "esp_cpu.h"
#include "esp_heap_caps.h"
#include "esp_ota_ops.h"
#include "esp_partition.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "sdkconfig.h"

#include "model_settings.h"
#include "person_detect_model_data.h"
#include "rq4_expected.h"
#include "tensorflow/lite/micro/kernels/kernel_util.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/micro_utils.h"
#include "tensorflow/lite/schema/schema_generated.h"

extern const uint8_t image0_start[] asm("_binary_image0_start");
extern const uint8_t image1_start[] asm("_binary_image1_start");
extern const uint8_t image2_start[] asm("_binary_image2_start");
extern const uint8_t image3_start[] asm("_binary_image3_start");
extern const uint8_t image4_start[] asm("_binary_image4_start");
extern const uint8_t image5_start[] asm("_binary_image5_start");
extern const uint8_t image6_start[] asm("_binary_image6_start");
extern const uint8_t image7_start[] asm("_binary_image7_start");
extern const uint8_t image8_start[] asm("_binary_image8_start");
extern const uint8_t image9_start[] asm("_binary_image9_start");
extern const uint8_t image10_start[] asm("_binary_image10_start");
extern const uint8_t image11_start[] asm("_binary_image11_start");

#ifndef CONFIG_ESP_TFLITE_MICRO_USE_ESP_NN
#define CONFIG_ESP_TFLITE_MICRO_USE_ESP_NN 0
#endif
#ifndef CONFIG_NN_OPTIMIZED
#define CONFIG_NN_OPTIMIZED 0
#endif
#ifndef CONFIG_NN_ANSI_C
#define CONFIG_NN_ANSI_C 0
#endif
#ifndef CONFIG_NN_SKIP_NUDGE
#define CONFIG_NN_SKIP_NUDGE 0
#endif
#ifndef TFLITE_SINGLE_ROUNDING
#define RQ4_SINGLE_ROUNDING_FLAG 0
#else
#define RQ4_SINGLE_ROUNDING_FLAG TFLITE_SINGLE_ROUNDING
#endif

namespace {

const uint8_t* const kImages[kKatImages] = {
    image0_start, image1_start, image2_start, image3_start, image4_start,  image5_start,
    image6_start, image7_start, image8_start, image9_start, image10_start, image11_start};

// Same arena rule as examples/person_detection/main/main_functions.cc.
#if CONFIG_NN_OPTIMIZED
constexpr int kScratchBufSize = 60 * 1024;
#else
constexpr int kScratchBufSize = 0;
#endif
constexpr int kTensorArenaSize = 100 * 1024 + kScratchBufSize;
// Allocated in app_main before any other task is created, so that the 160 KB block
// (optimized ESP-NN builds) is still available in one piece.
uint8_t* g_arena = nullptr;
size_t g_largest_block_before = 0;

// ---- operator-output hashing through wrapped kernel registrations ----
constexpr int kKinds = 5;
TFLMRegistration g_orig[kKinds];
int g_op_index = 0;
uint32_t g_op_fnv[kKatOps];
uint32_t g_op_n[kKatOps];
int g_op_type_ok[kKatOps];
int64_t g_hash_us = 0;

inline uint32_t Fnv1a(const uint8_t* p, size_t n) {
  uint32_t h = 2166136261u;
  for (size_t i = 0; i < n; ++i) h = (h ^ p[i]) * 16777619u;
  return h;
}

template <int K>
TfLiteStatus HashingInvoke(TfLiteContext* context, TfLiteNode* node) {
  const TfLiteStatus status = g_orig[K].invoke(context, node);
  const int idx = g_op_index++;
  if (status == kTfLiteOk && idx < kKatOps) {
    const int64_t t0 = esp_timer_get_time();
    const TfLiteEvalTensor* out = tflite::micro::GetEvalOutput(context, node, 0);
    const size_t n = static_cast<size_t>(tflite::ElementCount(*out->dims));
    g_op_type_ok[idx] = (out->type == kTfLiteInt8);
    g_op_n[idx] = static_cast<uint32_t>(n);
    g_op_fnv[idx] = Fnv1a(reinterpret_cast<const uint8_t*>(out->data.raw), n);
    g_hash_us += esp_timer_get_time() - t0;
  }
  return status;
}

template <int K>
TFLMRegistration Wrap(TFLMRegistration r) {
  g_orig[K] = r;
  r.invoke = HashingInvoke<K>;
  return r;
}

void HexOf(const uint8_t* b, int n, char* out) {
  static const char kHex[] = "0123456789abcdef";
  for (int i = 0; i < n; ++i) {
    out[2 * i] = kHex[b[i] >> 4];
    out[2 * i + 1] = kHex[b[i] & 15];
  }
  out[2 * n] = 0;
}

void KatTask(void*) {
  const int64_t t_boot = esp_timer_get_time();
  printf("\nRQ4_BOOT,reset_reason=%d,uptime_us=%lld\n", static_cast<int>(esp_reset_reason()),
         static_cast<long long>(t_boot));

  const esp_app_desc_t* desc = esp_app_get_description();
  printf("RQ4_BUILD,project=%s,version=%s,idf=%s,esp_nn=%d,nn_optimized=%d,nn_ansi_c=%d,"
         "skip_nudge=%d,single_rounding=%d,cpu_mhz=%d\n",
         desc->project_name, desc->version, desc->idf_ver, CONFIG_ESP_TFLITE_MICRO_USE_ESP_NN,
         CONFIG_NN_OPTIMIZED, CONFIG_NN_ANSI_C, CONFIG_NN_SKIP_NUDGE, RQ4_SINGLE_ROUNDING_FLAG,
         CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ);

  // ---- 1. identity ----
  const int64_t t_id0 = esp_timer_get_time();
  char elf_hex[65] = {0};
  esp_app_get_elf_sha256(elf_hex, sizeof(elf_hex));
  uint8_t app_digest[32] = {0};
  char app_hex[65] = "unavailable";
  const esp_partition_t* running = esp_ota_get_running_partition();
  if (running != nullptr && esp_partition_get_sha256(running, app_digest) == ESP_OK) {
    HexOf(app_digest, 32, app_hex);
  }
  const int64_t identity_us = esp_timer_get_time() - t_id0;
  printf("RQ4_IDENTITY,elf_sha256=%s,app_image_digest=%s,partition=%s,identity_us=%lld\n", elf_hex,
         app_hex, running ? running->label : "none", static_cast<long long>(identity_us));

  // ---- 2. interpreter with hashing kernels ----
  const int64_t t_setup0 = esp_timer_get_time();
  const tflite::Model* model = tflite::GetModel(g_person_detect_model_data);
  uint8_t* arena = g_arena;
  if (model->version() != TFLITE_SCHEMA_VERSION || arena == nullptr) {
    printf("RQ4_RESULT,verdict=FAIL,reason=setup,schema=%d,arena=%p,arena_wanted=%d,largest_block_before=%u\n",
           static_cast<int>(model->version()), arena, kTensorArenaSize,
           static_cast<unsigned>(g_largest_block_before));
    printf("RQ4_ACTUATION,BLOCKED\nRQ4_DONE\n");
    vTaskDelete(nullptr);
    return;
  }
  static tflite::MicroMutableOpResolver<5> resolver;
  resolver.AddAveragePool2D(Wrap<0>(tflite::Register_AVERAGE_POOL_2D()));
  resolver.AddConv2D(Wrap<1>(tflite::Register_CONV_2D()));
  resolver.AddDepthwiseConv2D(Wrap<2>(tflite::Register_DEPTHWISE_CONV_2D()));
  resolver.AddReshape(Wrap<3>(tflite::Register_RESHAPE()));
  resolver.AddSoftmax(Wrap<4>(tflite::Register_SOFTMAX()));
  static tflite::MicroInterpreter interpreter(model, resolver, arena, kTensorArenaSize);
  if (interpreter.AllocateTensors() != kTfLiteOk) {
    printf("RQ4_RESULT,verdict=FAIL,reason=allocate\nRQ4_ACTUATION,BLOCKED\nRQ4_DONE\n");
    vTaskDelete(nullptr);
    return;
  }
  TfLiteTensor* input = interpreter.input(0);
  const int64_t setup_us = esp_timer_get_time() - t_setup0;
  printf("RQ4_SETUP,arena_configured=%d,arena_used=%u,largest_block_before=%u,setup_us=%lld\n",
         kTensorArenaSize, static_cast<unsigned>(interpreter.arena_used_bytes()),
         static_cast<unsigned>(g_largest_block_before), static_cast<long long>(setup_us));

  // ---- 3. known-answer images ----
  int outputs_ok = 0, ops_ok_total = 0, first_fail_image = -1, first_fail_op = -1;
  int64_t sum_invoke_us = 0, sum_hash_us = 0, image0_check_us = 0;
  const int64_t t_kat0 = esp_timer_get_time();
  for (int img = 0; img < kKatImages; ++img) {
    const int64_t t_img0 = esp_timer_get_time();
    for (int i = 0; i < kNumCols * kNumRows; ++i) {
      input->data.int8[i] = static_cast<int8_t>(kImages[img][i] ^ 0x80);
    }
    g_op_index = 0;
    g_hash_us = 0;
    memset(g_op_fnv, 0, sizeof(g_op_fnv));
    memset(g_op_n, 0, sizeof(g_op_n));
    memset(g_op_type_ok, 0, sizeof(g_op_type_ok));
    const int64_t t_inv0 = esp_timer_get_time();
    const uint32_t c0 = esp_cpu_get_cycle_count();
    const TfLiteStatus st = interpreter.Invoke();
    const uint32_t cycles = esp_cpu_get_cycle_count() - c0;
    const int64_t invoke_us = esp_timer_get_time() - t_inv0;

    int person = 0, no_person = 0;
    if (st == kTfLiteOk) {
      const TfLiteTensor* out = interpreter.output(0);
      person = out->data.int8[kPersonIndex];
      no_person = out->data.int8[kNotAPersonIndex];
    }
    const int out_ok = (st == kTfLiteOk && person == kKatOutput[img][0] &&
                        no_person == kKatOutput[img][1]);
    int ops_ok = 0, first_bad = -1;
    for (int op = 0; op < kKatOps; ++op) {
      const int ok = (st == kTfLiteOk && g_op_type_ok[op] && g_op_n[op] == kKatOpElements[op] &&
                      g_op_fnv[op] == kKatOpFnv[img][op]);
      ops_ok += ok;
      if (!ok && first_bad < 0) first_bad = op;
    }
    const int64_t image_us = esp_timer_get_time() - t_img0;
    outputs_ok += out_ok;
    ops_ok_total += ops_ok;
    sum_invoke_us += invoke_us;
    sum_hash_us += g_hash_us;
    if (img == 0) image0_check_us = image_us;
    if ((!out_ok || first_bad >= 0) && first_fail_image < 0) {
      first_fail_image = img;
      first_fail_op = first_bad;
    }
    printf("RQ4_IMAGE,image=%d,invoke_ok=%d,ops_run=%d,person=%d,no_person=%d,expected_person=%d,"
           "expected_no_person=%d,output_match=%d,ops_match=%d,first_mismatch_op=%d,invoke_us=%lld,"
           "hash_us=%lld,image_us=%lld,cycles=%" PRIu32 "\n",
           img, st == kTfLiteOk, g_op_index, person, no_person, kKatOutput[img][0],
           kKatOutput[img][1], out_ok, ops_ok, first_bad, static_cast<long long>(invoke_us),
           static_cast<long long>(g_hash_us), static_cast<long long>(image_us), cycles);
    for (int op = 0; op < kKatOps; ++op) {
      if (g_op_fnv[op] != kKatOpFnv[img][op] || g_op_n[op] != kKatOpElements[op]) {
        printf("RQ4_OPMISMATCH,image=%d,op=%d,n=%" PRIu32 ",fnv=%08" PRIx32 ",expected=%08" PRIx32
               "\n",
               img, op, g_op_n[op], g_op_fnv[op], kKatOpFnv[img][op]);
      }
    }
    vTaskDelay(1);  // let the idle task run between images
  }
  const int64_t kat_us = esp_timer_get_time() - t_kat0;
  const int pass = (outputs_ok == kKatImages && ops_ok_total == kKatImages * kKatOps);

  printf("RQ4_RESULT,verdict=%s,images=%d,outputs_match=%d,ops_match=%d,ops_total=%d,"
         "first_fail_image=%d,first_fail_op=%d,identity_us=%lld,setup_us=%lld,kat_us=%lld,"
         "invoke_us_total=%lld,hash_us_total=%lld,minimal_test_us=%lld,boot_to_verdict_us=%lld\n",
         pass ? "PASS" : "FAIL", kKatImages, outputs_ok, ops_ok_total, kKatImages * kKatOps,
         first_fail_image, first_fail_op, static_cast<long long>(identity_us),
         static_cast<long long>(setup_us), static_cast<long long>(kat_us),
         static_cast<long long>(sum_invoke_us), static_cast<long long>(sum_hash_us),
         static_cast<long long>(identity_us + image0_check_us),
         static_cast<long long>(esp_timer_get_time()));
  printf("RQ4_ACTUATION,%s\n", pass ? "ENABLED" : "BLOCKED");
  printf("RQ4_HEAP,free_internal=%u,min_free_internal=%u\n",
         static_cast<unsigned>(heap_caps_get_free_size(MALLOC_CAP_INTERNAL)),
         static_cast<unsigned>(heap_caps_get_minimum_free_size(MALLOC_CAP_INTERNAL)));
  printf("RQ4_DONE\n");
  fflush(stdout);
  vTaskDelete(nullptr);
}

}  // namespace

extern "C" void app_main(void) {
  g_largest_block_before = heap_caps_get_largest_free_block(MALLOC_CAP_8BIT);
  g_arena = static_cast<uint8_t*>(heap_caps_malloc_prefer(
      kTensorArenaSize, 2, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT, MALLOC_CAP_8BIT));
  xTaskCreate(KatTask, "rq4_kat", 8 * 1024, nullptr, 8, nullptr);
}

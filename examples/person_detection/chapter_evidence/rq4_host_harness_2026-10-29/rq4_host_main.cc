// Host dry run of the RQ4 boot-time acceptance test logic (same wrapping and comparison as the
// ESP32 firmware examples/rq4_boot_kat/main/rq4_main.cc), on TFLM x86 reference kernels.
#include <stdint.h>
#include <string.h>
#include "tensorflow/lite/micro/examples/rq1_arm/rq1_data.h"
#include "tensorflow/lite/micro/examples/rq4_host/rq4_expected.h"
#include "tensorflow/lite/micro/kernels/kernel_util.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_log.h"
#include "tensorflow/lite/micro/micro_mutable_op_resolver.h"
#include "tensorflow/lite/micro/micro_utils.h"

namespace {
constexpr int kArenaSize = 200 * 1024;
alignas(16) uint8_t tensor_arena[kArenaSize];
TFLMRegistration g_orig[5];
int g_op_index = 0;
uint32_t g_op_fnv[kKatOps], g_op_n[kKatOps];
int g_op_type_ok[kKatOps];
uint32_t Fnv1a(const uint8_t* p, size_t n) { uint32_t h = 2166136261u; for (size_t i = 0; i < n; ++i) h = (h ^ p[i]) * 16777619u; return h; }
template <int K> TfLiteStatus HashingInvoke(TfLiteContext* c, TfLiteNode* node) {
  TfLiteStatus s = g_orig[K].invoke(c, node);
  int idx = g_op_index++;
  if (s == kTfLiteOk && idx < kKatOps) {
    const TfLiteEvalTensor* out = tflite::micro::GetEvalOutput(c, node, 0);
    size_t n = static_cast<size_t>(tflite::ElementCount(*out->dims));
    g_op_type_ok[idx] = (out->type == kTfLiteInt8);
    g_op_n[idx] = (uint32_t)n;
    g_op_fnv[idx] = Fnv1a(reinterpret_cast<const uint8_t*>(out->data.raw), n);
  }
  return s;
}
template <int K> TFLMRegistration Wrap(TFLMRegistration r) { g_orig[K] = r; r.invoke = HashingInvoke<K>; return r; }
}  // namespace

int main() {
  const tflite::Model* model = tflite::GetModel(g_rq1_model);
  static tflite::MicroMutableOpResolver<5> resolver;
  resolver.AddAveragePool2D(Wrap<0>(tflite::Register_AVERAGE_POOL_2D()));
  resolver.AddConv2D(Wrap<1>(tflite::Register_CONV_2D()));
  resolver.AddDepthwiseConv2D(Wrap<2>(tflite::Register_DEPTHWISE_CONV_2D()));
  resolver.AddReshape(Wrap<3>(tflite::Register_RESHAPE()));
  resolver.AddSoftmax(Wrap<4>(tflite::Register_SOFTMAX()));
  static tflite::MicroInterpreter interpreter(model, resolver, tensor_arena, kArenaSize);
  if (interpreter.AllocateTensors() != kTfLiteOk) { MicroPrintf("RQ4_ERROR,allocate"); return 1; }
  TfLiteTensor* input = interpreter.input(0);
  int outputs_ok = 0, ops_total = 0, ffi = -1, ffo = -1;
  for (int img = 0; img < kKatImages; ++img) {
    for (int i = 0; i < 9216; ++i) input->data.int8[i] = (int8_t)(g_rq1_images_u8[img][i] ^ 0x80);
    g_op_index = 0; memset(g_op_fnv, 0, sizeof g_op_fnv); memset(g_op_n, 0, sizeof g_op_n); memset(g_op_type_ok, 0, sizeof g_op_type_ok);
    TfLiteStatus st = interpreter.Invoke();
    TfLiteTensor* out = interpreter.output(0);
    int person = out->data.int8[1], no_person = out->data.int8[0];
    int out_ok = st == kTfLiteOk && person == kKatOutput[img][0] && no_person == kKatOutput[img][1];
    int ops_ok = 0, first_bad = -1;
    for (int op = 0; op < kKatOps; ++op) {
      int ok = st == kTfLiteOk && g_op_type_ok[op] && g_op_n[op] == kKatOpElements[op] && g_op_fnv[op] == kKatOpFnv[img][op];
      ops_ok += ok; if (!ok && first_bad < 0) first_bad = op;
    }
    outputs_ok += out_ok; ops_total += ops_ok;
    if ((!out_ok || first_bad >= 0) && ffi < 0) { ffi = img; ffo = first_bad; }
    MicroPrintf("RQ4_IMAGE,image=%d,ops_run=%d,person=%d,no_person=%d,output_match=%d,ops_match=%d,first_mismatch_op=%d",
                img, g_op_index, person, no_person, out_ok, ops_ok, first_bad);
  }
  int pass = outputs_ok == kKatImages && ops_total == kKatImages * kKatOps;
  MicroPrintf("RQ4_RESULT,verdict=%s,outputs_match=%d,ops_match=%d,first_fail_image=%d,first_fail_op=%d",
              pass ? "PASS" : "FAIL", outputs_ok, ops_total, ffi, ffo);
  return 0;
}

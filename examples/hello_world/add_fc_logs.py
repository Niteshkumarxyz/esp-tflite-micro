from pathlib import Path

p = Path(r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro\tensorflow\lite\micro\kernels\esp_nn\fully_connected.cc")
s = p.read_text(encoding="utf-8")

old = """        case kTfLiteInt8: {
          if (data.is_per_channel) {
#if ESP_NN"""

new = """        case kTfLiteInt8: {
          if (data.is_per_channel) {
#if ESP_NN
            MicroPrintf("FC_PATH: ESP_NN per-channel INT8");"""

if old not in s:
    raise SystemExit("ERROR: expected per-channel location not found; file unchanged")

s = s.replace(old, new, 1)

old2 = """          } else {
#if ESP_NN
            const RuntimeShape& filter_shape"""

new2 = """          } else {
#if ESP_NN
            MicroPrintf("FC_PATH: ESP_NN per-tensor INT8");
            const RuntimeShape& filter_shape"""

if old2 not in s:
    raise SystemExit("ERROR: expected per-tensor location not found; file unchanged")

s = s.replace(old2, new2, 1)
p.write_text(s, encoding="utf-8")
print("Instrumentation added successfully.")

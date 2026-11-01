from pathlib import Path
import hashlib
import sys

source = Path(
    r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro"
    r"\tensorflow\lite\micro\micro_interpreter_graph.cc"
)
backup = Path(str(source) + ".before_rq1_trace_20261025.bak")

if not source.is_file():
    raise SystemExit(f"SOURCE_NOT_FOUND={source}")
if backup.exists():
    raise SystemExit(f"BACKUP_ALREADY_EXISTS={backup}")

original = source.read_bytes()
if b"TFLM_RQ1_TRACE" in original:
    raise SystemExit("TRACE_MARKER_ALREADY_EXISTS: no changes made")

newline = b"\r\n" if b"\r\n" in original else b"\n"
needle = b"    invoke_status = registration->invoke(context_, node);"
full_line = needle + newline

if original.count(full_line) != 1:
    raise SystemExit(
        "EXPECTED_INVOKE_LINE_COUNT_NOT_ONE: no changes made"
    )

block = r'''#ifdef TFLM_RQ1_TRACE
    static uint32_t rq1_trace_run_id = 0;
    if (invoke_status == kTfLiteOk && subgraph_idx == 0 &&
        current_operator_index_ == 0) {
      ++rq1_trace_run_id;
    }

    if (invoke_status == kTfLiteOk && node->outputs != nullptr) {
      const auto* tensor_vector =
          model_->subgraphs()->Get(subgraph_idx)->tensors();

      for (int output_slot = 0; output_slot < node->outputs->size;
           ++output_slot) {
        const int tensor_index = node->outputs->data[output_slot];

        if (tensor_index < 0 ||
            static_cast<size_t>(tensor_index) >= tensor_vector->size()) {
          MicroPrintf("RQ1_TRACE,run=%u,op=%d,tensor=%d,skip=bad_index",
                      static_cast<unsigned int>(rq1_trace_run_id),
                      static_cast<int>(current_operator_index_), tensor_index);
          continue;
        }

        const TfLiteEvalTensor& trace_tensor =
            subgraph_allocations_[subgraph_idx].tensors[tensor_index];

        if (trace_tensor.type != kTfLiteInt8 ||
            trace_tensor.data.data == nullptr ||
            trace_tensor.dims == nullptr) {
          MicroPrintf("RQ1_TRACE,run=%u,op=%d,tensor=%d,skip=not_int8_or_null",
                      static_cast<unsigned int>(rq1_trace_run_id),
                      static_cast<int>(current_operator_index_), tensor_index);
          continue;
        }

        size_t element_count = 1;
        bool valid_shape = true;
        for (int dim_index = 0; dim_index < trace_tensor.dims->size;
             ++dim_index) {
          const int dim = trace_tensor.dims->data[dim_index];
          if (dim <= 0 ||
              element_count > 1000000u / static_cast<size_t>(dim)) {
            valid_shape = false;
            break;
          }
          element_count *= static_cast<size_t>(dim);
        }

        if (!valid_shape) {
          MicroPrintf("RQ1_TRACE,run=%u,op=%d,tensor=%d,skip=invalid_shape",
                      static_cast<unsigned int>(rq1_trace_run_id),
                      static_cast<int>(current_operator_index_), tensor_index);
          continue;
        }

        const int8_t* values =
            static_cast<const int8_t*>(trace_tensor.data.data);
        int min_value = 127;
        int max_value = -128;
        int32_t sum = 0;
        uint32_t hash = 2166136261u;

        for (size_t i = 0; i < element_count; ++i) {
          const int value = values[i];
          if (value < min_value) min_value = value;
          if (value > max_value) max_value = value;
          sum += static_cast<int32_t>(value);
          hash = (hash ^ static_cast<uint8_t>(values[i])) * 16777619u;
        }

        MicroPrintf(
            "RQ1_TRACE,run=%u,op=%d,tensor=%d,n=%u,min=%d,max=%d,"
            "sum=%d,fnv1a=%x",
            static_cast<unsigned int>(rq1_trace_run_id),
            static_cast<int>(current_operator_index_), tensor_index,
            static_cast<unsigned int>(element_count), min_value, max_value,
            static_cast<int>(sum), static_cast<unsigned int>(hash));
      }
    }
#endif  // TFLM_RQ1_TRACE
'''

block_bytes = block.replace("\n", newline.decode("ascii")).encode("ascii")
patched = original.replace(full_line, full_line + block_bytes, 1)

# Refuse to leave a backup behind if the patch content is unexpectedly absent.
if patched == original or b"RQ1_TRACE,run=" not in patched:
    raise SystemExit("PATCH_VALIDATION_FAILED: source unchanged")

backup.write_bytes(original)
try:
    source.write_bytes(patched)
except Exception:
    # Restore the original source if writing the patch fails.
    source.write_bytes(original)
    raise

print("PATCH_APPLIED=True")
print(f"SOURCE={source}")
print(f"BACKUP={backup}")
print(f"ORIGINAL_SHA256={hashlib.sha256(original).hexdigest().upper()}")
print(f"PATCHED_SHA256={hashlib.sha256(patched).hexdigest().upper()}")
print("TRACE_SCOPE=successful operator outputs; INT8 tensors only")
print("TRACE_POSITION=after kernel invoke, before allocator reset")

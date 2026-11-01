from pathlib import Path
import hashlib

source = Path(r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro\tensorflow\lite\micro\micro_interpreter_graph.cc")
backup = Path(str(source) + ".before_rq1_raw_values_20261025.bak")

original = source.read_bytes()
if b"TFLM_RQ1_TRACE" not in original:
    raise SystemExit("Trace patch not found; no changes made.")
if b"RQ1_RAW,run=" in original:
    raise SystemExit("Raw probe already exists; no changes made.")

newline = b"\r\n" if b"\r\n" in original else b"\n"
anchor = b"            static_cast<int>(sum), static_cast<unsigned int>(hash));"

if original.count(anchor) != 1:
    raise SystemExit("Expected unique trace fingerprint line not found; no changes made.")

extra = r'''        if (tensor_index == 28 || tensor_index == 31 ||
            tensor_index == 87) {
          MicroPrintf(
              "RQ1_RAW,run=%u,op=%d,tensor=%d,v0=%d,v1=%d",
              static_cast<unsigned int>(rq1_trace_run_id),
              static_cast<int>(current_operator_index_), tensor_index,
              static_cast<int>(values[0]),
              static_cast<int>(element_count > 1 ? values[1] : 0));
        }'''

extra_bytes = extra.replace("\n", newline.decode("ascii")).encode("ascii")
patched = original.replace(anchor, anchor + newline + extra_bytes, 1)

if patched == original or b"RQ1_RAW,run=" not in patched:
    raise SystemExit("Patch validation failed; source unchanged.")

backup.write_bytes(original)
try:
    source.write_bytes(patched)
except Exception:
    source.write_bytes(original)
    raise

print("RAW_PROBE_PATCH_APPLIED=True")
print(f"BACKUP={backup}")
print(f"PREVIOUS_SOURCE_SHA256={hashlib.sha256(original).hexdigest().upper()}")
print(f"PATCHED_SOURCE_SHA256={hashlib.sha256(patched).hexdigest().upper()}")

import csv
import hashlib
from pathlib import Path
from tensorflow.lite.python import schema_py_generated as schema

MODEL = Path(
    r"C:\Users\nk947\Downloads\robot-runtime-research\tflite-micro"
    r"\tensorflow\lite\micro\models\person_detect.tflite"
)
OUT_DIR = Path(
    r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro"
    r"\examples\person_detection\chapter_evidence"
)

OP_CSV = OUT_DIR / "rq1_model_operator_map_2026-10-25.csv"
TENSOR_CSV = OUT_DIR / "rq1_model_tensor_map_2026-10-25.csv"

for path in (OP_CSV, TENSOR_CSV):
    if path.exists():
        raise SystemExit(f"Refusing to overwrite existing evidence: {path}")

if not MODEL.is_file():
    raise SystemExit(f"Model file not found: {MODEL}")

raw = MODEL.read_bytes()
model_sha = hashlib.sha256(raw).hexdigest().upper()
model = schema.Model.GetRootAsModel(raw, 0)

if model.SubgraphsLength() < 1:
    raise SystemExit("Model contains no subgraph.")

graph = model.Subgraphs(0)
tensor_count = graph.TensorsLength()
operator_count = graph.OperatorsLength()

def tensor_info(index):
    if index < 0 or index >= tensor_count:
        return {"name": "<optional-or-invalid>", "shape": "", "type": "",
                "buffer": "", "data_bytes": 0, "scale_count": 0, "qdim": ""}

    t = graph.Tensors(index)
    name_raw = t.Name()
    name = name_raw.decode("utf-8", errors="replace") if name_raw else ""
    shape_raw = t.ShapeAsNumpy()
    shape = "x".join(str(int(x)) for x in shape_raw) if shape_raw is not None else ""

    buffer_index = int(t.Buffer())
    buf = model.Buffers(buffer_index)
    data_bytes = int(buf.DataLength()) if buf is not None else 0

    q = t.Quantization()
    scale_count = int(q.ScaleLength()) if q is not None else 0
    qdim = int(q.QuantizedDimension()) if q is not None else ""

    return {
        "name": name.replace(",", ";"),
        "shape": shape,
        "type": int(t.Type()),
        "buffer": buffer_index,
        "data_bytes": data_bytes,
        "scale_count": scale_count,
        "qdim": qdim,
    }

def builtin_code(opcode):
    try:
        return int(opcode.BuiltinCode())
    except Exception:
        return int(opcode.DeprecatedBuiltinCode())

producers = {}
consumers = {i: [] for i in range(tensor_count)}
op_rows = []

for op_index in range(operator_count):
    op = graph.Operators(op_index)
    opcode_index = int(op.OpcodeIndex())
    opcode = model.OperatorCodes(opcode_index)
    code = builtin_code(opcode)

    input_ids = [int(op.Inputs(i)) for i in range(op.InputsLength())]
    output_ids = [int(op.Outputs(i)) for i in range(op.OutputsLength())]

    input_names = []
    for tid in input_ids:
        info = tensor_info(tid)
        input_names.append(f"{tid}:{info['name']}")
        if tid >= 0 and tid < tensor_count:
            consumers[tid].append(op_index)

    output_names = []
    for tid in output_ids:
        info = tensor_info(tid)
        output_names.append(f"{tid}:{info['name']}")
        if tid >= 0 and tid < tensor_count:
            producers[tid] = (op_index, code)

    op_rows.append({
        "operator_index": op_index,
        "opcode_index": opcode_index,
        "builtin_code_numeric": code,
        "operator_version": int(opcode.Version()),
        "input_tensor_indices": ";".join(map(str, input_ids)),
        "input_tensor_names": " | ".join(input_names),
        "output_tensor_indices": ";".join(map(str, output_ids)),
        "output_tensor_names": " | ".join(output_names),
    })

with OP_CSV.open("x", newline="", encoding="utf-8") as f:
    fields = list(op_rows[0]) if op_rows else [
        "operator_index", "opcode_index", "builtin_code_numeric",
        "operator_version", "input_tensor_indices", "input_tensor_names",
        "output_tensor_indices", "output_tensor_names"
    ]
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(op_rows)

tensor_rows = []
for tensor_index in range(tensor_count):
    info = tensor_info(tensor_index)
    producer_info = producers.get(tensor_index, ("", ""))
    tensor_rows.append({
        "tensor_index": tensor_index,
        "name": info["name"],
        "shape": info["shape"],
        "type_numeric": info["type"],
        "buffer_index": info["buffer"],
        "buffer_data_bytes": info["data_bytes"],
        "has_embedded_buffer_data": info["data_bytes"] > 0,
        "scale_count": info["scale_count"],
        "quantized_dimension": info["qdim"],
        "producer_operator_index": producer_info[0],
        "producer_builtin_code_numeric": producer_info[1],
        "consumer_operator_indices": ";".join(map(str, consumers[tensor_index])),
    })

with TENSOR_CSV.open("x", newline="", encoding="utf-8") as f:
    fields = list(tensor_rows[0]) if tensor_rows else []
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(tensor_rows)

print(f"MODEL_PATH={MODEL}")
print(f"MODEL_BYTES={len(raw)}")
print(f"MODEL_SHA256={model_sha}")
print(f"SUBGRAPHS={model.SubgraphsLength()}")
print(f"TENSORS={tensor_count}")
print(f"OPERATORS={operator_count}")
print(f"GRAPH_INPUTS={';'.join(str(int(graph.Inputs(i))) for i in range(graph.InputsLength()))}")
print(f"GRAPH_OUTPUTS={';'.join(str(int(graph.Outputs(i))) for i in range(graph.OutputsLength()))}")

for path in (OP_CSV, TENSOR_CSV):
    print(f"OUTPUT={path}")
    print(f"OUTPUT_BYTES={path.stat().st_size}")
    print(f"OUTPUT_SHA256={hashlib.sha256(path.read_bytes()).hexdigest().upper()}")

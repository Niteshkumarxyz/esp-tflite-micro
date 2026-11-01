import tflite
from pathlib import Path

buf = Path("model_extracted.tflite").read_bytes()
model = tflite.Model.GetRootAsModel(buf, 0)
sg = model.Subgraphs(0)

type_names = {0: "FLOAT32", 2: "INT32", 3: "UINT8", 9: "INT8", 10: "FLOAT16", 14: "INT4"}

print("Model version:", model.Version())
print("Tensor count:", sg.TensorsLength())

for i in range(sg.TensorsLength()):
    t = sg.Tensors(i)
    raw_name = t.Name()
    name = raw_name.decode("utf-8", errors="replace") if raw_name else "(unnamed)"
    q = t.Quantization()

    print(f"\nTensor {i}: {name}")
    print("  Shape:", [t.Shape(j) for j in range(t.ShapeLength())])
    print("  Type:", type_names.get(t.Type(), f"UNKNOWN({t.Type()})"))

    if q:
        print("  Scales:", [q.Scale(j) for j in range(q.ScaleLength())])
        print("  Zero points:", [q.ZeroPoint(j) for j in range(q.ZeroPointLength())])
        print("  Quantized dimension:", q.QuantizedDimension())

print("\nOperators:")
for i in range(sg.OperatorsLength()):
    op = sg.Operators(i)
    code = model.OperatorCodes(op.OpcodeIndex())
    print("  Builtin opcode:", code.BuiltinCode(),
          "| Inputs:", [op.Inputs(j) for j in range(op.InputsLength())],
          "| Outputs:", [op.Outputs(j) for j in range(op.OutputsLength())])

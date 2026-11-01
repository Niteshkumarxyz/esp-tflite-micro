from pathlib import Path
from tensorflow.lite.python import schema_py_generated as s

p = Path(r"C:\Users\nk947\Downloads\robot-runtime-research\tflite-micro\tensorflow\lite\micro\models\person_detect.tflite")
m = s.Model.GetRootAsModel(p.read_bytes(), 0)
g = m.Subgraphs(0)

for oi in range(g.OperatorsLength()):
    op = g.Operators(oi)
    opcode = m.OperatorCodes(op.OpcodeIndex())
    inputs = op.InputsAsNumpy().tolist()
    for tensor_index in inputs:
        if tensor_index in [33,36,40,44,48,52,56,60,64,68,72,76,80,84]:
            names = []
            for idx in inputs:
                if idx >= 0:
                    t = g.Tensors(idx)
                    names.append(f"{idx}:{t.Name().decode('utf-8', errors='replace')}")
            print(f"Operator {oi}, builtin_code={opcode.DeprecatedBuiltinCode()}, version={opcode.Version()}")
            print("  Inputs:", " | ".join(names))

from pathlib import Path
from tensorflow.lite.python import schema_py_generated as s

p = Path(r"C:\Users\nk947\Downloads\robot-runtime-research\tflite-micro\tensorflow\lite\micro\models\person_detect.tflite")
m = s.Model.GetRootAsModel(p.read_bytes(), 0)
g = m.Subgraphs(0)
targets = [33,36,40,44,48,52,56,60,64,68,72,76,80,84]

for oi in range(g.OperatorsLength()):
    op = g.Operators(oi)
    inputs = op.InputsAsNumpy().tolist()
    for pos, idx in enumerate(inputs):
        if idx not in targets:
            continue
        print(f"\nOperator {oi}: bias tensor {idx}")
        for label, tid in zip(["input", "weights", "bias"], inputs):
            if tid < 0:
                continue
            t = g.Tensors(tid)
            q = t.Quantization()
            scales = q.ScaleAsNumpy().tolist() if q and q.ScaleLength() else []
            zeros = q.ZeroPointAsNumpy().tolist() if q and q.ZeroPointLength() else []
            print(f"  {label}: tensor={tid}, shape={t.ShapeAsNumpy().tolist()}, type={t.Type()}, qdim={q.QuantizedDimension() if q else 'None'}, scales={len(scales)}, zero_points={len(zeros)}")

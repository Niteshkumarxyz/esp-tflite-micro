from pathlib import Path
from tensorflow.lite.python import schema_py_generated as schema

p = Path(r"C:\Users\nk947\Downloads\robot-runtime-research\tflite-micro\tensorflow\lite\micro\models\person_detect.tflite")
m = schema.Model.GetRootAsModel(p.read_bytes(), 0)
g = m.Subgraphs(0)

with open("w1_tensor_metadata.csv", "w", encoding="utf-8") as f:
    f.write("index,name,shape,type,scale_count,quantized_dimension\n")
    for i in range(g.TensorsLength()):
        t = g.Tensors(i)
        q = t.Quantization()
        name = t.Name().decode("utf-8", errors="replace").replace(",", ";")
        shape = "x".join(map(str, t.ShapeAsNumpy().tolist()))
        scales = q.ScaleLength() if q else 0
        qdim = q.QuantizedDimension() if q else ""
        f.write(f"{i},{name},{shape},{t.Type()},{scales},{qdim}\n")

print("Saved: w1_tensor_metadata.csv")
print("Tensor rows:", g.TensorsLength())

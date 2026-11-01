from pathlib import Path
from tensorflow.lite.python import schema_py_generated as schema

model_path = Path(r"C:\Users\nk947\Downloads\robot-runtime-research\tflite-micro\tensorflow\lite\micro\models\person_detect.tflite")
model = schema.Model.GetRootAsModel(model_path.read_bytes(), 0)

print("Model version:", model.Version())
print("Subgraphs:", model.SubgraphsLength())
print("Operator entries:", model.OperatorCodesLength())

for i in range(model.OperatorCodesLength()):
    op = model.OperatorCodes(i)
    print(f"Operator entry {i}: deprecated_code={op.DeprecatedBuiltinCode()}, version={op.Version()}")

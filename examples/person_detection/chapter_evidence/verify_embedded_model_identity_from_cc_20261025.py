import hashlib
import re
from pathlib import Path

source_model = Path(
    r"C:\Users\nk947\Downloads\robot-runtime-research\tflite-micro"
    r"\tensorflow\lite\micro\models\person_detect.tflite"
)

source_cc = Path(
    r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro"
    r"\examples\person_detection\main\person_detect_model_data.cc"
)

for path in (source_model, source_cc):
    if not path.is_file():
        raise SystemExit(f"Required file not found: {path}")

model_bytes = source_model.read_bytes()
model_sha = hashlib.sha256(model_bytes).hexdigest().upper()

source_text = source_cc.read_text(encoding="latin-1")

pattern = re.compile(
    r"g_person_detect_model_data\s*\[\s*\]\s*=\s*\{(.*?)\}\s*;",
    re.S
)
match = pattern.search(source_text)

if not match:
    raise SystemExit(
        "Could not parse the model array from the .cc file. "
        "No identity conclusion can be made."
    )

tokens = re.findall(
    r"(?<![A-Za-z0-9_])0[xX]([0-9a-fA-F]{2})(?![0-9a-fA-F])",
    match.group(1)
)

if not tokens:
    raise SystemExit("No hexadecimal byte literals were parsed.")

embedded_bytes = bytes(int(token, 16) for token in tokens)
embedded_sha = hashlib.sha256(embedded_bytes).hexdigest().upper()

length_match = re.search(
    r"g_person_detect_model_data_len\s*=\s*(\d+)\s*;",
    source_text
)

declared_length = int(length_match.group(1)) if length_match else None

print(f"SOURCE_TFLITE_BYTES={len(model_bytes)}")
print(f"SOURCE_TFLITE_SHA256={model_sha}")
print(f"EMBEDDED_ARRAY_BYTES={len(embedded_bytes)}")
print(f"EMBEDDED_ARRAY_SHA256={embedded_sha}")
print(f"ARRAY_LENGTH_MATCH={len(embedded_bytes) == len(model_bytes)}")
print(f"ARRAY_HASH_MATCH={embedded_sha == model_sha}")
print(f"DECLARED_LENGTH={declared_length}")
print(
    "DECLARED_LENGTH_MATCH="
    + str(declared_length == len(embedded_bytes))
    if declared_length is not None else
    "DECLARED_LENGTH_MATCH=NOT_NUMERICALLY_DECLARED"
)

print(
    "FINAL_RESULT="
    + (
        "BYTE_IDENTICAL"
        if embedded_bytes == model_bytes
        else "MODEL_BYTES_DIFFER"
    )
)

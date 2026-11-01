import hashlib
import re
from pathlib import Path

esp_root = Path(r"C:\Users\nk947\Downloads\robot-runtime-research\esp-tflite-micro")
source_model = Path(r"C:\Users\nk947\Downloads\robot-runtime-research\tflite-micro\tensorflow\lite\micro\models\person_detect.tflite")
search_root = esp_root / "examples" / "person_detection"

if not source_model.is_file():
    raise SystemExit(f"Source model not found: {source_model}")

raw_model = source_model.read_bytes()
source_hash = hashlib.sha256(raw_model).hexdigest().upper()

print(f"SOURCE_MODEL={source_model}")
print(f"SOURCE_MODEL_BYTES={len(raw_model)}")
print(f"SOURCE_MODEL_SHA256={source_hash}")

headers = sorted(search_root.rglob("person_detect_model_data.h"))
headers = [
    p for p in headers
    if not any(part.lower() in {".git", "host-venv", "__pycache__"}
               for part in p.parts)
]

if not headers:
    print("RESULT=NO_EMBEDDED_MODEL_HEADER_FOUND")
    raise SystemExit(0)

pattern = re.compile(
    r"g_person_detect_model_data\s*\[\s*\]\s*[^=]*=\s*\{(.*?)\};",
    re.S
)

for header in headers:
    print("\n--- HEADER ---")
    print(f"HEADER_PATH={header}")

    text = header.read_text(encoding="latin-1")
    match = pattern.search(text)

    if not match:
        print("RESULT=ARRAY_NOT_PARSED")
        continue

    byte_tokens = re.findall(r"0[xX]([0-9a-fA-F]{2})\b", match.group(1))
    embedded = bytes(int(token, 16) for token in byte_tokens)
    embedded_hash = hashlib.sha256(embedded).hexdigest().upper()

    print(f"EMBEDDED_BYTES={len(embedded)}")
    print(f"EMBEDDED_SHA256={embedded_hash}")
    print(f"BYTE_LENGTH_MATCH={len(embedded) == len(raw_model)}")
    print(f"BYTE_HASH_MATCH={embedded_hash == source_hash}")

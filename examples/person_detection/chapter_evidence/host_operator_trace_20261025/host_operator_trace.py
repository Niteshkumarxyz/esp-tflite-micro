"""Host operator-level comparison against ESP32 R1 full tensor dumps (written 25 Oct 2026).
Paths: REF = LiteRT BUILTIN_REF, OPT = LiteRT BUILTIN_WITHOUT_DEFAULT_DELEGATES, XNN = LiteRT default (XNNPACK).
REF/OPT intermediates via experimental_preserve_all_tensors; XNN intermediates by re-pointing the single
subgraph output to each operator's output tensor (4-byte patch of a copy in memory)."""
import re, os, sys, csv, hashlib
import numpy as np, tflite
from PIL import Image
from ai_edge_litert.interpreter import Interpreter, OpResolverType
B = os.path.expanduser("~/mnt/robot-runtime-research")
PD = B + "/esp-tflite-micro/examples/person_detection"
MODEL = B + "/tflite-micro/evidence/host/r0_laptop_linuxvm_20261022/person_detect_qdimfix.tflite"
TD = B + "/tflite-micro/tensorflow/lite/micro/examples/person_detection/testdata"
OUTD = sys.argv[1]
R1LOG = {0:'20261025213331',1:'20261025213732',2:'20261025214425',3:'20261025215147',4:'20261025215752',5:'20261025220422',
         6:'20261025221100',7:'20261025221702',8:'20261025222658',9:'20261025223419',10:'20261025210819',11:'20261025211948'}
def device_tensors(ts):
    t = open(f"{PD}/log.person_detection.{ts}.txt", "rb").read().decode("latin1")
    ops = [(int(m.group(1)), int(m.group(2))) for m in re.finditer(r"RQ1_TRACE,run=\d+,op=(\d+),tensor=(\d+),", t)]
    ch = {}
    for m in re.finditer(r"RQ1_RAW,run=\d+,op=(\d+),tensor=\d+,offset=(\d+),count=\d+,hex=([0-9a-f]*)\s", t):
        ch.setdefault(int(m.group(1)), {})[int(m.group(2))] = bytes.fromhex(m.group(3))
    out = {}
    for op, ten in ops:
        out[op] = (ten, np.frombuffer(b"".join(ch[op][o] for o in sorted(ch[op])), dtype=np.int8))
    return out
mbytes = open(MODEL, "rb").read()
m = tflite.Model.GetRootAsModel(bytearray(mbytes), 0); sg = m.Subgraphs(0)
o = sg._tab.Offset(8); vec = sg._tab.Vector(o); assert sg.OutputsLength() == 1 and sg.Outputs(0) == 87
def model_with_output(ti):
    b = bytearray(mbytes); b[vec:vec + 4] = int(ti).to_bytes(4, "little", signed=True); return bytes(b)
def inp(k):
    raw = np.frombuffer(open(f"{PD}/static_images/sample_images/image{k}", "rb").read(), dtype=np.uint8)
    return (raw ^ 0x80).view(np.int8).reshape(1, 96, 96, 1)
# check images 10/11 equal the TFLM test images as fed by the host test
for k, f in ((10, "person"), (11, "no_person")):
    bmp = np.frombuffer(Image.open(f"{TD}/{f}.bmp").tobytes(), dtype=np.int8)
    print("input check", k, f, bool(np.array_equal(bmp, inp(k).ravel())))
rows = []
for k in range(12):
    dev = device_tensors(R1LOG[k])
    x = inp(k)
    for label, rt in (("REF", OpResolverType.BUILTIN_REF), ("OPT", OpResolverType.BUILTIN_WITHOUT_DEFAULT_DELEGATES)):
        it = Interpreter(model_content=mbytes, experimental_op_resolver_type=rt, experimental_preserve_all_tensors=True, num_threads=1)
        it.allocate_tensors(); it.set_tensor(it.get_input_details()[0]["index"], x); it.invoke()
        for op in range(31):
            ten, d = dev[op]; h = it.get_tensor(ten).ravel().astype(np.int8)
            diff = np.abs(h.astype(np.int16) - d.astype(np.int16))
            rows.append((k, label, op, ten, d.size, int((diff > 0).sum()), int(diff.max())))
    for op in range(31):
        ten, d = dev[op]
        it = Interpreter(model_content=model_with_output(ten), experimental_op_resolver_type=OpResolverType.BUILTIN, num_threads=1)
        it.allocate_tensors(); it.set_tensor(it.get_input_details()[0]["index"], x); it.invoke()
        out = it.get_output_details()[0]; assert out["index"] == ten
        h = it.get_tensor(ten).ravel().astype(np.int8)
        diff = np.abs(h.astype(np.int16) - d.astype(np.int16))
        rows.append((k, "XNN", op, ten, d.size, int((diff > 0).sum()), int(diff.max())))
with open(f"{OUTD}/host_vs_esp32_r1_operator_compare_2026-10-25.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["image", "host_path", "op", "tensor", "n", "differing_elements", "max_abs_lsb"]); w.writerows(rows)
# summaries
for label in ("REF", "OPT", "XNN"):
    rr = [r for r in rows if r[1] == label]
    eq = sum(1 for r in rr if r[5] == 0)
    print(f"{label}: tensors identical {eq}/{len(rr)}; differing elements {sum(r[5] for r in rr)} of {sum(r[4] for r in rr)}; max LSB {max(r[6] for r in rr)}")
    for k in range(12):
        fd = [r for r in rr if r[0] == k and r[5] > 0]
        if fd:
            print(f"  image {k}: first divergent op {fd[0][2]} (tensor {fd[0][3]}), ops differing {len(fd)}, max LSB {max(r[6] for r in fd)}, output-op diff {[r[5] for r in rr if r[0]==k and r[2]==30][0]}")
print("model sha", hashlib.sha256(mbytes).hexdigest())

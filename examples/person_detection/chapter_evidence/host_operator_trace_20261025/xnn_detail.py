import csv, collections, numpy as np, importlib.util, sys
spec = importlib.util.spec_from_file_location("h", "host_operator_trace.py")
src = open("host_operator_trace.py").read().split("rows = []")[0]
g = {}; sys.argv = ["x", "."]; exec(src, g)
from ai_edge_litert.interpreter import Interpreter, OpResolverType
rows = list(csv.DictReader(open("host_vs_esp32_r1_operator_compare_2026-10-25.csv")))
x = [r for r in rows if r["host_path"] == "XNN"]
print("op,frac_diff_mean,max_lsb,images_identical")
per = collections.defaultdict(list)
for r in x: per[int(r["op"])].append(r)
for op in range(31):
    rr = per[op]; n = int(rr[0]["n"])
    print(op, round(sum(int(r["differing_elements"]) for r in rr) / (n * 12), 4), max(int(r["max_abs_lsb"]) for r in rr), sum(1 for r in rr if r["differing_elements"] == "0"))
hist0 = collections.Counter(); histall = collections.Counter(); outs = []
for k in range(12):
    dev = g["device_tensors"](g["R1LOG"][k]); xin = g["inp"](k)
    for op in (0, 30):
        ten, d = dev[op]
        it = Interpreter(model_content=g["model_with_output"](ten), experimental_op_resolver_type=OpResolverType.BUILTIN, num_threads=1)
        it.allocate_tensors(); it.set_tensor(it.get_input_details()[0]["index"], xin); it.invoke()
        h = it.get_tensor(ten).ravel().astype(np.int16); dd = h - d.astype(np.int16)
        if op == 0: hist0.update(dd.tolist())
        else: outs.append((k, d.tolist(), h.tolist()))
print("op0 signed diff histogram (host XNN minus device):", sorted(hist0.items()))
print("output tensor 87 [no_person, person] device vs XNN:")
for k, d, h in outs:
    flip = (d[1] > d[0]) != (h[1] > h[0])
    print(k, d, h, "label change" if flip else "same label", "LSB", max(abs(a - b) for a, b in zip(d, h)))

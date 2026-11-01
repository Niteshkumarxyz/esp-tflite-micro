"""Upper bound on |acc| and on the value before the right shift for every conv / depthwise / FC layer of a TFLite int8 model."""
import sys, numpy as np, tflite
from tflite.BuiltinOperator import BuiltinOperator as BO
path = sys.argv[1]
buf = open(path, 'rb').read()
m = tflite.Model.GetRootAsModel(buf, 0); g = m.Subgraphs(0)
opname = {v: k for k, v in BO.__dict__.items() if not k.startswith('_')}
def tensor(i):
    t = g.Tensors(i); b = m.Buffers(t.Buffer()); q = t.Quantization()
    data = b.DataAsNumpy() if b.DataLength() else None
    return t, data, q
worst = 0; rows = []
for k in range(g.OperatorsLength()):
    op = g.Operators(k); code = m.OperatorCodes(op.OpcodeIndex())
    name = opname.get(max(code.BuiltinCode(), code.DeprecatedBuiltinCode()), '?')
    if name not in ('CONV_2D', 'DEPTHWISE_CONV_2D', 'FULLY_CONNECTED'): continue
    ti, _, qi = tensor(op.Inputs(0)); tw, wd, qw = tensor(op.Inputs(1)); to, _, qo = tensor(op.Outputs(0))
    w = np.frombuffer(wd.tobytes(), np.int8).reshape(tw.ShapeAsNumpy())
    bias = None
    if op.InputsLength() > 2 and op.Inputs(2) >= 0:
        tb, bd, _ = tensor(op.Inputs(2)); bias = np.frombuffer(bd.tobytes(), np.int32)
    zp_in = int(qi.ZeroPointAsNumpy()[0]); xmax = max(127 - zp_in, zp_in + 128)   # largest |q_x - Z_x|
    if name == 'DEPTHWISE_CONV_2D':   # weights [1, kh, kw, C]
        s = np.abs(w.astype(np.int64)).reshape(-1, w.shape[-1]).sum(0)
    else:                              # [O, kh, kw, I] or [O, I]
        s = np.abs(w.astype(np.int64)).reshape(w.shape[0], -1).sum(1)
    acc = s * xmax + (np.abs(bias.astype(np.int64)) if bias is not None else 0)
    S_in = float(qi.ScaleAsNumpy()[0]); S_w = qw.ScaleAsNumpy(); S_out = float(qo.ScaleAsNumpy()[0])
    M = S_in * S_w / S_out                               # real multiplier per channel
    pre = acc * np.minimum(M, 1.0) * 1.0                 # bound on the value before the right shift (left shift only when M >= 1)
    lim = int(acc.max()); worst = max(worst, lim)
    rows.append((k, name, lim, float(M.max())))
for r in rows: print(f"op {r[0]:2d} {r[1]:18s} max|acc| <= {r[2]:>12,d}  (2^{np.log2(r[2]):.1f})  max M = {r[3]:.4f}")
print(f"largest bound {worst:,d} = 2^{np.log2(worst):.2f}; overflow needs a value within 2^(e-1) of 2^31")

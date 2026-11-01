"""Hardware-in-the-loop W2 run on the ESP32 (lockstep over the console UART). Run on the Windows PC.

Example (one build flashed on the board):
  python w2_hil_esp32.py --port COM5 --label R1 --model per_tensor
  python w2_hil_esp32.py --port COM5 --label R1 --model per_channel
Needs: Python 3 with numpy and pyserial, and w2_sim.py, w2_runtime.py, w2_models.json and
openloop_obs_int8_<model>.npy in the same folder. Results go to hil_<label>_<model>/.
"""
import argparse
import csv
import hashlib
import json
import os
import sys
import time

import numpy as np
import serial

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from w2_runtime import ModelMeta, run_episode  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--port", default="COM5")
ap.add_argument("--baud", type=int, default=115200)
ap.add_argument("--label", required=True, help="R1, R2A or R2 (must match the flashed build)")
ap.add_argument("--model", choices=["per_tensor", "per_channel"], required=True)
ap.add_argument("--first-seed", type=int, default=3000)
ap.add_argument("--episodes", type=int, default=200)
ap.add_argument("--bench", type=int, default=10000)
args = ap.parse_args()
HERE = os.path.dirname(os.path.abspath(__file__))
meta = ModelMeta(os.path.join(HERE, "w2_models.json"), args.model)
OUTD = os.path.join(HERE, f"hil_{args.label}_{args.model}")
os.makedirs(OUTD, exist_ok=True)


class SerialRuntime:
    def __init__(self, port, baud):
        self.s = serial.Serial(port, baud, timeout=5)
        time.sleep(0.2)
        self.s.reset_input_buffer()
        self.name = "ESP32_" + args.label

    def cmd(self, text, expect):
        self.s.write((text + "\n").encode())
        t0 = time.time()
        while time.time() - t0 < 20:
            line = self.s.readline().decode(errors="replace").strip()
            if line.startswith(expect):
                return line
        raise RuntimeError(f"no reply to {text!r}")

    def act(self, q):
        line = self.cmd("W2 " + " ".join(str(int(v)) for v in q), "A ")
        return np.array([int(v) for v in line.split()[1:3]], dtype=np.int8)

    def batch(self, Q, chunk=40):
        out = []
        for s in range(0, len(Q), chunk):
            part = Q[s:s + chunk]
            self.s.write("".join("W2 " + " ".join(str(int(v)) for v in q) + "\n" for q in part).encode())
            got = 0
            while got < len(part):
                line = self.s.readline().decode(errors="replace").strip()
                if line.startswith("A "):
                    out.append([int(v) for v in line.split()[1:3]])
                    got += 1
                elif line == "":
                    raise RuntimeError("serial timeout during open-loop batch")
        return np.array(out, dtype=np.int8)


r = SerialRuntime(args.port, args.baud)
ident0 = r.cmd("ID", "ID ")
r.cmd("M " + ("1" if args.model == "per_channel" else "0"), "M_OK")
ident = r.cmd("ID", "ID ")
fields = dict(kv.split("=", 1) for kv in ident.split()[1:])
print(ident)
if fields.get("model_sha256") != meta.sha256:
    sys.exit(f"model on the board ({fields.get('model_sha256')}) is not {meta.sha256}; rebuild the firmware")
expected = {"R1": "R1_TFLM_REFERENCE", "R2A": "R2A_ESP_NN_ANSI_C", "R2": "R2_ESP_NN_OPTIMIZED"}[args.label]
if fields.get("kernels") != expected:
    sys.exit(f"board reports kernels={fields.get('kernels')}, expected {expected}: wrong build flashed")

bench = r.cmd(f"B {args.bench}", "BENCH ")
print(bench)
Q = np.load(os.path.join(HERE, f"openloop_obs_int8_{args.model}.npy"))
t0 = time.time()
A = r.batch(Q)
np.save(os.path.join(OUTD, "openloop_actions.npy"), A)
print(f"open loop: {len(A)} actions in {time.time() - t0:.0f} s")
exp_path = os.path.join(HERE, "expected_openloop.json")
match = "no reference file"
if os.path.exists(exp_path):
    exp = json.load(open(exp_path))[args.model]
    h = hashlib.sha256(A.tobytes()).hexdigest()
    match = next((k for k, v in exp.items() if v == h), "matches no host or Arm group")
print("open-loop actions match:", match)

eps, traj = [], {}
for k, sd in enumerate(range(args.first_seed, args.first_seed + args.episodes)):
    m, steps = run_episode(sd, r, meta, record=True)
    eps.append(m)
    traj[str(sd)] = np.frombuffer(b"".join(o + a for o, a in steps), dtype=np.int8).reshape(-1, 9)
    if k % 20 == 19:
        print(f"episodes {k + 1}/{args.episodes}, success so far {sum(e['success'] for e in eps)}")
np.savez_compressed(os.path.join(OUTD, "closed_loop_trajectories.npz"), **traj)
with open(os.path.join(OUTD, "closed_loop_episodes.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(eps[0].keys()))
    w.writeheader()
    w.writerows(eps)
summary = dict(label=args.label, model=args.model, open_loop_match=match, identity=ident, identity_before_model_select=ident0, bench=bench,
               open_loop_actions_sha256=hashlib.sha256(A.tobytes()).hexdigest(),
               success=int(sum(e["success"] for e in eps)), episodes=len(eps),
               mean_rms_xte_m=float(np.mean([e["rms_xte"] for e in eps])))
json.dump(summary, open(os.path.join(OUTD, "summary.json"), "w"), indent=1)
print(json.dumps(summary, indent=1))

"""Runtime adapters and episode runner for the W2 open-loop and closed-loop (RQ2) tests.

Every runtime receives the same int8 observation bytes and returns two int8 action bytes. The host
quantizes observations and dequantizes actions with the model's own parameters, identically for all
runtimes, so a closed-loop episode depends only on the numbers each runtime computes.
"""
import json
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import w2_sim as S  # noqa: E402


class ModelMeta:
    def __init__(self, models_json, name):
        m = json.load(open(models_json))[name]
        self.name = name
        self.in_scale, self.in_zp = m["input_scale"], m["input_zero_point"]
        self.out_scale, self.out_zp = m["output_scale"], m["output_zero_point"]
        self.sha256 = m["sha256"]

    def q_obs(self, obs):
        v = np.floor(np.asarray(obs, dtype=np.float64) / self.in_scale + 0.5) + self.in_zp
        return np.clip(v, -128, 127).astype(np.int8)

    def dq_act(self, a):
        return (np.asarray(a, dtype=np.float64) - self.out_zp) * self.out_scale


class LiteRT:
    """LiteRT/TFLite interpreter: mode REF (BUILTIN_REF), OPT (no default delegates) or XNN (default, XNNPACK)."""

    def __init__(self, model_path, mode):
        try:
            from ai_edge_litert.interpreter import Interpreter, OpResolverType
        except ImportError:
            import tensorflow as tf
            Interpreter, OpResolverType = tf.lite.Interpreter, tf.lite.experimental.OpResolverType
        rt = {"REF": OpResolverType.BUILTIN_REF, "OPT": OpResolverType.BUILTIN_WITHOUT_DEFAULT_DELEGATES,
              "XNN": OpResolverType.AUTO}[mode]
        self.it = Interpreter(model_path=model_path, experimental_op_resolver_type=rt, num_threads=1)
        self.it.allocate_tensors()
        self.i = self.it.get_input_details()[0]["index"]
        self.o = self.it.get_output_details()[0]["index"]
        self.name = f"LiteRT_{mode}"

    def act(self, q):
        self.it.set_tensor(self.i, np.asarray(q, dtype=np.int8).reshape(1, 7))
        self.it.invoke()
        return self.it.get_tensor(self.o).reshape(2).astype(np.int8)

    def batch(self, Q):
        return np.array([self.act(q) for q in Q], dtype=np.int8)

    def close(self):
        pass


class LineProc:
    """A TFLM harness speaking the W2 line protocol on stdin/stdout (x86 binary or qemu-arm)."""

    def __init__(self, cmd, name):
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)
        self.name = name
        line = self.p.stdout.readline()
        while line and not line.startswith("W2_READY"):
            line = self.p.stdout.readline()
        self.ready = line.strip()

    def act(self, q):
        self.p.stdin.write("W2 " + " ".join(str(int(v)) for v in q) + "\n")
        self.p.stdin.flush()
        line = self.p.stdout.readline()
        while not line.startswith("A "):
            if not line:
                raise RuntimeError(self.name + " closed")
            line = self.p.stdout.readline()
        return np.array([int(v) for v in line.split()[1:3]], dtype=np.int8)

    def batch(self, Q, chunk=2000):
        out = []
        for s in range(0, len(Q), chunk):
            part = Q[s:s + chunk]
            self.p.stdin.write("".join("W2 " + " ".join(str(int(v)) for v in q) + "\n" for q in part))
            self.p.stdin.flush()
            got = 0
            while got < len(part):
                line = self.p.stdout.readline()
                if line.startswith("A "):
                    out.append([int(v) for v in line.split()[1:3]])
                    got += 1
                elif not line:
                    raise RuntimeError(self.name + " closed")
        return np.array(out, dtype=np.int8)

    def close(self):
        try:
            self.p.stdin.write("Q\n")
            self.p.stdin.flush()
        except Exception:
            pass
        self.p.wait(timeout=10)


def run_episode(seed, runtime, meta, record=False):
    e = S.RowEnv(seed)
    o = e.reset_obs()
    steps = []
    while not e.done:
        q = meta.q_obs(o)
        a = runtime.act(q)
        if record:
            steps.append((q.tobytes(), a.tobytes()))
        o, _, _ = e.step(meta.dq_act(a))
    m = e.metrics()
    m["seed"] = seed
    return m, steps


def mcnemar_exact(b, c):
    """Two-sided exact McNemar p-value from the discordant counts b and c."""
    from math import comb
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    p = sum(comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * p)

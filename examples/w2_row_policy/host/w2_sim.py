"""W2 row-following simulator (2D differential drive), as specified in the chapter proposal.

Observation (7 values, all in [0, 1]):
  0-4  five-channel IR line array across the robot's front (reflectance of the row tape)
  5-6  left and right ultrasonic range to the plant rows, normalised by the 1.0 m maximum
Action (2 values in [-1, 1]): left and right wheel speed commands.
Control rate 20 Hz. Sensor noise and wheel slip are drawn from a seeded generator, so an episode
is fully determined by its seed and by the numbers the policy returns.
"""
import math
import numpy as np

DT = 0.05                 # 20 Hz control
WHEELBASE = 0.20          # m
V_MAX = 0.50              # m/s at command 1.0
ROW_HALF_WIDTH = 0.35     # plant rows at +/-0.35 m from the centre line
FAIL_OFFSET = 0.25        # leaving the row by more than this hits the plants
TRACK_LEN = 12.0          # m of row per episode
MAX_STEPS = 600           # 30 s: the row must be covered at >= 0.4 m/s on average
IR_OFFSETS = np.array([-0.06, -0.03, 0.0, 0.03, 0.06])  # lateral sensor positions (m)
IR_AHEAD = 0.10           # sensor bar ahead of the axle (m)
IR_SIGMA = 0.02           # tape reflectance width (m)
US_MAX = 1.0


class Track:
    """Smooth random row: heading changes as a sum of a few low-frequency sinusoids."""

    def __init__(self, rng, n=1200):
        s = np.linspace(0.0, TRACK_LEN + 3.0, n)
        k = np.zeros_like(s)
        for _ in range(3):
            amp = rng.uniform(0.2, 0.9)        # curvature amplitude (1/m)
            freq = rng.uniform(0.08, 0.40)     # cycles per metre
            ph = rng.uniform(0, 2 * math.pi)
            k += amp * np.sin(2 * math.pi * freq * s + ph)
        ds = s[1] - s[0]
        th = np.cumsum(k) * ds
        th -= th[0]
        x = np.cumsum(np.cos(th)) * ds
        y = np.cumsum(np.sin(th)) * ds
        self.s, self.x, self.y, self.th = s, x - x[0], y - y[0], th
        # worn or missing tape: 3-6 gaps of 0.15-0.45 m where the IR array sees nothing
        self.gaps = []
        for _ in range(int(rng.integers(3, 7))):
            g0 = rng.uniform(1.0, TRACK_LEN - 0.5)
            self.gaps.append((g0, g0 + rng.uniform(0.15, 0.45)))

    def tape_at(self, i):
        si = self.s[i]
        return not any(a <= si <= b for a, b in self.gaps)

    def project(self, px, py, hint):
        """Return (index, signed lateral offset, heading) of the nearest centre-line point."""
        lo, hi = max(0, hint - 40), min(len(self.s), hint + 80)
        d2 = (self.x[lo:hi] - px) ** 2 + (self.y[lo:hi] - py) ** 2
        i = lo + int(np.argmin(d2))
        th = self.th[i]
        dx, dy = px - self.x[i], py - self.y[i]
        lat = -math.sin(th) * dx + math.cos(th) * dy     # + = left of the line
        return i, lat, th


class RowEnv:
    def __init__(self, seed, obs_noise=0.03, us_noise=0.04, slip=0.10, us_dropout=0.25):
        self.rng = np.random.default_rng(seed)
        self.track = Track(self.rng)
        self.obs_noise, self.us_noise, self.slip, self.us_dropout = obs_noise, us_noise, slip, us_dropout
        lat0 = self.rng.uniform(-0.05, 0.05)
        dth0 = self.rng.uniform(-0.25, 0.25)
        th = self.track.th[0]
        self.x = -math.sin(th) * lat0
        self.y = math.cos(th) * lat0
        self.h = th + dth0
        self.idx = 0
        self.steps = 0
        self.done = False
        self.success = False
        self.lat_hist = []

    def _sense(self):
        ch, sh = math.cos(self.h), math.sin(self.h)
        ir = np.empty(5)
        for j, o in enumerate(IR_OFFSETS):
            sx = self.x + IR_AHEAD * ch - o * sh
            sy = self.y + IR_AHEAD * sh + o * ch
            k, lat, _ = self.track.project(sx, sy, self.idx)
            ir[j] = math.exp(-(lat / IR_SIGMA) ** 2) if self.track.tape_at(k) else 0.0
        ir = np.clip(ir + self.rng.normal(0, self.obs_noise, 5), 0.0, 1.0)
        _, lat, th = self.track.project(self.x, self.y, self.idx)
        rel = self.h - th
        c = max(math.cos(rel), 0.2)
        left = (ROW_HALF_WIDTH - lat) / c
        right = (ROW_HALF_WIDTH + lat) / c
        us = np.clip(np.array([left, right]) + self.rng.normal(0, self.us_noise, 2), 0.0, US_MAX)
        # gaps between plants: the echo is lost and the sensor reports maximum range
        us[self.rng.random(2) < self.us_dropout] = US_MAX
        us = us / US_MAX
        return np.concatenate([ir, us]).astype(np.float32)

    def reset_obs(self):
        return self._sense()

    def step(self, action):
        a = np.clip(np.asarray(action, dtype=np.float64), -1.0, 1.0)
        slip = 1.0 + self.rng.normal(0, self.slip, 2)
        vl, vr = a[0] * V_MAX * slip[0], a[1] * V_MAX * slip[1]
        v = 0.5 * (vl + vr)
        w = (vr - vl) / WHEELBASE
        self.x += v * math.cos(self.h) * DT
        self.y += v * math.sin(self.h) * DT
        self.h += w * DT
        prev = self.idx
        self.idx, lat, th = self.track.project(self.x, self.y, self.idx)
        self.lat_hist.append(lat)
        self.steps += 1
        progress = (self.track.s[self.idx] - self.track.s[prev])
        rel = math.atan2(math.sin(self.h - th), math.cos(self.h - th))
        reward = 10.0 * progress - 2.0 * abs(lat) - 0.05 * abs(rel)
        if abs(lat) > FAIL_OFFSET:
            self.done, reward = True, reward - 10.0
        elif self.track.s[self.idx] >= TRACK_LEN:
            self.done, self.success, reward = True, True, reward + 20.0
        elif self.steps >= MAX_STEPS:
            self.done, reward = True, reward - 10.0   # too slow counts as a failure
        return self._sense(), reward, self.done

    def metrics(self):
        lat = np.array(self.lat_hist) if self.lat_hist else np.zeros(1)
        return dict(success=self.success, steps=self.steps, rms_xte=float(np.sqrt(np.mean(lat ** 2))),
                    max_xte=float(np.max(np.abs(lat))), progress=float(self.track.s[self.idx]))


try:
    import gymnasium as gym

    class RowGym(gym.Env):
        observation_space = gym.spaces.Box(0.0, 1.0, (7,), np.float32)
        action_space = gym.spaces.Box(-1.0, 1.0, (2,), np.float32)

        def __init__(self, seed_base=0):
            self._n = seed_base

        def reset(self, seed=None, options=None):
            super().reset(seed=seed)
            self._n += 1
            self.env = RowEnv(10_000_000 + self._n)
            return self.env.reset_obs(), {}

        def step(self, action):
            obs, r, done = self.env.step(action)
            trunc = self.env.steps >= MAX_STEPS and not self.env.success
            return obs, r, done and not trunc, trunc, {}
except ImportError:
    pass

"""
generate_dataset.py
Physics-inspired synthetic data generator for the Smart Guardian IoT Helmet.

Each sample is a 4-second window of helmet IMU data (MPU6050 @ 50 Hz, +/-16 g,
+/-2000 deg/s) together with 1 Hz GPS speed (NEO-6M style, 0.5 s latency).
Five event classes are generated:
    0 normal_riding   1 hard_braking   2 pothole_bump   3 helmet_drop   4 accident
Label 4 is the positive ("accident") class for the binary detector.

Outputs:
    ../data/helmet_features.csv   feature table (one row per window)
    ../data/raw_examples.npz      a few raw windows for plotting
"""
import numpy as np, pandas as pd
from scipy.signal import butter, filtfilt

FS, WIN = 50, 4.0
N = int(FS * WIN)
T = np.arange(N) / FS
CLASSES = ["normal_riding", "hard_braking", "pothole_bump", "helmet_drop", "accident"]
rng = np.random.default_rng(42)


def rot(axis, deg):
    a = np.radians(deg); c, s = np.cos(a), np.sin(a)
    axis = axis / np.linalg.norm(axis); x, y, z = axis
    return np.array([[c+x*x*(1-c), x*y*(1-c)-z*s, x*z*(1-c)+y*s],
                     [y*x*(1-c)+z*s, c+y*y*(1-c), y*z*(1-c)-x*s],
                     [z*x*(1-c)-y*s, z*y*(1-c)+x*s, c+z*z*(1-c)]])


def unit(v): return v / np.linalg.norm(v)


def pulse(t0, sigma, amp, vec):
    p = amp * np.exp(-0.5 * ((T - t0) / sigma) ** 2)
    return p[:, None] * unit(vec)[None, :]


def smooth_step(t0, width):
    return 1 / (1 + np.exp(-(T - t0) / (width / 6)))


def make_window(cls):
    """Return acc (N,3) in g, gyro (N,3) in deg/s, gps speed (5,) in km/h."""
    pitch, roll = rng.uniform(-12, 12), rng.uniform(-8, 8)
    R0 = rot(np.array([0, 1, 0]), pitch) @ rot(np.array([1, 0, 0]), roll)
    g0 = R0 @ np.array([0, 0, 1.0])
    vib = rng.uniform(0.03, 0.10)                       # road vibration (g)
    acc = np.tile(g0, (N, 1)) + rng.normal(0, vib, (N, 3))
    gyro = rng.normal(0, rng.uniform(1.5, 4), (N, 3))
    gyro += 8 * np.sin(2*np.pi*rng.uniform(0.2, 0.8)*T + rng.uniform(0, 6.28))[:, None] * rng.uniform(0.3, 1, 3)
    v0 = rng.uniform(15, 85)
    v = np.full(N, v0) + np.cumsum(rng.normal(0, 0.02, N))   # km/h true speed
    t_ev = rng.uniform(1.0, 1.4)

    if cls == 0:                                         # normal riding (some turns/accelerations)
        if rng.random() < 0.5:
            d = rng.uniform(-8, 8); v += d * smooth_step(t_ev + 0.5, 1.5)
        if rng.random() < 0.4:                           # lean in a turn
            ang = rng.uniform(5, 25); tilt = ang * smooth_step(t_ev, 0.8)
            for i in range(N):
                acc[i] = rot(np.array([1, 0, 0]), tilt[i]) @ acc[i]
            gyro[:, 0] += 25 * np.exp(-0.5 * ((T - t_ev) / 0.4) ** 2)
        if rng.random() < 0.08:                          # violent swerve, no crash
            ang = rng.uniform(25, 60); tilt = ang * (smooth_step(t_ev, 0.4) - smooth_step(t_ev + 1.0, 0.4))
            for i in range(N):
                acc[i] = rot(np.array([1, 0.3, 0]), tilt[i]) @ acc[i]
            gyro += pulse(t_ev, 0.2, rng.uniform(120, 300), rng.normal(size=3))
    elif cls == 1:                                       # hard braking
        decel = rng.uniform(0.25, 0.65)                  # g
        dv = min(decel * 9.81 * 3.6 * 1.3, v0 * rng.uniform(0.4, 0.95))
        v -= dv * np.clip((T - t_ev) / 1.3, 0, 1)
        on = ((T > t_ev) & (T < t_ev + 1.3)).astype(float)
        acc[:, 0] -= decel * on
        gyro[:, 1] += 30 * np.exp(-0.5 * ((T - t_ev) / 0.3) ** 2)
        if rng.random() < 0.15: acc += pulse(t_ev + 0.6, 0.03, rng.uniform(1.5, 3.5), rng.normal(size=3))
    elif cls == 2:                                       # pothole / speed breaker
        acc += pulse(t_ev, rng.uniform(0.02, 0.05), rng.uniform(1.5, 8.0), np.array([0.2, 0.1, 1.0]) + rng.normal(0, .1, 3))
        gyro += pulse(t_ev, 0.05, rng.uniform(40, 220), rng.normal(size=3))
        v -= rng.uniform(0, 18) * smooth_step(t_ev + .3, .8)
    elif cls == 3:                                       # helmet dropped / handled while parked
        v = np.zeros(N) + rng.uniform(0, 1.0)
        tilt_ang = rng.uniform(30, 130)
        Rn = rot(rng.normal(size=3), tilt_ang)
        w = smooth_step(t_ev, 0.35)
        gt = (1 - w)[:, None] * g0 + w[:, None] * (Rn @ g0)
        acc = gt + rng.normal(0, rng.uniform(0.01, 0.04), (N, 3))
        for k in range(rng.integers(1, 4)):             # bounces
            acc += pulse(t_ev + k * rng.uniform(.1, .3), 0.025, rng.uniform(3, 10) / (k + 1), rng.normal(size=3))
        gyro += pulse(t_ev, 0.12, rng.uniform(200, 600), rng.normal(size=3))
    else:                                                # accident
        low_speed = rng.random() < 0.25
        v0 = rng.uniform(12, 28) if low_speed else v0
        v = np.full(N, v0)
        ratio = rng.uniform(0.7, 1.0) if rng.random() > 0.12 else rng.uniform(0.3, 0.55)  # some slide/skid crashes
        v -= v0 * ratio * smooth_step(t_ev + 0.25, 0.7)
        amp = rng.uniform(3.0, 6.5) if low_speed else rng.uniform(5.0, 16.0)
        if rng.random() < 0.08: amp = rng.uniform(3.0, 4.2)   # soft impact
        acc += pulse(t_ev, rng.uniform(0.03, 0.06), amp, rng.normal(size=3))
        acc += pulse(t_ev + rng.uniform(.1, .3), 0.03, amp * rng.uniform(.3, .8), rng.normal(size=3))
        tilt_ang = rng.uniform(15, 40) if rng.random() < 0.12 else rng.uniform(45, 160)
        Rn = rot(rng.normal(size=3), tilt_ang)
        w = smooth_step(t_ev + 0.1, 0.5)
        gt = (1 - w)[:, None] * g0 + w[:, None] * (Rn @ g0)
        acc = acc - g0 + gt                                # replace gravity with rotating gravity
        post = T > t_ev + 1.2                              # rider lying still afterwards
        acc[post] = gt[post] + rng.normal(0, 0.015, (post.sum(), 3))
        gyro += pulse(t_ev, 0.15, rng.uniform(250, 900), rng.normal(size=3))
        gyro[post] = rng.normal(0, 1.5, (post.sum(), 3))
    acc = np.clip(acc, -16, 16)
    gyro = np.clip(gyro, -2000, 2000)
    gps = np.interp(np.arange(0, 5) - 0.5, T, v) + rng.normal(0, 1.0, 5)   # 1 Hz, 0.5 s latency
    if rng.random() < 0.06:                             # GPS dropout: stale speed value
        gps[2:] = gps[1]
    return acc, gyro, np.clip(gps, 0, None)


def lowpass(x, fc=5.0):
    b, a = butter(2, fc / (FS / 2)); return filtfilt(b, a, x, axis=0)


def features(acc, gyro, gps):
    """Pre-processing + feature extraction for one window."""
    mag = np.linalg.norm(acc, axis=1)
    gmag = np.linalg.norm(gyro, axis=1)
    lp = lowpass(acc)
    pre = lp[int(0.5*FS):int(1.0*FS)].mean(0)        # gravity direction before event
    post = lp[int(3.0*FS):].mean(0)                  # after event
    cosang = np.dot(pre, post) / (np.linalg.norm(pre) * np.linalg.norm(post))
    tilt = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
    s_pre, s_post = gps[1], gps[3]
    return dict(acc_peak=mag.max(), acc_std=mag.std(), jerk_max=np.abs(np.diff(mag)).max() * FS,
                gyro_peak=gmag.max(), gyro_mean=gmag.mean(), tilt_change=tilt,
                speed_pre=s_pre, speed_post=s_post, speed_drop=s_pre - s_post,
                speed_drop_pct=100 * (s_pre - s_post) / max(s_pre, 1.0))


if __name__ == "__main__":
    counts = {0: 1400, 1: 700, 2: 600, 3: 300, 4: 500}
    rows, raw = [], {}
    for c, n in counts.items():
        for i in range(n):
            a, g, s = make_window(c)
            f = features(a, g, s); f["label"] = c; f["class_name"] = CLASSES[c]
            rows.append(f)
            if i == 0: raw[CLASSES[c]] = dict(acc=a, gyro=g, gps=s)
    df = pd.DataFrame(rows).sample(frac=1, random_state=1).reset_index(drop=True)
    df.to_csv("../data/helmet_features.csv", index=False)
    np.savez("../data/raw_examples.npz", **{f"{k}_{kk}": vv for k, d in raw.items() for kk, vv in d.items()})
    print(df.shape); print(df.class_name.value_counts())
    print(df.groupby("class_name")[["acc_peak", "gyro_peak", "tilt_change", "speed_drop"]].mean().round(1))

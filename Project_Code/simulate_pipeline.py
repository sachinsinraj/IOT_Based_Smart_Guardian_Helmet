"""
End-to-end software simulation of the helmet state machine
(MONITORING -> ALERT_PENDING -> SMS_SENT / CANCELLED) on synthetic windows.
Produces ../results/simulation_log.txt  (also rendered as an image by make_diagrams.py).
"""
import numpy as np
import generate_dataset as gd
from detector import is_accident, CALIBRATED

ALERT_WINDOW_S = 15
CONTACTS = ["+91XXXXXXXX01", "+91XXXXXXXX02"]       # placeholders
LAT, LON = 28.6139, 77.2090                    # demo coordinates (central Delhi)
log = ["# SOFTWARE SIMULATION - GPS/GSM events below are simulated, no hardware attached"]


def say(t, msg): log.append(f"[t={t:7.2f}s] {msg}")


def run(case, cls, rider_cancels, t0):
    gd.rng = np.random.default_rng({"pothole": 11, "braking": 5, "accident_cancel": 21, "accident_sms": 33, "drop": 8}[case])
    for _ in range(40):                               # pick a window the detector flags if class is accident
        a, g, s = gd.make_window(cls); f = gd.features(a, g, s)
        if cls != 4 or is_accident(f["acc_peak"], f["tilt_change"], f["speed_pre"], f["speed_drop"], CALIBRATED): break
    say(t0, f"--- Scenario: {case} ---")
    say(t0 + 1.0, f"MONITORING  speed={f['speed_pre']:.0f} km/h  |a|peak={f['acc_peak']:.1f} g  gyro peak={f['gyro_peak']:.0f} deg/s")
    say(t0 + 3.0, f"FEATURES    tilt change={f['tilt_change']:.0f} deg  speed drop={f['speed_drop']:.0f} km/h")
    if not is_accident(f["acc_peak"], f["tilt_change"], f["speed_pre"], f["speed_drop"], CALIBRATED):
        say(t0 + 3.0, "DECISION    NOT an accident (conditions not jointly satisfied) -> keep monitoring"); return t0 + 6
    say(t0 + 3.0, "DECISION    POSSIBLE ACCIDENT -> buzzer ON, 15 s cancel window started")
    if rider_cancels:
        say(t0 + 3.0 + 6.4, "BUTTON      pressed by rider -> alert CANCELLED, buzzer OFF"); return t0 + 14
    say(t0 + 3.0 + ALERT_WINDOW_S, "TIMEOUT     no cancellation -> reading GPS fix")
    say(t0 + 19.2, f"GPS         lat={LAT:.4f} lon={LON:.4f}")
    for c in CONTACTS:
        say(t0 + 20.5, f"GSM         AT+CMGS to {c} ... +CMGS: OK")
    say(t0 + 20.6, f"SMS TEXT    'EMERGENCY! Possible accident detected. Location: https://maps.google.com/?q={LAT:.4f},{LON:.4f}'")
    return t0 + 24


if __name__ == "__main__":
    t = 0.0
    for case, cls, cancel in [("pothole", 2, False), ("braking", 1, False), ("drop", 3, False),
                              ("accident_cancel", 4, True), ("accident_sms", 4, False)]:
        t = run(case, cls, cancel, t)
    open("../results/simulation_log.txt", "w").write("\n".join(log))
    print("\n".join(log))

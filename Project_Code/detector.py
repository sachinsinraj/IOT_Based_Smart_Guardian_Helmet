"""Rule-based multi-sensor accident detector (same logic as the ESP32 firmware)."""
# Thresholds from the project proposal (default) ...
DEFAULT = dict(IMPACT_G=4.0, TILT_DEG=45.0, SPEED_DROP=15.0, MIN_SPEED=15.0)
# ... and thresholds calibrated on the synthetic training split (see train_evaluate.py).
# Re-calibrate on real ride data before real-world use.
CALIBRATED = dict(IMPACT_G=3.0, TILT_DEG=15.0, SPEED_DROP=8.0, MIN_SPEED=15.0)


def is_accident(acc_peak, tilt_change, speed_pre, speed_drop, th=DEFAULT):
    """IF high impact AND major orientation change AND sudden speed reduction -> accident."""
    return (acc_peak >= th["IMPACT_G"] and tilt_change >= th["TILT_DEG"]
            and speed_pre >= th["MIN_SPEED"] and speed_drop >= th["SPEED_DROP"])

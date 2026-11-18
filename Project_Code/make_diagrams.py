"""Draw block diagram, wiring diagram, state machine and a terminal-style image of the simulation log."""
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
R = "../results/"


def box(ax, x, y, w, h, text, fc="#ebf4ff", ec="#2b6cb0", fs=9):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc, ec=ec, lw=1.4))
    ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=fs)


def arrow(ax, p, q, text=None):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=12, lw=1.3, color="#2d3748"))
    if text: ax.text((p[0]+q[0])/2, (p[1]+q[1])/2 + 0.12, text, ha="center", fontsize=7)

# 1) block diagram
fig, ax = plt.subplots(figsize=(10, 4.2)); ax.set_xlim(0, 10); ax.set_ylim(0, 4.2); ax.axis("off")
box(ax, 0.1, 2.7, 1.9, 0.9, "MPU6050\nAccel + Gyro", "#fefcbf", "#b7791f")
box(ax, 0.1, 0.8, 1.9, 0.9, "NEO-6M GPS\nlocation + speed", "#fefcbf", "#b7791f")
box(ax, 3.2, 1.6, 2.4, 1.3, "ESP32\nfeature extraction +\naccident detection logic", "#c6f6d5", "#2f855a")
box(ax, 6.8, 2.9, 1.7, 0.8, "Buzzer + LED", "#fed7d7", "#c53030")
box(ax, 6.8, 1.9, 1.7, 0.8, "Cancel button", "#fed7d7", "#c53030")
box(ax, 6.8, 0.7, 1.9, 0.9, "GSM SIM800L/\nSIM7600", "#e9d8fd", "#6b46c1")
box(ax, 8.9, 0.7, 1.0, 0.9, "Emergency\ncontacts", "#e9d8fd", "#6b46c1", 8)
box(ax, 3.2, 0.1, 2.4, 0.7, "Li-ion + TP4056 charger", "#e2e8f0", "#4a5568", 8)
arrow(ax, (2.0, 3.15), (3.2, 2.6), "I2C"); arrow(ax, (2.0, 1.25), (3.2, 1.9), "UART")
arrow(ax, (5.6, 2.7), (6.8, 3.3)); arrow(ax, (6.8, 2.3), (5.6, 2.2)); arrow(ax, (5.6, 1.9), (6.8, 1.2), "UART/AT")
arrow(ax, (8.7, 1.15), (8.9, 1.15)); arrow(ax, (4.4, 0.8), (4.4, 1.6), "power")
ax.set_title("Smart Guardian Helmet - system block diagram", fontsize=11)
plt.tight_layout(); plt.savefig(R + "fig_block_diagram.png", dpi=140); plt.close()

# 2) wiring table drawn as figure
rows = [("MPU6050", "VCC / GND", "3.3 V / GND"), ("MPU6050", "SDA / SCL", "GPIO21 / GPIO22"),
        ("NEO-6M GPS", "TX -> ESP32 RX2", "GPIO16"), ("NEO-6M GPS", "RX <- ESP32 TX2", "GPIO17"),
        ("GSM module", "TX -> ESP32", "GPIO26"), ("GSM module", "RX <- ESP32", "GPIO27 (level-shift)"),
        ("Buzzer", "signal", "GPIO25"), ("Status LED", "anode (+330 ohm)", "GPIO2"),
        ("Push button", "one leg / other leg", "GPIO33 / GND (INPUT_PULLUP)"),
        ("Battery", "Li-ion -> TP4056 -> buck 5 V", "ESP32 VIN, GPS, GSM (GSM needs ~2 A peak)")]
fig, ax = plt.subplots(figsize=(9, 3.9)); ax.axis("off")
t = ax.table(cellText=rows, colLabels=["Component", "Pin", "Connected to"], loc="center", cellLoc="left")
t.auto_set_font_size(False); t.set_fontsize(8.5); t.scale(1, 1.4)
for (r, c), cell in t.get_celld().items():
    if r == 0: cell.set_facecolor("#2b6cb0"); cell.set_text_props(color="white", weight="bold")
ax.set_title("Wiring / pin connections", fontsize=11); plt.tight_layout(); plt.savefig(R + "fig_wiring.png", dpi=140); plt.close()

# 3) state machine
fig, ax = plt.subplots(figsize=(10, 3.6)); ax.set_xlim(0, 10); ax.set_ylim(0, 3.6); ax.axis("off")
box(ax, 0.2, 1.4, 1.9, 0.9, "MONITORING\n50 Hz IMU, 1 Hz GPS", "#c6f6d5", "#2f855a", 8)
box(ax, 3.1, 1.4, 1.9, 0.9, "EVALUATING\n2 s after impact", "#fefcbf", "#b7791f", 8)
box(ax, 6.0, 1.4, 1.9, 0.9, "ALERT_PENDING\nbuzzer, 15 s", "#fed7d7", "#c53030", 8)
box(ax, 8.2, 2.7, 1.6, 0.7, "SMS + GPS link", "#e9d8fd", "#6b46c1", 8)
box(ax, 8.2, 0.3, 1.6, 0.7, "COOLDOWN 60 s", "#e2e8f0", "#4a5568", 8)
arrow(ax, (2.1, 1.85), (3.1, 1.85), "|a| >= impact"); arrow(ax, (5.0, 1.85), (6.0, 1.85), "all 3 rules")
arrow(ax, (7.9, 2.1), (8.4, 2.7), "timeout"); arrow(ax, (9.0, 2.7), (9.0, 1.0), "after SMS")
ax.plot([4.05, 4.05, 1.0, 1.0], [1.4, 0.95, 0.95, 1.4], color="#2d3748", lw=1.2); ax.annotate("", (1.0, 1.4), (1.0, 1.2), arrowprops=dict(arrowstyle="-|>", color="#2d3748"))
ax.text(2.5, 0.78, "rules not met -> back to MONITORING", ha="center", fontsize=7)
ax.plot([6.9, 6.9, 0.6, 0.6], [1.4, 0.45, 0.45, 1.4], color="#2d3748", lw=1.2); ax.annotate("", (0.6, 1.4), (0.6, 1.2), arrowprops=dict(arrowstyle="-|>", color="#2d3748"))
ax.text(3.7, 0.28, "rider presses button -> alert cancelled -> back to MONITORING", ha="center", fontsize=7)
ax.set_title("Firmware state machine", fontsize=11); plt.tight_layout(); plt.savefig(R + "fig_state_machine.png", dpi=140); plt.close()

# 4) terminal-style image of simulation log
lines = open(R + "simulation_log.txt").read().split("\n")
fig = plt.figure(figsize=(11, 0.24 * len(lines) + 0.6)); fig.patch.set_facecolor("#1a202c")
fig.text(0.01, 0.985, "$ python simulate_pipeline.py", color="#68d391", family="monospace", fontsize=8, va="top")
for i, l in enumerate(lines):
    col = "#fc8181" if "ACCIDENT" in l and "NOT" not in l else "#f6e05e" if "---" in l else "#e2e8f0"
    fig.text(0.01, 0.95 - i * (0.9 / len(lines)), l[:150], color=col, family="monospace", fontsize=6.6, va="top")
plt.savefig(R + "fig_simulation_log.png", dpi=140, facecolor=fig.get_facecolor()); plt.close()
print("ok")

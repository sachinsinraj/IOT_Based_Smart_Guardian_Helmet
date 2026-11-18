# Smart Guardian IoT Helmet - Code Package

```
firmware/smart_helmet/smart_helmet.ino   ESP32 firmware (Arduino IDE)
simulation/generate_dataset.py           synthetic IMU+GPS window generator + feature extraction
simulation/detector.py                   rule-based detector (proposal + calibrated thresholds)
simulation/train_evaluate.py             rule-based vs Logistic Regression / Decision Tree / Random Forest
simulation/simulate_pipeline.py          alert state-machine simulation (log output)
simulation/make_diagrams.py              block / wiring / state-machine figures
simulation/run_all.sh                    reproduces everything
data/helmet_features.csv                 generated feature table (3500 windows)
results/                                 figures, metrics.json, simulation_log.txt
```

## Run the software simulation (no hardware)
```
pip install -r simulation/requirements.txt
cd simulation && ./run_all.sh
```

## Flash the firmware
1. Arduino IDE -> Boards Manager -> install "esp32" by Espressif; select "ESP32 Dev Module".
2. Library Manager -> install **TinyGPSPlus**.
3. Open `firmware/smart_helmet/smart_helmet.ino`, put real phone numbers in `CONTACTS[]`.
4. Optional dry run: set `#define SIMULATION_MODE 1`, upload, open Serial Monitor at 115200 baud;
   a scripted crash at t = 5 s runs the whole alert flow (press the button within 15 s to cancel).
5. Set `SIMULATION_MODE 0` for the real hardware (wiring in the file header and the report).

## Important notes
* The dataset is SYNTHETIC (physics-inspired); reported accuracy is an optimistic upper bound.
* Thresholds in firmware were calibrated on that synthetic data - re-tune on real ride data.
* SIM800L is 2G-only and needs ~2 A peak current; use SIM7600 (4G) if 2G is not available.
* Test the helmet only in safe, controlled conditions; never crash-test with a person wearing it.

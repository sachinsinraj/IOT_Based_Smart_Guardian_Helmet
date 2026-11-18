/*
 * Smart Guardian IoT Helmet - ESP32 firmware
 * IoT-Based Smart Helmet for Accident Detection and Real-Time Emergency Alert
 *
 * Sensors : MPU6050 (I2C), NEO-6M GPS (UART2), SIM800L / SIM7600 GSM (UART1)
 * Outputs : buzzer, status LED;  Input: cancel push-button
 * Library : TinyGPSPlus (Mikal Hart)  -> Arduino IDE: Sketch > Include Library > Manage Libraries
 * Board   : "ESP32 Dev Module"
 *
 * Wiring (ESP32 GPIO):
 *   MPU6050 SDA=21, SCL=22, VCC=3.3V, GND
 *   NEO-6M  TX -> GPIO16 (RX2), RX <- GPIO17 (TX2), VCC 3.3-5V per module
 *   GSM     TX -> GPIO26, RX <- GPIO27 (use level shifter / divider if module is 5V logic)
 *   Buzzer  GPIO25 (via transistor if needed),  LED GPIO2,  Button GPIO33 to GND (INPUT_PULLUP)
 *   NOTE: SIM800L draws ~2 A peaks -> power it from the Li-ion cell/buck converter, NOT the ESP32 3V3 pin.
 *   NOTE: SIM800L is 2G-only; if 2G is unavailable on your network use SIM7600 (same AT SMS commands).
 *
 * Set SIMULATION_MODE 1 to run WITHOUT hardware: a scripted crash is replayed and the full
 * alert flow is printed on the Serial Monitor (useful for screenshots / viva).
 */
#include <Wire.h>
#include <TinyGPSPlus.h>

#define SIMULATION_MODE 0          // 1 = replay scripted scenario, no sensors needed

#if SIMULATION_MODE
float simSpeed();
bool simRead();
#endif

// ---------------- pins ----------------
const int PIN_BUZZER = 25, PIN_LED = 2, PIN_BUTTON = 33;
const int GPS_RX = 16, GPS_TX = 17, GSM_RX = 26, GSM_TX = 27;
const uint8_t MPU_ADDR = 0x68;

// ---------------- detection thresholds ----------------
// Defaults from proposal: 4 g / 45 deg / 15 km/h.  Values below were calibrated on the synthetic
// dataset (see simulation/train_evaluate.py) - RE-CALIBRATE with real ride data.
const float IMPACT_G      = 3.0;   // peak |a| in g
const float TILT_DEG      = 15.0;  // gravity-vector change before vs after event
const float SPEED_DROP_KMH= 8.0;   // sudden speed reduction
const float MIN_SPEED_KMH = 15.0;  // rider must have been moving
const unsigned long ALERT_WINDOW_MS = 15000;   // time to cancel false alarm
const unsigned long COOLDOWN_MS     = 60000;   // avoid repeated SMS
const unsigned long EVAL_DELAY_MS   = 2000;    // wait after impact before evaluating
const int SAMPLE_PERIOD_MS = 20;               // 50 Hz

// ---------------- emergency contacts ----------------
const char* CONTACTS[] = { "+91XXXXXXXXXX", "+91YYYYYYYYYY" };   // <-- put real numbers
const int N_CONTACTS = 2;

HardwareSerial gsm(1);
HardwareSerial gpsSerial(2);
TinyGPSPlus gps;

enum State { MONITORING, EVALUATING, ALERT_PENDING, COOLDOWN };
State state = MONITORING;

float ax, ay, az, gx, gy, gz;                  // g and deg/s
float gravX = 0, gravY = 0, gravZ = 1;         // slow low-pass gravity estimate
float recX = 0, recY = 0, recZ = 1;            // recent (0.5 s) average accel
float peakG = 0, peakGyro = 0, speedPre = 0;
float speedHist[4] = {0, 0, 0, 0};             // last GPS speeds (km/h)
unsigned long tImpact = 0, tAlert = 0, tCooldown = 0, tLastSample = 0, tLastSpeed = 0;

// ---------------- MPU6050 ----------------
void mpuInit() {
  Wire.begin(21, 22);
  Wire.beginTransmission(MPU_ADDR); Wire.write(0x6B); Wire.write(0); Wire.endTransmission(true); // wake
  Wire.beginTransmission(MPU_ADDR); Wire.write(0x1C); Wire.write(0x18); Wire.endTransmission(true); // +/-16 g
  Wire.beginTransmission(MPU_ADDR); Wire.write(0x1B); Wire.write(0x18); Wire.endTransmission(true); // +/-2000 dps
  Wire.beginTransmission(MPU_ADDR); Wire.write(0x1A); Wire.write(0x03); Wire.endTransmission(true); // DLPF ~44 Hz
}

bool mpuRead() {
#if SIMULATION_MODE
  return simRead();
#else
  Wire.beginTransmission(MPU_ADDR); Wire.write(0x3B); if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)MPU_ADDR, 14, (int)true) != 14) return false;
  int16_t r[7]; for (int i = 0; i < 7; i++) r[i] = (Wire.read() << 8) | Wire.read();
  ax = r[0] / 2048.0; ay = r[1] / 2048.0; az = r[2] / 2048.0;       // 16 g -> 2048 LSB/g
  gx = r[4] / 16.4;  gy = r[5] / 16.4;  gz = r[6] / 16.4;           // 2000 dps -> 16.4 LSB/dps
  return true;
#endif
}

// ---------------- helpers ----------------
float mag3(float x, float y, float z) { return sqrtf(x*x + y*y + z*z); }

float angleBetween(float x1, float y1, float z1, float x2, float y2, float z2) {
  float d = (x1*x2 + y1*y2 + z1*z2) / (mag3(x1,y1,z1) * mag3(x2,y2,z2) + 1e-6);
  d = constrain(d, -1.0, 1.0);
  return acosf(d) * 180.0 / PI;
}

float currentSpeedKmh() {
#if SIMULATION_MODE
  return simSpeed();
#else
  return gps.speed.isValid() ? gps.speed.kmph() : 0.0;
#endif
}

void buzzer(bool on) { digitalWrite(PIN_BUZZER, on); digitalWrite(PIN_LED, on); }

// ---------------- GSM ----------------
bool gsmCmd(const char* cmd, const char* expect, unsigned long timeout = 2000) {
  gsm.println(cmd);
  unsigned long t = millis(); String resp = "";
  while (millis() - t < timeout) { while (gsm.available()) resp += (char)gsm.read(); if (resp.indexOf(expect) >= 0) return true; }
  return false;
}

bool sendSMS(const char* number, const String& text) {
#if SIMULATION_MODE
  Serial.printf("[SIM] AT+CMGS=\"%s\"  ->  \"%s\"  -> +CMGS: OK\n", number, text.c_str());
  return true;
#else
  if (!gsmCmd("AT+CMGF=1", "OK")) return false;                       // text mode
  gsm.print("AT+CMGS=\""); gsm.print(number); gsm.println("\"");
  delay(300);
  gsm.print(text); delay(100); gsm.write(26);                         // Ctrl+Z
  return gsmCmd("", "+CMGS", 10000);
#endif
}

void sendEmergency() {
  double lat = 0, lon = 0; bool fix = false;
#if SIMULATION_MODE
  lat = 28.6139; lon = 77.2090; fix = true;
#else
  unsigned long t = millis();                                          // wait up to 10 s for a fresh fix
  while (millis() - t < 10000) {
    while (gpsSerial.available()) gps.encode(gpsSerial.read());
    if (gps.location.isValid() && gps.location.age() < 3000) break;
  }
  if (gps.location.isValid()) { lat = gps.location.lat(); lon = gps.location.lng(); fix = true; }
#endif
  String msg = "EMERGENCY! Possible accident detected. ";
  if (fix) msg += "Location: https://maps.google.com/?q=" + String(lat, 6) + "," + String(lon, 6);
  else     msg += "GPS fix unavailable.";
  Serial.println("Sending SMS: " + msg);
  for (int i = 0; i < N_CONTACTS; i++) {
    for (int attempt = 0; attempt < 2; attempt++) if (sendSMS(CONTACTS[i], msg)) break;   // one retry
  }
}

// ---------------- setup / loop ----------------
void setup() {
  Serial.begin(115200);
  pinMode(PIN_BUZZER, OUTPUT); pinMode(PIN_LED, OUTPUT); pinMode(PIN_BUTTON, INPUT_PULLUP);
  gpsSerial.begin(9600, SERIAL_8N1, GPS_RX, GPS_TX);
  gsm.begin(9600, SERIAL_8N1, GSM_RX, GSM_TX);
  mpuInit();
  buzzer(false);
  Serial.println("Smart Guardian Helmet ready" + String(SIMULATION_MODE ? " (SIMULATION MODE)" : ""));
}

void loop() {
  while (gpsSerial.available()) gps.encode(gpsSerial.read());
  unsigned long now = millis();

  // keep a 4-second speed history (1 Hz)
  if (now - tLastSpeed >= 1000) {
    tLastSpeed = now;
    for (int i = 3; i > 0; i--) speedHist[i] = speedHist[i-1];
    speedHist[0] = currentSpeedKmh();
  }

  if (now - tLastSample >= SAMPLE_PERIOD_MS) {
    tLastSample = now;
    if (!mpuRead()) return;
    float a = mag3(ax, ay, az), w = mag3(gx, gy, gz);

    switch (state) {
      case MONITORING:
        // slow gravity estimate (time constant ~ 1 s) and fast "recent" estimate (~ 0.1 s)
        gravX += 0.02 * (ax - gravX); gravY += 0.02 * (ay - gravY); gravZ += 0.02 * (az - gravZ);
        recX  += 0.20 * (ax - recX);  recY  += 0.20 * (ay - recY);  recZ  += 0.20 * (az - recZ);
        if (a >= IMPACT_G) {                       // possible impact -> start evaluation window
          tImpact = now; peakG = a; peakGyro = w; speedPre = max(speedHist[1], speedHist[0]);
          state = EVALUATING;
          Serial.printf("IMPACT: %.1f g, speed before = %.0f km/h\n", a, speedPre);
        }
        break;

      case EVALUATING:
        peakG = max(peakG, a); peakGyro = max(peakGyro, w);
        recX  += 0.05 * (ax - recX); recY += 0.05 * (ay - recY); recZ += 0.05 * (az - recZ);
        if (now - tImpact >= EVAL_DELAY_MS) {
          float tilt = angleBetween(gravX, gravY, gravZ, recX, recY, recZ);
          float drop = speedPre - currentSpeedKmh();
          bool accident = peakG >= IMPACT_G && tilt >= TILT_DEG && speedPre >= MIN_SPEED_KMH && drop >= SPEED_DROP_KMH;
          Serial.printf("EVAL: peak=%.1f g gyro=%.0f dps tilt=%.0f deg speed drop=%.0f km/h -> %s\n",
                        peakG, peakGyro, tilt, drop, accident ? "ACCIDENT" : "no accident");
          if (accident && now > tCooldown) { state = ALERT_PENDING; tAlert = now; buzzer(true); }
          else { state = MONITORING; }
        }
        break;

      case ALERT_PENDING:
        if (digitalRead(PIN_BUTTON) == LOW) {      // rider cancels
          buzzer(false); state = MONITORING; Serial.println("Alert CANCELLED by rider");
        } else if (now - tAlert >= ALERT_WINDOW_MS) {
          buzzer(false);
          Serial.println("No response -> sending emergency alert");
          sendEmergency();
          state = COOLDOWN; tCooldown = now + COOLDOWN_MS;
        } else {
          digitalWrite(PIN_BUZZER, (now / 250) % 2);   // beep pattern
        }
        break;

      case COOLDOWN:
        if (now >= tCooldown) state = MONITORING;
        break;
    }
  }
}

// ======================= simulation helpers (SIMULATION_MODE) =======================
#if SIMULATION_MODE
unsigned long simStart = 0;
float simSpeed() {
  float t = (millis() - simStart) / 1000.0;
  if (t < 5) return 45; if (t < 6) return 45 - 40 * (t - 5); return 3;    // crash at t = 5 s
}
bool simRead() {
  if (simStart == 0) simStart = millis();
  float t = (millis() - simStart) / 1000.0;
  ax = 0.02; ay = 0.02; az = 1.0; gx = gy = gz = 2;
  if (t >= 5.0 && t < 5.06) { ax = 7.0; ay = 3.0; az = 2.0; gx = 700; }   // impact spike
  if (t >= 5.3) { ax = 0.9; ay = 0.2; az = 0.1; gx = gy = gz = 1; }       // helmet lying on its side
  return true;
}
#endif

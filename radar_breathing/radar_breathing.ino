/*
 * ============================================================
 *  Non-Contact Breathing Rate Monitor using HB100 Doppler Radar
 * ============================================================
 * Project: Non-Contact Vital Signs Monitor
 * Authors: Nirmal Verma, Divyanshi Sharma, Prashansa Sharma
 * Institution: SGSITS Indore, Dept. of Biomedical Engineering
 * Session: 2025-2026
 *
 * Hardware:
 *   - Arduino Uno R3 (ATmega328P, 16 MHz)
 *   - HB100 Doppler Radar Module (10.525 GHz CW)
 *   - SSD1306 OLED Display (0.96 inch, 128x64, I2C)
 *
 * Connections:
 *   HB100 VCC  -> Arduino 5V
 *   HB100 GND  -> Arduino GND
 *   HB100 IF   -> Arduino A0
 *   OLED VCC   -> Arduino 5V
 *   OLED GND   -> Arduino GND
 *   OLED SDA   -> Arduino A4
 *   OLED SCL   -> Arduino A5
 *
 * Signal Processing:
 *   - 50-sample moving average (low-pass filter for IF signal)
 *   - Peak detection with 2-second refractory period
 *   - Circular buffer (last 10 breaths) for stable BR calculation
 *   - Apnea detection at 8-second breath gap threshold
 *
 * Serial Output: Smoothed signal at 115200 baud for Python dashboard
 * ============================================================
 */

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1

Adafruit_SSD1306 oled(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// Signal processing variables
int smoothVal = 0, prevSmooth = 0;
bool rising = false;
float br = 0;
int peakVal = 0, valleyVal = 1023;

// Circular buffer for breath timestamps (last 10 breaths)
long breathTimes[10];
int breathIdx = 0, breathCount = 0;

void setup() {
  Serial.begin(115200);

  // Initialize OLED
  if (!oled.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("SSD1306 OLED not found. Check wiring.");
    while (true); // Halt if OLED not found
  }

  oled.clearDisplay();
  oled.setTextColor(WHITE);
  oled.setTextSize(1);
  oled.setCursor(15, 20);
  oled.println("BREATHING MONITOR");
  oled.setCursor(25, 35);
  oled.println("Initializing...");
  oled.display();
  delay(1500);

  // Initialize signal baseline
  smoothVal = analogRead(A0);
  prevSmooth = smoothVal;
  peakVal = smoothVal;
  valleyVal = smoothVal;
}

void loop() {
  int raw = analogRead(A0);

  // === 50-Sample Moving Average ===
  // Accumulates 50 ADC samples and computes average.
  // Acts as a low-pass filter to smooth the noisy HB100 IF signal.
  static long sum = 0;
  static int cnt = 0;

  sum += raw;
  cnt++;

  if (cnt >= 50) {
    prevSmooth = smoothVal;
    smoothVal = sum / cnt;
    sum = 0;
    cnt = 0;

    // === Peak Detection with Refractory Period ===
    // Detects breathing peaks (signal transitions from rising to falling).
    // Refractory period (2000 ms) prevents counting multiple peaks per breath.

    if (smoothVal > prevSmooth) {
      rising = true;
      if (smoothVal > peakVal) peakVal = smoothVal;
    }

    if (rising && smoothVal < prevSmooth) {
      rising = false;
      int swing = peakVal - valleyVal;

      // Validate peak: amplitude swing > 2 ADC units AND > 2 seconds since last breath
      long lastBreathTime = breathTimes[(breathIdx - 1 + 10) % 10];
      if (swing > 2 && millis() - lastBreathTime > 2000) {
        breathTimes[breathIdx % 10] = millis();
        breathIdx++;
        if (breathCount < 10) breathCount++;
      }

      valleyVal = smoothVal;
      peakVal = smoothVal;
    }

    if (smoothVal < valleyVal) valleyVal = smoothVal;

    // === Breathing Rate Calculation ===
    // Uses average inter-breath interval from circular buffer.
    // BR (breaths/min) = 60000 ms / avg_interval_ms
    if (breathCount >= 3) {
      int newest = (breathIdx - 1 + 10) % 10;
      int oldest = (breathIdx - breathCount + 10) % 10;
      long timeDiff = breathTimes[newest] - breathTimes[oldest];

      if (timeDiff > 0) {
        float avgInterval = (float)timeDiff / (breathCount - 1);
        br = 60000.0 / avgInterval;
        if (br > 30 || br < 4) br = 0; // Reject out-of-range values
      }
    }

    // === Apnea Detection ===
    // If no breath detected for > 8 seconds, flag as apnea
    long timeSinceLastBreath = 0;
    if (breathCount > 0) {
      int lastIdx = (breathIdx - 1 + 10) % 10;
      timeSinceLastBreath = millis() - breathTimes[lastIdx];
    }
    bool apnea = (breathCount > 0 && timeSinceLastBreath > 8000);

    // Send smoothed signal to Python dashboard via serial
    Serial.println(smoothVal);

    // === OLED Display Update (every 300 ms) ===
    static long lastDisplay = 0;
    if (millis() - lastDisplay >= 300) {
      lastDisplay = millis();
      oled.clearDisplay();
      oled.setTextColor(WHITE);

      // Header
      oled.setTextSize(1);
      oled.setCursor(5, 0);
      oled.println("BREATHING MONITOR");
      oled.drawLine(0, 10, 127, 10, WHITE);

      // Signal value
      oled.setCursor(5, 14);
      oled.print("Sig: ");
      oled.println(smoothVal);

      // Breathing rate (large font)
      oled.setCursor(5, 26);
      oled.print("Breaths/min:");
      oled.setTextSize(3);
      oled.setCursor(20, 38);

      if (apnea) {
        oled.setTextSize(1);
        oled.setCursor(10, 42);
        oled.println("!! APNEA !!");
        oled.println("No breath >8s");
      } else if (br >= 4 && br <= 30) {
        oled.println((int)br);
      } else {
        oled.println("--");
      }

      oled.display();
    }
  }

  delay(5);
}

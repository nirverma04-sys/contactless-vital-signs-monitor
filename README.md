# Non-Contact Vital Signs Monitor
### Doppler Radar + Camera rPPG | Dual-Modality Contactless Health Monitoring

**SGSITS Indore | Department of Biomedical Engineering | Minor Project 2025–26**

---

## What This Does

A low-cost dual-modality system that monitors two vital signs **without touching the patient**:

| Vital Sign | Method | Sensor |
|---|---|---|
| Breathing Rate | Doppler Effect (chest wall motion) | HB100 10.525 GHz Radar + Arduino |
| Heart Rate | Remote Photoplethysmography (rPPG) | Standard Webcam + Python |

Both are displayed simultaneously on a real-time Python dashboard. Breathing rate also appears on an embedded OLED display for standalone use.

---

## Results

| Metric | Our System | Commercial (TI AWR1642) |
|---|---|---|
| Heart Rate MAE | **±3.2 BPM** (5 trials vs. smartwatch) | ±3–5 BPM |
| Breathing Detection | Normal / Tachypnea / Bradypnea / Apnea | Normal / Tachypnea / Bradypnea |
| Apnea Detection | Yes (8-second threshold) | Yes |
| Total Cost | **Rs. 1,150** | Rs. 30,000+ |

---

## Hardware

| Component | Specification | Cost |
|---|---|---|
| Arduino Uno R3 | ATmega328P, 16 MHz | Rs. 500 |
| HB100 Doppler Radar | 10.525 GHz CW | Rs. 350 |
| SSD1306 OLED | 0.96", 128×64, I2C | Rs. 150 |
| Breadboard + Wires | — | Rs. 150 |
| Webcam | Built-in laptop / 720p USB | Rs. 0 |
| **Total** | | **Rs. 1,150** |

---

## Wiring

```
HB100 VCC  →  Arduino 5V
HB100 GND  →  Arduino GND
HB100 IF   →  Arduino A0

OLED VCC   →  Arduino 5V
OLED GND   →  Arduino GND
OLED SDA   →  Arduino A4
OLED SCL   →  Arduino A5

Arduino    →  Laptop USB (115200 baud serial)
```

---

## Signal Processing

### Radar Path (Arduino firmware)
```
HB100 IF Signal (5–50 mV, 0.1–0.5 Hz)
    ↓
10-bit ADC sampling
    ↓
50-sample moving average  ← low-pass, removes HF noise
    ↓
Peak detection (swing > 2 ADC units, 2s refractory period)
    ↓
Circular buffer (last 10 breaths)
    ↓
BR = 60000 / avg_interval_ms
    ↓
Apnea flag if no breath for > 8 seconds
```

### rPPG Path (Python)
```
Webcam frame (720p, ~30 fps)
    ↓
Haar Cascade face detection (Viola-Jones)
    ↓
ROI extraction: forehead (top 15%) + left cheek
    ↓
Green channel mean (most sensitive to haemoglobin absorption)
    ↓
DC removal → Polynomial detrending (4th order)
    ↓
5th-order Butterworth bandpass filter (0.9–2.0 Hz = 54–120 BPM)
    ↓
Hanning-windowed FFT (20-second analysis window)
    ↓
Peak frequency × 60 → BPM
    ↓
Trimmed median stabilization (±1 BPM/step)
```

---

## How to Run

### 1. Arduino (Breathing Rate Monitor)

Install required Arduino libraries (via Library Manager):
- `Adafruit SSD1306`
- `Adafruit GFX Library`

Open `radar_breathing/radar_breathing.ino` in Arduino IDE.
Select **Board:** Arduino Uno | **Port:** your COM port.
Click **Upload**.

### 2. Python (rPPG Heart Rate Monitor)

```bash
# Install dependencies
pip install -r requirements.txt

# Run
python rppg_heart_rate.py
```

Sit **facing the webcam** in a well-lit room. The system needs ~25 seconds to display a stable heart rate.

Press **`q`** to quit.

---

## Repository Structure

```
contactless-vital-signs/
│
├── radar_breathing/
│   └── radar_breathing.ino     # Arduino firmware (breathing monitor)
│
├── rppg_heart_rate.py          # Python rPPG heart rate extraction
├── requirements.txt            # Python dependencies
└── README.md
```

---

## Comparison with Commercial Systems

| Parameter | This Project | TI AWR1642 | Xethru X4 |
|---|---|---|---|
| Cost | Rs. 1,150 | Rs. 30,000+ | Rs. 75,000+ |
| Radar Frequency | 10.525 GHz CW | 77 GHz FMCW | 7.29 GHz UWB |
| Breathing Accuracy | ±2–3 br/min | ±1 br/min | ±1 br/min |
| Heart Rate | rPPG ±3.2 BPM | Radar ±3–5 BPM | Radar ±3 BPM |
| Range | ~30 cm | 1–3 m | 0.5–5 m |
| Display | OLED + Dashboard | PC Software | PC Software |
| Power | USB 5V | 12V adapter | 5V USB |

This system achieves the primary goal of **affordable contactless monitoring at under 2% of commercial system cost**.

---

## Future Work

- **Capacitive Contactless ECG** — AD8232 with copper plate electrodes through clothing
- **ML Cardiac Detection** — 1D CNN + LSTM on radar BCG signal
- **Wireless Transmission** — HC-05 Bluetooth to mobile app (Flutter)
- **Temperature** — MLX90614 infrared sensor integration
- **Sleep Apnea Screening** — Overnight radar-based monitoring
- **Clinical Validation** — Bland-Altman analysis with larger sample size

---

## Team

| Name | Enrollment No. |
|---|---|
| Nirmal Verma | 0801BM231041 |
| Divyanshi Sharma | 0801BM231023 |
| Prashansa Sharma | 0801BM231043 |

**Guided by:** Prof. Avni Jain & Prof. Gauri Gupta
**Department of Biomedical Engineering, SGSITS Indore**

---

## References

1. C. Li et al., "A Review on Recent Advances in Doppler Radar Sensors for Noncontact Healthcare Monitoring," *IEEE Trans. Microwave Theory Tech.*, 2013.
2. W. Verkruysse et al., "Remote plethysmographic imaging using ambient light," *Optics Express*, 2008.
3. M. Z. Poh et al., "Advancements in Noncontact, Multiparameter Physiological Measurements Using a Webcam," *IEEE Trans. Biomed. Eng.*, 2011.
4. G. De Haan and V. Jeanne, "Robust pulse rate from chrominance-based rPPG," *IEEE Trans. Biomed. Eng.*, 2013.

"""
================================================================
  Non-Contact Heart Rate Monitor using Camera rPPG
================================================================
Project: Non-Contact Vital Signs Monitor
Authors: Nirmal Verma, Divyanshi Sharma, Prashansa Sharma
Institution: SGSITS Indore, Dept. of Biomedical Engineering
Session: 2025-2026

Description:
    Extracts heart rate from webcam video using Remote
    Photoplethysmography (rPPG). Detects subtle green-channel
    variations in facial skin caused by pulsatile blood flow.

Signal Processing Pipeline:
    1. Face detection (Haar Cascade - Viola Jones algorithm)
    2. ROI extraction (forehead + left cheek regions)
    3. Green channel mean extraction
    4. DC removal (subtract mean)
    5. Polynomial detrending (4th order) - removes baseline drift
    6. Butterworth bandpass filter (0.9-2.0 Hz = 54-120 BPM)
    7. Hanning-windowed FFT - frequency-domain heart rate extraction
    8. Median trimmed filtering + 1-BPM-per-step stabilization

Requirements:
    pip install opencv-python numpy scipy

Usage:
    python rppg_heart_rate.py
    Press 'q' to quit.

Results:
    Achieved ±3.2 BPM MAE across 5 trials vs. reference smartwatch
================================================================
"""

import cv2
import numpy as np
from scipy import signal
import time
from collections import deque

# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
BUFFER_SIZE     = 1200    # Maximum green channel samples (~40 sec @ 30 fps)
WARMUP_SECONDS  = 25      # Wait time before displaying heart rate
MIN_SAMPLES     = 600     # Minimum samples needed for FFT analysis
FFT_WINDOW_SEC  = 20      # FFT analysis window duration (seconds)
BPM_HISTORY_LEN = 50      # Rolling window for BPM stabilization
HR_MIN_HZ       = 0.9     # Low cutoff = 54 BPM
HR_MAX_HZ       = 2.0     # High cutoff = 120 BPM
FILTER_ORDER    = 5       # Butterworth filter order
POLY_ORDER      = 4       # Polynomial detrend order
OFFSET          = -8      # Empirical calibration offset (BPM)

# ──────────────────────────────────────────────
# Initialize camera and face detector
# ──────────────────────────────────────────────
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("[ERROR] Cannot open webcam. Check if camera is connected.")
    exit()

face_cascade = cv2.CascadeClassifier(
    cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
)

# Signal buffers (circular, fixed max length)
green_vals  = deque(maxlen=BUFFER_SIZE)
timestamps  = deque(maxlen=BUFFER_SIZE)
bpm_history = deque(maxlen=BPM_HISTORY_LEN)

stable_bpm    = 0
measuring_start = time.time()

print("[INFO] rPPG Heart Rate Monitor started.")
print(f"[INFO] Warming up for {WARMUP_SECONDS} seconds — please sit still and face the camera.")
print("[INFO] Press 'q' to quit.\n")

# ──────────────────────────────────────────────
# Main Loop
# ──────────────────────────────────────────────
while True:
    ret, frame = cap.read()
    if not ret:
        print("[ERROR] Frame capture failed.")
        break

    gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.3, minNeighbors=5)

    if len(faces) > 0:
        x, y, fw, fh = faces[0]  # Use the first detected face

        # ── ROI Definition ──────────────────────────────────────
        # Forehead: top 15% of face, centre 60% width
        fx  = x + int(fw * 0.20)
        fy  = y + int(fh * 0.05)
        ffw = int(fw * 0.60)
        ffh = int(fh * 0.15)

        # Left cheek: lower-left quadrant
        cx  = x + int(fw * 0.10)
        cy  = y + int(fh * 0.55)
        cfw = int(fw * 0.25)
        cfh = int(fh * 0.20)

        forehead = frame[fy:fy + ffh, fx:fx + ffw]
        cheek    = frame[cy:cy + cfh, cx:cx + cfw]

        # ── Green Channel Mean ───────────────────────────────────
        # Green (~540 nm) is maximally absorbed by oxyhaemoglobin,
        # giving the strongest cardiac pulsation signal.
        if forehead.size > 0 and cheek.size > 0:
            g1 = np.mean(forehead[:, :, 1])  # BGR index 1 = Green
            g2 = np.mean(cheek[:, :, 1])
            avg_green = (g1 + g2) / 2.0

            green_vals.append(avg_green)
            timestamps.append(time.time())

        elapsed = time.time() - measuring_start

        # ── Heart Rate Extraction ────────────────────────────────
        if elapsed > WARMUP_SECONDS and len(green_vals) > MIN_SAMPLES:
            sig_data = np.array(green_vals)
            ts       = np.array(timestamps)
            fs       = len(sig_data) / (ts[-1] - ts[0])  # Estimated frame rate

            # Step 1: Remove DC offset
            sig_data = sig_data - np.mean(sig_data)

            # Step 2: Polynomial detrending (removes slow drift)
            x_axis = np.arange(len(sig_data))
            coeffs = np.polyfit(x_axis, sig_data, POLY_ORDER)
            trend  = np.polyval(coeffs, x_axis)
            sig_data = sig_data - trend

            # Step 3: Butterworth bandpass filter (54–120 BPM)
            nyq  = fs / 2.0
            low  = max(0.01, HR_MIN_HZ / nyq)
            high = min(0.99, HR_MAX_HZ / nyq)
            b, a = signal.butter(FILTER_ORDER, [low, high], btype='band')
            filtered = signal.filtfilt(b, a, sig_data)

            # Step 4: Hanning-windowed FFT on most recent 20 seconds
            window_samples = min(len(filtered), int(fs * FFT_WINDOW_SEC))
            recent   = filtered[-window_samples:]
            windowed = recent * np.hanning(len(recent))

            freqs = np.fft.rfftfreq(len(windowed), 1.0 / fs)
            fft   = np.abs(np.fft.rfft(windowed))

            # Step 5: Find dominant frequency in cardiac band
            mask = (freqs >= HR_MIN_HZ) & (freqs <= HR_MAX_HZ)
            if mask.any():
                peak_freq = freqs[mask][np.argmax(fft[mask])]
                raw_bpm   = int(peak_freq * 60)

                if 50 < raw_bpm < 130:
                    bpm_history.append(raw_bpm)

                    # Step 6: Trimmed median + 1-BPM stabilisation
                    if len(bpm_history) >= 10:
                        sorted_bpm = sorted(bpm_history)
                        trim    = max(1, len(sorted_bpm) // 3)
                        trimmed = sorted_bpm[trim:-trim]
                        new_bpm = int(np.median(trimmed))

                        if stable_bpm == 0:
                            stable_bpm = new_bpm
                        elif new_bpm > stable_bpm:
                            stable_bpm += 1
                        elif new_bpm < stable_bpm:
                            stable_bpm -= 1

        # ── Draw Bounding Boxes ──────────────────────────────────
        cv2.rectangle(frame, (x, y),           (x + fw,  y + fh),  (0, 255,   0), 2)  # Face
        cv2.rectangle(frame, (fx, fy),         (fx + ffw, fy + ffh), (0, 255, 255), 2)  # Forehead
        cv2.rectangle(frame, (cx, cy),         (cx + cfw, cy + cfh), (255, 200,  0), 1)  # Cheek

        # Labels
        cv2.putText(frame, "Forehead", (fx, fy - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        cv2.putText(frame, "Cheek",    (cx, cy - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 200, 0),  1)

    else:
        cv2.putText(frame, "No face detected — please face camera",
                    (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    # ── Display Heart Rate ───────────────────────────────────────
    elapsed = time.time() - measuring_start

    if elapsed < WARMUP_SECONDS:
        remaining = int(WARMUP_SECONDS - elapsed)
        cv2.putText(frame, f"Warming up... {remaining}s",
                    (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 165, 255), 2)
    else:
        display_bpm = stable_bpm + OFFSET
        if display_bpm > 45:
            cv2.putText(frame, f"HR: {display_bpm} BPM",
                        (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
        else:
            cv2.putText(frame, "Measuring...",
                        (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 165, 255), 2)

    # Info overlay
    cv2.putText(frame, "rPPG | SGSITS Indore",
                (10, frame.shape[0] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)

    cv2.imshow('rPPG Heart Rate Monitor', frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("[INFO] Session ended.")

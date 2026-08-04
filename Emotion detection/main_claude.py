import os
import cv2
import numpy as np
import sys
import RPi.GPIO as GPIO
import time
import tflite_runtime.interpreter as tflite
from picamera2 import Picamera2

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CASC_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

IM_WIDTH  = 320
IM_HEIGHT = 180

CONFIDENCE_THRESHOLD = 70
REPEAT_THRESHOLD     = 3
SMOOTH_ALPHA         = 0.4

MODEL_PATH = "emotions.tflite"

MAPPER = {
    0: 'anger',
    1: 'disgust',
    2: 'fear',
    3: 'happiness',
    4: 'sadness',
    5: 'surprise',
    6: 'neutral',
}

# ---------------------------------------------------------------------------
# GPIO setup
# ---------------------------------------------------------------------------

GPIO.setmode(GPIO.BOARD)
BUZZER_PIN = 8
GPIO.setup(BUZZER_PIN, GPIO.OUT)

def buzz():
    GPIO.output(BUZZER_PIN, True)
    time.sleep(0.1)
    GPIO.output(BUZZER_PIN, False)
    time.sleep(0.2)
    GPIO.output(BUZZER_PIN, True)
    time.sleep(0.1)
    GPIO.output(BUZZER_PIN, False)

# ---------------------------------------------------------------------------
# Load face detector
# ---------------------------------------------------------------------------

face_cascade = cv2.CascadeClassifier(CASC_PATH)

# ---------------------------------------------------------------------------
# Load TFLite model ONCE
# ---------------------------------------------------------------------------

print("[INFO] Loading TFLite model...")
interpreter = tflite.Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()

input_details  = interpreter.get_input_details()
output_details = interpreter.get_output_details()

print("[INFO] Model loaded.")

# ---------------------------------------------------------------------------
# Camera setup (picamera2)
# ---------------------------------------------------------------------------

picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(
    main={"size": (IM_WIDTH, IM_HEIGHT)}
))
picam2.start()

# ---------------------------------------------------------------------------
# State variables
# ---------------------------------------------------------------------------

prev_emo_state      = 6
confirmed_emo_state = 6
repeats             = 0

smooth_box = None

freq = cv2.getTickFrequency()
frame_rate_calc = 1.0
font = cv2.FONT_HERSHEY_SIMPLEX

print("[INFO] Starting capture loop. Press 'q' to quit.")

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

while True:

    t1 = cv2.getTickCount()

    frame = picam2.capture_array()
    frame = cv2.resize(frame, (IM_WIDTH, IM_HEIGHT))
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # --- Face detection ---
    faces = face_cascade.detectMultiScale(
        frame_gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(50, 50),
        flags=cv2.CASCADE_SCALE_IMAGE,
    )

    face_found = len(faces) > 0

    if face_found:
        (x, y, w, h) = max(faces, key=lambda f: f[2] * f[3])
        box = np.array([x, y, w, h], dtype=float)

        if smooth_box is None:
            smooth_box = box.copy()
        else:
            smooth_box = SMOOTH_ALPHA * box + (1 - SMOOTH_ALPHA) * smooth_box

        sx, sy, sw, sh = smooth_box.astype(int)
        box_size = max(sw, sh)

        # Clamp bounding box
        h_img, w_img = frame_gray.shape

        sx = max(0, sx)
        sy = max(0, sy)
        ex = min(w_img, sx + box_size)
        ey = min(h_img, sy + box_size)

        roi_gray = frame_gray[sy:ey, sx:ex]

        cv2.rectangle(frame, (sx, sy), (ex, ey), (0, 255, 0), 2)

    else:
        roi_gray = frame_gray

    # Skip if ROI too small
    if roi_gray.shape[0] < 20 or roi_gray.shape[1] < 20:
        continue

    # --- Preprocess ---
    face_48 = cv2.resize(roi_gray, (48, 48))
    face_input = np.expand_dims(face_48 / 255.0, axis=2).astype('float32')

    # --- Inference ---
    interpreter.set_tensor(input_details[0]['index'], [face_input])
    interpreter.invoke()
    output_data = interpreter.get_tensor(output_details[0]['index'])[0]

    best_idx   = int(np.argmax(output_data))
    confidence = float(output_data[best_idx]) * 100
    emo_label  = MAPPER[best_idx]

    # --- State logic ---
    if confidence >= CONFIDENCE_THRESHOLD:
        if best_idx == prev_emo_state:
            repeats += 1
        else:
            repeats = 1
            prev_emo_state = best_idx

        if repeats >= REPEAT_THRESHOLD:
            if best_idx != confirmed_emo_state:
                print(f"[STATE CHANGE] {MAPPER[confirmed_emo_state]} → {emo_label}")
                buzz()
                confirmed_emo_state = best_idx
            repeats = 0

    # --- Display ---
    cv2.putText(frame, f"{emo_label} {confidence:.0f}%", 
                (10, IM_HEIGHT - 10), font, 0.6, (0, 255, 0), 2)

    cv2.putText(frame, f"FPS: {frame_rate_calc:.1f}", 
                (10, 25), font, 0.6, (255, 255, 0), 2)

    cv2.imshow("Emotion Detector", frame)

    # --- FPS ---
    t2 = cv2.getTickCount()
    frame_rate_calc = freq / (t2 - t1)

    # Exit
    if cv2.waitKey(1) == ord('q'):
        break

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

picam2.stop()
GPIO.cleanup()
cv2.destroyAllWindows()
print("[INFO] Done.")
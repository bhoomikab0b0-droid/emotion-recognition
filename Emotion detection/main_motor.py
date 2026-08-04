import os
import cv2
import numpy as np
import sys
import RPi.GPIO as GPIO
import time
import tflite_runtime.interpreter as tflite
from picamera2 import Picamera2
import serial
import pigpio

# ---------------------------------------------------------------------------
# TEXT TO SPEECH (NEW)
# ---------------------------------------------------------------------------
def speak(text):
    os.system(f'espeak "{text}"')

responses = {
    "HAPPINESS": "You look happy today, whats up!",
    "SADNESS": "Hey, everything okay?",
    "ANGER": "You seem upset, take it easy.",
    "SURPRISE": "Wow, that surprised you!",
    "FEAR": "Don't worry, it's okay.",
    "DISGUST": "Hmm, that doesn't look good.",
    "NEUTRAL": "Just chilling, huh?"
}

# ---------------------------------------------------------------------------
# PIGPIO SETUP
# ---------------------------------------------------------------------------
pi = pigpio.pi()
SERVO_PIN = 18

if not pi.connected:
    print("❌ Run: sudo pigpiod")
    exit()

# ---------------------------------------------------------------------------
# SERIAL SETUP
# ---------------------------------------------------------------------------
ser = serial.Serial('/dev/ttyACM0', 9600)
time.sleep(2)

last_sent = ""

# ---------------------------------------------------------------------------
# SERVO SETTINGS
# ---------------------------------------------------------------------------
current_pos = 0.0
target_pos = 0.0

SMOOTH_STEP = 0.1
DEAD_ZONE = 0.1
UPDATE_THRESHOLD = 0.02

def set_servo(position):
    pulsewidth = 1500 + position * 700
    pulsewidth = max(800, min(2200, pulsewidth))
    pi.set_servo_pulsewidth(SERVO_PIN, pulsewidth)

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
CASC_PATH = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"

IM_WIDTH  = 320
IM_HEIGHT = 180

CONFIDENCE_THRESHOLD = 70
REPEAT_THRESHOLD     = 3
SMOOTH_ALPHA         = 0.4

MODEL_PATH = "emotions.tflite"

MAPPER = {
    0: 'ANGER',
    1: 'DISGUST',
    2: 'FEAR',
    3: 'HAPPINESS',
    4: 'SADNESS',
    5: 'SURPRISE',
    6: 'NEUTRAL',
}

# ---------------------------------------------------------------------------
# GPIO BUZZER
# ---------------------------------------------------------------------------
GPIO.setmode(GPIO.BOARD)
BUZZER_PIN = 8
GPIO.setup(BUZZER_PIN, GPIO.OUT)

def buzz():
    GPIO.output(BUZZER_PIN, True)
    time.sleep(0.1)
    GPIO.output(BUZZER_PIN, False)

# ---------------------------------------------------------------------------
# LOAD MODEL
# ---------------------------------------------------------------------------
face_cascade = cv2.CascadeClassifier(CASC_PATH)

print("[INFO] Loading model...")
interpreter = tflite.Interpreter(model_path=MODEL_PATH)
interpreter.allocate_tensors()

input_details  = interpreter.get_input_details()
output_details = interpreter.get_output_details()

print("[INFO] Model loaded.")

# ---------------------------------------------------------------------------
# CAMERA
# ---------------------------------------------------------------------------
picam2 = Picamera2()
picam2.configure(picam2.create_preview_configuration(
    main={"size": (IM_WIDTH, IM_HEIGHT)}
))
picam2.start()

# ---------------------------------------------------------------------------
# STATE VARIABLES
# ---------------------------------------------------------------------------
prev_emo_state      = 6
confirmed_emo_state = 6
repeats             = 0

smooth_box = None

no_face_counter = 0
NO_FACE_LIMIT = 10

freq = cv2.getTickFrequency()
font = cv2.FONT_HERSHEY_SIMPLEX

print("[INFO] Running... Press q to exit")

# ---------------------------------------------------------------------------
# MAIN LOOP
# ---------------------------------------------------------------------------
while True:

    frame = picam2.capture_array()
    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    frame = cv2.resize(frame, (IM_WIDTH, IM_HEIGHT))
    frame_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    faces = face_cascade.detectMultiScale(
        frame_gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(50, 50)
    )

    face_found = len(faces) > 0

    if face_found:
        no_face_counter = 0

        (x, y, w, h) = max(faces, key=lambda f: f[2]*f[3])

        # ---------------- SERVO ----------------
        frame_center = IM_WIDTH / 2
        face_center = x + w / 2

        error = -(face_center - frame_center) / frame_center
        error = error * 1.5
        error = max(min(error, 1.0), -1.0)

        if abs(error) < DEAD_ZONE:
            error = 0

        target_pos = error

        if abs(target_pos - current_pos) > UPDATE_THRESHOLD:
            current_pos += (target_pos - current_pos) * SMOOTH_STEP
            set_servo(current_pos)

        roi_gray = frame_gray[y:y+h, x:x+w]

    else:
        roi_gray = frame_gray
        no_face_counter += 1

        target_pos = 0
        if abs(target_pos - current_pos) > UPDATE_THRESHOLD:
            current_pos += (target_pos - current_pos) * SMOOTH_STEP
            set_servo(current_pos)

    if roi_gray.shape[0] < 20 or roi_gray.shape[1] < 20:
        continue

    # ---------------- MODEL ----------------
    face_48 = cv2.resize(roi_gray, (48,48))
    face_input = np.expand_dims(face_48/255.0, axis=2).astype('float32')

    interpreter.set_tensor(input_details[0]['index'], [face_input])
    interpreter.invoke()

    output = interpreter.get_tensor(output_details[0]['index'])[0]

    best_idx = int(np.argmax(output))
    confidence = float(output[best_idx])*100
    emotion = MAPPER[best_idx]

    # ---------------- EMOTION ACTION ----------------
    if face_found and confidence >= CONFIDENCE_THRESHOLD:

        if best_idx == prev_emo_state:
            repeats += 1
        else:
            repeats = 1
            prev_emo_state = best_idx

        if repeats >= REPEAT_THRESHOLD:

            if emotion != last_sent:
                print("[SEND]", emotion)
                ser.write((emotion + "\n").encode())

                # 🔊 SPEAK
                if emotion in responses:
                    speak(responses[emotion])

                last_sent = emotion

            if best_idx != confirmed_emo_state:
                buzz()
                confirmed_emo_state = best_idx

            repeats = 0

    elif no_face_counter > NO_FACE_LIMIT:
        if last_sent != "NEUTRAL":
            print("[SEND] NEUTRAL")
            ser.write(("NEUTRAL\n").encode())
            speak(responses["NEUTRAL"])
            last_sent = "NEUTRAL"

    # ---------------- DISPLAY ----------------
    cv2.putText(frame, f"{emotion} {confidence:.0f}%",
                (10, IM_HEIGHT-10), font, 0.6, (0,255,0), 2)

    cv2.imshow("Emotion Detector", frame)

    if cv2.waitKey(1) == ord('q'):
        break

# ---------------------------------------------------------------------------
# CLEANUP
# ---------------------------------------------------------------------------
picam2.stop()
GPIO.cleanup()
cv2.destroyAllWindows()
ser.close()

pi.set_servo_pulsewidth(SERVO_PIN, 0)
pi.stop()

print("[INFO] Done.")
import cv2
import mediapipe as mp
import numpy as np
import time
import sqlite3
import threading
import os

# Constants
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
EAR_THRESHOLD = 0.20
WINDOW_SIZE = 60     
PERCLOS_THRESHOLD = 0.33

def EAR(eye):
    p1, p2, p3, p4, p5, p6 = eye
    v1 = np.linalg.norm(np.array(p2) - np.array(p6))
    v2 = np.linalg.norm(np.array(p3) - np.array(p5))
    h = np.linalg.norm(np.array(p1) - np.array(p4))
    return (v1 + v2) / (2.0 * h) if h != 0 else 0

class DrowsinessMonitor:
    def __init__(self, db_path="drowsiness.db", user_id=1):
        self.db_path = db_path
        self.user_id = user_id
        self.running = False
        self.overlay_landmarks = True
        self.session_id = None
        self.eye_states = []
        self.latest_frame = None
        self.last_save = time.time()
        self.latest_stats = {"ear": 0, "perclos": 0, "eye_closed": 0, "fps": 0, "drowsy": False}
        self.lock = threading.Lock()

        # MediaPipe Setup
        self.mpFaceMesh = mp.solutions.face_mesh
        self.faceMesh = self.mpFaceMesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=True, 
        min_detection_confidence=0.5, # Lowering slightly speeds up the initial find
        min_tracking_confidence=0.5,
        static_image_mode=False # CRITICAL: This tells MediaPipe to treat frames as a video stream
        )
        self.mpDraw = mp.solutions.drawing_utils
        self.drawSpec = self.mpDraw.DrawingSpec(thickness=1, circle_radius=1)

    def create_session(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        # Using standard 'now' for cloud compatibility
        cur.execute("INSERT INTO sessions (user_id, start_time) VALUES (?, datetime('now'))", (self.user_id,))
        self.session_id = cur.lastrowid
        conn.commit()
        conn.close()

    def end_session(self):
        if self.session_id:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("UPDATE sessions SET end_time=datetime('now') WHERE id=?", (self.session_id,))
            conn.commit()
            conn.close()

    def save_record(self, ear, perclos, eye_closed):
        if not self.session_id: return
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("INSERT INTO perclos_data (session_id, ear, perclos, eye_closed) VALUES (?, ?, ?, ?)",
                    (self.session_id, ear, perclos, eye_closed))
        conn.commit()
        conn.close()

    # --- NEW METHOD FOR OPTION B ---
    def process_web_frame(self, image_bytes):
        """Processes a single frame sent from the browser."""
        # Convert bytes to OpenCV image
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return self.latest_stats

        # Pre-processing
        img = cv2.flip(img, 1)
        imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        results = self.faceMesh.process(imgRGB)

        ear, perclos, eye_closed, drowsy = 0.0, 0.0, 0, False

        if results.multi_face_landmarks:
            for faceLMS in results.multi_face_landmarks:
                ih, iw, _ = img.shape
                left_eye, right_eye = [], []

                for idx in LEFT_EYE:
                    lm = faceLMS.landmark[idx]
                    left_eye.append((int(lm.x * iw), int(lm.y * ih)))
                for idx in RIGHT_EYE:
                    lm = faceLMS.landmark[idx]
                    right_eye.append((int(lm.x * iw), int(lm.y * ih)))

                ear = (EAR(left_eye) + EAR(right_eye)) / 2
                eye_closed = 1 if ear < EAR_THRESHOLD else 0
                
                with self.lock:
                    self.eye_states.append(eye_closed)
                    if len(self.eye_states) > WINDOW_SIZE: 
                        self.eye_states.pop(0)
                    perclos = sum(self.eye_states) / len(self.eye_states)
                
                drowsy = perclos > PERCLOS_THRESHOLD

                if self.overlay_landmarks:
                    self.mpDraw.draw_landmarks(img, faceLMS, self.mpFaceMesh.FACEMESH_CONTOURS, self.drawSpec, self.drawSpec)

                if drowsy:
                    cv2.putText(img, "ALERT: DROWSY", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

        # Update latest frame and stats
        with self.lock:
            ret, buffer = cv2.imencode(".jpg", img)
            if ret: 
                self.latest_frame = buffer.tobytes()
            
            self.latest_stats = {
                "ear": round(float(ear), 3), 
                "perclos": round(float(perclos), 3),
                "eye_closed": int(eye_closed), 
                "drowsy": bool(drowsy)
            }

        # Auto-save to DB every 2 seconds
        if time.time() - self.last_save >= 2:
            self.save_record(ear, perclos, eye_closed)
            self.last_save = time.time()

        return self.latest_stats

    def stop(self):
        self.running = False
        self.end_session()
        with self.lock:
            self.eye_states = []
            self.latest_frame = None
            self.latest_stats = {"ear": 0, "perclos": 0, "eye_closed": 0, "fps": 0, "drowsy": False}

    def set_overlay(self, enabled):
        with self.lock: self.overlay_landmarks = enabled

    def get_latest_frame(self):
        with self.lock: return self.latest_frame

    def get_latest_stats(self):
        with self.lock: return dict(self.latest_stats)
import cv2
import mediapipe as mp
import numpy as np
import time
import sqlite3
import threading
import winsound


# Constants
LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
EAR_THRESHOLD = 0.22 # Adjusted slightly for general use
WINDOW_SIZE = 60     # Smaller window is more responsive
PERCLOS_THRESHOLD = 0.35

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
        self.last_beep = 0
        self.latest_stats = {"ear": 0, "perclos": 0, "eye_closed": 0, "fps": 0, "drowsy": False}
        self.lock = threading.Lock()

        # MediaPipe Setup (Optimized for performance)
        self.mpFaceMesh = mp.solutions.face_mesh
        self.faceMesh = self.mpFaceMesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=False, # DISABLED to prevent friend's laptop crash
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mpDraw = mp.solutions.drawing_utils
        self.drawSpec = self.mpDraw.DrawingSpec(thickness=1, circle_radius=1)

    def create_session(self):
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()
        cur.execute("INSERT INTO sessions (user_id, start_time) VALUES (?, datetime('now','+5 hours','+30 minutes'))", (self.user_id,))
        self.session_id = cur.lastrowid
        conn.commit()
        conn.close()

    def end_session(self):
        if self.session_id:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("UPDATE sessions  SET end_time=datetime('now','+5 hours','+30 minutes') WHERE id=?", (self.session_id,))
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

    def start(self):
        self.eye_states = []
        self.running = True
        self.create_session()
        
        # Using CAP_DSHOW for Windows stability
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        # cap = cv2.flip(cap,1)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        pTime = time.time()
        last_save = time.time()

        while self.running:
            success, img = cap.read()
            if not success:
                time.sleep(0.01)
                continue
            img = cv2.flip(img ,1)
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
                    self.eye_states.append(eye_closed)
                    if len(self.eye_states) > WINDOW_SIZE: self.eye_states.pop(0)

                    perclos = sum(self.eye_states) / len(self.eye_states)
                    drowsy = perclos > PERCLOS_THRESHOLD

                    # if self.overlay_landmarks:
                    #     self.mpDraw.draw_landmarks(img, faceLMS, self.mpFaceMesh.FACEMESH_CONTOURS, self.drawSpec, self.drawSpec)
                    #     if drowsy:
                    #         cv2.putText(img, "ALERT: DROWSY", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 3)

                    # draw landmarks only
                    if self.overlay_landmarks:
                        self.mpDraw.draw_landmarks(img,  faceLMS, self.mpFaceMesh.FACEMESH_CONTOURS,  self.drawSpec, self.drawSpec)

                    # draw alert ALWAYS when drowsy
                    if drowsy:
                        cv2.putText( img, "ALERT: DROWSY",  (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1,  (0, 0, 255),3)
                        #winsound
                        if time.time() - self.last_beep > 2:
                            winsound.Beep(1000, 800)
                            self.last_beep = time.time()
                        

            # FPS and Timing
            cTime = time.time()
            fps = 1 / (cTime - pTime) if (cTime - pTime) > 0 else 0
            pTime = cTime

            if time.time() - last_save >= 1:
                self.save_record(ear, perclos, eye_closed)
                last_save = time.time()

            # Thread-safe update
            with self.lock:
                self.latest_stats = {
                    "ear": round(float(ear), 3), "perclos": round(float(perclos), 3),
                    "eye_closed": int(eye_closed), "fps": round(float(fps), 1), "drowsy": bool(drowsy)
                }
                ret, buffer = cv2.imencode(".jpg", img)
                if ret: self.latest_frame = buffer.tobytes()
            
            # Windows WaitKey Fix
            if cv2.waitKey(1) & 0xFF == ord('q'): break

        cap.release()
        self.faceMesh.close() # CRITICAL: Releases C++ memory

    def stop(self):
        self.running = False
        self.end_session()
        with self.lock:
            self.eye_states = []
            self.latest_frame = None
            self.latest_stats = {
                "ear": 0,
                "perclos": 0,
                "eye_closed": 0,
                "fps": 0,
                "drowsy": False
            }

    def set_overlay(self, enabled):
        with self.lock: self.overlay_landmarks = enabled

    def get_latest_frame(self):
        with self.lock: return self.latest_frame

    def get_latest_stats(self):
        with self.lock: return dict(self.latest_stats)
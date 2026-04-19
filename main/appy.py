from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
import sqlite3
import time
import os

from database import init_db, DB_PATH
from drowsiness import DrowsinessMonitor

app = Flask(__name__)
# Crucial for Render: ensure sessions are handled strictly
app.secret_key = os.environ.get("SECRET_KEY", "secret_key")
app.config.update(
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
)

# Ensure DB is ready on startup
with app.app_context():
    init_db()

monitor = None

def cleanup_monitor():
    global monitor
    if monitor:
        monitor.end_session()
    monitor = None

# --- AUTH & NAVIGATION ROUTES ---
@app.route("/")
def landing():
    return render_template("landing.html")

@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('home.html')

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username=? AND password=?", (username, password))
        user = cur.fetchone()
        conn.close()
        if user:
            session["user_id"] = user[0]
            session["username"] = username
            return redirect(url_for("home"))
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            conn.close()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template("register.html", error="Username already exists")
    return render_template("register.html")

@app.route("/logout")
def logout():
    cleanup_monitor()
    session.clear()
    return redirect(url_for("landing"))

# --- MONITORING ROUTES ---
@app.route("/monitor")
def monitor_page():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("monitor.html", username=session["username"])

@app.route("/start", methods=["POST"])
def start_monitoring():
    global monitor
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    cleanup_monitor()
    monitor = DrowsinessMonitor(db_path=DB_PATH, user_id=session["user_id"])
    monitor.create_session()
    return jsonify({"message": "Monitoring session initialized"})

@app.route("/stop", methods=["POST"])
def stop_monitoring():
    cleanup_monitor()
    return jsonify({"message": "Monitoring stopped"})

# --- SELF-HEALING PROCESS ROUTE ---
@app.route("/api/process", methods=["POST"])
def process_frame():
    global monitor
    
    # If monitor is None, try to re-initialize it using the active session
    if monitor is None:
        if "user_id" in session:
            monitor = DrowsinessMonitor(db_path=DB_PATH, user_id=session["user_id"])
            monitor.create_session()
        else:
            return jsonify({"error": "Session lost, please re-login"}), 400
    
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "No image provided"}), 400

    image_bytes = file.read()
    stats = monitor.process_web_frame(image_bytes)
    return jsonify(stats)

@app.route("/video_feed")
def video_feed():
    def generate():
        last_frame_sent = None
        while True:
            if monitor is None:
                time.sleep(1)
                continue
            
            frame = monitor.get_latest_frame()
            
            # Only send the frame if it's new/different to save bandwidth
            if frame is None or frame == last_frame_sent:
                time.sleep(0.1) # Wait for a new frame
                continue
                
            last_frame_sent = frame
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            
            # Reduce FPS of the stream to 10-12 FPS for stability on Render
            time.sleep(0.1) 
            
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/api/live")
def api_live():
    if monitor is None:
        return jsonify({"ear": 0, "perclos": 0, "eye_closed": 0, "fps": 0, "drowsy": False})
    return jsonify(monitor.get_latest_stats())

# --- OTHER ROUTES ---
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html", username=session["username"])

@app.route("/api/overlay", methods=["POST"])
def toggle_overlay():
    data = request.get_json()
    enabled = data.get("enabled", False)
    if monitor:
        monitor.set_overlay(enabled)
    return jsonify({"success": True, "overlay": enabled})

@app.route("/api/sessions")
def get_sessions():
    if "user_id" not in session:
        return jsonify([])
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, start_time, end_time FROM sessions WHERE user_id=? ORDER BY start_time DESC", (session["user_id"],))
    rows = cur.fetchall()
    conn.close()
    return jsonify([{"id": r[0], "start": r[1], "end": r[2]} for r in rows])

@app.route("/api/perclos/session/<int:session_id>")
def get_session_data(session_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT timestamp, perclos
        FROM perclos_data
        WHERE session_id=?
        ORDER BY timestamp
    """, (session_id,))
    rows = cur.fetchall()
    conn.close()
    return jsonify([{"time": r[0], "perclos": r[1]} for r in rows])

@app.route('/about')
def about():
    if 'username' not in session: return redirect(url_for('login'))
    return render_template("about.html")

@app.route('/faq')
def faq():
    if 'username' not in session: return redirect(url_for('login'))
    return render_template('faq.html')

if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, threaded=True)
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
import sqlite3
import threading
import time
import os

# Assuming these are your local files
from database import init_db, DB_PATH
from drowsiness import DrowsinessMonitor

app = Flask(__name__)
app.secret_key = "secret_key"

monitor = None
monitor_thread = None

# --- SAFETY CLEANUP HELPER ---
def cleanup_monitor():
    global monitor, monitor_thread
    if monitor:
        monitor.stop()
        time.sleep(0.5) # Give hardware time to release
    monitor = None
    monitor_thread = None

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

@app.route('/about')
def about():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template("about.html")

@app.route('/faq')
def faq():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('faq.html')

# --- MONITORING ROUTES ---
@app.route("/monitor")
def monitor_page():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("monitor.html", username=session["username"])

@app.route("/start", methods=["POST"])
def start_monitoring():
    global monitor, monitor_thread
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    cleanup_monitor() # Kill any existing zombie processes

    monitor = DrowsinessMonitor(db_path=DB_PATH, user_id=session["user_id"])
    monitor_thread = threading.Thread(target=monitor.start, daemon=True)
    monitor_thread.start()
    return jsonify({"message": "Monitoring started"})

@app.route("/stop", methods=["POST"])
def stop_monitoring():
    cleanup_monitor()
    return jsonify({"message": "Monitoring stopped"})

@app.route("/video_feed")
def video_feed():
    def generate():
        while True:
            if monitor is None or not monitor.running:
                time.sleep(0.2)
                continue
            frame = monitor.get_latest_frame()
            if frame is None:
                time.sleep(0.01)
                continue
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.03) 
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route("/api/live")
def api_live():
    if monitor is None:
        return jsonify({"ear": 0, "perclos": 0, "eye_closed": 0, "fps": 0, "drowsy": False})
    return jsonify(monitor.get_latest_stats())

# --- DASHBOARD & DATA ROUTES ---
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html", username=session["username"])

overlay_enabled = False

#new route
@app.route("/api/overlay", methods=["POST"])
def toggle_overlay():
    global overlay_enabled
    data = request.get_json()
    overlay_enabled = data.get("enabled", False)

    if monitor:
        monitor.set_overlay(overlay_enabled)

    return jsonify({"success": True, "overlay": overlay_enabled})

@app.route("/api/sessions")
def get_sessions():
    if "user_id" not in session:
        return jsonify([])
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT id, start_time, end_time
        FROM sessions
        WHERE user_id=?
        ORDER BY start_time DESC
    """, (session["user_id"],))
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

# --- SYSTEM START ---
if __name__ == "__main__":
    init_db()
    # Critical flags for Windows stability
    app.run(debug=True, use_reloader=False, threaded=True)
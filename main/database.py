import sqlite3
import os

# Create an absolute path for the database file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "drowsiness.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # --- USERS TABLE ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    # --- SESSIONS TABLE ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        start_time DATETIME DEFAULT (datetime('now','+5 hours','+30 minutes')),
        end_time DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    # --- PERCLOS DATA TABLE ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS perclos_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        timestamp DATETIME DEFAULT (datetime('now','+5 hours','+30 minutes')),
        ear REAL,
        perclos REAL,
        eye_closed INTEGER,
        FOREIGN KEY (session_id) REFERENCES sessions(id)
    )
    """)

    # --- DEFAULT USER ---
    cur.execute("SELECT * FROM users WHERE username=?", ("admin",))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            ("admin", "admin123")
        )

    conn.commit()
    conn.close()
    print(f"Database initialized at: {DB_PATH}")

if __name__ == "__main__":
    init_db()
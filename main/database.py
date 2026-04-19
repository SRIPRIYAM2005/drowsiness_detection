import sqlite3

DB_PATH = "drowsiness.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # -----------------------------
    # USERS TABLE
    # -----------------------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    # -----------------------------
    # SESSIONS TABLE (NEW)
    # -----------------------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        end_time DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)


    # -----------------------------
    # PERCLOS DATA TABLE (UPDATED)
    # -----------------------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS perclos_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        ear REAL,
        perclos REAL,
        eye_closed INTEGER,
        FOREIGN KEY (session_id) REFERENCES sessions(id)
    )
    """)

    # -----------------------------
    # DEFAULT USER (for testing)
    # -----------------------------
    cur.execute("SELECT * FROM users WHERE username=?", ("admin",))
    if cur.fetchone() is None:
        cur.execute(
            "INSERT INTO users (username, password) VALUES (?, ?)",
            ("admin", "admin123")
        )

    conn.commit()
    conn.close()
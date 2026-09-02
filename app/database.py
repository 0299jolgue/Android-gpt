import sqlite3
import time
import secrets
from .config import settings
from .security import hash_password

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 username TEXT UNIQUE NOT NULL,
 password_hash TEXT NOT NULL,
 created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS devices(
 id TEXT PRIMARY KEY,
 name TEXT NOT NULL,
 model TEXT DEFAULT '',
 android_version TEXT DEFAULT '',
 status TEXT DEFAULT 'offline',
 last_seen REAL DEFAULT 0,
 token TEXT UNIQUE NOT NULL,
 created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs(
 id TEXT PRIMARY KEY,
 device_id TEXT NOT NULL,
 command TEXT NOT NULL,
 payload TEXT DEFAULT '',
 status TEXT DEFAULT 'queued',
 created_at REAL NOT NULL,
 FOREIGN KEY(device_id) REFERENCES devices(id)
);
"""


def connect():
    settings.database.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(settings.database)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)
        row = conn.execute("SELECT id FROM users WHERE username=?", (settings.admin_username,)).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO users(username,password_hash,created_at) VALUES(?,?,?)",
                (settings.admin_username, hash_password(settings.admin_password), time.time()),
            )
        # A server restart must never delete devices. They simply become offline
        # until the installed agent sends its next heartbeat.
        conn.execute("UPDATE devices SET status='offline' WHERE status='online'")


def get_user(username):
    with connect() as conn:
        return conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()


def _refresh_stale_statuses(conn, timeout_seconds: int = 90):
    cutoff = time.time() - timeout_seconds
    conn.execute(
        "UPDATE devices SET status='offline' WHERE status='online' AND last_seen < ?",
        (cutoff,),
    )


def list_devices():
    with connect() as conn:
        _refresh_stale_statuses(conn)
        return conn.execute("SELECT * FROM devices ORDER BY status DESC,last_seen DESC").fetchall()


def get_device(device_id):
    with connect() as conn:
        _refresh_stale_statuses(conn)
        return conn.execute("SELECT * FROM devices WHERE id=?", (device_id,)).fetchone()


def upsert_device(device_id, name, model, android_version):
    token = secrets.token_urlsafe(32)
    now = time.time()
    with connect() as conn:
        old = conn.execute("SELECT token FROM devices WHERE id=?", (device_id,)).fetchone()
        if old:
            # Keep the same pairing token and device record across restarts/reconnects.
            token = old["token"]
            conn.execute(
                "UPDATE devices SET name=?,model=?,android_version=?,last_seen=?,status='online' WHERE id=?",
                (name, model, android_version, now, device_id),
            )
        else:
            conn.execute(
                "INSERT INTO devices(id,name,model,android_version,status,last_seen,token,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (device_id, name, model, android_version, "online", now, token, now),
            )
    return token


def set_device_status(device_id, status):
    with connect() as conn:
        conn.execute(
            "UPDATE devices SET status=?,last_seen=? WHERE id=?",
            (status, time.time(), device_id),
        )


def create_job(device_id, command, payload=""):
    job_id = secrets.token_hex(10)
    with connect() as conn:
        conn.execute(
            "INSERT INTO jobs(id,device_id,command,payload,created_at) VALUES(?,?,?,?,?)",
            (job_id, device_id, command, payload, time.time()),
        )
    return job_id

import sqlite3
from datetime import datetime, timezone

DATABASE = "nuthh.db"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def get_conn():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT NOT NULL,
            expires_at TEXT,
            activated_by INTEGER,
            activated_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            license_key TEXT,
            joined_at TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user'
        )
    """)

    # Migration សម្រាប់ database ចាស់
    columns = [
        row["name"]
        for row in cur.execute("PRAGMA table_info(users)").fetchall()
    ]

    if "role" not in columns:
        cur.execute(
            "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'"
        )

    conn.commit()
    conn.close()


def ensure_user(user_id):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user_id,)
    )

    if cur.fetchone() is None:
        cur.execute(
            """
            INSERT INTO users (user_id, license_key, joined_at, role)
            VALUES (?, NULL, ?, 'user')
            """,
            (user_id, now_iso())
        )

    conn.commit()
    conn.close()


def get_user_role(user_id):
    ensure_user(user_id)

    conn = get_conn()
    row = conn.execute(
        "SELECT role FROM users WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    conn.close()

    return row["role"] if row else "user"


def set_user_role(user_id, role):
    if role not in ("owner", "user"):
        return False

    ensure_user(user_id)

    conn = get_conn()
    conn.execute(
        "UPDATE users SET role = ? WHERE user_id = ?",
        (role, user_id)
    )
    conn.commit()
    conn.close()

    return True


def list_users():
    conn = get_conn()

    rows = conn.execute("""
        SELECT user_id, license_key, joined_at, role
        FROM users
        ORDER BY joined_at DESC
    """).fetchall()

    conn.close()
    return rows


def create_license(key, expires_at):
    conn = get_conn()

    conn.execute("""
        INSERT INTO licenses
        (license_key, status, created_at, expires_at)
        VALUES (?, 'active', ?, ?)
    """, (
        key,
        now_iso(),
        expires_at
    ))

    conn.commit()
    conn.close()


def get_license(key):
    conn = get_conn()

    row = conn.execute(
        "SELECT * FROM licenses WHERE license_key = ?",
        (key,)
    ).fetchone()

    conn.close()
    return row


def activate_license(key, user_id):
    ensure_user(user_id)

    conn = get_conn()

    license_row = conn.execute(
        "SELECT * FROM licenses WHERE license_key = ?",
        (key,)
    ).fetchone()

    if not license_row:
        conn.close()
        return False, "not_found"

    if license_row["status"] != "active":
        conn.close()
        return False, "inactive"

    # Key មួយប្រើបានតែមួយ account
    if (
        license_row["activated_by"] is not None
        and license_row["activated_by"] != user_id
    ):
        conn.close()
        return False, "used"

    conn.execute("""
        UPDATE licenses
        SET activated_by = ?, activated_at = ?
        WHERE license_key = ?
    """, (
        user_id,
        now_iso(),
        key
    ))

    conn.execute("""
        UPDATE users
        SET license_key = ?
        WHERE user_id = ?
    """, (
        key,
        user_id
    ))

    conn.commit()
    conn.close()

    return True, "success"


def get_user_license(user_id):
    conn = get_conn()

    row = conn.execute("""
        SELECT l.*
        FROM licenses l
        JOIN users u ON u.license_key = l.license_key
        WHERE u.user_id = ?
    """, (user_id,)).fetchone()

    conn.close()
    return row


def revoke_license(key):
    conn = get_conn()

    conn.execute(
        "UPDATE licenses SET status = 'revoked' WHERE license_key = ?",
        (key,)
    )

    conn.execute(
        "UPDATE users SET license_key = NULL WHERE license_key = ?",
        (key,)
    )

    conn.commit()
    conn.close()


def delete_license(key):
    conn = get_conn()

    conn.execute(
        "UPDATE users SET license_key = NULL WHERE license_key = ?",
        (key,)
    )

    conn.execute(
        "DELETE FROM licenses WHERE license_key = ?",
        (key,)
    )

    conn.commit()
    conn.close()


def list_licenses():
    conn = get_conn()

    rows = conn.execute("""
        SELECT *
        FROM licenses
        ORDER BY id DESC
    """).fetchall()

    conn.close()
    return rows

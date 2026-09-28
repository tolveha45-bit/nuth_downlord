import sqlite3
from datetime import (
    datetime,
    timezone,
)

from config import DATABASE_PATH
from license import normalize_license_key


# =========================
# CONNECTION
# =========================

def get_connection():

    conn = sqlite3.connect(
        DATABASE_PATH,
        timeout=30
    )

    conn.row_factory = sqlite3.Row

    return conn


# =========================
# INIT DATABASE
# =========================

def init_db():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (

            user_id INTEGER PRIMARY KEY,

            username TEXT,

            first_name TEXT,

            role TEXT DEFAULT 'user',

            joined_at TEXT NOT NULL,

            last_seen TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS licenses (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            license_key TEXT UNIQUE NOT NULL,

            status TEXT DEFAULT 'active',

            created_at TEXT NOT NULL,

            expires_at TEXT,

            created_by INTEGER,

            last_activated_by INTEGER,

            last_activated_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS channels (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            username TEXT UNIQUE NOT NULL,

            title TEXT,

            added_at TEXT NOT NULL,

            added_by INTEGER
        )
    """)

    conn.commit()
    conn.close()

    print(
        "SQLite:",
        DATABASE_PATH
    )


# =========================
# USERS
# =========================

def ensure_user(
    user_id,
    username=None,
    first_name=None
):

    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now(
        timezone.utc
    ).isoformat()

    cur.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user_id,)
    )

    row = cur.fetchone()

    if row:

        cur.execute("""
            UPDATE users

            SET username = ?,
                first_name = ?,
                last_seen = ?

            WHERE user_id = ?
        """, (
            username,
            first_name,
            now,
            user_id
        ))

    else:

        cur.execute("""
            INSERT INTO users (

                user_id,
                username,
                first_name,
                role,
                joined_at,
                last_seen

            )

            VALUES (?, ?, ?, 'user', ?, ?)
        """, (
            user_id,
            username,
            first_name,
            now,
            now
        ))

    conn.commit()
    conn.close()


def get_user_role(user_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT role
        FROM users
        WHERE user_id = ?
        """,
        (user_id,)
    )

    row = cur.fetchone()

    conn.close()

    if row:
        return row["role"]

    return "user"


def set_user_role(
    user_id,
    role
):

    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now(
        timezone.utc
    ).isoformat()

    cur.execute("""
        INSERT INTO users (
            user_id,
            role,
            joined_at,
            last_seen
        )

        VALUES (?, ?, ?, ?)

        ON CONFLICT(user_id)

        DO UPDATE SET
            role = excluded.role
    """, (
        user_id,
        role,
        now,
        now
    ))

    conn.commit()
    conn.close()


def list_users():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM users
        ORDER BY joined_at DESC
    """)

    rows = cur.fetchall()

    conn.close()

    return rows


# =========================
# LICENSES
# =========================

def create_license(
    license_key,
    expires_at=None,
    created_by=None
):

    license_key = normalize_license_key(
        license_key
    )

    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now(
        timezone.utc
    ).isoformat()

    try:

        cur.execute("""
            INSERT INTO licenses (

                license_key,
                status,
                created_at,
                expires_at,
                created_by

            )

            VALUES (?, 'active', ?, ?, ?)
        """, (
            license_key,
            now,
            expires_at,
            created_by
        ))

        conn.commit()

        return True

    except sqlite3.IntegrityError:

        return False

    finally:

        conn.close()


def get_license(
    license_key
):

    license_key = normalize_license_key(
        license_key
    )

    if not license_key:
        return None

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM licenses
        WHERE license_key = ?
    """, (
        license_key,
    ))

    row = cur.fetchone()

    conn.close()

    return row


def activate_license(
    license_key,
    user_id
):

    license_key = normalize_license_key(
        license_key
    )

    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now(
        timezone.utc
    ).isoformat()

    cur.execute("""
        UPDATE licenses

        SET
            last_activated_by = ?,
            last_activated_at = ?

        WHERE license_key = ?
    """, (
        user_id,
        now,
        license_key
    ))

    conn.commit()
    conn.close()


def revoke_license(
    license_key
):

    license_key = normalize_license_key(
        license_key
    )

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE licenses

        SET status = 'revoked'

        WHERE license_key = ?
    """, (
        license_key,
    ))

    changed = cur.rowcount > 0

    conn.commit()
    conn.close()

    return changed


def restore_license(
    license_key
):

    license_key = normalize_license_key(
        license_key
    )

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        UPDATE licenses

        SET status = 'active'

        WHERE license_key = ?
    """, (
        license_key,
    ))

    changed = cur.rowcount > 0

    conn.commit()
    conn.close()

    return changed


def delete_license(
    license_key
):

    license_key = normalize_license_key(
        license_key
    )

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM licenses
        WHERE license_key = ?
    """, (
        license_key,
    ))

    changed = cur.rowcount > 0

    conn.commit()
    conn.close()

    return changed


def list_licenses():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM licenses
        ORDER BY id DESC
    """)

    rows = cur.fetchall()

    conn.close()

    return rows


# =========================
# CHANNELS
# =========================

def add_channel(
    username,
    title=None,
    added_by=None
):

    conn = get_connection()
    cur = conn.cursor()

    try:

        cur.execute("""
            INSERT INTO channels (

                username,
                title,
                added_at,
                added_by

            )

            VALUES (?, ?, ?, ?)
        """, (
            username,
            title,
            datetime.now(
                timezone.utc
            ).isoformat(),
            added_by
        ))

        conn.commit()

        return True

    except sqlite3.IntegrityError:

        return False

    finally:

        conn.close()


def get_channels():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM channels
        ORDER BY id ASC
    """)

    rows = cur.fetchall()

    conn.close()

    return rows


def delete_channel(
    username
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        DELETE FROM channels
        WHERE username = ?
    """, (
        username,
    ))

    changed = cur.rowcount > 0

    conn.commit()
    conn.close()

    return changed


# =========================
# STATISTICS
# =========================

def get_statistics():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) AS total FROM users"
    )

    users = cur.fetchone()["total"]

    cur.execute(
        "SELECT COUNT(*) AS total FROM licenses"
    )

    licenses = cur.fetchone()["total"]

    cur.execute("""
        SELECT COUNT(*) AS total
        FROM licenses
        WHERE status = 'active'
    """)

    active_licenses = (
        cur.fetchone()["total"]
    )

    cur.execute(
        "SELECT COUNT(*) AS total FROM channels"
    )

    channels = cur.fetchone()["total"]

    conn.close()

    return {
        "users": users,
        "licenses": licenses,
        "active_licenses": active_licenses,
        "channels": channels,
    }

import sqlite3
from datetime import datetime, timezone

DATABASE = "nuthh.db"


def get_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            license_key TEXT DEFAULT NULL,
            joined_at TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL,
            expires_at TEXT DEFAULT NULL,
            activated_by INTEGER DEFAULT NULL,
            activated_at TEXT DEFAULT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            title TEXT DEFAULT '',
            added_at TEXT NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


def ensure_user(
    user_id: int,
    username: str = "",
    first_name: str = "",
):
    conn = get_connection()
    cursor = conn.cursor()

    existing = cursor.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    if existing:
        cursor.execute(
            """
            UPDATE users
            SET username = ?, first_name = ?
            WHERE user_id = ?
            """,
            (
                username,
                first_name,
                user_id,
            ),
        )
    else:
        cursor.execute(
            """
            INSERT INTO users (
                user_id,
                username,
                first_name,
                joined_at,
                role
            )
            VALUES (?, ?, ?, ?, 'user')
            """,
            (
                user_id,
                username,
                first_name,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    conn.commit()
    conn.close()


def get_user_role(user_id: int):
    conn = get_connection()

    row = conn.execute(
        "SELECT role FROM users WHERE user_id = ?",
        (user_id,),
    ).fetchone()

    conn.close()

    if not row:
        return "user"

    return row["role"]


def set_user_role(
    user_id: int,
    role: str,
):
    conn = get_connection()

    conn.execute(
        """
        INSERT INTO users (
            user_id,
            joined_at,
            role
        )
        VALUES (?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET role = excluded.role
        """,
        (
            user_id,
            datetime.now(timezone.utc).isoformat(),
            role,
        ),
    )

    conn.commit()
    conn.close()


def create_license(
    license_key: str,
    expires_at: str | None,
    created_by: int,
):
    conn = get_connection()

    conn.execute(
        """
        INSERT INTO licenses (
            license_key,
            status,
            created_at,
            expires_at,
            activated_by,
            activated_at
        )
        VALUES (?, 'active', ?, ?, ?, NULL)
        """,
        (
            license_key,
            datetime.now(timezone.utc).isoformat(),
            expires_at,
            created_by,
        ),
    )

    conn.commit()
    conn.close()


def get_license(license_key: str):
    conn = get_connection()

    row = conn.execute(
        """
        SELECT *
        FROM licenses
        WHERE license_key = ?
        """,
        (license_key,),
    ).fetchone()

    conn.close()

    return dict(row) if row else None


def revoke_license(license_key: str):
    conn = get_connection()

    cursor = conn.execute(
        """
        UPDATE licenses
        SET status = 'revoked'
        WHERE license_key = ?
        """,
        (license_key,),
    )

    conn.commit()
    conn.close()

    return cursor.rowcount > 0


def delete_license(license_key: str):
    conn = get_connection()

    cursor = conn.execute(
        """
        DELETE FROM licenses
        WHERE license_key = ?
        """,
        (license_key,),
    )

    conn.commit()
    conn.close()

    return cursor.rowcount > 0


def list_licenses():
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM licenses
        ORDER BY id DESC
        """
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def list_users():
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM users
        ORDER BY joined_at DESC
        """
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


# =========================================================
# CHANNELS
# =========================================================

def add_channel(
    username: str,
    title: str = "",
):
    conn = get_connection()

    try:
        conn.execute(
            """
            INSERT INTO channels (
                username,
                title,
                added_at
            )
            VALUES (?, ?, ?)
            """,
            (
                username,
                title,
                datetime.now(timezone.utc).isoformat(),
            ),
        )

        conn.commit()
        return True

    except sqlite3.IntegrityError:
        return False

    finally:
        conn.close()


def get_channels():
    conn = get_connection()

    rows = conn.execute(
        """
        SELECT *
        FROM channels
        ORDER BY id ASC
        """
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def delete_channel(username: str):
    conn = get_connection()

    cursor = conn.execute(
        """
        DELETE FROM channels
        WHERE username = ?
        """,
        (username,),
    )

    conn.commit()
    conn.close()

    return cursor.rowcount > 0

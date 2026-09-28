import sqlite3
from datetime import datetime, timezone


DATABASE = "nuthh.db"


def get_connection():

    conn = sqlite3.connect(
        DATABASE,
        check_same_thread=False,
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    conn = get_connection()
    cur = conn.cursor()

    # =====================================================
    # USERS
    # =====================================================

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            license_key TEXT,
            joined_at TEXT,
            role TEXT NOT NULL DEFAULT 'user'
        )
        """
    )

    # =====================================================
    # LICENSES
    # =====================================================

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at TEXT,
            expires_at TEXT,
            activated_by INTEGER,
            activated_at TEXT
        )
        """
    )

    # =====================================================
    # CHANNELS
    # =====================================================

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            title TEXT DEFAULT '',
            added_at TEXT
        )
        """
    )

    # =====================================================
    # MIGRATION
    # =====================================================

    cur.execute(
        "PRAGMA table_info(users)"
    )

    columns = [
        row["name"]
        for row in cur.fetchall()
    ]

    if "role" not in columns:

        cur.execute(
            """
            ALTER TABLE users
            ADD COLUMN role TEXT
            NOT NULL DEFAULT 'user'
            """
        )

    if "username" not in columns:

        cur.execute(
            """
            ALTER TABLE users
            ADD COLUMN username TEXT
            DEFAULT ''
            """
        )

    if "first_name" not in columns:

        cur.execute(
            """
            ALTER TABLE users
            ADD COLUMN first_name TEXT
            DEFAULT ''
            """
        )

    conn.commit()
    conn.close()


# =========================================================
# USERS
# =========================================================

def ensure_user(
    user_id,
    username="",
    first_name="",
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO users (
            user_id,
            username,
            first_name,
            joined_at
        )
        VALUES (?, ?, ?, ?)

        ON CONFLICT(user_id)
        DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name
        """,
        (
            user_id,
            username,
            first_name,
            datetime.now(
                timezone.utc
            ).isoformat(),
        ),
    )

    conn.commit()
    conn.close()


def get_user_role(user_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT role
        FROM users
        WHERE user_id=?
        """,
        (user_id,),
    )

    row = cur.fetchone()

    conn.close()

    if not row:
        return "user"

    return row["role"] or "user"


def set_user_role(
    user_id,
    role,
):

    ensure_user(user_id)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE users
        SET role=?
        WHERE user_id=?
        """,
        (
            role,
            user_id,
        ),
    )

    conn.commit()
    conn.close()


def list_users():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM users
        ORDER BY joined_at DESC
        """
    )

    rows = cur.fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


# =========================================================
# LICENSE
# =========================================================

def create_license(
    license_key,
    expires_at=None,
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO licenses (
            license_key,
            status,
            created_at,
            expires_at
        )
        VALUES (?, 'active', ?, ?)
        """,
        (
            license_key,
            datetime.now(
                timezone.utc
            ).isoformat(),
            expires_at,
        ),
    )

    conn.commit()
    conn.close()


def get_license(
    license_key,
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM licenses
        WHERE license_key=?
        """,
        (license_key,),
    )

    row = cur.fetchone()

    conn.close()

    if not row:
        return None

    return dict(row)


def activate_license(
    user_id,
    license_key,
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM licenses
        WHERE license_key=?
        """,
        (license_key,),
    )

    row = cur.fetchone()

    if not row:

        conn.close()
        return None

    data = dict(row)

    if data["status"] != "active":

        conn.close()
        return None

    if data["activated_by"]:

        if data["activated_by"] != user_id:

            conn.close()
            return None

    now = datetime.now(
        timezone.utc
    ).isoformat()

    cur.execute(
        """
        UPDATE licenses
        SET
            activated_by=?,
            activated_at=?
        WHERE license_key=?
        """,
        (
            user_id,
            now,
            license_key,
        ),
    )

    cur.execute(
        """
        UPDATE users
        SET license_key=?
        WHERE user_id=?
        """,
        (
            license_key,
            user_id,
        ),
    )

    conn.commit()
    conn.close()

    return data


def get_user_license(
    user_id,
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT license_key
        FROM users
        WHERE user_id=?
        """,
        (user_id,),
    )

    row = cur.fetchone()

    if not row or not row["license_key"]:

        conn.close()
        return None

    key = row["license_key"]

    cur.execute(
        """
        SELECT *
        FROM licenses
        WHERE license_key=?
        """,
        (key,),
    )

    license_row = cur.fetchone()

    conn.close()

    if not license_row:
        return None

    return dict(license_row)


def revoke_license(
    license_key,
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE licenses
        SET status='revoked'
        WHERE license_key=?
        """,
        (license_key,),
    )

    changed = cur.rowcount > 0

    conn.commit()
    conn.close()

    return changed


def delete_license(
    license_key,
):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM licenses
        WHERE license_key=?
        """,
        (license_key,),
    )

    changed = cur.rowcount > 0

    cur.execute(
        """
        UPDATE users
        SET license_key=NULL
        WHERE license_key=?
        """,
        (license_key,),
    )

    conn.commit()
    conn.close()

    return changed


def list_licenses():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM licenses
        ORDER BY created_at DESC
        """
    )

    rows = cur.fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


# =========================================================
# CHANNELS
# =========================================================

def add_channel(
    username,
    title="",
):

    username = username.lower().strip()

    if not username.startswith("@"):

        username = "@" + username

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO channels (
            username,
            title,
            added_at
        )
        VALUES (?, ?, ?)

        ON CONFLICT(username)
        DO UPDATE SET
            title=excluded.title
        """,
        (
            username,
            title,
            datetime.now(
                timezone.utc
            ).isoformat(),
        ),
    )

    conn.commit()
    conn.close()


def get_channels():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM channels
        ORDER BY added_at DESC
        """
    )

    rows = cur.fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


def get_channel(
    username,
):

    username = username.lower().strip()

    if not username.startswith("@"):

        username = "@" + username

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT *
        FROM channels
        WHERE username=?
        """,
        (username,),
    )

    row = cur.fetchone()

    conn.close()

    if not row:
        return None

    return dict(row)


def delete_channel(
    username,
):

    username = username.lower().strip()

    if not username.startswith("@"):

        username = "@" + username

    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        DELETE FROM channels
        WHERE username=?
        """,
        (username,),
    )

    changed = cur.rowcount > 0

    conn.commit()
    conn.close()

    return changed

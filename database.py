```python
import sqlite3
from datetime import datetime, timezone

DB_NAME = "nuthh.db"


def now():
    return datetime.now(timezone.utc).isoformat()


def connect():
    return sqlite3.connect(DB_NAME)


def init_db():
    with connect() as db:
        db.execute("""
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

        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                license_key TEXT,
                joined_at TEXT NOT NULL
            )
        """)

        db.commit()


def create_license(key, expires_at):
    with connect() as db:
        db.execute(
            """
            INSERT INTO licenses
            (license_key, status, created_at, expires_at)
            VALUES (?, 'active', ?, ?)
            """,
            (key, now(), expires_at),
        )
        db.commit()


def get_license(key):
    with connect() as db:
        return db.execute(
            """
            SELECT id, license_key, status,
                   created_at, expires_at,
                   activated_by, activated_at
            FROM licenses
            WHERE license_key = ?
            """,
            (key,),
        ).fetchone()


def activate_license(key, user_id):
    with connect() as db:
        row = db.execute(
            """
            SELECT status, expires_at, activated_by
            FROM licenses
            WHERE license_key = ?
            """,
            (key,),
        ).fetchone()

        if not row:
            return False, "invalid"

        status, expires_at, activated_by = row

        if status != "active":
            return False, "inactive"

        if expires_at:
            expiry = datetime.fromisoformat(expires_at)

            if datetime.now(timezone.utc) >= expiry:
                db.execute(
                    """
                    UPDATE licenses
                    SET status = 'expired'
                    WHERE license_key = ?
                    """,
                    (key,),
                )
                db.commit()
                return False, "expired"

        if activated_by is not None and activated_by != user_id:
            return False, "used"

        db.execute(
            """
            UPDATE licenses
            SET activated_by = ?,
                activated_at = ?
            WHERE license_key = ?
            """,
            (user_id, now(), key),
        )

        db.execute(
            """
            INSERT INTO users(user_id, license_key, joined_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET license_key = excluded.license_key
            """,
            (user_id, key, now()),
        )

        db.commit()

    return True, "success"


def revoke_license(key):
    with connect() as db:
        cur = db.execute(
            """
            UPDATE licenses
            SET status = 'revoked'
            WHERE license_key = ?
            """,
            (key,),
        )
        db.commit()
        return cur.rowcount > 0


def delete_license(key):
    with connect() as db:
        cur = db.execute(
            "DELETE FROM licenses WHERE license_key = ?",
            (key,),
        )
        db.commit()
        return cur.rowcount > 0


def get_user_license(user_id):
    with connect() as db:
        row = db.execute(
            """
            SELECT license_key
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()

    return row[0] if row else None


def list_licenses():
    with connect() as db:
        return db.execute(
            """
            SELECT license_key, status,
                   created_at, expires_at,
                   activated_by
            FROM licenses
            ORDER BY id DESC
            """
        ).fetchall()
```

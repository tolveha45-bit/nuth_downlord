import re
import secrets

from datetime import (
    datetime,
    timedelta,
    timezone,
)


# =========================
# KEY NORMALIZATION
# =========================

def normalize_license_key(value: str) -> str:

    if not value:
        return ""

    value = str(value)

    # Remove ALL whitespace
    value = re.sub(
        r"\s+",
        "",
        value
    )

    # Uppercase
    value = value.upper()

    return value.strip()


# =========================
# VALIDATE KEY FORMAT
# =========================

def is_valid_key_format(key: str) -> bool:

    key = normalize_license_key(key)

    pattern = r"^NUTHH-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}$"

    return bool(
        re.fullmatch(
            pattern,
            key
        )
    )


# =========================
# GENERATE KEY
# =========================

def generate_key():

    part1 = secrets.token_hex(2).upper()
    part2 = secrets.token_hex(2).upper()
    part3 = secrets.token_hex(2).upper()

    return (
        f"NUTHH-{part1}-{part2}-{part3}"
    )


# =========================
# EXPIRATION
# =========================

def calculate_expiry(duration: str):

    now = datetime.now(timezone.utc)

    duration = duration.lower().strip()

    if duration == "1d":
        return (
            now + timedelta(days=1)
        ).isoformat()

    if duration == "7d":
        return (
            now + timedelta(days=7)
        ).isoformat()

    if duration == "30d":
        return (
            now + timedelta(days=30)
        ).isoformat()

    if duration == "90d":
        return (
            now + timedelta(days=90)
        ).isoformat()

    if duration == "1y":
        return (
            now + timedelta(days=365)
        ).isoformat()

    if duration == "lifetime":
        return None

    raise ValueError(
        "Invalid duration"
    )


# =========================
# EXPIRY CHECK
# =========================

def is_expired(expires_at):

    if not expires_at:
        return False

    try:

        date = datetime.fromisoformat(
            expires_at
        )

        if date.tzinfo is None:
            date = date.replace(
                tzinfo=timezone.utc
            )

        return (
            datetime.now(timezone.utc)
            >= date
        )

    except Exception:

        return True


# =========================
# FORMAT EXPIRY
# =========================

def format_expiry(expires_at):

    if not expires_at:
        return "♾️ Lifetime"

    try:

        date = datetime.fromisoformat(
            expires_at
        )

        if date.tzinfo is None:
            date = date.replace(
                tzinfo=timezone.utc
            )

        return date.strftime(
            "%Y-%m-%d %H:%M UTC"
        )

    except Exception:

        return str(expires_at)


# =========================
# REMAINING TIME
# =========================

def remaining_time(expires_at):

    if not expires_at:
        return "Lifetime"

    try:

        date = datetime.fromisoformat(
            expires_at
        )

        if date.tzinfo is None:
            date = date.replace(
                tzinfo=timezone.utc
            )

        seconds = int(
            (
                date -
                datetime.now(timezone.utc)
            ).total_seconds()
        )

        if seconds <= 0:
            return "Expired"

        days = seconds // 86400
        hours = (
            seconds % 86400
        ) // 3600
        minutes = (
            seconds % 3600
        ) // 60

        if days > 0:
            return (
                f"{days}d "
                f"{hours}h "
                f"{minutes}m"
            )

        if hours > 0:
            return (
                f"{hours}h "
                f"{minutes}m"
            )

        return f"{minutes}m"

    except Exception:

        return "Unknown"

import secrets
from datetime import datetime, timedelta, timezone


def generate_key():
    part1 = secrets.token_hex(2).upper()
    part2 = secrets.token_hex(2).upper()
    part3 = secrets.token_hex(2).upper()

    return f"NUTHH-{part1}-{part2}-{part3}"


def calculate_expiry(duration: str):
    now = datetime.now(timezone.utc)

    if duration == "1d":
        return (now + timedelta(days=1)).isoformat()

    if duration == "7d":
        return (now + timedelta(days=7)).isoformat()

    if duration == "30d":
        return (now + timedelta(days=30)).isoformat()

    if duration == "90d":
        return (now + timedelta(days=90)).isoformat()

    if duration == "1y":
        return (now + timedelta(days=365)).isoformat()

    if duration == "lifetime":
        return None

    raise ValueError("Invalid license duration.")


def format_expiry(expires_at):
    if not expires_at:
        return "Lifetime"

    try:
        date = datetime.fromisoformat(expires_at)

        if date.tzinfo is None:
            date = date.replace(
                tzinfo=timezone.utc
            )

        return date.strftime(
            "%Y-%m-%d %H:%M UTC"
        )

    except Exception:
        return str(expires_at)

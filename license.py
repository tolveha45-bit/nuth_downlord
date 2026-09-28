import secrets
import string
from datetime import datetime, timedelta, timezone


def generate_key():
    alphabet = string.ascii_uppercase + string.digits

    parts = []

    for _ in range(3):
        parts.append(
            "".join(
                secrets.choice(alphabet)
                for _ in range(4)
            )
        )

    return "NUTHH-" + "-".join(parts)


def calculate_expiry(duration):
    duration = duration.lower().strip()

    current = datetime.now(timezone.utc)

    if duration == "lifetime":
        return None

    if duration.endswith("d"):
        days = int(duration[:-1])

    elif duration.endswith("m"):
        days = int(duration[:-1]) * 30

    elif duration.endswith("y"):
        days = int(duration[:-1]) * 365

    else:
        raise ValueError("Invalid duration")

    return (
        current + timedelta(days=days)
    ).isoformat()


def format_expiry(expires_at):
    if not expires_at:
        return "♾️ Lifetime"

    dt = datetime.fromisoformat(expires_at)

    return dt.astimezone().strftime(
        "%d/%m/%Y %H:%M"
    )

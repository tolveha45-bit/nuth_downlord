import secrets
import string
from datetime import datetime, timedelta, timezone


def generate_key():

    alphabet = (
        string.ascii_uppercase
        + string.digits
    )

    parts = []

    for _ in range(3):

        part = "".join(
            secrets.choice(alphabet)
            for _ in range(4)
        )

        parts.append(part)

    return (
        "NUTHH-"
        + "-".join(parts)
    )


def calculate_expiry(
    duration,
):

    now = datetime.now(
        timezone.utc
    )

    if duration == "lifetime":
        return None

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

    raise ValueError(
        "Invalid duration"
    )


def format_expiry(
    expires_at,
):

    if not expires_at:
        return "Lifetime"

    try:

        dt = datetime.fromisoformat(
            expires_at
        )

        if dt.tzinfo is None:

            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt.astimezone().strftime(
            "%d %b %Y %H:%M"
        )

    except Exception:

        return str(expires_at)

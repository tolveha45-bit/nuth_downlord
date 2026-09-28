import os
from pathlib import Path


# =========================
# BASIC CONFIG
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

MAIN_OWNER_ID = int(
    os.getenv("OWNER_ID", "8736435737").strip()
)


# =========================
# DATABASE
# =========================

DATABASE_PATH = os.getenv(
    "DATABASE_PATH",
    "nuthh.db"
)


# =========================
# DOWNLOAD SETTINGS
# =========================

MAX_FILE_SIZE = int(
    os.getenv(
        "MAX_FILE_SIZE",
        str(49 * 1024 * 1024)
    )
)


DOWNLOAD_DIR = Path(
    os.getenv(
        "DOWNLOAD_DIR",
        "downloads"
    )
)


DOWNLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# =========================
# SUPPORTED SITES
# =========================

SUPPORTED_DOMAINS = (
    "youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
    "tiktok.com",
    "www.tiktok.com",
)


# =========================
# BOT SETTINGS
# =========================

BOT_NAME = "NUTHH’ Downloader"

BOT_VERSION = "2.0.0"


def validate_config():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing."
        )

    print("=" * 50)
    print(BOT_NAME)
    print("Version:", BOT_VERSION)
    print("Main Owner:", MAIN_OWNER_ID)
    print("Database:", DATABASE_PATH)
    print("Download Dir:", DOWNLOAD_DIR.resolve())
    print("=" * 50)

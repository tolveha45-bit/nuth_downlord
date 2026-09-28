import asyncio
import os
import shutil
import tempfile

from pathlib import Path

import yt_dlp
import imageio_ffmpeg

from config import (
    MAX_FILE_SIZE,
    SUPPORTED_DOMAINS,
)


FFMPEG_PATH = (
    imageio_ffmpeg.get_ffmpeg_exe()
)


# =========================
# URL CHECK
# =========================

def is_supported_url(
    url: str
):

    if not url:
        return False

    url = url.lower().strip()

    return any(
        domain in url
        for domain in SUPPORTED_DOMAINS
    )


# =========================
# TEMP DIRECTORY
# =========================

def create_temp_dir():

    return tempfile.mkdtemp(
        prefix="nuthh_"
    )


# =========================
# FIND MEDIA FILE
# =========================

def find_media_file(
    folder,
    extensions
):

    folder = Path(folder)

    files = []

    for ext in extensions:

        files.extend(
            folder.glob(
                f"*.{ext}"
            )
        )

    if not files:
        return None

    return max(
        files,
        key=lambda x: x.stat().st_mtime
    )


# =========================
# VIDEO DOWNLOAD
# =========================

def download_video_sync(
    url,
    folder
):

    output = os.path.join(
        folder,
        "%(title).100s.%(ext)s"
    )

    options = {

        "outtmpl": output,

        "format": (
            "bestvideo[ext=mp4]+"
            "bestaudio[ext=m4a]/"
            "best[ext=mp4]/best"
        ),

        "merge_output_format": "mp4",

        "ffmpeg_location": FFMPEG_PATH,

        "noplaylist": True,

        "quiet": True,

        "no_warnings": True,

        "restrictfilenames": True,

        "overwrites": True,

    }

    with yt_dlp.YoutubeDL(
        options
    ) as ydl:

        ydl.download([url])

    return find_media_file(
        folder,
        [
            "mp4",
            "mkv",
            "webm",
            "mov"
        ]
    )


# =========================
# MP3 DOWNLOAD
# =========================

def download_mp3_sync(
    url,
    folder
):

    output = os.path.join(
        folder,
        "%(title).100s.%(ext)s"
    )

    options = {

        "outtmpl": output,

        "format": "bestaudio/best",

        "ffmpeg_location": FFMPEG_PATH,

        "postprocessors": [

            {
                "key": "FFmpegExtractAudio",

                "preferredcodec": "mp3",

                "preferredquality": "192",
            }

        ],

        "noplaylist": True,

        "quiet": True,

        "no_warnings": True,

        "restrictfilenames": True,

        "overwrites": True,
    }

    with yt_dlp.YoutubeDL(
        options
    ) as ydl:

        ydl.download([url])

    return find_media_file(
        folder,
        ["mp3"]
    )


# =========================
# ASYNC WRAPPERS
# =========================

async def download_video(
    url,
    folder
):

    return await asyncio.to_thread(
        download_video_sync,
        url,
        folder
    )


async def download_mp3(
    url,
    folder
):

    return await asyncio.to_thread(
        download_mp3_sync,
        url,
        folder
    )


# =========================
# FILE SIZE
# =========================

def file_size(path):

    return os.path.getsize(
        path
    )


def is_file_too_large(path):

    return (
        file_size(path)
        > MAX_FILE_SIZE
    )


# =========================
# CLEANUP
# =========================

def cleanup_folder(folder):

    if not folder:
        return

    try:

        shutil.rmtree(
            folder,
            ignore_errors=True
        )

    except Exception:
        pass

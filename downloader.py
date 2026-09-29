import asyncio
import shutil
import uuid
from pathlib import Path

import yt_dlp
import imageio_ffmpeg


# =========================================================
# CONFIG
# =========================================================

MAX_QUALITY = {
    "4k": 2160,
    "2k": 1440,
    "1080p": 1080,
    "720p": 720,
}


# =========================================================
# FFMPEG
# =========================================================

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()


# =========================================================
# SUPPORTED URL
# =========================================================

SUPPORTED_DOMAINS = (
    "youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
    "tiktok.com",
    "www.tiktok.com",
)


def is_supported_url(url: str) -> bool:
    """
    Check whether URL is supported.
    """

    if not url:
        return False

    url = url.lower().strip()

    return any(domain in url for domain in SUPPORTED_DOMAINS)


# =========================================================
# TEMP DIRECTORY
# =========================================================

def create_temp_dir(base_dir="downloads") -> Path:
    """
    Create a unique temporary download directory.
    """

    base = Path(base_dir)
    base.mkdir(parents=True, exist_ok=True)

    folder = base / f"download_{uuid.uuid4().hex}"

    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    return folder


# =========================================================
# FIND MEDIA FILE
# =========================================================

def find_media_file(
    folder: Path,
    extensions=None
):
    """
    Find downloaded media file.
    """

    if extensions is None:
        extensions = (
            ".mp4",
            ".mkv",
            ".webm",
            ".mov",
            ".avi",
            ".mp3",
            ".m4a",
        )

    files = []

    for file in folder.iterdir():

        if not file.is_file():
            continue

        if file.suffix.lower() in extensions:
            files.append(file)

    if not files:
        return None

    return max(
        files,
        key=lambda x: x.stat().st_mtime
    )


# =========================================================
# GET VIDEO INFO
# =========================================================

def get_video_info_sync(url: str):
    """
    Get video information without downloading.
    """

    if not is_supported_url(url):
        raise ValueError(
            "Unsupported URL. "
            "Only YouTube and TikTok are supported."
        )

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "ffmpeg_location": FFMPEG_PATH,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(
            url,
            download=False
        )


async def get_video_info(url: str):
    """
    Async wrapper.
    """

    return await asyncio.to_thread(
        get_video_info_sync,
        url
    )


# =========================================================
# QUALITY FORMAT
# =========================================================

def build_video_format(quality: str) -> str:
    """
    Build yt-dlp format selector.

    4K   = up to 2160p
    2K   = up to 1440p
    1080 = up to 1080p
    720  = up to 720p
    best = highest available up to 2160p
    """

    quality = quality.lower().strip()

    if quality == "4k":
        max_height = 2160

    elif quality == "2k":
        max_height = 1440

    elif quality == "1080p":
        max_height = 1080

    elif quality == "720p":
        max_height = 720

    elif quality == "best":
        max_height = 2160

    else:
        raise ValueError(
            "Invalid quality. "
            "Use 4k, 2k, 1080p, 720p or best."
        )

    return (
        f"bestvideo[height<={max_height}]"
        f"+bestaudio/"
        f"best[height<={max_height}]"
    )


# =========================================================
# DOWNLOAD VIDEO
# =========================================================

def download_video_sync(
    url: str,
    output_dir: Path,
    quality: str = "best"
):
    """
    Download video with selected quality.

    Supported:
        4k
        2k
        1080p
        720p
        best
    """

    if not is_supported_url(url):
        raise ValueError(
            "Unsupported URL."
        )

    output_dir = Path(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    format_selector = build_video_format(
        quality
    )

    output_template = str(
        output_dir /
        "%(title).200s.%(ext)s"
    )

    ydl_opts = {
        "format": format_selector,

        "outtmpl": output_template,

        "merge_output_format": "mp4",

        "ffmpeg_location": FFMPEG_PATH,

        "noplaylist": True,

        "quiet": True,

        "no_warnings": True,

        "retries": 3,

        "fragment_retries": 3,

        "socket_timeout": 30,

        "continuedl": True,

        "overwrites": True,

        "postprocessors": [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
        ],
    }

    with yt_dlp.YoutubeDL(
        ydl_opts
    ) as ydl:

        info = ydl.extract_info(
            url,
            download=True
        )

        requested = (
            info.get("requested_downloads")
            or []
        )

        filepath = None

        # -------------------------------------------------
        # Try requested file path
        # -------------------------------------------------

        for item in requested:

            path = item.get(
                "filepath"
            )

            if path:
                filepath = Path(path)

        # -------------------------------------------------
        # Try normal yt-dlp filename
        # -------------------------------------------------

        if filepath is None:

            try:

                filename = ydl.prepare_filename(
                    info
                )

                filepath = Path(
                    filename
                ).with_suffix(".mp4")

            except Exception:

                filepath = None

        # -------------------------------------------------
        # Search folder
        # -------------------------------------------------

        if (
            filepath is None
            or not filepath.exists()
        ):

            found = find_media_file(
                output_dir,
                extensions=(
                    ".mp4",
                    ".mkv",
                    ".webm",
                    ".mov",
                )
            )

            if found:
                filepath = found

        # -------------------------------------------------
        # Final check
        # -------------------------------------------------

        if (
            filepath is None
            or not filepath.exists()
        ):

            raise FileNotFoundError(
                "Downloaded video file "
                "was not found."
            )

        return filepath


async def download_video(
    url: str,
    output_dir: Path,
    quality: str = "best"
):
    """
    Async video downloader.
    """

    return await asyncio.to_thread(
        download_video_sync,
        url,
        output_dir,
        quality
    )


# =========================================================
# DOWNLOAD MP3
# =========================================================

def download_mp3_sync(
    url: str,
    output_dir: Path,
    bitrate: str = "192"
):
    """
    Download audio and convert to MP3.
    """

    if not is_supported_url(url):
        raise ValueError(
            "Unsupported URL."
        )

    output_dir = Path(output_dir)

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    output_template = str(
        output_dir /
        "%(title).200s.%(ext)s"
    )

    ydl_opts = {

        "format": (
            "bestaudio/"
            "best"
        ),

        "outtmpl": output_template,

        "ffmpeg_location": FFMPEG_PATH,

        "noplaylist": True,

        "quiet": True,

        "no_warnings": True,

        "retries": 3,

        "fragment_retries": 3,

        "socket_timeout": 30,

        "postprocessors": [

            {
                "key":
                    "FFmpegExtractAudio",

                "preferredcodec":
                    "mp3",

                "preferredquality":
                    bitrate,
            }

        ],
    }

    with yt_dlp.YoutubeDL(
        ydl_opts
    ) as ydl:

        info = ydl.extract_info(
            url,
            download=True
        )

        # ---------------------------------------------
        # Find MP3
        # ---------------------------------------------

        filename = ydl.prepare_filename(
            info
        )

        expected_mp3 = Path(
            filename
        ).with_suffix(".mp3")

        if expected_mp3.exists():
            return expected_mp3

        # ---------------------------------------------
        # Search folder
        # ---------------------------------------------

        found = find_media_file(
            output_dir,
            extensions=(
                ".mp3",
            )
        )

        if found:
            return found

        raise FileNotFoundError(
            "MP3 file was not found."
        )


async def download_mp3(
    url: str,
    output_dir: Path,
    bitrate: str = "192"
):
    """
    Async MP3 downloader.
    """

    return await asyncio.to_thread(
        download_mp3_sync,
        url,
        output_dir,
        bitrate
    )


# =========================================================
# FILE SIZE
# =========================================================

def file_size(path: Path) -> int:
    """
    Return file size in bytes.
    """

    path = Path(path)

    if not path.exists():
        return 0

    return path.stat().st_size


# =========================================================
# FILE SIZE CHECK
# =========================================================

def is_file_too_large(
    path: Path,
    max_size: int
) -> bool:

    return file_size(path) > max_size


# =========================================================
# CLEANUP
# =========================================================

def cleanup_folder(folder: Path):
    """
    Delete temporary download folder.
    """

    folder = Path(folder)

    if not folder.exists():
        return

    try:

        shutil.rmtree(
            folder,
            ignore_errors=True
        )

    except Exception:
        pass


# =========================================================
# GET AVAILABLE QUALITIES
# =========================================================

def get_available_qualities(info: dict):
    """
    Detect available video qualities.

    Returns:
        {
            "4k": True,
            "2k": True,
            "1080p": True,
            "720p": True
        }
    """

    result = {
        "4k": False,
        "2k": False,
        "1080p": False,
        "720p": False,
    }

    formats = info.get(
        "formats",
        []
    )

    heights = []

    for fmt in formats:

        height = fmt.get(
            "height"
        )

        if height:
            try:
                heights.append(
                    int(height)
                )
            except Exception:
                pass

    if not heights:
        return result

    highest = max(
        heights
    )

    result["4k"] = highest >= 2160
    result["2k"] = highest >= 1440
    result["1080p"] = highest >= 1080
    result["720p"] = highest >= 720

    return result


# =========================================================
# FORMAT QUALITY TEXT
# =========================================================

def quality_label(quality: str) -> str:

    labels = {
        "4k": "🎬 4K (2160p)",
        "2k": "🎬 2K (1440p)",
        "1080p": "🎬 Full HD (1080p)",
        "720p": "🎬 HD (720p)",
        "best": "🏆 Best Available",
    }

    return labels.get(
        quality.lower(),
        quality
    )

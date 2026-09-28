import os
import re
import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone

import yt_dlp
import imageio_ffmpeg

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from database import (
    init_db,
    ensure_user,
    get_user_role,
    set_user_role,
    create_license,
    get_license,
    revoke_license,
    delete_license,
    list_licenses,
    list_users,
    add_channel,
    get_channels,
    delete_channel,
)

from license import generate_key, calculate_expiry, format_expiry


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

MAX_FILE_SIZE = 49 * 1024 * 1024
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

SUPPORTED_DOMAINS = (
    "youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
    "tiktok.com",
)

# IMPORTANT:
# This dictionary is intentionally stored only in RAM.
# When Railway/Bot restarts, all active sessions disappear.
ACTIVE_SESSIONS = {}

# user_id -> state
USER_STATES = {}


# =========================================================
# CONFIG CHECK
# =========================================================

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing.")

if OWNER_ID <= 0:
    raise RuntimeError("OWNER_ID is missing or invalid.")


# =========================================================
# DATABASE
# =========================================================

init_db()


# =========================================================
# BASIC HELPERS
# =========================================================

def is_owner(user_id: int) -> bool:
    return get_user_role(user_id) in ("owner", "main_owner")


def is_main_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


def ensure_user_from_update(update: Update):
    user = update.effective_user

    if not user:
        return

    ensure_user(
        user.id,
        user.username or "",
        user.first_name or "",
    )

    # Main owner always has main_owner role.
    if user.id == OWNER_ID:
        set_user_role(user.id, "main_owner")


def extract_url(text: str) -> str | None:
    if not text:
        return None

    match = re.search(
        r"https?://[^\s]+",
        text,
        flags=re.IGNORECASE,
    )

    if not match:
        return None

    url = match.group(0).strip()
    url = url.rstrip(".,!?)]}")

    return url


def is_supported_url(url: str) -> bool:
    url_lower = url.lower()

    return any(
        domain in url_lower
        for domain in SUPPORTED_DOMAINS
    )


def normalize_channel_username(value: str) -> str | None:
    value = value.strip()

    value = re.sub(
        r"^https?://t\.me/",
        "",
        value,
        flags=re.IGNORECASE,
    )

    value = value.strip("/ ")

    if value.startswith("@"):
        username = value
    else:
        username = "@" + value

    raw = username[1:]

    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", raw):
        return None

    return username


# =========================================================
# LICENSE SESSION SYSTEM
# =========================================================

def get_session_license(user_id: int):
    """
    Returns the active license for this Bot session.

    IMPORTANT:
    ACTIVE_SESSIONS exists only in RAM.

    After bot restart:
        ACTIVE_SESSIONS = {}
    Therefore every user must activate a key again.
    """

    key = ACTIVE_SESSIONS.get(user_id)

    if not key:
        return None

    license_data = get_license(key)

    if not license_data:
        ACTIVE_SESSIONS.pop(user_id, None)
        return None

    if license_data["status"] != "active":
        ACTIVE_SESSIONS.pop(user_id, None)
        return None

    expires_at = license_data["expires_at"]

    if expires_at:
        try:
            expiry = datetime.fromisoformat(expires_at)

            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)

            if datetime.now(timezone.utc) >= expiry:
                ACTIVE_SESSIONS.pop(user_id, None)
                revoke_license(key)
                return None

        except Exception:
            ACTIVE_SESSIONS.pop(user_id, None)
            return None

    return license_data


def has_active_session(user_id: int) -> bool:
    return get_session_license(user_id) is not None


# =========================================================
# KEYBOARD
# =========================================================

def main_keyboard(user_id: int):
    buttons = [
        [
            InlineKeyboardButton("🔑 Activate Key", callback_data="activate"),
            InlineKeyboardButton("📋 My License", callback_data="my_license"),
        ],
        [
            InlineKeyboardButton("📥 Download", callback_data="download"),
            InlineKeyboardButton("🎵 MP3", callback_data="mp3"),
        ],
        [
            InlineKeyboardButton("🆔 My ID", callback_data="my_id"),
            InlineKeyboardButton("ℹ️ Help", callback_data="help"),
        ],
    ]

    if is_owner(user_id):
        buttons.append(
            [
                InlineKeyboardButton(
                    "👑 Owner Panel",
                    callback_data="owner_panel",
                )
            ]
        )

    return InlineKeyboardMarkup(buttons)


def owner_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "➕ Generate Key",
                    callback_data="gen_key",
                ),
                InlineKeyboardButton(
                    "📋 All Keys",
                    callback_data="all_keys",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔍 Key Info",
                    callback_data="key_info",
                ),
                InlineKeyboardButton(
                    "🚫 Revoke Key",
                    callback_data="revoke_key",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🗑 Delete Key",
                    callback_data="delete_key",
                ),
                InlineKeyboardButton(
                    "👥 Users",
                    callback_data="users",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📢 Channels",
                    callback_data="channels",
                ),
                InlineKeyboardButton(
                    "➕ Add Channel",
                    callback_data="add_channel",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🗑 Remove Channel",
                    callback_data="remove_channel",
                ),
            ],
            [
                InlineKeyboardButton(
                    "👑 Set Owner",
                    callback_data="set_owner",
                ),
                InlineKeyboardButton(
                    "👤 Set User",
                    callback_data="set_user",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Back",
                    callback_data="back",
                )
            ],
        ]
    )


# =========================================================
# START / HELP
# =========================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_from_update(update)

    user_id = update.effective_user.id

    text = (
        "🤖 *NUTHH Downloader Bot*\n\n"
        "🎬 YouTube / TikTok Downloader\n"
        "🎵 MP3 Downloader\n"
        "🔑 License System\n\n"
        "⚠️ You must activate a valid license before downloading.\n\n"
        "📥 One activated key gives unlimited downloads "
        "during the current bot session.\n\n"
        "🔄 If the bot restarts, you must activate the key again."
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=main_keyboard(user_id),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ensure_user_from_update(update)

    text = (
        "ℹ️ *NUTHH Downloader Help*\n\n"
        "1️⃣ Activate a valid license key.\n"
        "2️⃣ Press 📥 Download for video.\n"
        "3️⃣ Press 🎵 MP3 for audio.\n"
        "4️⃣ Send a YouTube or TikTok URL.\n\n"
        "📥 Downloads are unlimited while your session is active.\n"
        "🔄 Bot restart resets all active sessions.\n"
        "🔑 After restart, activate a valid key again.\n\n"
        "Supported:\n"
        "• YouTube\n"
        "• TikTok"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=main_keyboard(update.effective_user.id),
    )


# =========================================================
# DOWNLOAD FUNCTIONS
# =========================================================

def download_video(url: str, output_dir: str):
    options = {
        "outtmpl": str(Path(output_dir) / "%(title).80s-%(id)s.%(ext)s"),
        "format": "best[ext=mp4]/bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "fragment_retries": 3,
        "ffmpeg_location": FFMPEG_PATH,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)

        possible = [
            Path(filename),
            Path(filename).with_suffix(".mp4"),
            Path(filename).with_suffix(".mkv"),
            Path(filename).with_suffix(".webm"),
        ]

        for path in possible:
            if path.exists():
                return path

    raise FileNotFoundError("Downloaded video file not found.")


def download_mp3(url: str, output_dir: str):
    options = {
        "outtmpl": str(Path(output_dir) / "%(title).80s-%(id)s.%(ext)s"),
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "fragment_retries": 3,
        "ffmpeg_location": FFMPEG_PATH,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        original = Path(ydl.prepare_filename(info))
        mp3_path = original.with_suffix(".mp3")

        if mp3_path.exists():
            return mp3_path

        candidates = list(Path(output_dir).glob("*.mp3"))

        if candidates:
            return candidates[0]

    raise FileNotFoundError("MP3 file not found.")


# =========================================================
# POST MP3 TO ALL CHANNELS
# =========================================================

async def post_mp3_to_channels(
    context: ContextTypes.DEFAULT_TYPE,
    mp3_path: Path,
    title: str,
):
    channels = get_channels()

    if not channels:
        return 0, 0

    success = 0
    failed = 0

    for channel in channels:
        username = channel["username"]

        try:
            with open(mp3_path, "rb") as audio_file:
                await context.bot.send_audio(
                    chat_id=username,
                    audio=audio_file,
                    title=title[:64],
                    caption=f"🎵 {title}\n\n🤖 NUTHH Downloader",
                )

            success += 1

        except Exception as exc:
            failed += 1
            print(
                f"Channel post failed for {username}: {exc}"
            )

    return success, failed


# =========================================================
# PROCESS DOWNLOAD
# =========================================================

async def process_download(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    url: str,
    mode: str,
):
    user_id = update.effective_user.id

    if not has_active_session(user_id):
        await update.message.reply_text(
            "🔒 Your license session is not active.\n\n"
            "Please press 🔑 Activate Key first.",
            reply_markup=main_keyboard(user_id),
        )
        return

    if not is_supported_url(url):
        await update.message.reply_text(
            "❌ Unsupported URL.\n\n"
            "Please send a YouTube or TikTok URL."
        )
        return

    progress = await update.message.reply_text(
        "⏳ Downloading...\nPlease wait."
    )

    temp_dir = tempfile.mkdtemp(prefix="nuthh_")

    try:
        if mode == "video":
            video_path = await asyncio.to_thread(
                download_video,
                url,
                temp_dir,
            )

            if not video_path.exists():
                raise FileNotFoundError(
                    "Video file was not created."
                )

            if video_path.stat().st_size > MAX_FILE_SIZE:
                await progress.edit_text(
                    "❌ File is larger than Telegram's configured "
                    "49 MB limit."
                )
                return

            await progress.edit_text(
                "📤 Uploading video..."
            )

            with open(video_path, "rb") as video_file:
                await update.message.reply_video(
                    video=video_file,
                    supports_streaming=True,
                )

            await progress.edit_text(
                "⏳ Creating MP3 for configured channels..."
            )

            mp3_path = await asyncio.to_thread(
                download_mp3,
                url,
                temp_dir,
            )

            if mp3_path.exists():
                success, failed = await post_mp3_to_channels(
                    context,
                    mp3_path,
                    mp3_path.stem,
                )

                if success or failed:
                    await update.message.reply_text(
                        f"📢 Channel posting:\n"
                        f"✅ Success: {success}\n"
                        f"❌ Failed: {failed}"
                    )

        elif mode == "mp3":
            mp3_path = await asyncio.to_thread(
                download_mp3,
                url,
                temp_dir,
            )

            if not mp3_path.exists():
                raise FileNotFoundError(
                    "MP3 file was not created."
                )

            if mp3_path.stat().st_size > MAX_FILE_SIZE:
                await progress.edit_text(
                    "❌ MP3 file is larger than 49 MB."
                )
                return

            await progress.edit_text(
                "📤 Uploading MP3..."
            )

            title = mp3_path.stem

            with open(mp3_path, "rb") as audio_file:
                await update.message.reply_audio(
                    audio=audio_file,
                    title=title[:64],
                    performer="NUTHH Downloader",
                )

            success, failed = await post_mp3_to_channels(
                context,
                mp3_path,
                title,
            )

            if success or failed:
                await update.message.reply_text(
                    f"📢 Channel posting:\n"
                    f"✅ Success: {success}\n"
                    f"❌ Failed: {failed}"
                )

        await progress.delete()

    except Exception as exc:
        print(f"Download error: {exc}")

        try:
            await progress.edit_text(
                "❌ Download failed.\n\n"
                f"Error: {str(exc)[:800]}"
            )
        except Exception:
            pass

    finally:
        shutil.rmtree(
            temp_dir,
            ignore_errors=True,
        )

    USER_STATES.pop(user_id, None)


# =========================================================
# CALLBACK BUTTONS
# =========================================================

async def button_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    ensure_user(
        user_id,
        query.from_user.username or "",
        query.from_user.first_name or "",
    )

    data = query.data

    # -------------------------
    # ACTIVATE
    # -------------------------

    if data == "activate":
        USER_STATES[user_id] = "activate"

        await query.message.reply_text(
            "🔑 Send your license key.\n\n"
            "Example:\n"
            "`NUTHH-ABCD-1234-EFGH`",
            parse_mode="Markdown",
        )
        return

    # -------------------------
    # MY LICENSE
    # -------------------------

    if data == "my_license":
        license_data = get_session_license(user_id)

        if not license_data:
            await query.message.reply_text(
                "🔒 No active license session.\n\n"
                "Please activate a key.",
                reply_markup=main_keyboard(user_id),
            )
            return

        await query.message.reply_text(
            "✅ *License Active*\n\n"
            f"🔑 `{license_data['license_key']}`\n"
            f"📅 Expires: "
            f"{format_expiry(license_data['expires_at'])}\n\n"
            "📥 Downloads: Unlimited\n"
            "🔄 Bot restart: Activate again",
            parse_mode="Markdown",
            reply_markup=main_keyboard(user_id),
        )
        return

    # -------------------------
    # DOWNLOAD
    # -------------------------

    if data == "download":
        if not has_active_session(user_id):
            await query.message.reply_text(
                "🔒 Activate a license first.",
                reply_markup=main_keyboard(user_id),
            )
            return

        USER_STATES[user_id] = "download"

        await query.message.reply_text(
            "📥 Send a YouTube or TikTok video URL."
        )
        return

    # -------------------------
    # MP3
    # -------------------------

    if data == "mp3":
        if not has_active_session(user_id):
            await query.message.reply_text(
                "🔒 Activate a license first.",
                reply_markup=main_keyboard(user_id),
            )
            return

        USER_STATES[user_id] = "mp3"

        await query.message.reply_text(
            "🎵 Send a YouTube or TikTok URL."
        )
        return

    # -------------------------
    # MY ID
    # -------------------------

    if data == "my_id":
        await query.message.reply_text(
            f"🆔 Your Telegram ID:\n`{user_id}`",
            parse_mode="Markdown",
        )
        return

    # -------------------------
    # HELP
    # -------------------------

    if data == "help":
        await query.message.reply_text(
            "ℹ️ *NUTHH Downloader*\n\n"
            "🔑 Activate Key\n"
            "📥 Download Video\n"
            "🎵 Download MP3\n"
            "📥 Unlimited Downloads\n"
            "🔄 Restart = Activate Again\n\n"
            "Supported: YouTube / TikTok",
            parse_mode="Markdown",
        )
        return

    # -------------------------
    # OWNER PANEL
    # -------------------------

    if data == "owner_panel":
        if not is_owner(user_id):
            return

        await query.message.reply_text(
            "👑 *Owner Panel*",
            parse_mode="Markdown",
            reply_markup=owner_keyboard(),
        )
        return

    # -------------------------
    # BACK
    # -------------------------

    if data == "back":
        await query.message.reply_text(
            "🏠 Main Menu",
            reply_markup=main_keyboard(user_id),
        )
        return

    # =====================================================
    # OWNER ONLY
    # =====================================================

    if not is_owner(user_id):
        await query.message.reply_text(
            "❌ Owner only."
        )
        return

    # -------------------------
    # GENERATE KEY
    # -------------------------

    if data == "gen_key":
        USER_STATES[user_id] = "gen_key"

        await query.message.reply_text(
            "➕ Send duration:\n\n"
            "`1d`\n"
            "`7d`\n"
            "`30d`\n"
            "`90d`\n"
            "`1y`\n"
            "`lifetime`",
            parse_mode="Markdown",
        )
        return

    # -------------------------
    # ALL KEYS
    # -------------------------

    if data == "all_keys":
        licenses = list_licenses()

        if not licenses:
            await query.message.reply_text(
                "📋 No license keys."
            )
            return

        lines = ["📋 *All Keys*\n"]

        for item in licenses[:100]:
            lines.append(
                f"🔑 `{item['license_key']}`\n"
                f"Status: `{item['status']}`\n"
                f"Expires: {format_expiry(item['expires_at'])}\n"
            )

        await query.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
        )
        return

    # -------------------------
    # KEY INFO
    # -------------------------

    if data == "key_info":
        USER_STATES[user_id] = "key_info"

        await query.message.reply_text(
            "🔍 Send the license key."
        )
        return

    # -------------------------
    # REVOKE KEY
    # -------------------------

    if data == "revoke_key":
        USER_STATES[user_id] = "revoke_key"

        await query.message.reply_text(
            "🚫 Send the license key to revoke."
        )
        return

    # -------------------------
    # DELETE KEY
    # -------------------------

    if data == "delete_key":
        USER_STATES[user_id] = "delete_key"

        await query.message.reply_text(
            "🗑 Send the license key to delete."
        )
        return

    # -------------------------
    # USERS
    # -------------------------

    if data == "users":
        users = list_users()

        if not users:
            await query.message.reply_text(
                "👥 No users."
            )
            return

        lines = ["👥 *Users*\n"]

        for user in users[:100]:
            username = (
                f"@{user['username']}"
                if user["username"]
                else "No username"
            )

            lines.append(
                f"🆔 `{user['user_id']}`\n"
                f"👤 {username}\n"
                f"Role: `{user['role']}`\n"
            )

        await query.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
        )
        return

    # -------------------------
    # CHANNELS
    # -------------------------

    if data == "channels":
        channels = get_channels()

        if not channels:
            await query.message.reply_text(
                "📢 No channels configured."
            )
            return

        lines = ["📢 *Configured Channels*\n"]

        for channel in channels:
            lines.append(
                f"• `{channel['username']}`"
            )

        await query.message.reply_text(
            "\n".join(lines),
            parse_mode="Markdown",
        )
        return

    # -------------------------
    # ADD CHANNEL
    # -------------------------

    if data == "add_channel":
        USER_STATES[user_id] = "add_channel"

        await query.message.reply_text(
            "➕ Send public channel username.\n\n"
            "Example:\n"
            "`@song_chill22`\n\n"
            "The bot must be Administrator in the channel.",
            parse_mode="Markdown",
        )
        return

    # -------------------------
    # REMOVE CHANNEL
    # -------------------------

    if data == "remove_channel":
        USER_STATES[user_id] = "remove_channel"

        await query.message.reply_text(
            "🗑 Send the channel username to remove.\n\n"
            "Example: `@song_chill22`",
            parse_mode="Markdown",
        )
        return

    # -------------------------
    # SET OWNER
    # -------------------------

    if data == "set_owner":
        if not is_main_owner(user_id):
            await query.message.reply_text(
                "❌ Main Owner only."
            )
            return

        USER_STATES[user_id] = "set_owner"

        await query.message.reply_text(
            "👑 Send Telegram User ID to make Owner."
        )
        return

    # -------------------------
    # SET USER
    # -------------------------

    if data == "set_user":
        if not is_main_owner(user_id):
            await query.message.reply_text(
                "❌ Main Owner only."
            )
            return

        USER_STATES[user_id] = "set_user"

        await query.message.reply_text(
            "👤 Send Telegram User ID to make User."
        )
        return


# =========================================================
# TEXT HANDLER
# =========================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message or not update.effective_user:
        return

    ensure_user_from_update(update)

    user_id = update.effective_user.id
    text = update.message.text.strip()

    state = USER_STATES.get(user_id)

    # =====================================================
    # LICENSE ACTIVATION
    # =====================================================

    if state == "activate":
        key = text.upper().strip()

        license_data = get_license(key)

        if not license_data:
            await update.message.reply_text(
                "❌ Invalid license key."
            )
            return

        if license_data["status"] != "active":
            await update.message.reply_text(
                "❌ This license is revoked/inactive."
            )
            return

        expires_at = license_data["expires_at"]

        if expires_at:
            try:
                expiry = datetime.fromisoformat(expires_at)

                if expiry.tzinfo is None:
                    expiry = expiry.replace(
                        tzinfo=timezone.utc
                    )

                if datetime.now(timezone.utc) >= expiry:
                    revoke_license(key)

                    await update.message.reply_text(
                        "❌ This license has expired."
                    )
                    return

            except Exception:
                await update.message.reply_text(
                    "❌ Invalid expiry data."
                )
                return

        # Session only.
        # NOT saved as active session in database.
        ACTIVE_SESSIONS[user_id] = key

        USER_STATES.pop(user_id, None)

        await update.message.reply_text(
            "✅ *License Activated!*\n\n"
            f"🔑 `{key}`\n"
            f"📅 Expires: "
            f"{format_expiry(expires_at)}\n\n"
            "📥 Downloads: Unlimited\n"
            "🔄 Bot restart: Activate again",
            parse_mode="Markdown",
            reply_markup=main_keyboard(user_id),
        )
        return

    # =====================================================
    # DOWNLOAD VIDEO
    # =====================================================

    if state == "download":
        url = extract_url(text)

        if not url:
            await update.message.reply_text(
                "❌ Please send a valid URL."
            )
            return

        await process_download(
            update,
            context,
            url,
            "video",
        )
        return

    # =====================================================
    # DOWNLOAD MP3
    # =====================================================

    if state == "mp3":
        url = extract_url(text)

        if not url:
            await update.message.reply_text(
                "❌ Please send a valid URL."
            )
            return

        await process_download(
            update,
            context,
            url,
            "mp3",
        )
        return

    # =====================================================
    # OWNER STATES
    # =====================================================

    if not is_owner(user_id):
        return

    # -------------------------
    # GENERATE KEY
    # -------------------------

    if state == "gen_key":
        duration = text.lower()

        allowed = (
            "1d",
            "7d",
            "30d",
            "90d",
            "1y",
            "lifetime",
        )

        if duration not in allowed:
            await update.message.reply_text(
                "❌ Invalid duration.\n\n"
                "Use: 1d, 7d, 30d, 90d, 1y, lifetime"
            )
            return

        key = generate_key()
        expires_at = calculate_expiry(duration)

        create_license(
            key,
            expires_at,
            user_id,
        )

        USER_STATES.pop(user_id, None)

        await update.message.reply_text(
            "✅ *License Created*\n\n"
            f"🔑 `{key}`\n"
            f"⏳ Duration: `{duration}`\n"
            f"📅 Expires: {format_expiry(expires_at)}\n\n"
            "📥 Downloads: Unlimited",
            parse_mode="Markdown",
            reply_markup=owner_keyboard(),
        )
        return

    # -------------------------
    # KEY INFO
    # -------------------------

    if state == "key_info":
        key = text.upper()

        data = get_license(key)

        if not data:
            await update.message.reply_text(
                "❌ Key not found."
            )
            return

        USER_STATES.pop(user_id, None)

        await update.message.reply_text(
            "🔍 *Key Information*\n\n"
            f"🔑 `{data['license_key']}`\n"
            f"Status: `{data['status']}`\n"
            f"Expires: {format_expiry(data['expires_at'])}\n"
            f"Created: {data['created_at']}\n",
            parse_mode="Markdown",
        )
        return

    # -------------------------
    # REVOKE
    # -------------------------

    if state == "revoke_key":
        key = text.upper()

        if revoke_license(key):
            ACTIVE_SESSIONS = {
                uid: license_key
                for uid, license_key in ACTIVE_SESSIONS.items()
                if license_key != key
            }

            USER_STATES.pop(user_id, None)

            await update.message.reply_text(
                f"🚫 License revoked:\n`{key}`",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "❌ Key not found."
            )

        return

    # -------------------------
    # DELETE
    # -------------------------

    if state == "delete_key":
        key = text.upper()

        if delete_license(key):
            for uid in list(ACTIVE_SESSIONS):
                if ACTIVE_SESSIONS.get(uid) == key:
                    ACTIVE_SESSIONS.pop(uid, None)

            USER_STATES.pop(user_id, None)

            await update.message.reply_text(
                f"🗑 License deleted:\n`{key}`",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "❌ Key not found."
            )

        return

    # -------------------------
    # ADD CHANNEL
    # -------------------------

    if state == "add_channel":
        channel_username = normalize_channel_username(text)

        if not channel_username:
            await update.message.reply_text(
                "❌ Invalid public channel username.\n\n"
                "Example: `@song_chill22`",
                parse_mode="Markdown",
            )
            return

        try:
            chat = await context.bot.get_chat(
                channel_username
            )

            title = chat.title or channel_username

            if add_channel(
                channel_username,
                title,
            ):
                USER_STATES.pop(user_id, None)

                await update.message.reply_text(
                    "✅ Channel added.\n\n"
                    f"📢 {channel_username}\n"
                    f"📝 {title}\n\n"
                    "Make sure the bot is Administrator "
                    "with permission to post messages.",
                    reply_markup=owner_keyboard(),
                )
            else:
                await update.message.reply_text(
                    "⚠️ This channel is already added."
                )

        except Exception as exc:
            await update.message.reply_text(
                "❌ Cannot access this channel.\n\n"
                "Make sure:\n"
                "• Channel is public\n"
                "• Username is correct\n"
                "• Bot is in the channel\n\n"
                f"Error: {str(exc)[:500]}"
            )

        return

    # -------------------------
    # REMOVE CHANNEL
    # -------------------------

    if state == "remove_channel":
        channel_username = normalize_channel_username(text)

        if not channel_username:
            await update.message.reply_text(
                "❌ Invalid channel username."
            )
            return

        if delete_channel(channel_username):
            USER_STATES.pop(user_id, None)

            await update.message.reply_text(
                f"🗑 Removed:\n`{channel_username}`",
                parse_mode="Markdown",
            )
        else:
            await update.message.reply_text(
                "❌ Channel not found."
            )

        return

    # -------------------------
    # SET OWNER
    # -------------------------

    if state == "set_owner":
        if not is_main_owner(user_id):
            return

        try:
            target_id = int(text)
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid Telegram ID."
            )
            return

        set_user_role(target_id, "owner")

        USER_STATES.pop(user_id, None)

        await update.message.reply_text(
            f"👑 User `{target_id}` is now Owner.",
            parse_mode="Markdown",
        )
        return

    # -------------------------
    # SET USER
    # -------------------------

    if state == "set_user":
        if not is_main_owner(user_id):
            return

        try:
            target_id = int(text)
        except ValueError:
            await update.message.reply_text(
                "❌ Invalid Telegram ID."
            )
            return

        set_user_role(target_id, "user")

        USER_STATES.pop(user_id, None)

        await update.message.reply_text(
            f"👤 User `{target_id}` is now normal User.",
            parse_mode="Markdown",
        )
        return


# =========================================================
# COMMAND: /genkey
# =========================================================

async def genkey_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    ensure_user_from_update(update)

    user_id = update.effective_user.id

    if not is_owner(user_id):
        await update.message.reply_text(
            "❌ Owner only."
        )
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n"
            "/genkey 1d\n"
            "/genkey 7d\n"
            "/genkey 30d\n"
            "/genkey 90d\n"
            "/genkey 1y\n"
            "/genkey lifetime"
        )
        return

    duration = context.args[0].lower()

    if duration not in (
        "1d",
        "7d",
        "30d",
        "90d",
        "1y",
        "lifetime",
    ):
        await update.message.reply_text(
            "❌ Invalid duration."
        )
        return

    key = generate_key()
    expires_at = calculate_expiry(duration)

    create_license(
        key,
        expires_at,
        user_id,
    )

    await update.message.reply_text(
        "✅ License Created\n\n"
        f"🔑 `{key}`\n"
        f"⏳ {duration}\n"
        f"📅 {format_expiry(expires_at)}\n"
        "📥 Unlimited downloads",
        parse_mode="Markdown",
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
):
    print(
        "Unhandled error:",
        context.error,
    )


# =========================================================
# MAIN
# =========================================================

def main():
    print("===================================")
    print("      NUTHH DOWNLOADER BOT")
    print("===================================")
    print("Bot starting...")
    print("License sessions are RAM-only.")
    print("Bot restart will reset sessions.")
    print("===================================")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("help", help_command)
    )

    app.add_handler(
        CommandHandler("genkey", genkey_command)
    )

    app.add_handler(
        CallbackQueryHandler(button_handler)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            text_handler,
        )
    )

    app.add_error_handler(error_handler)

    print("Bot is running...")

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()

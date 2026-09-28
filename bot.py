import os
import re
import asyncio

from pathlib import Path

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import (
    BOT_TOKEN,
    MAIN_OWNER_ID,
    MAX_FILE_SIZE,
    validate_config,
)

from database import (
    init_db,
    ensure_user,
    get_user_role,
    set_user_role,
    create_license,
    get_license,
    activate_license,
    revoke_license,
    restore_license,
    delete_license,
    list_licenses,
    list_users,
    add_channel,
    get_channels,
    delete_channel,
    get_statistics,
)

from license import (
    generate_key,
    calculate_expiry,
    normalize_license_key,
    format_expiry,
    remaining_time,
    is_expired,
    is_valid_key_format,
)

from downloader import (
    is_supported_url,
    create_temp_dir,
    download_video,
    download_mp3,
    is_file_too_large,
    cleanup_folder,
)


# ==================================================
# SESSION STORAGE
# ==================================================

# Important:
# RAM only.
# Bot restart = users must activate their key again.

ACTIVE_SESSIONS = {}

USER_STATES = {}


# ==================================================
# MAIN OWNER
# ==================================================

def is_main_owner(user_id):

    return user_id == MAIN_OWNER_ID


def is_owner(user_id):

    if user_id == MAIN_OWNER_ID:
        return True

    return get_user_role(user_id) == "owner"


# ==================================================
# SESSION LICENSE
# ==================================================

def get_session_license(
    user_id
):

    key = ACTIVE_SESSIONS.get(
        user_id
    )

    if not key:
        return None

    key = normalize_license_key(
        key
    )

    data = get_license(
        key
    )

    if not data:

        ACTIVE_SESSIONS.pop(
            user_id,
            None
        )

        return None

    if data["status"] != "active":

        ACTIVE_SESSIONS.pop(
            user_id,
            None
        )

        return None

    if is_expired(
        data["expires_at"]
    ):

        revoke_license(key)

        ACTIVE_SESSIONS.pop(
            user_id,
            None
        )

        return None

    return data


# ==================================================
# KEYBOARDS
# ==================================================

def main_menu(
    user_id
):

    buttons = [

        [
            InlineKeyboardButton(
                "🔑 Activate Key",
                callback_data="activate"
            ),
            InlineKeyboardButton(
                "📋 My License",
                callback_data="my_license"
            ),
        ],

        [
            InlineKeyboardButton(
                "📥 Download",
                callback_data="download"
            ),
            InlineKeyboardButton(
                "🎵 MP3",
                callback_data="mp3"
            ),
        ],

        [
            InlineKeyboardButton(
                "🆔 My ID",
                callback_data="my_id"
            ),
            InlineKeyboardButton(
                "ℹ️ Help",
                callback_data="help"
            ),
        ],
    ]

    if is_owner(user_id):

        buttons.append([
            InlineKeyboardButton(
                "👑 Owner Panel",
                callback_data="owner_panel"
            )
        ])

    return InlineKeyboardMarkup(
        buttons
    )


def owner_menu():

    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "➕ Generate Key",
                callback_data="gen_key"
            ),
            InlineKeyboardButton(
                "📋 All Keys",
                callback_data="all_keys"
            ),
        ],

        [
            InlineKeyboardButton(
                "🔍 Key Info",
                callback_data="key_info"
            ),
            InlineKeyboardButton(
                "🚫 Revoke",
                callback_data="revoke"
            ),
        ],

        [
            InlineKeyboardButton(
                "♻️ Restore",
                callback_data="restore"
            ),
            InlineKeyboardButton(
                "🗑 Delete",
                callback_data="delete"
            ),
        ],

        [
            InlineKeyboardButton(
                "👥 Users",
                callback_data="users"
            ),
            InlineKeyboardButton(
                "📊 Statistics",
                callback_data="stats"
            ),
        ],

        [
            InlineKeyboardButton(
                "📢 Channels",
                callback_data="channels"
            ),
        ],

        [
            InlineKeyboardButton(
                "➕ Add Channel",
                callback_data="add_channel"
            ),
            InlineKeyboardButton(
                "🗑 Remove Channel",
                callback_data="remove_channel"
            ),
        ],

        [
            InlineKeyboardButton(
                "👑 Set Owner",
                callback_data="set_owner"
            ),
            InlineKeyboardButton(
                "👤 Set User",
                callback_data="set_user"
            ),
        ],

        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="back"
            ),
        ],

    ])


# ==================================================
# START
# ==================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    ensure_user(
        user.id,
        user.username,
        user.first_name
    )

    await update.message.reply_text(

        "👋 Welcome to NUTHH’ Downloader!\n\n"

        "🎬 YouTube\n"
        "🎵 TikTok\n"
        "🎧 MP3\n"
        "🔑 License System\n"
        "📢 Multi Channel\n\n"

        "Please activate your license first.",

        reply_markup=main_menu(
            user.id
        )
    )


# ==================================================
# HELP
# ==================================================

async def show_help(
    update,
    context
):

    text = (
        "ℹ️ NUTHH’ Downloader Help\n\n"

        "1️⃣ Activate your license.\n"
        "2️⃣ Press 📥 Download or 🎵 MP3.\n"
        "3️⃣ Send YouTube/TikTok URL.\n\n"

        "Supported:\n"
        "• YouTube\n"
        "• YouTube Shorts\n"
        "• TikTok\n\n"

        "🔑 One activated key allows "
        "unlimited downloads during "
        "the current bot session.\n\n"

        "🔄 After bot restart, "
        "activate your key again."
    )

    if update.callback_query:

        await update.callback_query.message.reply_text(
            text,
            reply_markup=main_menu(
                update.effective_user.id
            )
        )

    else:

        await update.message.reply_text(
            text,
            reply_markup=main_menu(
                update.effective_user.id
            )
        )


# ==================================================
# CALLBACK
# ==================================================

async def callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()

    user = query.from_user

    ensure_user(
        user.id,
        user.username,
        user.first_name
    )

    data = query.data

    # ----------------------------
    # Activate
    # ----------------------------

    if data == "activate":

        USER_STATES[user.id] = "activate"

        await query.message.reply_text(
            "🔑 Send your license key.\n\n"
            "Example:\n"
            "`NUTHH-AB12-CD34-EF56`\n\n"
            "Lowercase and spaces are accepted.",
            parse_mode="Markdown"
        )

        return

    # ----------------------------
    # My License
    # ----------------------------

    if data == "my_license":

        license_data = get_session_license(
            user.id
        )

        if not license_data:

            await query.message.reply_text(
                "❌ No active license session.\n\n"
                "Please activate your key.",
                reply_markup=main_menu(
                    user.id
                )
            )

            return

        await query.message.reply_text(

            "📋 Your License\n\n"

            f"🔑 `{license_data['license_key']}`\n"
            f"📌 Status: `{license_data['status']}`\n"
            f"⏳ Expires: "
            f"{format_expiry(license_data['expires_at'])}\n"
            f"🕐 Remaining: "
            f"{remaining_time(license_data['expires_at'])}\n\n"

            "♾️ Downloads: Unlimited",

            parse_mode="Markdown"
        )

        return

    # ----------------------------
    # Download
    # ----------------------------

    if data == "download":

        if not get_session_license(user.id):

            await query.message.reply_text(
                "🔒 License required.\n\n"
                "Please activate your key first."
            )

            return

        USER_STATES[user.id] = "video"

        await query.message.reply_text(
            "📥 Send a YouTube or TikTok URL."
        )

        return

    # ----------------------------
    # MP3
    # ----------------------------

    if data == "mp3":

        if not get_session_license(user.id):

            await query.message.reply_text(
                "🔒 License required.\n\n"
                "Please activate your key first."
            )

            return

        USER_STATES[user.id] = "mp3"

        await query.message.reply_text(
            "🎵 Send a YouTube or TikTok URL."
        )

        return

    # ----------------------------
    # My ID
    # ----------------------------

    if data == "my_id":

        await query.message.reply_text(
            f"🆔 Your Telegram ID:\n\n"
            f"`{user.id}`",
            parse_mode="Markdown"
        )

        return

    # ----------------------------
    # Help
    # ----------------------------

    if data == "help":

        await show_help(
            update,
            context
        )

        return

    # ----------------------------
    # Owner Panel
    # ----------------------------

    if data == "owner_panel":

        if not is_owner(user.id):

            await query.message.reply_text(
                "❌ Owner access required."
            )

            return

        await query.message.reply_text(
            "👑 NUTHH’ Owner Panel",
            reply_markup=owner_menu()
        )

        return

    # ----------------------------
    # Back
    # ----------------------------

    if data == "back":

        await query.message.reply_text(
            "🏠 Main Menu",
            reply_markup=main_menu(
                user.id
            )
        )

        return

    # ----------------------------
    # Generate Key
    # ----------------------------

    if data == "gen_key":

        if not is_owner(user.id):

            return

        USER_STATES[user.id] = "gen_key"

        await query.message.reply_text(

            "➕ Generate License\n\n"

            "Send duration:\n\n"

            "`1d`\n"
            "`7d`\n"
            "`30d`\n"
            "`90d`\n"
            "`1y`\n"
            "`lifetime`",

            parse_mode="Markdown"
        )

        return

    # ----------------------------
    # All Keys
    # ----------------------------

    if data == "all_keys":

        if not is_owner(user.id):

            return

        rows = list_licenses()

        if not rows:

            await query.message.reply_text(
                "📋 No licenses found."
            )

            return

        text = "📋 LICENSES\n\n"

        for row in rows[:50]:

            text += (
                f"🔑 `{row['license_key']}`\n"
                f"📌 {row['status']}\n"
                f"⏳ "
                f"{format_expiry(row['expires_at'])}\n\n"
            )

        await query.message.reply_text(
            text,
            parse_mode="Markdown"
        )

        return

    # ----------------------------
    # Key Info
    # ----------------------------

    if data == "key_info":

        if not is_owner(user.id):

            return

        USER_STATES[user.id] = "key_info"

        await query.message.reply_text(
            "🔍 Send license key."
        )

        return

    # ----------------------------
    # Revoke
    # ----------------------------

    if data == "revoke":

        if not is_main_owner(user.id):

            await query.message.reply_text(
                "🔒 Main Owner only."
            )

            return

        USER_STATES[user.id] = "revoke"

        await query.message.reply_text(
            "🚫 Send license key to revoke."
        )

        return

    # ----------------------------
    # Restore
    # ----------------------------

    if data == "restore":

        if not is_main_owner(user.id):

            await query.message.reply_text(
                "🔒 Main Owner only."
            )

            return

        USER_STATES[user.id] = "restore"

        await query.message.reply_text(
            "♻️ Send revoked license key."
        )

        return

    # ----------------------------
    # Delete
    # ----------------------------

    if data == "delete":

        if not is_main_owner(user.id):

            await query.message.reply_text(
                "🔒 Main Owner only."
            )

            return

        USER_STATES[user.id] = "delete"

        await query.message.reply_text(
            "🗑 Send license key to delete."
        )

        return

    # ----------------------------
    # Users
    # ----------------------------

    if data == "users":

        if not is_owner(user.id):

            return

        rows = list_users()

        text = "👥 USERS\n\n"

        for row in rows[:50]:

            username = (
                f"@{row['username']}"
                if row["username"]
                else "No username"
            )

            text += (
                f"🆔 `{row['user_id']}`\n"
                f"👤 {username}\n"
                f"👑 {row['role']}\n\n"
            )

        await query.message.reply_text(
            text,
            parse_mode="Markdown"
        )

        return

    # ----------------------------
    # Statistics
    # ----------------------------

    if data == "stats":

        if not is_owner(user.id):

            return

        stats = get_statistics()

        await query.message.reply_text(

            "📊 NUTHH’ STATISTICS\n\n"

            f"👥 Users: "
            f"{stats['users']}\n"

            f"🔑 Total Keys: "
            f"{stats['licenses']}\n"

            f"✅ Active Keys: "
            f"{stats['active_licenses']}\n"

            f"📢 Channels: "
            f"{stats['channels']}\n\n"

            f"🟢 Active Sessions: "
            f"{len(ACTIVE_SESSIONS)}"
        )

        return

    # ----------------------------
    # Channels
    # ----------------------------

    if data == "channels":

        if not is_owner(user.id):

            return

        rows = get_channels()

        if not rows:

            await query.message.reply_text(
                "📢 No channels configured."
            )

            return

        text = "📢 CHANNELS\n\n"

        for row in rows:

            text += (
                f"• `{row['username']}`\n"
            )

        await query.message.reply_text(
            text,
            parse_mode="Markdown"
        )

        return

    # ----------------------------
    # Add Channel
    # ----------------------------

    if data == "add_channel":

        if not is_owner(user.id):

            return

        USER_STATES[user.id] = "add_channel"

        await query.message.reply_text(

            "➕ Send public channel username.\n\n"

            "Example:\n"
            "`@music_khmer`\n\n"

            "The bot must be Administrator "
            "with Post Messages permission.",

            parse_mode="Markdown"
        )

        return

    # ----------------------------
    # Remove Channel
    # ----------------------------

    if data == "remove_channel":

        if not is_owner(user.id):

            return

        USER_STATES[user.id] = "remove_channel"

        await query.message.reply_text(
            "🗑 Send channel username."
        )

        return

    # ----------------------------
    # Set Owner
    # ----------------------------

    if data == "set_owner":

        if not is_main_owner(user.id):

            await query.message.reply_text(
                "🔒 Main Owner only."
            )

            return

        USER_STATES[user.id] = "set_owner"

        await query.message.reply_text(
            "👑 Send Telegram User ID."
        )

        return

    # ----------------------------
    # Set User
    # ----------------------------

    if data == "set_user":

        if not is_main_owner(user.id):

            await query.message.reply_text(
                "🔒 Main Owner only."
            )

            return

        USER_STATES[user.id] = "set_user"

        await query.message.reply_text(
            "👤 Send Telegram User ID."
        )

        return


# ==================================================
# MESSAGE HANDLER
# ==================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    if not user:
        return

    text = (
        update.message.text or ""
    ).strip()

    ensure_user(
        user.id,
        user.username,
        user.first_name
    )

    state = USER_STATES.get(
        user.id
    )

    # ==================================================
    # ACTIVATE KEY
    # ==================================================

    if state == "activate":

        key = normalize_license_key(
            text
        )

        # Format check
        if not is_valid_key_format(key):

            await update.message.reply_text(

                "❌ Invalid license format.\n\n"

                "Example:\n"
                "`NUTHH-AB12-CD34-EF56`\n\n"

                "Spaces and lowercase are accepted.",

                parse_mode="Markdown"
            )

            return

        license_data = get_license(
            key
        )

        if not license_data:

            await update.message.reply_text(
                "❌ Invalid license key.\n\n"
                "The key does not exist."
            )

            return

        if license_data["status"] != "active":

            await update.message.reply_text(
                "🚫 This license is "
                f"{license_data['status']}."
            )

            return

        if is_expired(
            license_data["expires_at"]
        ):

            revoke_license(key)

            await update.message.reply_text(
                "⏳ This license has expired."
            )

            return

        # Activate RAM session
        ACTIVE_SESSIONS[
            user.id
        ] = key

        # Record activation
        activate_license(
            key,
            user.id
        )

        USER_STATES.pop(
            user.id,
            None
        )

        await update.message.reply_text(

            "✅ LICENSE ACTIVATED!\n\n"

            f"🔑 `{key}`\n"
            f"📌 Status: Active\n"
            f"⏳ "
            f"{format_expiry(license_data['expires_at'])}\n"
            f"🕐 "
            f"{remaining_time(license_data['expires_at'])}\n\n"

            "♾️ Unlimited downloads\n"
            "🔄 Bot restart requires activation again.",

            parse_mode="Markdown",

            reply_markup=main_menu(
                user.id
            )
        )

        return

    # ==================================================
    # GENERATE KEY
    # ==================================================

    if state == "gen_key":

        if not is_owner(user.id):

            return

        duration = text.lower().strip()

        allowed = {
            "1d",
            "7d",
            "30d",
            "90d",
            "1y",
            "lifetime",
        }

        if duration not in allowed:

            await update.message.reply_text(
                "❌ Invalid duration.\n\n"
                "Use: 1d, 7d, 30d, 90d, 1y, lifetime"
            )

            return

        key = generate_key()

        expires_at = calculate_expiry(
            duration
        )

        success = create_license(
            key,
            expires_at,
            user.id
        )

        USER_STATES.pop(
            user.id,
            None
        )

        if not success:

            await update.message.reply_text(
                "❌ Failed to create license."
            )

            return

        await update.message.reply_text(

            "✅ LICENSE CREATED\n\n"

            f"🔑 `{key}`\n"
            f"⏳ {format_expiry(expires_at)}\n"
            f"📦 Type: `{duration}`\n\n"

            "Copy this key and give it to the user.",

            parse_mode="Markdown"
        )

        return

    # ==================================================
    # KEY INFO
    # ==================================================

    if state == "key_info":

        if not is_owner(user.id):

            return

        key = normalize_license_key(
            text
        )

        data = get_license(key)

        USER_STATES.pop(
            user.id,
            None
        )

        if not data:

            await update.message.reply_text(
                "❌ Key not found."
            )

            return

        await update.message.reply_text(

            "🔍 LICENSE INFO\n\n"

            f"🔑 `{data['license_key']}`\n"
            f"📌 Status: `{data['status']}`\n"
            f"📅 Created: `{data['created_at']}`\n"
            f"⏳ Expires: "
            f"{format_expiry(data['expires_at'])}\n"
            f"🆔 Created By: "
            f"`{data['created_by']}`\n"
            f"👤 Last Activated By: "
            f"`{data['last_activated_by']}`",

            parse_mode="Markdown"
        )

        return

    # ==================================================
    # REVOKE
    # ==================================================

    if state == "revoke":

        if not is_main_owner(user.id):

            return

        key = normalize_license_key(
            text
        )

        if revoke_license(key):

            # Remove all active sessions
            for uid in list(
                ACTIVE_SESSIONS.keys()
            ):

                if (
                    ACTIVE_SESSIONS.get(uid)
                    == key
                ):

                    ACTIVE_SESSIONS.pop(
                        uid,
                        None
                    )

            await update.message.reply_text(
                f"🚫 License revoked:\n`{key}`",
                parse_mode="Markdown"
            )

        else:

            await update.message.reply_text(
                "❌ Key not found."
            )

        USER_STATES.pop(
            user.id,
            None
        )

        return

    # ==================================================
    # RESTORE
    # ==================================================

    if state == "restore":

        if not is_main_owner(user.id):

            return

        key = normalize_license_key(
            text
        )

        if restore_license(key):

            await update.message.reply_text(
                f"♻️ License restored:\n`{key}`",
                parse_mode="Markdown"
            )

        else:

            await update.message.reply_text(
                "❌ Key not found."
            )

        USER_STATES.pop(
            user.id,
            None
        )

        return

    # ==================================================
    # DELETE
    # ==================================================

    if state == "delete":

        if not is_main_owner(user.id):

            return

        key = normalize_license_key(
            text
        )

        # Remove active sessions first
        for uid in list(
            ACTIVE_SESSIONS.keys()
        ):

            if (
                ACTIVE_SESSIONS.get(uid)
                == key
            ):

                ACTIVE_SESSIONS.pop(
                    uid,
                    None
                )

        if delete_license(key):

            await update.message.reply_text(
                f"🗑 License deleted:\n`{key}`",
                parse_mode="Markdown"
            )

        else:

            await update.message.reply_text(
                "❌ Key not found."
            )

        USER_STATES.pop(
            user.id,
            None
        )

        return

    # ==================================================
    # ADD CHANNEL
    # ==================================================

    if state == "add_channel":

        if not is_owner(user.id):

            return

        channel = text.strip()

        channel = re.sub(
            r"^https?://t\.me/",
            "",
            channel,
            flags=re.I
        )

        if not channel.startswith("@"):

            channel = "@" + channel

        if not re.fullmatch(
            r"@[A-Za-z0-9_]{5,32}",
            channel
        ):

            await update.message.reply_text(
                "❌ Invalid public channel username."
            )

            return

        success = add_channel(
            channel,
            None,
            user.id
        )

        USER_STATES.pop(
            user.id,
            None
        )

        if success:

            await update.message.reply_text(
                f"✅ Channel added:\n{channel}\n\n"
                "Make sure the bot is Administrator "
                "and can Post Messages."
            )

        else:

            await update.message.reply_text(
                "⚠️ This channel already exists."
            )

        return

    # ==================================================
    # REMOVE CHANNEL
    # ==================================================

    if state == "remove_channel":

        if not is_owner(user.id):

            return

        channel = text.strip()

        if not channel.startswith("@"):

            channel = "@" + channel

        success = delete_channel(
            channel
        )

        USER_STATES.pop(
            user.id,
            None
        )

        if success:

            await update.message.reply_text(
                f"🗑 Removed:\n{channel}"
            )

        else:

            await update.message.reply_text(
                "❌ Channel not found."
            )

        return

    # ==================================================
    # SET OWNER
    # ==================================================

    if state == "set_owner":

        if not is_main_owner(user.id):

            return

        try:

            target_id = int(
                text
            )

        except ValueError:

            await update.message.reply_text(
                "❌ Invalid Telegram ID."
            )

            return

        set_user_role(
            target_id,
            "owner"
        )

        USER_STATES.pop(
            user.id,
            None
        )

        await update.message.reply_text(
            f"👑 `{target_id}` is now Owner.",
            parse_mode="Markdown"
        )

        return

    # ==================================================
    # SET USER
    # ==================================================

    if state == "set_user":

        if not is_main_owner(user.id):

            return

        try:

            target_id = int(
                text
            )

        except ValueError:

            await update.message.reply_text(
                "❌ Invalid Telegram ID."
            )

            return

        # Main owner cannot be demoted
        if target_id == MAIN_OWNER_ID:

            await update.message.reply_text(
                "❌ Main Owner cannot be changed."
            )

            return

        set_user_role(
            target_id,
            "user"
        )

        USER_STATES.pop(
            user.id,
            None
        )

        await update.message.reply_text(
            f"👤 `{target_id}` is now User.",
            parse_mode="Markdown"
        )

        return

    # ==================================================
    # VIDEO / MP3 URL
    # ==================================================

    if state in (
        "video",
        "mp3"
    ):

        license_data = get_session_license(
            user.id
        )

        if not license_data:

            USER_STATES.pop(
                user.id,
                None
            )

            await update.message.reply_text(
                "🔒 Your license session is "
                "not active.\n\n"
                "Please activate your key again."
            )

            return

        url = text.strip()

        if not is_supported_url(url):

            await update.message.reply_text(

                "❌ Unsupported URL.\n\n"

                "Supported:\n"
                "• YouTube\n"
                "• YouTube Shorts\n"
                "• TikTok"
            )

            return

        mode = state

        USER_STATES.pop(
            user.id,
            None
        )

        status_message = await update.message.reply_text(
            "⏳ Downloading...\n\n"
            "Please wait."
        )

        folder = create_temp_dir()

        try:

            if mode == "video":

                file_path = await download_video(
                    url,
                    folder
                )

            else:

                file_path = await download_mp3(
                    url,
                    folder
                )

            if not file_path:

                await status_message.edit_text(
                    "❌ Could not find downloaded file."
                )

                return

            if is_file_too_large(
                file_path
            ):

                size_mb = (
                    Path(file_path).stat().st_size
                    / 1024
                    / 1024
                )

                await status_message.edit_text(

                    "❌ File is too large.\n\n"

                    f"📦 Size: {size_mb:.2f} MB\n"
                    f"🚫 Maximum: "
                    f"{MAX_FILE_SIZE / 1024 / 1024:.0f} MB"
                )

                return

            await status_message.edit_text(
                "📤 Uploading..."
            )

            filename = Path(
                file_path
            ).name

            if mode == "video":

                with open(
                    file_path,
                    "rb"
                ) as video:

                    await update.message.reply_video(
                        video=video,
                        caption=(
                            "🎬 NUTHH’ Downloader"
                            "\n\n"
                            f"📁 {filename}"
                        ),
                        supports_streaming=True
                    )

            else:

                with open(
                    file_path,
                    "rb"
                ) as audio:

                    await update.message.reply_audio(
                        audio=audio,
                        caption=(
                            "🎵 NUTHH’ MP3"
                            "\n\n"
                            f"📁 {filename}"
                        ),
                        title=filename
                    )

                # --------------------------------
                # AUTO POST MP3 TO CHANNELS
                # --------------------------------

                channels = get_channels()

                success_count = 0
                failed_count = 0

                for channel in channels:

                    try:

                        with open(
                            file_path,
                            "rb"
                        ) as audio:

                            await context.bot.send_audio(

                                chat_id=channel[
                                    "username"
                                ],

                                audio=audio,

                                caption=(
                                    "🎵 NUTHH’ Music"
                                    "\n\n"
                                    f"📁 {filename}"
                                )
                            )

                        success_count += 1

                    except Exception as channel_error:

                        failed_count += 1

                        print(
                            "Channel error:",
                            channel_error
                        )

                if channels:

                    await update.message.reply_text(

                        "📢 Channel Distribution\n\n"

                        f"✅ Success: "
                        f"{success_count}\n"

                        f"❌ Failed: "
                        f"{failed_count}"
                    )

            await status_message.delete()

        except Exception as error:

            print(
                "DOWNLOAD ERROR:",
                repr(error)
            )

            try:

                await status_message.edit_text(

                    "❌ Download failed.\n\n"

                    "Possible reasons:\n"
                    "• URL is unavailable\n"
                    "• Video is private\n"
                    "• Platform changed\n"
                    "• File cannot be downloaded\n\n"

                    "Please try another URL."
                )

            except Exception:
                pass

        finally:

            cleanup_folder(
                folder
            )

        return

    # ==================================================
    # UNKNOWN TEXT
    # ==================================================

    await update.message.reply_text(
        "Please use the buttons below.",
        reply_markup=main_menu(
            user.id
        )
    )


# ==================================================
# COMMAND: /id
# ==================================================

async def my_id_command(
    update,
    context
):

    await update.message.reply_text(
        f"🆔 Your Telegram ID:\n\n"
        f"`{update.effective_user.id}`",
        parse_mode="Markdown"
    )


# ==================================================
# COMMAND: /panel
# ==================================================

async def panel_command(
    update,
    context
):

    user_id = update.effective_user.id

    if not is_owner(user_id):

        await update.message.reply_text(
            "❌ Owner access required."
        )

        return

    await update.message.reply_text(
        "👑 Owner Panel",
        reply_markup=owner_menu()
    )


# ==================================================
# COMMAND: /genkey
# ==================================================

async def genkey_command(
    update,
    context
):

    user_id = update.effective_user.id

    if not is_owner(user_id):

        await update.message.reply_text(
            "❌ Owner access required."
        )

        return

    if not context.args:

        await update.message.reply_text(

            "Usage:\n\n"

            "/genkey 1d\n"
            "/genkey 7d\n"
            "/genkey 30d\n"
            "/genkey 90d\n"
            "/genkey 1y\n"
            "/genkey lifetime"
        )

        return

    duration = (
        context.args[0]
        .lower()
        .strip()
    )

    allowed = {
        "1d",
        "7d",
        "30d",
        "90d",
        "1y",
        "lifetime"
    }

    if duration not in allowed:

        await update.message.reply_text(
            "❌ Invalid duration."
        )

        return

    key = generate_key()

    expires_at = calculate_expiry(
        duration
    )

    create_license(
        key,
        expires_at,
        user_id
    )

    await update.message.reply_text(

        "✅ License Generated\n\n"

        f"🔑 `{key}`\n"
        f"⏳ {format_expiry(expires_at)}",

        parse_mode="Markdown"
    )


# ==================================================
# ERROR HANDLER
# ==================================================

async def error_handler(
    update,
    context
):

    print(
        "BOT ERROR:",
        repr(context.error)
    )


# ==================================================
# MAIN
# ==================================================

def main():

    validate_config()

    init_db()

    app = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    app.add_handler(
        CommandHandler(
            "id",
            my_id_command
        )
    )

    app.add_handler(
        CommandHandler(
            "panel",
            panel_command
        )
    )

    app.add_handler(
        CommandHandler(
            "genkey",
            genkey_command
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            callback_handler
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            text_handler
        )
    )

    app.add_error_handler(
        error_handler
    )

    print(
        "NUTHH’ Downloader is running..."
    )

    app.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()

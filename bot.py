import os
import re
import asyncio
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone

import yt_dlp
import imageio_ffmpeg

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

from database import (
    init_db,
    ensure_user,
    get_user_role,
    set_user_role,
    list_users,

    create_license,
    get_license,
    activate_license,
    get_user_license,
    revoke_license,
    delete_license,
    list_licenses,

    add_channel,
    get_channels,
    get_channel,
    delete_channel,
)

from license import (
    generate_key,
    calculate_expiry,
    format_expiry,
)


# =========================================================
# CONFIG
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

MAIN_OWNER_ID = int(
    os.getenv("OWNER_ID", "0")
)

MAX_FILE_SIZE_MB = 49
MAX_FILE_SIZE_BYTES = (
    MAX_FILE_SIZE_MB * 1024 * 1024
)

FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()


URL_PATTERN = re.compile(
    r"(https?://(?:www\.)?"
    r"(?:youtube\.com|youtu\.be|"
    r"youtube-nocookie\.com|tiktok\.com)"
    r"/\S+)",
    re.IGNORECASE,
)


if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is missing."
    )

if MAIN_OWNER_ID == 0:
    raise RuntimeError(
        "OWNER_ID is missing or invalid."
    )


init_db()


# =========================================================
# ROLE
# =========================================================

def is_owner(user_id: int) -> bool:

    if user_id == MAIN_OWNER_ID:
        return True

    return get_user_role(user_id) == "owner"


# =========================================================
# LICENSE
# =========================================================

def license_active(user_id: int):

    data = get_user_license(user_id)

    if not data:
        return None

    key = data["license_key"]

    license_data = get_license(key)

    if not license_data:
        return None

    if license_data["status"] != "active":
        return None

    expires_at = license_data["expires_at"]

    if expires_at:

        try:

            expiry = datetime.fromisoformat(
                expires_at
            )

            if expiry.tzinfo is None:
                expiry = expiry.replace(
                    tzinfo=timezone.utc
                )

            if datetime.now(
                timezone.utc
            ) >= expiry:

                revoke_license(key)

                return None

        except Exception:

            return None

    return license_data


# =========================================================
# MAIN MENU
# =========================================================

def main_menu(user_id):

    buttons = [
        [
            InlineKeyboardButton(
                "🔑 Activate Key",
                callback_data="activate",
            ),
            InlineKeyboardButton(
                "📋 My License",
                callback_data="my_license",
            ),
        ],
        [
            InlineKeyboardButton(
                "📥 Download",
                callback_data="download",
            ),
            InlineKeyboardButton(
                "🎵 MP3",
                callback_data="mp3",
            ),
        ],
        [
            InlineKeyboardButton(
                "🆔 My ID",
                callback_data="my_id",
            ),
            InlineKeyboardButton(
                "ℹ️ Help",
                callback_data="help",
            ),
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


# =========================================================
# OWNER MENU
# =========================================================

def owner_menu():

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "➕ Generate Key",
                    callback_data="genkey_menu",
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
                )
            ],
            [
                InlineKeyboardButton(
                    "➕ Add Channel",
                    callback_data="add_channel",
                ),
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
                    "🔙 Back",
                    callback_data="back_main",
                )
            ],
        ]
    )


# =========================================================
# DURATION MENU
# =========================================================

def duration_keyboard():

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "1 Day",
                    callback_data="duration:1d",
                ),
                InlineKeyboardButton(
                    "7 Days",
                    callback_data="duration:7d",
                ),
            ],
            [
                InlineKeyboardButton(
                    "30 Days",
                    callback_data="duration:30d",
                ),
                InlineKeyboardButton(
                    "90 Days",
                    callback_data="duration:90d",
                ),
            ],
            [
                InlineKeyboardButton(
                    "1 Year",
                    callback_data="duration:1y",
                ),
                InlineKeyboardButton(
                    "Lifetime",
                    callback_data="duration:lifetime",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔙 Back",
                    callback_data="owner_panel",
                )
            ],
        ]
    )


# =========================================================
# START
# =========================================================

async def start(update, context):

    user = update.effective_user

    ensure_user(
        user.id,
        user.username or "",
        user.first_name or "",
    )

    await update.message.reply_text(
        "👋 Welcome to NUTHH Downloader\n\n"
        "🎬 YouTube / TikTok Downloader\n"
        "🎵 MP3 Converter\n"
        "📢 Multi-Channel Auto Post\n\n"
        "🔐 Activate License Key first.",
        reply_markup=main_menu(user.id),
    )


# =========================================================
# HELP
# =========================================================

async def help_command(update, context):

    user_id = update.effective_user.id

    await update.message.reply_text(
        "ℹ️ NUTHH Downloader\n\n"
        "🔑 Activate Key\n"
        "📥 Download MP4\n"
        "🎵 Download MP3\n"
        "📢 MP3 automatically posts "
        "to all configured Channels.\n\n"
        "Only content you have permission "
        "to download/share should be used.",
        reply_markup=main_menu(user_id),
    )


# =========================================================
# LICENSE CHECK
# =========================================================

async def require_license(update):

    user_id = update.effective_user.id

    if license_active(user_id):
        return True

    await update.effective_message.reply_text(
        "🔒 License Required\n\n"
        "Please activate your License Key first.",
        reply_markup=main_menu(user_id),
    )

    return False


# =========================================================
# BUTTON HANDLER
# =========================================================

async def button_handler(update, context):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id
    data = query.data

    ensure_user(
        user_id,
        query.from_user.username or "",
        query.from_user.first_name or "",
    )

    # =====================================================
    # BACK
    # =====================================================

    if data == "back_main":

        await query.edit_message_text(
            "🏠 NUTHH Downloader",
            reply_markup=main_menu(user_id),
        )

        return

    # =====================================================
    # ACTIVATE
    # =====================================================

    if data == "activate":

        context.user_data[
            "waiting_for_key"
        ] = True

        await query.edit_message_text(
            "🔑 Activate License\n\n"
            "Send your License Key.\n\n"
            "Example:\n"
            "`NUTHH-ABCD-1234-WXYZ`",
            parse_mode="Markdown",
        )

        return

    # =====================================================
    # MY LICENSE
    # =====================================================

    if data == "my_license":

        data_license = license_active(
            user_id
        )

        if not data_license:

            await query.edit_message_text(
                "🔒 No active License.",
                reply_markup=main_menu(user_id),
            )

            return

        await query.edit_message_text(
            "📋 My License\n\n"
            f"🔑 `{data_license['license_key']}`\n"
            f"📌 Status: {data_license['status']}\n"
            f"📅 Expires: "
            f"{format_expiry(data_license['expires_at'])}",
            parse_mode="Markdown",
            reply_markup=main_menu(user_id),
        )

        return

    # =====================================================
    # MY ID
    # =====================================================

    if data == "my_id":

        await query.edit_message_text(
            f"🆔 Telegram ID\n\n`{user_id}`",
            parse_mode="Markdown",
            reply_markup=main_menu(user_id),
        )

        return

    # =====================================================
    # HELP
    # =====================================================

    if data == "help":

        await query.edit_message_text(
            "ℹ️ Help\n\n"
            "1️⃣ Activate Key\n"
            "2️⃣ Choose Download or MP3\n"
            "3️⃣ Send URL\n\n"
            "🎵 MP3 will be posted to "
            "all configured Channels.",
            reply_markup=main_menu(user_id),
        )

        return

    # =====================================================
    # DOWNLOAD
    # =====================================================

    if data == "download":

        if not await require_license(update):
            return

        context.user_data[
            "download_mode"
        ] = "video"

        await query.edit_message_text(
            "📥 Download Video\n\n"
            "Send YouTube/TikTok URL.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 Back",
                            callback_data="back_main",
                        )
                    ]
                ]
            ),
        )

        return

    # =====================================================
    # MP3
    # =====================================================

    if data == "mp3":

        if not await require_license(update):
            return

        context.user_data[
            "download_mode"
        ] = "mp3"

        await query.edit_message_text(
            "🎵 MP3 Downloader\n\n"
            "Send YouTube/TikTok URL.\n\n"
            "MP3 will be sent to you and "
            "all configured Channels.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 Back",
                            callback_data="back_main",
                        )
                    ]
                ]
            ),
        )

        return

    # =====================================================
    # OWNER PANEL
    # =====================================================

    if data == "owner_panel":

        if not is_owner(user_id):

            await query.edit_message_text(
                "❌ Owner only."
            )

            return

        await query.edit_message_text(
            "👑 NUTHH Owner Panel",
            reply_markup=owner_menu(),
        )

        return

    # =====================================================
    # GENERATE KEY
    # =====================================================

    if data == "genkey_menu":

        if user_id != MAIN_OWNER_ID:

            await query.edit_message_text(
                "❌ Main Owner only."
            )

            return

        await query.edit_message_text(
            "➕ Generate License Key\n\n"
            "Choose duration:",
            reply_markup=duration_keyboard(),
        )

        return

    # =====================================================
    # DURATION
    # =====================================================

    if data.startswith("duration:"):

        if user_id != MAIN_OWNER_ID:
            return

        duration = data.split(
            ":",
            1
        )[1]

        key = generate_key()

        expires_at = calculate_expiry(
            duration
        )

        create_license(
            key,
            expires_at,
        )

        await query.edit_message_text(
            "✅ License Created\n\n"
            f"🔑 `{key}`\n"
            f"⏳ {duration}\n"
            f"📅 {format_expiry(expires_at)}",
            parse_mode="Markdown",
            reply_markup=owner_menu(),
        )

        return

    # =====================================================
    # ALL KEYS
    # =====================================================

    if data == "all_keys":

        if not is_owner(user_id):
            return

        licenses = list_licenses()

        if not licenses:

            text = "📋 No License Keys."

        else:

            lines = [
                "📋 License Keys\n"
            ]

            for item in licenses[:50]:

                lines.append(
                    f"🔑 `{item['license_key']}`\n"
                    f"📌 {item['status']}\n"
                    f"📅 "
                    f"{format_expiry(item['expires_at'])}\n"
                )

            text = "\n".join(lines)

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=owner_menu(),
        )

        return

    # =====================================================
    # KEY INFO
    # =====================================================

    if data == "key_info":

        if not is_owner(user_id):
            return

        context.user_data[
            "owner_action"
        ] = "key_info"

        await query.edit_message_text(
            "🔍 Key Info\n\n"
            "Send License Key.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 Back",
                            callback_data="owner_panel",
                        )
                    ]
                ]
            ),
        )

        return

    # =====================================================
    # REVOKE
    # =====================================================

    if data == "revoke_key":

        if user_id != MAIN_OWNER_ID:
            return

        context.user_data[
            "owner_action"
        ] = "revoke"

        await query.edit_message_text(
            "🚫 Revoke License\n\n"
            "Send License Key.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 Back",
                            callback_data="owner_panel",
                        )
                    ]
                ]
            ),
        )

        return

    # =====================================================
    # DELETE KEY
    # =====================================================

    if data == "delete_key":

        if user_id != MAIN_OWNER_ID:
            return

        context.user_data[
            "owner_action"
        ] = "delete"

        await query.edit_message_text(
            "🗑 Delete License\n\n"
            "Send License Key.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 Back",
                            callback_data="owner_panel",
                        )
                    ]
                ]
            ),
        )

        return

    # =====================================================
    # USERS
    # =====================================================

    if data == "users":

        if not is_owner(user_id):
            return

        users = list_users()

        lines = [
            "👥 Users\n"
        ]

        for user in users[:50]:

            lines.append(
                f"🆔 `{user['user_id']}`\n"
                f"👤 Role: "
                f"{user.get('role', 'user')}\n"
                f"🔑 License: "
                f"{user.get('license_key') or 'None'}\n"
            )

        await query.edit_message_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=owner_menu(),
        )

        return

    # =====================================================
    # ADD CHANNEL
    # =====================================================

    if data == "add_channel":

        if user_id != MAIN_OWNER_ID:

            await query.edit_message_text(
                "❌ Main Owner only."
            )

            return

        context.user_data[
            "owner_action"
        ] = "add_channel"

        await query.edit_message_text(
            "➕ Add Telegram Channel\n\n"
            "Send the Channel username.\n\n"
            "Example:\n"
            "`@song_chill22`\n\n"
            "The Bot must already be an "
            "Administrator of that Channel "
            "with Post Messages permission.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 Back",
                            callback_data="owner_panel",
                        )
                    ]
                ]
            ),
        )

        return

    # =====================================================
    # CHANNEL LIST
    # =====================================================

    if data == "channels":

        if not is_owner(user_id):
            return

        channels = get_channels()

        if not channels:

            text = (
                "📢 Channels\n\n"
                "No Channels added yet.\n\n"
                "Press ➕ Add Channel."
            )

        else:

            lines = [
                "📢 Configured Channels\n"
            ]

            for index, channel in enumerate(
                channels,
                start=1,
            ):

                lines.append(
                    f"{index}. "
                    f"`{channel['username']}`"
                )

            text = "\n".join(lines)

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=owner_menu(),
        )

        return

    # =====================================================
    # REMOVE CHANNEL
    # =====================================================

    if data == "remove_channel":

        if user_id != MAIN_OWNER_ID:
            return

        context.user_data[
            "owner_action"
        ] = "remove_channel"

        channels = get_channels()

        if not channels:

            await query.edit_message_text(
                "📢 No Channels to remove.",
                reply_markup=owner_menu(),
            )

            return

        lines = [
            "🗑 Remove Channel\n",
            "Send the username of the Channel.\n",
        ]

        for channel in channels:

            lines.append(
                f"• `{channel['username']}`"
            )

        await query.edit_message_text(
            "\n".join(lines),
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 Back",
                            callback_data="owner_panel",
                        )
                    ]
                ]
            ),
        )

        return

    # =====================================================
    # SET OWNER
    # =====================================================

    if data == "set_owner":

        if user_id != MAIN_OWNER_ID:
            return

        context.user_data[
            "owner_action"
        ] = "set_owner"

        await query.edit_message_text(
            "👑 Set Owner\n\n"
            "Send Telegram User ID.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 Back",
                            callback_data="owner_panel",
                        )
                    ]
                ]
            ),
        )

        return

    # =====================================================
    # SET USER
    # =====================================================

    if data == "set_user":

        if user_id != MAIN_OWNER_ID:
            return

        context.user_data[
            "owner_action"
        ] = "set_user"

        await query.edit_message_text(
            "👤 Set User\n\n"
            "Send Telegram User ID.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 Back",
                            callback_data="owner_panel",
                        )
                    ]
                ]
            ),
        )

        return


# =========================================================
# TEXT HANDLER
# =========================================================

async def text_handler(
    update,
    context,
):

    if not update.message:
        return

    user = update.effective_user

    if not user:
        return

    user_id = user.id
    text = update.message.text.strip()

    ensure_user(
        user_id,
        user.username or "",
        user.first_name or "",
    )

    # =====================================================
    # ACTIVATE KEY
    # =====================================================

    if context.user_data.get(
        "waiting_for_key"
    ):

        context.user_data[
            "waiting_for_key"
        ] = False

        key = text.upper()

        result = activate_license(
            user_id,
            key,
        )

        if result:

            await update.message.reply_text(
                "✅ License Activated!\n\n"
                f"🔑 `{key}`\n"
                f"📅 Expires: "
                f"{format_expiry(result['expires_at'])}",
                parse_mode="Markdown",
                reply_markup=main_menu(user_id),
            )

        else:

            await update.message.reply_text(
                "❌ Invalid, expired, revoked, "
                "or already-used key.",
                reply_markup=main_menu(user_id),
            )

        return

    # =====================================================
    # OWNER ACTION
    # =====================================================

    if is_owner(user_id):

        action = context.user_data.get(
            "owner_action"
        )

        if action:

            context.user_data[
                "owner_action"
            ] = None

            # ---------------------------------------------
            # ADD CHANNEL
            # ---------------------------------------------

            if action == "add_channel":

                if user_id != MAIN_OWNER_ID:
                    return

                username = text.strip()

                if username.startswith(
                    "https://t.me/"
                ):

                    username = (
                        "@"
                        + username
                        .split(
                            "https://t.me/",
                            1
                        )[1]
                        .split(
                            "?",
                            1
                        )[0]
                        .strip("/")
                    )

                elif username.startswith(
                    "t.me/"
                ):

                    username = (
                        "@"
                        + username
                        .split(
                            "t.me/",
                            1
                        )[1]
                        .split(
                            "?",
                            1
                        )[0]
                        .strip("/")
                    )

                if not username.startswith("@"):

                    username = (
                        "@"
                        + username
                    )

                username = username.lower()

                if not re.fullmatch(
                    r"@[a-zA-Z0-9_]{5,32}",
                    username,
                ):

                    await update.message.reply_text(
                        "❌ Invalid Channel username.\n\n"
                        "Example: `@song_chill22`",
                        parse_mode="Markdown",
                        reply_markup=owner_menu(),
                    )

                    return

                # Test channel access
                try:

                    chat = await context.bot.get_chat(
                        username
                    )

                    me = await context.bot.get_me()

                    member = (
                        await context.bot.get_chat_member(
                            chat.id,
                            me.id,
                        )
                    )

                    if member.status not in (
                        "administrator",
                        "creator",
                    ):

                        await update.message.reply_text(
                            "❌ Bot is not an "
                            "Administrator of this Channel.\n\n"
                            f"Channel: {username}",
                            reply_markup=owner_menu(),
                        )

                        return

                    add_channel(
                        username=username,
                        title=chat.title or username,
                    )

                    await update.message.reply_text(
                        "✅ Channel Added!\n\n"
                        f"📢 {username}\n"
                        f"📝 {chat.title or 'Channel'}\n\n"
                        "MP3 will now be posted "
                        "to this Channel.",
                        reply_markup=owner_menu(),
                    )

                except Exception as e:

                    print(
                        "ADD CHANNEL ERROR:",
                        repr(e),
                    )

                    await update.message.reply_text(
                        "❌ Could not add Channel.\n\n"
                        "Make sure:\n"
                        "• Channel is public\n"
                        "• Bot is Administrator\n"
                        "• Bot has Post Messages permission\n"
                        "• Username is correct",
                        reply_markup=owner_menu(),
                    )

                return

            # ---------------------------------------------
            # REMOVE CHANNEL
            # ---------------------------------------------

            if action == "remove_channel":

                if user_id != MAIN_OWNER_ID:
                    return

                username = text.strip()

                if username.startswith(
                    "https://t.me/"
                ):

                    username = (
                        "@"
                        + username.split(
                            "https://t.me/",
                            1
                        )[1]
                        .split(
                            "?",
                            1
                        )[0]
                        .strip("/")
                    )

                elif not username.startswith("@"):

                    username = (
                        "@"
                        + username
                    )

                success = delete_channel(
                    username.lower()
                )

                if success:

                    await update.message.reply_text(
                        "🗑 Channel Removed\n\n"
                        f"📢 {username}",
                        reply_markup=owner_menu(),
                    )

                else:

                    await update.message.reply_text(
                        "❌ Channel was not found.",
                        reply_markup=owner_menu(),
                    )

                return

            # ---------------------------------------------
            # KEY INFO
            # ---------------------------------------------

            if action == "key_info":

                data = get_license(
                    text.upper()
                )

                if not data:

                    await update.message.reply_text(
                        "❌ Key not found.",
                        reply_markup=owner_menu(),
                    )

                    return

                await update.message.reply_text(
                    "🔍 License Info\n\n"
                    f"🔑 `{data['license_key']}`\n"
                    f"📌 {data['status']}\n"
                    f"📅 "
                    f"{format_expiry(data['expires_at'])}\n"
                    f"👤 "
                    f"{data.get('activated_by') or 'None'}",
                    parse_mode="Markdown",
                    reply_markup=owner_menu(),
                )

                return

            # ---------------------------------------------
            # REVOKE
            # ---------------------------------------------

            if action == "revoke":

                success = revoke_license(
                    text.upper()
                )

                await update.message.reply_text(
                    "✅ License revoked."
                    if success
                    else "❌ Key not found.",
                    reply_markup=owner_menu(),
                )

                return

            # ---------------------------------------------
            # DELETE
            # ---------------------------------------------

            if action == "delete":

                success = delete_license(
                    text.upper()
                )

                await update.message.reply_text(
                    "🗑 License deleted."
                    if success
                    else "❌ Key not found.",
                    reply_markup=owner_menu(),
                )

                return

            # ---------------------------------------------
            # SET OWNER
            # ---------------------------------------------

            if action == "set_owner":

                try:

                    target_id = int(text)

                    ensure_user(target_id)

                    set_user_role(
                        target_id,
                        "owner",
                    )

                    await update.message.reply_text(
                        f"👑 `{target_id}` is now Owner.",
                        parse_mode="Markdown",
                        reply_markup=owner_menu(),
                    )

                except ValueError:

                    await update.message.reply_text(
                        "❌ Invalid Telegram ID.",
                        reply_markup=owner_menu(),
                    )

                return

            # ---------------------------------------------
            # SET USER
            # ---------------------------------------------

            if action == "set_user":

                try:

                    target_id = int(text)

                    if target_id == MAIN_OWNER_ID:

                        await update.message.reply_text(
                            "❌ Main Owner cannot be changed.",
                            reply_markup=owner_menu(),
                        )

                        return

                    ensure_user(target_id)

                    set_user_role(
                        target_id,
                        "user",
                    )

                    await update.message.reply_text(
                        f"👤 `{target_id}` is now User.",
                        parse_mode="Markdown",
                        reply_markup=owner_menu(),
                    )

                except ValueError:

                    await update.message.reply_text(
                        "❌ Invalid Telegram ID.",
                        reply_markup=owner_menu(),
                    )

                return

    # =====================================================
    # URL
    # =====================================================

    match = URL_PATTERN.search(text)

    if match:

        if not await require_license(update):
            return

        url = match.group(1)

        mode = context.user_data.get(
            "download_mode",
            "video",
        )

        await process_download(
            update,
            url,
            mode,
        )

        return

    # =====================================================
    # DEFAULT
    # =====================================================

    await update.message.reply_text(
        "👇 Please use the buttons.",
        reply_markup=main_menu(user_id),
    )


# =========================================================
# DOWNLOAD VIDEO
# =========================================================

def download_video(
    url,
    output_dir,
):

    output_template = os.path.join(
        output_dir,
        "%(title).80s.%(ext)s",
    )

    options = {
        "format":
            "bestvideo[ext=mp4]+"
            "bestaudio[ext=m4a]/"
            "best[ext=mp4]/best",

        "outtmpl":
            output_template,

        "merge_output_format":
            "mp4",

        "noplaylist":
            True,

        "retries":
            3,

        "fragment_retries":
            3,

        "continuedl":
            True,

        "restrictfilenames":
            True,

        "quiet":
            True,

        "no_warnings":
            True,

        "ffmpeg_location":
            FFMPEG_PATH,
    }

    with yt_dlp.YoutubeDL(
        options
    ) as ydl:

        info = ydl.extract_info(
            url,
            download=True,
        )

        title = info.get(
            "title",
            "NUTHH Video",
        )

        files = list(
            Path(output_dir).glob("*")
        )

        video_files = [
            f
            for f in files
            if f.is_file()
            and f.suffix.lower()
            in {
                ".mp4",
                ".mkv",
                ".webm",
                ".mov",
            }
        ]

        if not video_files:

            raise RuntimeError(
                "Video file not found."
            )

        video_file = max(
            video_files,
            key=lambda x:
            x.stat().st_mtime,
        )

        return video_file, title


# =========================================================
# DOWNLOAD MP3
# =========================================================

def download_mp3(
    url,
    output_dir,
):

    output_template = os.path.join(
        output_dir,
        "%(title).80s.%(ext)s",
    )

    options = {
        "format":
            "bestaudio/best",

        "outtmpl":
            output_template,

        "noplaylist":
            True,

        "retries":
            3,

        "fragment_retries":
            3,

        "continuedl":
            True,

        "restrictfilenames":
            True,

        "quiet":
            True,

        "no_warnings":
            True,

        "ffmpeg_location":
            FFMPEG_PATH,

        "postprocessors": [
            {
                "key":
                    "FFmpegExtractAudio",

                "preferredcodec":
                    "mp3",

                "preferredquality":
                    "192",
            }
        ],
    }

    with yt_dlp.YoutubeDL(
        options
    ) as ydl:

        info = ydl.extract_info(
            url,
            download=True,
        )

        title = info.get(
            "title",
            "NUTHH MP3",
        )

        files = list(
            Path(output_dir).glob(
                "*.mp3"
            )
        )

        if not files:

            raise RuntimeError(
                "MP3 conversion failed."
            )

        mp3_file = max(
            files,
            key=lambda x:
            x.stat().st_mtime,
        )

        return mp3_file, title


# =========================================================
# PROCESS DOWNLOAD
# =========================================================

async def process_download(
    update,
    url,
    mode,
):

    message = update.effective_message

    status = await message.reply_text(
        "⏳ Processing..."
    )

    temp_dir = tempfile.mkdtemp(
        prefix="nuthh_"
    )

    try:

        # =================================================
        # MP3
        # =================================================

        if mode == "mp3":

            await status.edit_text(
                "🎵 Downloading audio..."
            )

            mp3_file, title = (
                await asyncio.to_thread(
                    download_mp3,
                    url,
                    temp_dir,
                )
            )

            size = mp3_file.stat().st_size

            if size > MAX_FILE_SIZE_BYTES:

                await status.edit_text(
                    f"❌ MP3 is larger than "
                    f"{MAX_FILE_SIZE_MB} MB."
                )

                return

            await status.edit_text(
                "🎵 MP3 ready.\n"
                "📤 Sending..."
            )

            # Send to User
            with open(
                mp3_file,
                "rb",
            ) as audio:

                await message.reply_audio(
                    audio=audio,
                    title=title[:64],
                    performer="NUTHH Downloader",
                )

            # Post to all channels
            await post_to_all_channels(
                context=update.get_bot(),
                mp3_file=mp3_file,
                title=title,
            )

            await status.delete()

            return

        # =================================================
        # VIDEO
        # =================================================

        await status.edit_text(
            "🎬 Downloading video..."
        )

        video_file, title = (
            await asyncio.to_thread(
                download_video,
                url,
                temp_dir,
            )
        )

        size = video_file.stat().st_size

        if size > MAX_FILE_SIZE_BYTES:

            await status.edit_text(
                f"❌ Video is larger than "
                f"{MAX_FILE_SIZE_MB} MB."
            )

            return

        await status.edit_text(
            "🎬 Video ready.\n"
            "📤 Sending..."
        )

        with open(
            video_file,
            "rb",
        ) as video:

            await message.reply_video(
                video=video,
                caption=(
                    f"🎬 {title[:900]}\n\n"
                    "🤖 NUTHH Downloader"
                ),
                supports_streaming=True,
            )

        # =================================================
        # CREATE MP3
        # =================================================

        await status.edit_text(
            "🎵 Creating MP3..."
        )

        mp3_file, mp3_title = (
            await asyncio.to_thread(
                download_mp3,
                url,
                temp_dir,
            )
        )

        if (
            mp3_file.stat().st_size
            <= MAX_FILE_SIZE_BYTES
        ):

            await status.edit_text(
                "📢 Posting MP3 to Channels..."
            )

            await post_to_all_channels(
                context=update.get_bot(),
                mp3_file=mp3_file,
                title=mp3_title,
            )

        await status.delete()

    except yt_dlp.utils.DownloadError as e:

        print(
            "yt-dlp ERROR:",
            repr(e),
        )

        await status.edit_text(
            "❌ Download failed.\n\n"
            "Possible reasons:\n"
            "• Private video\n"
            "• Login required\n"
            "• Unsupported URL\n"
            "• Platform changed\n"
            "• Network problem"
        )

    except Exception as e:

        print(
            "DOWNLOAD ERROR:",
            repr(e),
        )

        await status.edit_text(
            "❌ Error\n\n"
            f"`{str(e)[:700]}`",
            parse_mode="Markdown",
        )

    finally:

        shutil.rmtree(
            temp_dir,
            ignore_errors=True,
        )


# =========================================================
# POST MP3 TO ALL CHANNELS
# =========================================================

async def post_to_all_channels(
    context,
    mp3_file,
    title,
):

    channels = get_channels()

    if not channels:

        print(
            "No channels configured."
        )

        return

    success_count = 0

    for channel in channels:

        username = channel["username"]

        try:

            with open(
                mp3_file,
                "rb",
            ) as audio:

                await context.bot.send_audio(
                    chat_id=username,
                    audio=audio,
                    title=title[:64],
                    performer="NUTHH Downloader",
                    caption=(
                        "🎵 New MP3\n\n"
                        f"🎧 {title[:800]}\n\n"
                        "🤖 NUTHH Downloader"
                    ),
                )

            success_count += 1

            print(
                f"✅ Posted to {username}"
            )

        except Exception as e:

            print(
                f"❌ Failed {username}:",
                repr(e),
            )

    print(
        f"Channel result: "
        f"{success_count}/{len(channels)}"
    )


# =========================================================
# /genkey
# =========================================================

async def genkey_command(
    update,
    context,
):

    user_id = update.effective_user.id

    if user_id != MAIN_OWNER_ID:

        await update.message.reply_text(
            "❌ Main Owner only."
        )

        return

    if not context.args:

        await update.message.reply_text(
            "/genkey 1d\n"
            "/genkey 7d\n"
            "/genkey 30d\n"
            "/genkey 90d\n"
            "/genkey 1y\n"
            "/genkey lifetime"
        )

        return

    duration = context.args[0]

    try:

        expires_at = calculate_expiry(
            duration
        )

    except ValueError:

        await update.message.reply_text(
            "❌ Invalid duration."
        )

        return

    key = generate_key()

    create_license(
        key,
        expires_at,
    )

    await update.message.reply_text(
        "✅ License Created\n\n"
        f"🔑 `{key}`\n"
        f"⏳ {duration}\n"
        f"📅 {format_expiry(expires_at)}",
        parse_mode="Markdown",
    )


# =========================================================
# ERROR
# =========================================================

async def error_handler(
    update,
    context,
):

    print(
        "BOT ERROR:",
        repr(context.error),
    )


# =========================================================
# MAIN
# =========================================================

def main():

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start,
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command,
        )
    )

    application.add_handler(
        CommandHandler(
            "genkey",
            genkey_command,
        )
    )

    application.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            text_handler,
        )
    )

    application.add_error_handler(
        error_handler
    )

    print(
        "================================"
    )

    print(
        " NUTHH Multi-Channel Downloader"
    )

    print(
        " Status: RUNNING"
    )

    print(
        "================================"
    )

    application.run_polling(
        allowed_updates=Update.ALL_TYPES
    )


if __name__ == "__main__":
    main()

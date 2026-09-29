import re

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
    DOWNLOAD_DIR,
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
    get_video_info,
    get_available_qualities,
)


# =========================================================
# SESSION DATA
# =========================================================

# user_id -> license key
ACTIVE_SESSIONS = {}

# user_id -> current state
USER_STATES = {}

# user_id -> URL waiting for quality selection
PENDING_URLS = {}


# =========================================================
# ROLE
# =========================================================

def is_main_owner(user_id: int) -> bool:
    return user_id == MAIN_OWNER_ID


def is_owner(user_id: int) -> bool:
    return (
        user_id == MAIN_OWNER_ID
        or get_user_role(user_id) == "owner"
    )


# =========================================================
# LICENSE SESSION
# =========================================================

def get_session_license(user_id: int):

    key = ACTIVE_SESSIONS.get(user_id)

    if not key:
        return None

    key = normalize_license_key(key)

    row = get_license(key)

    if not row:
        ACTIVE_SESSIONS.pop(user_id, None)
        return None

    if row["status"] != "active":
        ACTIVE_SESSIONS.pop(user_id, None)
        return None

    if is_expired(row["expires_at"]):

        ACTIVE_SESSIONS.pop(
            user_id,
            None
        )

        revoke_license(key)

        return None

    return row


# =========================================================
# MAIN MENU
# =========================================================

def main_menu(user_id: int):

    keyboard = [

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

        keyboard.append(
            [
                InlineKeyboardButton(
                    "👑 Owner Panel",
                    callback_data="owner_panel"
                )
            ]
        )

    return InlineKeyboardMarkup(keyboard)


# =========================================================
# OWNER MENU
# =========================================================

def owner_menu():

    return InlineKeyboardMarkup([

        [
            InlineKeyboardButton(
                "➕ Generate Key",
                callback_data="gen"
            ),

            InlineKeyboardButton(
                "📋 All Keys",
                callback_data="keys"
            ),
        ],

        [
            InlineKeyboardButton(
                "🔍 Key Info",
                callback_data="keyinfo"
            ),

            InlineKeyboardButton(
                "🚫 Revoke Key",
                callback_data="revoke"
            ),
        ],

        [
            InlineKeyboardButton(
                "♻️ Restore Key",
                callback_data="restore"
            ),

            InlineKeyboardButton(
                "🗑 Delete Key",
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

            InlineKeyboardButton(
                "➕ Add Channel",
                callback_data="addchannel"
            ),
        ],

        [
            InlineKeyboardButton(
                "🗑 Remove Channel",
                callback_data="removechannel"
            ),
        ],

        [
            InlineKeyboardButton(
                "👑 Set Owner",
                callback_data="setowner"
            ),

            InlineKeyboardButton(
                "👤 Set User",
                callback_data="setuser"
            ),
        ],

        [
            InlineKeyboardButton(
                "⬅️ Back",
                callback_data="back"
            )
        ],
    ])


# =========================================================
# QUALITY MENU
# =========================================================

def quality_menu_from_available(available):

    buttons = []

    row = []

    qualities = [

        (
            "4k",
            "🎬 4K (2160p)"
        ),

        (
            "2k",
            "🎬 2K (1440p)"
        ),

        (
            "1080p",
            "🎬 1080p"
        ),

        (
            "720p",
            "🎬 720p"
        ),
    ]

    for quality, label in qualities:

        if available.get(quality):

            row.append(
                InlineKeyboardButton(
                    label,
                    callback_data=f"quality:{quality}"
                )
            )

            if len(row) == 2:

                buttons.append(row)

                row = []

    if row:
        buttons.append(row)

    buttons.append(
        [
            InlineKeyboardButton(
                "🏆 Best Available",
                callback_data="quality:best"
            )
        ]
    )

    buttons.append(
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="cancel"
            )
        ]
    )

    return InlineKeyboardMarkup(buttons)


# =========================================================
# CANCEL MENU
# =========================================================

def cancel_menu():

    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "❌ Cancel",
                callback_data="cancel"
            )
        ]
    ])


# =========================================================
# START
# =========================================================

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

    USER_STATES.pop(
        user.id,
        None
    )

    PENDING_URLS.pop(
        user.id,
        None
    )

    await update.message.reply_text(
        "hello\n\n"
        "🤖 Welcome to NUTHH’ Downloader\n\n"
        "Choose an option below:",
        reply_markup=main_menu(user.id)
    )


# =========================================================
# ACTIVATE LICENSE
# =========================================================

async def activate_key_for_user(
    user_id: int,
    raw_key: str
):

    key = normalize_license_key(
        raw_key
    )

    if not is_valid_key_format(key):

        return (
            False,
            "❌ Invalid license key format."
        )

    row = get_license(key)

    if not row:

        return (
            False,
            "❌ License key not found."
        )

    if row["status"] != "active":

        return (
            False,
            f"❌ This key is {row['status']}."
        )

    if is_expired(
        row["expires_at"]
    ):

        revoke_license(key)

        return (
            False,
            "❌ This license has expired."
        )

    ACTIVE_SESSIONS[user_id] = key

    activate_license(
        key,
        user_id
    )

    return (
        True,
        "✅ License Activated!\n\n"
        f"🔑 `{key}`\n"
        f"⏳ Remaining: "
        f"{remaining_time(row['expires_at'])}\n"
        f"📅 Expires: "
        f"{format_expiry(row['expires_at'])}"
    )


# =========================================================
# /ACTIVATE COMMAND
# =========================================================

async def activate_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    ensure_user(
        user.id,
        user.username,
        user.first_name
    )

    if not context.args:

        USER_STATES[user.id] = "activate"

        await update.message.reply_text(
            "🔑 Please send your license key.\n\n"
            "Example:\n"
            "`NUTHH-AB12-CD34-EF56`",
            parse_mode="Markdown",
            reply_markup=cancel_menu()
        )

        return

    raw_key = " ".join(
        context.args
    )

    success, message = await activate_key_for_user(
        user.id,
        raw_key
    )

    await update.message.reply_text(
        message,
        parse_mode="Markdown",
        reply_markup=main_menu(user.id)
    )


# =========================================================
# CALLBACK HANDLER
# =========================================================

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


    # =====================================================
    # CANCEL
    # =====================================================

    if data == "cancel":

        USER_STATES.pop(
            user.id,
            None
        )

        PENDING_URLS.pop(
            user.id,
            None
        )

        await query.edit_message_text(
            "❌ Cancelled.",
            reply_markup=main_menu(user.id)
        )

        return


    # =====================================================
    # BACK
    # =====================================================

    if data == "back":

        USER_STATES.pop(
            user.id,
            None
        )

        await query.edit_message_text(
            "🏠 Main Menu",
            reply_markup=main_menu(user.id)
        )

        return


    # =====================================================
    # ACTIVATE KEY
    # =====================================================

    if data == "activate":

        USER_STATES[user.id] = "activate"

        await query.edit_message_text(
            "🔑 Activate License\n\n"
            "Send your license key.\n\n"
            "Example:\n"
            "`NUTHH-AB12-CD34-EF56`",
            parse_mode="Markdown",
            reply_markup=cancel_menu()
        )

        return


    # =====================================================
    # MY LICENSE
    # =====================================================

    if data == "my_license":

        license_row = get_session_license(
            user.id
        )

        if not license_row:

            text = (
                "📋 My License\n\n"
                "❌ No active license.\n\n"
                "Press 🔑 Activate Key."
            )

        else:

            text = (
                "📋 My License\n\n"
                f"🔑 `{license_row['license_key']}`\n\n"
                f"📌 Status: "
                f"{license_row['status']}\n"
                f"⏳ Remaining: "
                f"{remaining_time(license_row['expires_at'])}\n"
                f"📅 Expires: "
                f"{format_expiry(license_row['expires_at'])}"
            )

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=main_menu(user.id)
        )

        return


    # =====================================================
    # DOWNLOAD
    # =====================================================

    if data == "download":

        license_row = get_session_license(
            user.id
        )

        if not license_row:

            await query.edit_message_text(
                "❌ You need an active license first.\n\n"
                "Press 🔑 Activate Key.",
                reply_markup=main_menu(user.id)
            )

            return

        USER_STATES[user.id] = "video_url"

        await query.edit_message_text(
            "📥 Video Download\n\n"
            "Send your YouTube or TikTok URL.",
            reply_markup=cancel_menu()
        )

        return


    # =====================================================
    # MP3
    # =====================================================

    if data == "mp3":

        license_row = get_session_license(
            user.id
        )

        if not license_row:

            await query.edit_message_text(
                "❌ You need an active license first.\n\n"
                "Press 🔑 Activate Key.",
                reply_markup=main_menu(user.id)
            )

            return

        USER_STATES[user.id] = "mp3"

        await query.edit_message_text(
            "🎵 MP3 Download\n\n"
            "Send your YouTube or TikTok URL.",
            reply_markup=cancel_menu()
        )

        return


    # =====================================================
    # MY ID
    # =====================================================

    if data == "my_id":

        await query.edit_message_text(
            "🆔 Your Telegram ID:\n\n"
            f"`{user.id}`",
            parse_mode="Markdown",
            reply_markup=main_menu(user.id)
        )

        return


    # =====================================================
    # HELP
    # =====================================================

    if data == "help":

        text = (
            "ℹ️ NUTHH’ Downloader Help\n\n"

            "🔑 Activate Key\n"
            "Activate your license.\n\n"

            "📥 Download\n"
            "Download YouTube/TikTok video.\n\n"

            "🎬 Video Quality\n"
            "• 4K 2160p\n"
            "• 2K 1440p\n"
            "• 1080p\n"
            "• 720p\n"
            "• Best Available\n\n"

            "🎵 MP3\n"
            "Download audio as MP3 192kbps.\n\n"

            "⚠️ Important\n"
            "Owner also needs an active license "
            "before downloading."
        )

        await query.edit_message_text(
            text,
            reply_markup=main_menu(user.id)
        )

        return


    # =====================================================
    # OWNER PANEL
    # =====================================================

    if data == "owner_panel":

        if not is_owner(user.id):

            await query.answer(
                "Owner only.",
                show_alert=True
            )

            return

        await query.edit_message_text(
            "👑 Owner Panel",
            reply_markup=owner_menu()
        )

        return


    # =====================================================
    # QUALITY SELECTION
    # =====================================================

    if data.startswith("quality:"):

        quality = data.split(
            ":",
            1
        )[1]

        url = PENDING_URLS.get(
            user.id
        )

        if not url:

            await query.edit_message_text(
                "❌ Download session expired.",
                reply_markup=main_menu(user.id)
            )

            return

        if not get_session_license(
            user.id
        ):

            await query.edit_message_text(
                "❌ Your license is no longer active.",
                reply_markup=main_menu(user.id)
            )

            return

        USER_STATES.pop(
            user.id,
            None
        )

        PENDING_URLS.pop(
            user.id,
            None
        )

        quality_names = {
            "4k": "4K (2160p)",
            "2k": "2K (1440p)",
            "1080p": "1080p",
            "720p": "720p",
            "best": "Best Available",
        }

        quality_name = quality_names.get(
            quality,
            quality
        )

        await query.edit_message_text(
            f"⏳ Downloading...\n\n"
            f"🎬 Quality: {quality_name}\n\n"
            "Please wait."
        )

        folder = create_temp_dir(
            str(DOWNLOAD_DIR)
        )

        try:

            file_path = await download_video(
                url,
                folder,
                quality
            )

            if is_file_too_large(
                file_path,
                MAX_FILE_SIZE
            ):

                await query.message.reply_text(
                    "❌ File is too large for "
                    "the configured Telegram upload limit."
                )

                return

            with file_path.open(
                "rb"
            ) as video:

                await query.message.reply_video(
                    video=video,
                    caption=(
                        "🎬 NUTHH’ Downloader\n\n"
                        f"Quality: {quality_name}"
                    ),
                    supports_streaming=True
                )

        except Exception as error:

            await query.message.reply_text(
                "❌ Download failed.\n\n"
                f"{str(error)[:1500]}"
            )

        finally:

            cleanup_folder(
                folder
            )

        return


    # =====================================================
    # OWNER CHECK
    # =====================================================

    if not is_owner(user.id):

        await query.answer(
            "Owner only.",
            show_alert=True
        )

        return


    # =====================================================
    # GENERATE KEY
    # =====================================================

    if data == "gen":

        await query.edit_message_text(
            "➕ Generate License Key\n\n"
            "Choose duration:",
            reply_markup=InlineKeyboardMarkup([

                [
                    InlineKeyboardButton(
                        "1 Day",
                        callback_data="gend:1d"
                    ),

                    InlineKeyboardButton(
                        "7 Days",
                        callback_data="gend:7d"
                    ),
                ],

                [
                    InlineKeyboardButton(
                        "30 Days",
                        callback_data="gend:30d"
                    ),

                    InlineKeyboardButton(
                        "90 Days",
                        callback_data="gend:90d"
                    ),
                ],

                [
                    InlineKeyboardButton(
                        "1 Year",
                        callback_data="gend:1y"
                    ),

                    InlineKeyboardButton(
                        "Lifetime",
                        callback_data="gend:lifetime"
                    ),
                ],

                [
                    InlineKeyboardButton(
                        "⬅️ Back",
                        callback_data="owner_panel"
                    )
                ],

            ])
        )

        return


    # =====================================================
    # GENERATE KEY RESULT
    # =====================================================

    if data.startswith("gend:"):

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
            user.id
        )

        await query.edit_message_text(
            "🔑 NEW LICENSE KEY\n\n"

            f"`{key}`\n\n"

            f"⏳ Duration: {duration}\n"

            f"📅 Expires: "
            f"{format_expiry(expires_at)}\n\n"

            "⚠️ Owner must activate this key "
            "before downloading.",
            parse_mode="Markdown",
            reply_markup=owner_menu()
        )

        return


    # =====================================================
    # ALL KEYS
    # =====================================================

    if data == "keys":

        rows = list_licenses()

        if not rows:

            text = (
                "📋 All Keys\n\n"
                "No licenses found."
            )

        else:

            parts = [
                "📋 ALL LICENSES\n"
            ]

            for row in rows[:50]:

                parts.append(
                    f"🔑 `{row['license_key']}`\n"
                    f"📌 {row['status']}\n"
                    f"⏳ {remaining_time(row['expires_at'])}\n"
                )

            text = "\n".join(parts)

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=owner_menu()
        )

        return


    # =====================================================
    # USERS
    # =====================================================

    if data == "users":

        rows = list_users()

        if not rows:

            text = "👥 No users."

        else:

            parts = [
                "👥 USERS\n"
            ]

            for row in rows[:50]:

                username = (
                    f"@{row['username']}"
                    if row["username"]
                    else "-"
                )

                parts.append(
                    f"🆔 {row['user_id']}\n"
                    f"👤 {username}\n"
                    f"👑 Role: {row['role']}\n"
                )

            text = "\n".join(parts)

        await query.edit_message_text(
            text,
            reply_markup=owner_menu()
        )

        return


    # =====================================================
    # STATISTICS
    # =====================================================

    if data == "stats":

        stats = get_statistics()

        text = (
            "📊 STATISTICS\n\n"

            f"👥 Users: "
            f"{stats['users']}\n"

            f"🔑 Licenses: "
            f"{stats['licenses']}\n"

            f"✅ Active Licenses: "
            f"{stats['active_licenses']}\n"

            f"📢 Channels: "
            f"{stats['channels']}"
        )

        await query.edit_message_text(
            text,
            reply_markup=owner_menu()
        )

        return


    # =====================================================
    # CHANNELS
    # =====================================================

    if data == "channels":

        rows = get_channels()

        if not rows:

            text = (
                "📢 CHANNELS\n\n"
                "No channels configured."
            )

        else:

            parts = [
                "📢 CHANNELS\n"
            ]

            for index, row in enumerate(
                rows,
                start=1
            ):

                parts.append(
                    f"{index}. "
                    f"{row['username']}"
                )

            text = "\n".join(parts)

        await query.edit_message_text(
            text,
            reply_markup=owner_menu()
        )

        return


    # =====================================================
    # OWNER-ONLY STATES
    # =====================================================

    owner_actions = {
        "keyinfo": "keyinfo",
        "revoke": "revoke",
        "restore": "restore",
        "delete": "delete",
        "addchannel": "addchannel",
        "removechannel": "removechannel",
        "setowner": "setowner",
        "setuser": "setuser",
    }

    if data in owner_actions:

        action = owner_actions[data]

        if action in (
            "revoke",
            "restore",
            "delete",
            "setowner",
            "setuser",
        ):

            if not is_main_owner(
                user.id
            ):

                await query.answer(
                    "Main Owner only.",
                    show_alert=True
                )

                return

        USER_STATES[user.id] = action

        prompts = {

            "keyinfo":
                "🔍 Send license key:",

            "revoke":
                "🚫 Send license key to revoke:",

            "restore":
                "♻️ Send license key to restore:",

            "delete":
                "🗑 Send license key to delete:",

            "addchannel":
                "➕ Send public channel username.\n\n"
                "Example:\n"
                "@music_khmer",

            "removechannel":
                "🗑 Send channel username to remove:",

            "setowner":
                "👑 Send Telegram User ID:",

            "setuser":
                "👤 Send Telegram User ID:",
        }

        await query.edit_message_text(
            prompts[action],
            reply_markup=cancel_menu()
        )

        return


# =========================================================
# TEXT HANDLER
# =========================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user = update.effective_user

    text = (
        update.message.text
        or ""
    ).strip()

    ensure_user(
        user.id,
        user.username,
        user.first_name
    )

    state = USER_STATES.get(
        user.id
    )


    # =====================================================
    # AUTO DETECT LICENSE KEY
    # =====================================================

    possible_key = normalize_license_key(
        text
    )

    if is_valid_key_format(
        possible_key
    ):

        success, message = await activate_key_for_user(
            user.id,
            possible_key
        )

        USER_STATES.pop(
            user.id,
            None
        )

        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=main_menu(user.id)
        )

        return


    # =====================================================
    # ACTIVATE STATE
    # =====================================================

    if state == "activate":

        success, message = await activate_key_for_user(
            user.id,
            text
        )

        if success:

            USER_STATES.pop(
                user.id,
                None
            )

        await update.message.reply_text(
            message,
            parse_mode="Markdown",
            reply_markup=(
                main_menu(user.id)
                if success
                else cancel_menu()
            )
        )

        return


    # =====================================================
    # VIDEO URL
    # =====================================================

    if state == "video_url":

        if not get_session_license(
            user.id
        ):

            USER_STATES.pop(
                user.id,
                None
            )

            await update.message.reply_text(
                "❌ Active license required.",
                reply_markup=main_menu(user.id)
            )

            return

        if not is_supported_url(
            text
        ):

            await update.message.reply_text(
                "❌ Invalid URL.\n\n"
                "Please send a YouTube or TikTok URL."
            )

            return

        PENDING_URLS[user.id] = text

        try:

            await update.message.reply_text(
                "🔎 Checking available video qualities..."
            )

            info = await get_video_info(
                text
            )

            available = get_available_qualities(
                info
            )

            title = info.get(
                "title",
                "Video"
            )

            await update.message.reply_text(
                f"🎬 {title}\n\n"
                "Choose your video quality:",
                reply_markup=quality_menu_from_available(
                    available
                )
            )

        except Exception as error:

            PENDING_URLS.pop(
                user.id,
                None
            )

            await update.message.reply_text(
                "❌ Could not read video.\n\n"
                f"{str(error)[:1200]}",
                reply_markup=main_menu(user.id)
            )

        return


    # =====================================================
    # MP3
    # =====================================================

    if state == "mp3":

        if not get_session_license(
            user.id
        ):

            USER_STATES.pop(
                user.id,
                None
            )

            await update.message.reply_text(
                "❌ Active license required.",
                reply_markup=main_menu(user.id)
            )

            return

        if not is_supported_url(
            text
        ):

            await update.message.reply_text(
                "❌ Invalid URL.\n\n"
                "Please send a YouTube or TikTok URL."
            )

            return

        USER_STATES.pop(
            user.id,
            None
        )

        folder = create_temp_dir(
            str(DOWNLOAD_DIR)
        )

        try:

            await update.message.reply_text(
                "⏳ Downloading MP3...\n\n"
                "Please wait."
            )

            file_path = await download_mp3(
                text,
                folder,
                "192"
            )

            if is_file_too_large(
                file_path,
                MAX_FILE_SIZE
            ):

                await update.message.reply_text(
                    "❌ MP3 file is too large."
                )

                return

            with file_path.open(
                "rb"
            ) as audio:

                await update.message.reply_audio(
                    audio=audio,
                    caption=(
                        "🎵 NUTHH’ Downloader\n"
                        "MP3 192kbps"
                    )
                )

            # ---------------------------------------------
            # POST MP3 TO ALL CHANNELS
            # ---------------------------------------------

            channels = get_channels()

            for channel in channels:

                try:

                    with file_path.open(
                        "rb"
                    ) as audio:

                        await context.bot.send_audio(
                            chat_id=channel["username"],
                            audio=audio,
                            caption=(
                                "🎵 NUTHH’ Downloader\n"
                                "MP3 192kbps"
                            )
                        )

                except Exception as error:

                    print(
                        f"Channel "
                        f"{channel['username']} "
                        f"failed: {error}"
                    )

        except Exception as error:

            await update.message.reply_text(
                "❌ MP3 download failed.\n\n"
                f"{str(error)[:1500]}"
            )

        finally:

            cleanup_folder(
                folder
            )

        return


    # =====================================================
    # KEY INFO / REVOKE / RESTORE / DELETE
    # =====================================================

    if state in (
        "keyinfo",
        "revoke",
        "restore",
        "delete",
    ):

        key = normalize_license_key(
            text
        )

        row = get_license(
            key
        )

        if not row:

            await update.message.reply_text(
                "❌ License key not found."
            )

            return


        # ---------------------------------------------
        # KEY INFO
        # ---------------------------------------------

        if state == "keyinfo":

            message = (
                "🔍 LICENSE INFO\n\n"

                f"🔑 `{row['license_key']}`\n\n"

                f"📌 Status: "
                f"{row['status']}\n"

                f"⏳ Remaining: "
                f"{remaining_time(row['expires_at'])}\n"

                f"📅 Expires: "
                f"{format_expiry(row['expires_at'])}"
            )

            await update.message.reply_text(
                message,
                parse_mode="Markdown",
                reply_markup=owner_menu()
            )


        # ---------------------------------------------
        # REVOKE
        # ---------------------------------------------

        elif state == "revoke":

            if not is_main_owner(
                user.id
            ):

                await update.message.reply_text(
                    "❌ Main Owner only."
                )

                return

            revoke_license(
                key
            )

            # Remove active sessions
            for uid, active_key in list(
                ACTIVE_SESSIONS.items()
            ):

                if normalize_license_key(
                    active_key
                ) == key:

                    ACTIVE_SESSIONS.pop(
                        uid,
                        None
                    )

            await update.message.reply_text(
                "✅ License revoked.",
                reply_markup=owner_menu()
            )


        # ---------------------------------------------
        # RESTORE
        # ---------------------------------------------

        elif state == "restore":

            if not is_main_owner(
                user.id
            ):

                await update.message.reply_text(
                    "❌ Main Owner only."
                )

                return

            restore_license(
                key
            )

            await update.message.reply_text(
                "✅ License restored.",
                reply_markup=owner_menu()
            )


        # ---------------------------------------------
        # DELETE
        # ---------------------------------------------

        elif state == "delete":

            if not is_main_owner(
                user.id
            ):

                await update.message.reply_text(
                    "❌ Main Owner only."
                )

                return

            for uid, active_key in list(
                ACTIVE_SESSIONS.items()
            ):

                if normalize_license_key(
                    active_key
                ) == key:

                    ACTIVE_SESSIONS.pop(
                        uid,
                        None
                    )

            delete_license(
                key
            )

            await update.message.reply_text(
                "✅ License deleted.",
                reply_markup=owner_menu()
            )

        USER_STATES.pop(
            user.id,
            None
        )

        return


    # =====================================================
    # ADD CHANNEL
    # =====================================================

    if state == "addchannel":

        if not is_owner(
            user.id
        ):

            await update.message.reply_text(
                "❌ Owner only."
            )

            return

        channel = text.strip()

        if not re.fullmatch(
            r"@[A-Za-z0-9_]{5,}",
            channel
        ):

            await update.message.reply_text(
                "❌ Invalid channel username.\n\n"
                "Example:\n"
                "@music_khmer"
            )

            return

        try:

            add_channel(
                channel,
                channel,
                user.id
            )

            USER_STATES.pop(
                user.id,
                None
            )

            await update.message.reply_text(
                f"✅ Channel added:\n"
                f"{channel}\n\n"
                "Make sure the bot is Administrator "
                "and has permission to post messages.",
                reply_markup=owner_menu()
            )

        except Exception as error:

            await update.message.reply_text(
                f"❌ Could not add channel:\n"
                f"{str(error)}"
            )

        return


    # =====================================================
    # REMOVE CHANNEL
    # =====================================================

    if state == "removechannel":

        if not is_owner(
            user.id
        ):

            await update.message.reply_text(
                "❌ Owner only."
            )

            return

        delete_channel(
            text.strip()
        )

        USER_STATES.pop(
            user.id,
            None
        )

        await update.message.reply_text(
            "✅ Channel removed.",
            reply_markup=owner_menu()
        )

        return


    # =====================================================
    # SET OWNER / USER
    # =====================================================

    if state in (
        "setowner",
        "setuser",
    ):

        if not is_main_owner(
            user.id
        ):

            await update.message.reply_text(
                "❌ Main Owner only."
            )

            return

        try:

            target_id = int(
                text.strip()
            )

        except ValueError:

            await update.message.reply_text(
                "❌ Invalid Telegram User ID."
            )

            return


        if (
            state == "setuser"
            and target_id == MAIN_OWNER_ID
        ):

            await update.message.reply_text(
                "❌ Main Owner cannot be demoted."
            )

            return


        role = (
            "owner"
            if state == "setowner"
            else "user"
        )

        set_user_role(
            target_id,
            role
        )

        USER_STATES.pop(
            user.id,
            None
        )

        await update.message.reply_text(
            f"✅ User `{target_id}` "
            f"is now `{role}`.",
            parse_mode="Markdown",
            reply_markup=owner_menu()
        )

        return


    # =====================================================
    # FALLBACK
    # =====================================================

    await update.message.reply_text(
        "Please use the buttons below.",
        reply_markup=main_menu(user.id)
    )


# =========================================================
# ERROR HANDLER
# =========================================================

async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE
):

    print(
        "BOT ERROR:",
        context.error
    )


# =========================================================
# MAIN
# =========================================================

def main():

    validate_config()

    init_db()

    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # Commands
    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "activate",
            activate_command
        )
    )

    # Buttons
    application.add_handler(
        CallbackQueryHandler(
            callback_handler
        )
    )

    # Text
    application.add_handler(
        MessageHandler(
            filters.TEXT
            & ~filters.COMMAND,
            text_handler
        )
    )

    # Errors
    application.add_error_handler(
        error_handler
    )

    print(
        "========================================"
    )

    print(
        "NUTHH’ Downloader is running..."
    )

    print(
        "4K / 2K / 1080p / 720p enabled"
    )

    print(
        "Owner:",
        MAIN_OWNER_ID
    )

    print(
        "========================================"
    )

    application.run_polling(
        drop_pending_updates=True
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    main()

import os
import re
from datetime import datetime, timezone

from dotenv import load_dotenv

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
)

from license import (
    generate_key,
    calculate_expiry,
    format_expiry,
)


# =========================
# CONFIG
# =========================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
MAIN_OWNER_ID = int(os.getenv("OWNER_ID", "0"))

URL_PATTERN = re.compile(
    r"https?://(?:www\.)?"
    r"(?:youtube\.com|youtu\.be|tiktok\.com)/\S+",
    re.IGNORECASE
)


# =========================
# HELPERS
# =========================

def is_main_owner(user_id: int) -> bool:
    return user_id == MAIN_OWNER_ID


def is_owner(user_id: int) -> bool:
    if user_id == MAIN_OWNER_ID:
        return True

    return get_user_role(user_id) == "owner"


def license_active(user_id: int) -> bool:
    license_row = get_user_license(user_id)

    if not license_row:
        return False

    if license_row["status"] != "active":
        return False

    expires_at = license_row["expires_at"]

    if not expires_at:
        return True

    try:
        expires = datetime.fromisoformat(expires_at)

        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) >= expires:
            revoke_license(license_row["license_key"])
            return False

    except Exception:
        return False

    return True


def main_menu(user_id: int):
    buttons = [
        [
            InlineKeyboardButton("🔑 Activate Key", callback_data="activate"),
            InlineKeyboardButton("📋 My License", callback_data="my_license"),
        ],
        [
            InlineKeyboardButton("📥 Download", callback_data="download"),
            InlineKeyboardButton("🆔 My ID", callback_data="my_id"),
        ],
        [
            InlineKeyboardButton("ℹ️ Help", callback_data="help"),
        ],
    ]

    if is_owner(user_id):
        buttons.append([
            InlineKeyboardButton("👑 Owner Panel", callback_data="owner_panel")
        ])

    return InlineKeyboardMarkup(buttons)


def owner_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("➕ Generate Key", callback_data="genkey"),
            InlineKeyboardButton("📋 All Keys", callback_data="keys"),
        ],
        [
            InlineKeyboardButton("🔍 Key Info", callback_data="keyinfo"),
            InlineKeyboardButton("🚫 Revoke Key", callback_data="revoke"),
        ],
        [
            InlineKeyboardButton("🗑 Delete Key", callback_data="delete"),
            InlineKeyboardButton("👥 Users", callback_data="users"),
        ],
        [
            InlineKeyboardButton("👑 Set Owner", callback_data="set_owner"),
            InlineKeyboardButton("👤 Set User", callback_data="set_user"),
        ],
        [
            InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu"),
        ],
    ])


def duration_menu():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1 Day", callback_data="duration_1d"),
            InlineKeyboardButton("7 Days", callback_data="duration_7d"),
        ],
        [
            InlineKeyboardButton("30 Days", callback_data="duration_30d"),
            InlineKeyboardButton("90 Days", callback_data="duration_90d"),
        ],
        [
            InlineKeyboardButton("1 Year", callback_data="duration_1y"),
            InlineKeyboardButton("Lifetime", callback_data="duration_lifetime"),
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="owner_panel"),
        ],
    ])


# =========================
# START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    ensure_user(user.id)

    text = (
        "🤖 *NUTHH BOT*\n\n"
        f"👋 Hello, {user.first_name}!\n\n"
        "Choose an option below:"
    )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=main_menu(user.id)
    )


# =========================
# CALLBACKS
# =========================

async def callback_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    query = update.callback_query

    await query.answer()

    user = query.from_user
    user_id = user.id
    data = query.data

    ensure_user(user_id)

    # =====================
    # MAIN MENU
    # =====================

    if data == "main_menu":
        await query.edit_message_text(
            "🤖 *NUTHH BOT*\n\nChoose an option:",
            parse_mode="Markdown",
            reply_markup=main_menu(user_id)
        )
        return

    # =====================
    # ACTIVATE
    # =====================

    if data == "activate":
        context.user_data["waiting"] = "activate_key"

        await query.edit_message_text(
            "🔐 *Activate License*\n\n"
            "Please send your license key.\n\n"
            "Example:\n"
            "`NUTHH-ABCD-EFGH-IJKL`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "❌ Cancel",
                        callback_data="main_menu"
                    )
                ]
            ])
        )
        return

    # =====================
    # MY LICENSE
    # =====================

    if data == "my_license":
        license_row = get_user_license(user_id)

        if not license_row:
            text = (
                "🔐 *My License*\n\n"
                "❌ No active license.\n\n"
                "Please activate a key first."
            )
        else:
            expires = license_row["expires_at"]

            if expires:
                expiry_text = format_expiry(expires)
            else:
                expiry_text = "Lifetime"

            text = (
                "🔐 *My License*\n\n"
                f"🔑 Key: `{license_row['license_key']}`\n"
                f"📌 Status: `{license_row['status']}`\n"
                f"📅 Expires: `{expiry_text}`"
            )

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="main_menu"
                    )
                ]
            ])
        )
        return

    # =====================
    # MY ID
    # =====================

    if data == "my_id":
        await query.edit_message_text(
            "🆔 *Your Telegram ID*\n\n"
            f"`{user_id}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="main_menu"
                    )
                ]
            ])
        )
        return

    # =====================
    # DOWNLOAD
    # =====================

    if data == "download":
        if not license_active(user_id):
            await query.edit_message_text(
                "🔒 *License Required*\n\n"
                "You need an active license key before using "
                "the downloader.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton(
                            "🔑 Activate Key",
                            callback_data="activate"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔙 Back",
                            callback_data="main_menu"
                        )
                    ],
                ])
            )
            return

        context.user_data["waiting"] = "download_url"

        await query.edit_message_text(
            "📥 *Download Video*\n\n"
            "Send a YouTube or TikTok link now.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "❌ Cancel",
                        callback_data="main_menu"
                    )
                ]
            ])
        )
        return

    # =====================
    # HELP
    # =====================

    if data == "help":
        await query.edit_message_text(
            "ℹ️ *NUTHH BOT Help*\n\n"
            "🔑 Activate Key — activate your license\n"
            "📋 My License — check your license\n"
            "📥 Download — send a supported video URL\n"
            "🆔 My ID — show your Telegram ID",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 Back",
                        callback_data="main_menu"
                    )
                ]
            ])
        )
        return

    # =====================
    # OWNER PANEL
    # =====================

    if data == "owner_panel":
        if not is_owner(user_id):
            await query.edit_message_text("❌ Owner only.")
            return

        await query.edit_message_text(
            "👑 *OWNER PANEL*\n\n"
            "Choose an action:",
            parse_mode="Markdown",
            reply_markup=owner_menu()
        )
        return

    # =====================
    # GENERATE KEY
    # =====================

    if data == "genkey":
        if not is_owner(user_id):
            await query.edit_message_text("❌ Owner only.")
            return

        await query.edit_message_text(
            "➕ *Generate License Key*\n\n"
            "Select duration:",
            parse_mode="Markdown",
            reply_markup=duration_menu()
        )
        return

    if data.startswith("duration_"):
        if not is_owner(user_id):
            await query.edit_message_text("❌ Owner only.")
            return

        duration = data.replace("duration_", "")

        key = generate_key()
        expires_at = calculate_expiry(duration)

        create_license(key, expires_at)

        expiry_text = (
            "Lifetime"
            if expires_at is None
            else format_expiry(expires_at)
        )

        await query.edit_message_text(
            "✅ *License Created*\n\n"
            f"🔑 Key:\n`{key}`\n\n"
            f"⏳ Duration: `{duration}`\n"
            f"📅 Expires: `{expiry_text}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "➕ Generate Another",
                        callback_data="genkey"
                    )
                ],
                [
                    InlineKeyboardButton(
                        "🔙 Owner Panel",
                        callback_data="owner_panel"
                    )
                ],
            ])
        )
        return

    # =====================
    # ALL KEYS
    # =====================

    if data == "keys":
        if not is_owner(user_id):
            await query.edit_message_text("❌ Owner only.")
            return

        rows = list_licenses()

        if not rows:
            text = "📋 *License Keys*\n\nNo keys found."
        else:
            lines = ["📋 *License Keys*\n"]

            for row in rows[:30]:
                status = row["status"]
                key = row["license_key"]

                lines.append(
                    f"🔑 `{key}`\n"
                    f"Status: `{status}`\n"
                )

            text = "\n".join(lines)

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 Owner Panel",
                        callback_data="owner_panel"
                    )
                ]
            ])
        )
        return

    # =====================
    # USERS
    # =====================

    if data == "users":
        if not is_owner(user_id):
            await query.edit_message_text("❌ Owner only.")
            return

        rows = list_users()

        if not rows:
            text = "👥 No users found."
        else:
            lines = ["👥 *Users*\n"]

            for row in rows[:30]:
                role = row["role"]
                uid = row["user_id"]

                icon = "👑" if role == "owner" else "👤"

                lines.append(
                    f"{icon} `{uid}` — `{role}`"
                )

            text = "\n".join(lines)

        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "🔙 Owner Panel",
                        callback_data="owner_panel"
                    )
                ]
            ])
        )
        return

    # =====================
    # SET OWNER
    # =====================

    if data == "set_owner":
        if not is_main_owner(user_id):
            await query.edit_message_text(
                "❌ Only the Main Owner can change roles."
            )
            return

        context.user_data["waiting"] = "set_owner"

        await query.edit_message_text(
            "👑 *Set Owner*\n\n"
            "Send the Telegram User ID you want to promote.\n\n"
            "Example:\n"
            "`123456789`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "❌ Cancel",
                        callback_data="owner_panel"
                    )
                ]
            ])
        )
        return

    # =====================
    # SET USER
    # =====================

    if data == "set_user":
        if not is_main_owner(user_id):
            await query.edit_message_text(
                "❌ Only the Main Owner can change roles."
            )
            return

        context.user_data["waiting"] = "set_user"

        await query.edit_message_text(
            "👤 *Set User*\n\n"
            "Send the Telegram User ID you want to change to User.\n\n"
            "Example:\n"
            "`123456789`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "❌ Cancel",
                        callback_data="owner_panel"
                    )
                ]
            ])
        )
        return

    # =====================
    # KEY INFO
    # =====================

    if data == "keyinfo":
        if not is_owner(user_id):
            await query.edit_message_text("❌ Owner only.")
            return

        context.user_data["waiting"] = "keyinfo"

        await query.edit_message_text(
            "🔍 *Key Info*\n\n"
            "Send the license key.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "❌ Cancel",
                        callback_data="owner_panel"
                    )
                ]
            ])
        )
        return

    # =====================
    # REVOKE
    # =====================

    if data == "revoke":
        if not is_owner(user_id):
            await query.edit_message_text("❌ Owner only.")
            return

        context.user_data["waiting"] = "revoke"

        await query.edit_message_text(
            "🚫 *Revoke Key*\n\n"
            "Send the license key to revoke.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "❌ Cancel",
                        callback_data="owner_panel"
                    )
                ]
            ])
        )
        return

    # =====================
    # DELETE
    # =====================

    if data == "delete":
        if not is_owner(user_id):
            await query.edit_message_text("❌ Owner only.")
            return

        context.user_data["waiting"] = "delete"

        await query.edit_message_text(
            "🗑 *Delete Key*\n\n"
            "Send the license key to delete.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "❌ Cancel",
                        callback_data="owner_panel"
                    )
                ]
            ])
        )
        return


# =========================
# TEXT HANDLER
# =========================

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    user = update.effective_user
    user_id = user.id

    ensure_user(user_id)

    text = update.message.text.strip()

    waiting = context.user_data.get("waiting")

    # =====================
    # ACTIVATE KEY
    # =====================

    if waiting == "activate_key":

        success, reason = activate_license(text, user_id)

        context.user_data.pop("waiting", None)

        if success:
            license_row = get_user_license(user_id)

            expiry = license_row["expires_at"]

            expiry_text = (
                "Lifetime"
                if not expiry
                else format_expiry(expiry)
            )

            await update.message.reply_text(
                "✅ *License Activated!*\n\n"
                f"🔑 Key: `{text}`\n"
                f"📅 Expires: `{expiry_text}`\n\n"
                "🎬 You can now use the downloader.",
                parse_mode="Markdown",
                reply_markup=main_menu(user_id)
            )
            return

        messages = {
            "not_found": "❌ License key not found.",
            "inactive": "❌ This license is inactive.",
            "used": "❌ This key is already activated by another account.",
        }

        await update.message.reply_text(
            messages.get(reason, "❌ Unable to activate key."),
            reply_markup=main_menu(user_id)
        )
        return

    # =====================
    # SET OWNER
    # =====================

    if waiting == "set_owner":

        if not is_main_owner(user_id):
            await update.message.reply_text("❌ Main Owner only.")
            return

        try:
            target_id = int(text)

            if target_id == MAIN_OWNER_ID:
                await update.message.reply_text(
                    "ℹ️ This account is already the Main Owner."
                )
            else:
                set_user_role(target_id, "owner")

                await update.message.reply_text(
                    f"👑 User `{target_id}` is now an Owner.",
                    parse_mode="Markdown",
                    reply_markup=owner_menu()
                )

        except ValueError:
            await update.message.reply_text(
                "❌ Invalid Telegram User ID."
            )

        context.user_data.pop("waiting", None)
        return

    # =====================
    # SET USER
    # =====================

    if waiting == "set_user":

        if not is_main_owner(user_id):
            await update.message.reply_text("❌ Main Owner only.")
            return

        try:
            target_id = int(text)

            if target_id == MAIN_OWNER_ID:
                await update.message.reply_text(
                    "❌ The Main Owner cannot be changed to User."
                )
            else:
                set_user_role(target_id, "user")

                await update.message.reply_text(
                    f"👤 User `{target_id}` is now a normal User.",
                    parse_mode="Markdown",
                    reply_markup=owner_menu()
                )

        except ValueError:
            await update.message.reply_text(
                "❌ Invalid Telegram User ID."
            )

        context.user_data.pop("waiting", None)
        return

    # =====================
    # KEY INFO
    # =====================

    if waiting == "keyinfo":

        if not is_owner(user_id):
            return

        row = get_license(text)

        context.user_data.pop("waiting", None)

        if not row:
            await update.message.reply_text(
                "❌ Key not found.",
                reply_markup=owner_menu()
            )
            return

        activated = row["activated_by"]

        await update.message.reply_text(
            "🔍 *Key Information*\n\n"
            f"🔑 `{row['license_key']}`\n"
            f"📌 Status: `{row['status']}`\n"
            f"👤 Activated By: `{activated or 'None'}`\n"
            f"📅 Expires: `{row['expires_at'] or 'Lifetime'}`",
            parse_mode="Markdown",
            reply_markup=owner_menu()
        )
        return

    # =====================
    # REVOKE
    # =====================

    if waiting == "revoke":

        if not is_owner(user_id):
            return

        revoke_license(text)

        context.user_data.pop("waiting", None)

        await update.message.reply_text(
            "🚫 License revoked.",
            reply_markup=owner_menu()
        )
        return

    # =====================
    # DELETE
    # =====================

    if waiting == "delete":

        if not is_owner(user_id):
            return

        delete_license(text)

        context.user_data.pop("waiting", None)

        await update.message.reply_text(
            "🗑 License deleted.",
            reply_markup=owner_menu()
        )
        return

    # =====================
    # DOWNLOAD URL
    # =====================

    if URL_PATTERN.search(text):

        if not license_active(user_id):
            await update.message.reply_text(
                "🔒 You need an active license key first.",
                reply_markup=main_menu(user_id)
            )
            return

        await update.message.reply_text(
            "⏳ Link received.\n\n"
            "The downloader engine is ready to be connected "
            "to an authorized download/API provider.\n\n"
            f"🔗 `{text}`",
            parse_mode="Markdown",
            reply_markup=main_menu(user_id)
        )
        return

    # =====================
    # DEFAULT
    # =====================

    await update.message.reply_text(
        "Please use the buttons below 👇",
        reply_markup=main_menu(user_id)
    )


# =========================
# COMMAND FALLBACK
# =========================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    await update.message.reply_text(
        "Use the buttons below 👇",
        reply_markup=main_menu(update.effective_user.id)
    )


# =========================
# MAIN
# =========================

def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing. Add it to Railway Variables."
        )

    if MAIN_OWNER_ID == 0:
        raise RuntimeError(
            "OWNER_ID is missing. Add your Telegram User ID."
        )

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(
        CallbackQueryHandler(callback_handler)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    print("NUTHH BOT is running...")

    app.run_polling()


if __name__ == "__main__":
    main()

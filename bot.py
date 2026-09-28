import os
import re
from datetime import datetime, timezone

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from database import (
    init_db,
    create_license,
    get_license,
    activate_license,
    revoke_license,
    delete_license,
    get_user_license,
    list_licenses,
)

from license import generate_key, calculate_expiry, format_expiry


load_dotenv()

BOT_TOKEN = os.getenv("8983376229:AAHhObqcUpd7e7z3Y8zpSYvh8jXs--jrWW4")
OWNER_ID = int(os.getenv("8736435737", "0"))

URL_PATTERN = re.compile(
    r"https?://(?:www\.)?(?:youtube\.com|youtu\.be|tiktok\.com)/\S+",
    re.IGNORECASE,
)


def is_owner(user_id):
    return user_id == OWNER_ID


def license_active(user_id):
    key = get_user_license(user_id)

    if not key:
        return False

    row = get_license(key)

    if not row:
        return False

    status = row[2]
    expires_at = row[4]

    if status != "active":
        return False

    if expires_at:
        expiry = datetime.fromisoformat(expires_at)

        if datetime.now(timezone.utc) >= expiry:
            revoke_license(key)
            return False

    return True


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if is_owner(user_id):
        await update.message.reply_text(
            "👑 NUTHH OWNER PANEL\n\n"
            "/genkey 1d\n"
            "/genkey 7d\n"
            "/genkey 30d\n"
            "/genkey 90d\n"
            "/genkey 1y\n"
            "/genkey lifetime\n\n"
            "/keys\n"
            "/keyinfo KEY\n"
            "/revoke KEY\n"
            "/deletekey KEY"
        )
        return

    if license_active(user_id):
        await update.message.reply_text(
            "✅ License Active!\n\n"
            "📥 Send your supported video URL."
        )
        return

    await update.message.reply_text(
        "🔐 NUTHH Downloader\n\n"
        "Your license is not active.\n\n"
        "Please send your License Key."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 NUTHH Downloader Help\n\n"
        "• Send your License Key first.\n"
        "• After activation, send a supported URL.\n\n"
        "Supported platforms:\n"
        "• YouTube\n"
        "• TikTok\n\n"
        "⚠️ Only download content you are authorized "
        "to download."
    )


async def genkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("❌ Owner only.")
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

    duration = context.args[0]

    try:
        expires_at = calculate_expiry(duration)
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid duration.\n\n"
            "Use 1d, 7d, 30d, 90d, 1y or lifetime."
        )
        return

    key = generate_key()

    create_license(key, expires_at)

    await update.message.reply_text(
        "🔑 LICENSE CREATED\n\n"
        f"Key:\n`{key}`\n\n"
        f"⏱ Duration: {duration}\n"
        f"📅 Expires: {format_expiry(expires_at)}\n"
        "🟢 Status: Active",
        parse_mode="Markdown",
    )


async def keys_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("❌ Owner only.")
        return

    rows = list_licenses()

    if not rows:
        await update.message.reply_text("📭 No licenses found.")
        return

    text = "🔑 LICENSES\n\n"

    for key, status, created, expires, activated_by in rows:
        text += (
            f"🔐 `{key}`\n"
            f"Status: {status}\n"
            f"Expires: {format_expiry(expires)}\n"
            f"User: {activated_by or 'Not activated'}\n\n"
        )

    await update.message.reply_text(
        text,
        parse_mode="Markdown",
    )


async def keyinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("❌ Owner only.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n/keyinfo NUTHH-XXXX-XXXX-XXXX"
        )
        return

    key = context.args[0].upper()
    row = get_license(key)

    if not row:
        await update.message.reply_text("❌ Key not found.")
        return

    await update.message.reply_text(
        "🔐 LICENSE INFO\n\n"
        f"Key: `{row[1]}`\n"
        f"Status: {row[2]}\n"
        f"Created: {row[3]}\n"
        f"Expires: {format_expiry(row[4])}\n"
        f"Activated By: {row[5] or 'None'}",
        parse_mode="Markdown",
    )


async def revoke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("❌ Owner only.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n/revoke NUTHH-XXXX-XXXX-XXXX"
        )
        return

    key = context.args[0].upper()

    if revoke_license(key):
        await update.message.reply_text(
            "🚫 License revoked successfully."
        )
    else:
        await update.message.reply_text(
            "❌ Key not found."
        )


async def deletekey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_owner(update.effective_user.id):
        await update.message.reply_text("❌ Owner only.")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage:\n/deletekey NUTHH-XXXX-XXXX-XXXX"
        )
        return

    key = context.args[0].upper()

    if delete_license(key):
        await update.message.reply_text(
            "🗑️ License deleted."
        )
    else:
        await update.message.reply_text(
            "❌ Key not found."
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()

    if is_owner(user_id):
        await update.message.reply_text(
            "👑 Owner commands:\n\n"
            "/genkey 30d\n"
            "/keys\n"
            "/keyinfo KEY\n"
            "/revoke KEY\n"
            "/deletekey KEY"
        )
        return

    # Active user
    if license_active(user_id):
        if URL_PATTERN.search(text):
            await update.message.reply_text(
                "✅ License verified.\n\n"
                "🔗 URL received.\n"
                "⏳ Ready for an authorized downloader/API provider."
            )
        else:
            await update.message.reply_text(
                "📥 Please send a YouTube or TikTok URL."
            )
        return

    # Try license activation
    success, reason = activate_license(
        text.upper(),
        user_id,
    )

    if success:
        row = get_license(text.upper())

        await update.message.reply_text(
            "✅ LICENSE ACTIVATED!\n\n"
            f"🔑 Key: `{text.upper()}`\n"
            f"📅 Expires: {format_expiry(row[4])}\n\n"
            "Now send your supported video URL.",
            parse_mode="Markdown",
        )
        return

    messages = {
        "invalid": "❌ Invalid License Key.",
        "inactive": "🚫 This License Key is inactive.",
        "expired": "⏰ This License Key has expired.",
        "used": "⚠️ This License Key is already used by another account.",
    }

    await update.message.reply_text(
        messages.get(reason, "❌ License activation failed.")
    )


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is missing in environment variables."
        )

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("genkey", genkey_command))
    app.add_handler(CommandHandler("keys", keys_command))
    app.add_handler(CommandHandler("keyinfo", keyinfo_command))
    app.add_handler(CommandHandler("revoke", revoke_command))
    app.add_handler(CommandHandler("deletekey", deletekey_command))

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message,
        )
    )

    print("🤖 NUTHH Downloader Bot is running...")

    app.run_polling()


if __name__ == "__main__":
    main()

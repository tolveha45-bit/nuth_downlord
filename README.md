````markdown id="9s4k2q"
# 🤖 NUTHH Downloader Bot

Python Telegram Bot with a License Key system.

## Features

- 🔐 License Key activation
- ⏳ Expiration dates
- ♾️ Lifetime keys
- 👑 Owner-only commands
- 🚫 Revoke license
- 🗑️ Delete license
- 📋 License list
- 🔎 License information
- 💾 SQLite database
- 🔗 YouTube/TikTok URL detection
- 🔒 Environment variables for secrets

## Project Structure

nuthh_downloader/

├── bot.py
├── database.py
├── license.py
├── requirements.txt
├── README.md
└── downloads/

## Installation

Install Python 3.10+.

Create a virtual environment:

```bash
python -m venv venv
````

Windows:

```powershell
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file locally:

```env
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
OWNER_ID=YOUR_TELEGRAM_USER_ID
```

Never upload `.env` or your bot token to GitHub.

## Run

```bash
python bot.py
```

You should see:

```text
🤖 NUTHH Downloader Bot is running...
```

## Owner Commands

Generate 1 day key:

```text
/genkey 1d
```

Generate 7 day key:

```text
/genkey 7d
```

Generate 30 day key:

```text
/genkey 30d
```

Generate 90 day key:

```text
/genkey 90d
```

Generate 1 year key:

```text
/genkey 1y
```

Generate lifetime key:

```text
/genkey lifetime
```

List keys:

```text
/keys
```

View key:

```text
/keyinfo NUTHH-XXXX-XXXX-XXXX
```

Revoke:

```text
/revoke NUTHH-XXXX-XXXX-XXXX
```

Delete:

```text
/deletekey NUTHH-XXXX-XXXX-XXXX
```

## License System

A user must activate a valid license before using the downloader.

Example:

```text
NUTHH-A7K2-P9QX-4M8Z
```

The license can be:

* Active
* Expired
* Revoked
* Activated by a Telegram account

## Security

Keep these values private:

```text
BOT_TOKEN
OWNER_ID
```

Do not commit `.env` to GitHub.

## Downloader

The current project handles Telegram bot logic and licensing.

For media retrieval, connect an authorized downloader/API provider and only process content that you have permission to download.

```
```

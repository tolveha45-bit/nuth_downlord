# NUTHH’ Downloader V2

A Telegram YouTube/TikTok Downloader Bot with License System.

## Features

- YouTube download
- YouTube Shorts
- TikTok
- MP4
- MP3
- SQLite
- License system
- Multiple owners
- User management
- Multiple Telegram channels
- Automatic MP3 channel posting
- License expiration
- Revoke
- Restore
- Delete
- Statistics
- Session-based activation
- Railway ready
- GitHub ready

## License Durations

- 1d
- 7d
- 30d
- 90d
- 1y
- lifetime

## Main Owner

Telegram ID:

8736435737

## Environment Variables

BOT_TOKEN=YOUR_NEW_BOT_TOKEN

OWNER_ID=8736435737

DATABASE_PATH=nuthh.db

## Install

pip install -r requirements.txt

## Run

python bot.py

## Generate Key

/genkey 1d

/genkey 7d

/genkey 30d

/genkey 90d

/genkey 1y

/genkey lifetime

## License Behavior

A user must activate a valid license.

The license allows unlimited downloads during
the current bot session.

After bot restart, users must activate the
license again.

The actual license remains stored in SQLite.

## Key Normalization

These are treated as the same key:

NUTHH-AB12-CD34-EF56

nuthh-ab12-cd34-ef56

 NUTHH-AB12-CD34-EF56

nuthh-ab12- cd34-ef56

## Channels

Channels are stored inside SQLite.

No CHANNEL_ID environment variable is required.

Add channels from:

Owner Panel
→ Add Channel

Use:

@channel_username

The bot must be Administrator and have
permission to Post Messages.

## Railway

Set:

BOT_TOKEN
OWNER_ID
DATABASE_PATH

Recommended:

DATABASE_PATH=/data/nuthh.db

If using a Railway Volume, mount it to:

/data

Then the SQLite database will survive
service replacement/redeployment.

## Security

Never upload BOT_TOKEN to GitHub.

If the token is exposed, revoke it through
BotFather and generate a new token.
User/Owner
   ↓
🔑 Activate Key
   ↓
License OK
   ↓
📥 Download
   ↓
YouTube/TikTok URL
   ↓
🔎 Bot checks available qualities
   ↓
┌───────────────────────┐
│ 🎬 4K (2160p)         │
│ 🎬 2K (1440p)         │
│ 🎬 1080p              │
│ 🎬 720p               │
│ 🏆 Best Available     │
└───────────────────────┘
   ↓
Download + MP4

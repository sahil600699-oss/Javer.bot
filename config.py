import os

# Bot Token Configuration (Render Environment Variable se uthayega)
BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    "token",
)

# Prefix used by message commands, e.g. !play <song>
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")

# Bot Owner Configuration
OWNER_ID = 1302619411529732136

# Lavalink Node Configuration for Music System
LAVALINK_HOST = "in-1.visihost.in"
LAVALINK_PORT = 3002
LAVALINK_PASSWORD = "pvt@1211"
LAVALINK_SECURE = False

import os

# Bot Token Configuration
# Priority 1: Render Environment Variable (Secret)
# Note: Local code mein hardcoded token bilkul nahi daalna hai, warna GitHub leak kar dega.
BOT_TOKEN = os.getenv("")

# Bot Owner Configuration
OWNER_ID = 1302619411529732136

# Lavalink Node Configuration
LAVALINK_HOST = os.getenv("LAVALINK_HOST", "in-1.visihost.in")
LAVALINK_PORT = int(os.getenv("LAVALINK_PORT", 3002))
LAVALINK_PASSWORD = os.getenv("LAVALINK_PASSWORD", "pvt@1211")
LAVALINK_SECURE = False

import asyncio
import os
import threading
from flask import Flask
import discord
from discord.ext import commands
from pymongo import MongoClient
import config

# --- Keep Alive Flask Server ---
app = Flask('')


@app.route('/')
def home():
  return 'Bot is alive!'


def run():
  app.run(host='0.0.0.0', port=8080)


def keep_alive():
  t = threading.Thread(target=run)
  t.start()


keep_alive()
# -------------------------------

# --- MongoDB Setup ---
MONGO_URI = os.getenv(
    'MONGO_URI', getattr(config, 'MONGO_URI', None)
)  # Render environment variable ya config se lega
db = None

if MONGO_URI:
  try:
    cluster = MongoClient(MONGO_URI)
    db = cluster[
        'javer_database'
    ]  # Database Name (Aap isse change kar sakte ho)
    print('[MongoDB] Successfully connected to Database!')
  except Exception as e:
    print(f'[MongoDB Connection Error]: {e}')
else:
  print('[MongoDB Warning] MONGO_URI variable missing in environment!')
# ----------------------

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True
intents.presences = False

PREFIXES = commands.when_mentioned_or(
    '.', ',', '-', '?', '$', ';', '/', ':', "'", '!'
)

bot = commands.Bot(command_prefix=PREFIXES, intents=intents, help_command=None)
bot.db = db  # Sabhi Cogs mein database access karne ke liye `bot.db` bind kar diya


@bot.event
async def on_ready():
  print('----------------------------------------')
  print(f'Bot Online: {bot.user} ({bot.user.id})')
  print('----------------------------------------')
  try:
    synced = await bot.tree.sync()
    print(f'Slash Commands Synced: {len(synced)}')
  except Exception as e:
    print(f'Slash Sync Error: {e}')

  await bot.change_presence(status=discord.Status.online, activity=None)


async def main():
  async with bot:
    cogs = [
        'cogs.help',
        'cogs.vchelper',
        'cogs.music',
        'cogs.moderation',
        'cogs.fungames',
        'cogs.utility',
        'cogs.vctracker',
        'cogs.gif',
        'cogs.msgtracker',
        'cogs.role',
        'cogs.kingdom',
        'cogs.welcome',
        'cogs.imposter',
        'cogs.modlogs',
        'cogs.xo',
        'cogs.autosend',
        'cogs.afk',
        'cogs.autoresponder',
        'cogs.premium',
    ]

    for cog in cogs:
      try:
        await bot.load_extension(cog)
        print(f'Loaded {cog}')
      except Exception as e:
        print(f'Error loading {cog}: {e}')

    await bot.start(config.BOT_TOKEN)


if __name__ == '__main__':
  asyncio.run(main())

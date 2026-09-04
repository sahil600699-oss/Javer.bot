import discord
from discord.ext import commands
import sqlite3

try:
    from config import OWNER_ID
except ImportError:
    OWNER_ID = None

DB_NAME = "autoresponder.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS auto_responses (guild_id INTEGER, trigger_text TEXT, response_text TEXT, PRIMARY KEY (guild_id, trigger_text))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS auto_reactions (guild_id INTEGER, trigger_text TEXT, emoji TEXT, PRIMARY KEY (guild_id, trigger_text))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS server_locks (guild_id INTEGER PRIMARY KEY, is_locked INTEGER DEFAULT 0)''')
        conn.commit()

init_db()

class AutoResponder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        msg_content = message.content.lower().strip()

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT emoji FROM auto_reactions WHERE guild_id = ? AND trigger_text = ?", (message.guild.id, msg_content))
            rec_row = cursor.fetchone()
            if rec_row:
                try: await message.add_reaction(rec_row[0])
                except: pass

            cursor.execute("SELECT response_text FROM auto_responses WHERE guild_id = ? AND trigger_text = ?", (message.guild.id, msg_content))
            res_row = cursor.fetchone()
            if res_row:
                try: await message.channel.send(res_row[0])
                except: pass

    @commands.command(name="autoadd")
    async def auto_add(self, ctx, *, content: str):
        if "|" not in content:
            return await ctx.send("❌ Usage: `!autoadd trigger | response`")
        trigger, response = [item.strip() for item in content.split("|", 1)]
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO auto_responses VALUES (?, ?, ?)", (ctx.guild.id, trigger.lower(), response))
            conn.commit()
        await ctx.send(f"✅ Set Auto-Response for `{trigger}`")

async def setup(bot):
    await bot.add_cog(AutoResponder(bot))
            

import discord
from discord.ext import commands

try:
    from config import OWNER_ID
except ImportError:
    OWNER_ID = None

class AutoResponder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.init_db()

    def init_db(self):
        cursor = self.db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auto_responses (
                guild_id INTEGER,
                trigger_text TEXT,
                response_text TEXT,
                PRIMARY KEY (guild_id, trigger_text)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS auto_reactions (
                guild_id INTEGER,
                trigger_text TEXT,
                emoji TEXT,
                PRIMARY KEY (guild_id, trigger_text)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS server_locks (
                guild_id INTEGER PRIMARY KEY,
                is_locked INTEGER DEFAULT 0
            )
        ''')
        self.db.commit()

    async def is_bot_owner(self, user):
        if OWNER_ID and user.id == int(OWNER_ID):
            return True
        return await self.bot.is_owner(user)

    def is_locked(self, guild_id):
        cursor = self.db.cursor()
        cursor.execute("SELECT is_locked FROM server_locks WHERE guild_id = ?", (guild_id,))
        row = cursor.fetchone()
        return bool(row[0]) if row else False

    async def cog_check(self, ctx):
        if not ctx.guild:
            return True

        if await self.is_bot_owner(ctx.author):
            return True

        if self.is_locked(ctx.guild.id):
            if ctx.author.id == ctx.guild.owner_id or ctx.author.guild_permissions.manage_messages:
                return True
            else:
                await ctx.send("🔒 **Is server me AutoResponder system locked hai.** Ye commands sirf **Manage Messages** permission wale users hi use kar sakte hain.")
                return False
        return True

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        msg_content = message.content.lower().strip()
        cursor = self.db.cursor()

        cursor.execute("SELECT emoji FROM auto_reactions WHERE guild_id = ? AND trigger_text = ?", (message.guild.id, msg_content))
        reaction_row = cursor.fetchone()

        if reaction_row:
            try:
                await message.add_reaction(reaction_row[0])
            except Exception as e:
                print(f"Auto-Reaction Error: {e}")

        cursor.execute("SELECT response_text FROM auto_responses WHERE guild_id = ? AND trigger_text = ?", (message.guild.id, msg_content))
        response_row = cursor.fetchone()

        if response_row:
            try:
                await message.channel.send(response_row[0])
            except Exception as e:
                print(f"Auto-Response Error: {e}")

    @commands.command(name="autolock")
    async def auto_lock(self, ctx, mode: str = None):
        is_bot_owner = await self.is_bot_owner(ctx.author)
        is_server_owner = (ctx.author.id == ctx.guild.owner_id)

        if not (is_server_owner or is_bot_owner):
            await ctx.send("❌ Ye command sirf **Server Owner** ya **Bot Owner** hi use kar sakta hai!")
            return

        if not mode or mode.lower() not in ["on", "off"]:
            await ctx.send("❌ Incorrect Format! Correct Format: `!autolock on` ya `!autolock off`")
            return

        mode = mode.lower()
        lock_status = 1 if mode == "on" else 0

        cursor = self.db.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO server_locks (guild_id, is_locked) VALUES (?, ?)",
            (ctx.guild.id, lock_status)
        )
        self.db.commit()

        if mode == "on":
            await ctx.send("🔒 **AutoResponder Locked!** Ab is server me saare auto-responder commands sirf **Manage Messages** permission wale hi run kar sakte hain.")
        else:
            await ctx.send("🔓 **AutoResponder Unlocked!** Ab is server me saare members normal commands use kar sakte hain.")

    @commands.command(name="autoadd")
    async def auto_add(self, ctx, *, content: str):
        """Format: !autoadd [trigger] | [response]"""
        if not (await self.is_bot_owner(ctx.author)) and not ctx.author.guild_permissions.manage_messages:
            await ctx.send("❌ Aapke paas `Manage Messages` permission nahi hai!")
            return

        if "|" not in content:
            await ctx.send("❌ Incorrect Format! Correct Format: `!autoadd trigger | response`\n*Example:* `!autoadd hi | Hello brother welcome!`")
            return

        trigger, response = [item.strip() for item in content.split("|", 1)]

        cursor = self.db.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO auto_responses (guild_id, trigger_text, response_text) VALUES (?, ?, ?)",
            (ctx.guild.id, trigger.lower(), response)
        )
        self.db.commit()

        await ctx.send(f"✅ **Auto-Response Set!**\n🔹 **Trigger:** `{trigger}`\n💬 **Response:** {response}")

    @commands.command(name="autodel")
    async def auto_del(self, ctx, *, trigger: str):
        if not (await self.is_bot_owner(ctx.author)) and not ctx.author.guild_permissions.manage_messages:
            await ctx.send("❌ Aapke paas `Manage Messages` permission nahi hai!")
            return

        cursor = self.db.cursor()
        cursor.execute("DELETE FROM auto_responses WHERE guild_id = ? AND trigger_text = ?", (ctx.guild.id, trigger.lower()))
        changes = cursor.rowcount
        self.db.commit()

        if changes > 0:
            await ctx.send(f"✅ Trigger **`{trigger}`** ka Auto-Response delete kar diya gaya hai.")
        else:
            await ctx.send(f"⚠️ Trigger **`{trigger}`** mila nahi.")

    @commands.command(name="autolist")
    async def auto_list(self, ctx):
        cursor = self.db.cursor()
        cursor.execute("SELECT trigger_text, response_text FROM auto_responses WHERE guild_id = ?", (ctx.guild.id,))
        rows = cursor.fetchall()

        embed = discord.Embed(title="📜 Server Auto-Responses List", color=discord.Color.blue())
        if not rows:
            embed.description = "⚠️ Koi Active Auto-Responses configured nahi hain."
        else:
            lines = [f"• **`{trig}`** ➔ {resp}" for trig, resp in rows]
            embed.description = "\n".join(lines[:20])

        await ctx.send(embed=embed)

    @commands.command(name="autorec")
    async def auto_rec_add(self, ctx, trigger: str, emoji: str):
        """Format: !autorec [message] [emoji]"""
        if not (await self.is_bot_owner(ctx.author)) and not ctx.author.guild_permissions.manage_messages:
            await ctx.send("❌ Aapke paas `Manage Messages` permission nahi hai!")
            return

        cursor = self.db.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO auto_reactions (guild_id, trigger_text, emoji) VALUES (?, ?, ?)",
            (ctx.guild.id, trigger.lower(), emoji)
        )
        self.db.commit()

        await ctx.send(f"✅ **Auto-Reaction Set!**\n🔹 **Message/Trigger:** `{trigger}`\n🎭 **Reaction Emoji:** {emoji}")

    @commands.command(name="autorecoff")
    async def auto_rec_off(self, ctx, *, trigger: str):
        if not (await self.is_bot_owner(ctx.author)) and not ctx.author.guild_permissions.manage_messages:
            await ctx.send("❌ Aapke paas `Manage Messages` permission nahi hai!")
            return

        cursor = self.db.cursor()
        cursor.execute("DELETE FROM auto_reactions WHERE guild_id = ? AND trigger_text = ?", (ctx.guild.id, trigger.lower()))
        changes = cursor.rowcount
        self.db.commit()

        if changes > 0:
            await ctx.send(f"🛑 Trigger **`{trigger}`** ke liye Auto-Reaction OFF kar diya gaya hai.")
        else:
            await ctx.send(f"⚠️ Trigger **`{trigger}`** ke liye koi Active Auto-Reaction nahi mila.")

    @commands.command(name="autoreclist")
    async def auto_rec_list(self, ctx):
        cursor = self.db.cursor()
        cursor.execute("SELECT trigger_text, emoji FROM auto_reactions WHERE guild_id = ?", (ctx.guild.id,))
        rows = cursor.fetchall()

        embed = discord.Embed(title="🎭 Server Auto-Reactions List", color=discord.Color.gold())
        if not rows:
            embed.description = "⚠️ Koi Active Auto-Reactions configured nahi hain."
        else:
            lines = [f"• **`{trig}`** ➔ {emo}" for trig, emo in rows]
            embed.description = "\n".join(lines[:20])

        await ctx.send(embed=embed)

    @commands.group(name="auto", invoke_without_command=True)
    async def auto_group(self, ctx):
        await ctx.send("❓ Help ke liye **`!auto help`** type karein.")

    @auto_group.command(name="help")
    async def auto_help(self, ctx):
        embed = discord.Embed(
            title="⚙️ Auto-Response & Auto-Reaction System — Guide",
            description="Is system se aap custom reply messages aur automated emojis reactions set kar sakte hain.",
            color=discord.Color.purple()
        )
        embed.add_field(
            name="🤖 Auto-Responses (Chat Replies)",
            value="• `!autoadd trigger | response` — Naya response add karein.\n"
                  "• `!autodel trigger` — Response delete karein.\n"
                  "• `!autolist` — Saved responses dekhein.",
            inline=False
        )
        embed.add_field(
            name="🎭 Auto-Reactions (Emoji Reactions)",
            value="• `!autorec trigger emoji` — Naya emoji reaction set karein.\n"
                  "• `!autorecoff trigger` — Emoji reaction turn off karein.\n"
                  "• `!autoreclist` — Saved reactions dekhein.",
            inline=False
        )
        embed.add_field(
            name="🔒 Server Security (Owner Only)",
            value="• `!autolock on` — Commands ko sirf 'Manage Messages' wale members tak limit karein.\n"
                  "• `!autolock off` — Sabhi members ko commands use karne ki permission dein.",
            inline=False
        )
        embed.set_footer(text="Lock control is strictly for Server Owner and Bot Owner.")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AutoResponder(bot))
                       

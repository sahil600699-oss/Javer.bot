import discord
from discord.ext import commands

try:
    from config import OWNER_ID
except ImportError:
    OWNER_ID = None

class AutoResponder(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return getattr(self.bot, "async_db", None)

    @property
    def responses_col(self):
        return self.db["auto_responses"] if self.db is not None else None

    @property
    def reactions_col(self):
        return self.db["auto_reactions"] if self.db is not None else None

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild or self.db is None:
            return

        msg_content = message.content.lower().strip()

        # Check Auto Reaction
        rec_row = await self.reactions_col.find_one({
            "guild_id": message.guild.id,
            "trigger_text": msg_content
        })
        if rec_row and "emoji" in rec_row:
            try:
                await message.add_reaction(rec_row["emoji"])
            except Exception:
                pass

        # Check Auto Response
        res_row = await self.responses_col.find_one({
            "guild_id": message.guild.id,
            "trigger_text": msg_content
        })
        if res_row and "response_text" in res_row:
            try:
                await message.channel.send(res_row["response_text"])
            except Exception:
                pass

    @commands.command(name="autoadd")
    async def auto_add(self, ctx, *, content: str):
        if self.responses_col is None:
            return await ctx.send("❌ Database connection error!")

        if "|" not in content:
            return await ctx.send("❌ Usage: `!autoadd trigger | response`")
        
        trigger, response = [item.strip() for item in content.split("|", 1)]
        
        await self.responses_col.update_one(
            {"guild_id": ctx.guild.id, "trigger_text": trigger.lower()},
            {"$set": {"guild_id": ctx.guild.id, "trigger_text": trigger.lower(), "response_text": response}},
            upsert=True
        )
        await ctx.send(f"✅ Set Auto-Response for `{trigger}`")

async def setup(bot):
    await bot.add_cog(AutoResponder(bot))
    

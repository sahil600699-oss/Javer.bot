import sqlite3
import discord
from discord.ext import commands

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.init_db()

    def init_db(self):
        with sqlite3.connect("welcome_config.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS welcome_settings (
                    guild_id INTEGER PRIMARY KEY, channel_id INTEGER, description TEXT, image_url TEXT
                )
            """)
            conn.commit()

    @commands.group(name="welcome", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def welcome(self, ctx):
        await ctx.send("Use `!welcome setup #channel` or `!welcome test`")

    @welcome.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup_cmd(self, ctx, channel: discord.TextChannel):
        with sqlite3.connect("welcome_config.db") as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT OR REPLACE INTO welcome_settings (guild_id, channel_id) VALUES (?, ?)", (ctx.guild.id, channel.id))
            conn.commit()
        await ctx.send(f"✅ Welcome channel set to {channel.mention}")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        with sqlite3.connect("welcome_config.db") as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT channel_id, description, image_url FROM welcome_settings WHERE guild_id = ?", (member.guild.id,))
            row = cursor.fetchone()

        if row and row[0]:
            channel = member.guild.get_channel(row[0])
            if channel:
                desc = row[1] or f"Welcome {member.mention} to **{member.guild.name}**!"
                desc = desc.replace("{user}", member.mention).replace("{server}", member.guild.name)
                embed = discord.Embed(title="✦ WELCOME ✦", description=desc, color=discord.Color.blue())
                embed.set_thumbnail(url=member.display_avatar.url)
                if row[2]: embed.set_image(url=row[2])
                await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Welcome(bot))
    

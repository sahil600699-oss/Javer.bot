import discord
from discord.ext import commands
from datetime import datetime

class AFK(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.init_db()

    def init_db(self):
        cursor = self.db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS afk_users (
                guild_id INTEGER,
                user_id INTEGER,
                reason TEXT,
                afk_since DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (guild_id, user_id)
            )
        ''')
        self.db.commit()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        if message.content.lower().startswith("!afk"):
            return

        cursor = self.db.cursor()

        cursor.execute(
            "SELECT reason, afk_since FROM afk_users WHERE guild_id = ? AND user_id = ?",
            (message.guild.id, message.author.id)
        )
        row = cursor.fetchone()

        if row:
            cursor.execute(
                "DELETE FROM afk_users WHERE guild_id = ? AND user_id = ?",
                (message.guild.id, message.author.id)
            )
            self.db.commit()
            
            embed = discord.Embed(
                description=f"👋 Welcome back {message.author.mention}! Aapka **AFK** status remove kar diya gaya hai.",
                color=discord.Color.green()
            )
            await message.channel.send(embed=embed)

        if message.mentions:
            for member in message.mentions:
                if member.id == message.author.id:
                    continue

                cursor.execute(
                    "SELECT reason, afk_since FROM afk_users WHERE guild_id = ? AND user_id = ?",
                    (message.guild.id, member.id)
                )
                afk_data = cursor.fetchone()

                if afk_data:
                    reason, afk_since_str = afk_data
                    
                    try:
                        afk_since = datetime.strptime(afk_since_str, "%Y-%m-%d %H:%M:%S")
                        duration = datetime.utcnow() - afk_since
                        minutes, seconds = divmod(int(duration.total_seconds()), 60)
                        hours, minutes = divmod(minutes, 60)
                        
                        if hours > 0:
                            time_text = f"{hours}h {minutes}m ago"
                        elif minutes > 0:
                            time_text = f"{minutes}m ago"
                        else:
                            time_text = "just now"
                    except Exception:
                        time_text = "recently"

                    embed = discord.Embed(
                        title="⚠️ Member is AFK!",
                        description=f"**{member.display_name}** abhi Away From Keyboard hain.\n\n"
                                    f"📝 **Reason:** {reason}\n"
                                    f"⏰ **AFK Since:** {time_text}",
                        color=discord.Color.gold()
                    )
                    await message.channel.send(embed=embed)
                    break

    @commands.group(name="afk", invoke_without_command=True)
    async def afk_group(self, ctx, *, reason: str = "AFK"):
        cursor = self.db.cursor()

        current_time_str = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute('''
            INSERT OR REPLACE INTO afk_users (guild_id, user_id, reason, afk_since) 
            VALUES (?, ?, ?, ?)
        ''', (ctx.guild.id, ctx.author.id, reason, current_time_str))

        self.db.commit()

        embed = discord.Embed(
            description=f"💤 {ctx.author.mention} ab **AFK** hain.\n📝 **Reason:** {reason}",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @afk_group.command(name="help")
    async def afk_help(self, ctx):
        embed = discord.Embed(
            title="💤 AFK System — Help & Commands",
            description="Is system se aap server me apna Away Status set kar sakte hain.",
            color=discord.Color.blue()
        )
        embed.add_field(name="🔹 Set AFK Status", value="• `!afk [reason]`\n*Example:* `!afk Khana khane ja raha hu`", inline=False)
        embed.add_field(name="🔹 Auto Un-AFK", value="Aap `!afk` set karne ke baad jab DUSRA message send karenge tabhi AFK status automatically remove hoga.", inline=False)
        embed.add_field(name="🔹 Mention Alert", value="Koi aapko tag karega toh bot unhe bata dega ki aap AFK hain aur kitni der se hain.", inline=False)
        embed.set_footer(text="AFK System Active")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AFK(bot))
    

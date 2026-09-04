import discord
from discord.ext import commands

class AutoSend(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Memory storage: {(guild_id, user_id): {"amount": int, "message": str}}
        self.active_tasks = {}

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        key = (message.guild.id, message.author.id)

        if key in self.active_tasks:
            task = self.active_tasks[key]
            
            try:
                await message.channel.send(f"{message.author.mention} {task['message']}")
            except Exception as e:
                print(f"AutoSend Error: {e}")

            task['amount'] -= 1

            if task['amount'] <= 0:
                del self.active_tasks[key]
                await message.channel.send(f"✅ {message.author.mention} ke liye AutoSend process complete ho gaya hai!")

    @commands.group(name="autosend", invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    async def autosend_group(self, ctx, member: discord.Member = None, amount: int = None, *, custom_message: str = None):
        if not member or not amount or not custom_message:
            await ctx.send("❓ Format: `!autosend @user [amount] [message]`\nHelp: `!autosend help`")
            return

        if amount <= 0:
            await ctx.send("❌ Amount positive number hona chahiye!")
            return

        key = (ctx.guild.id, member.id)
        self.active_tasks[key] = {
            "amount": amount,
            "message": custom_message
        }

        embed = discord.Embed(
            title="🚀 AutoSend Activated!",
            description=f"**Target:** {member.mention}\n**Count:** `{amount}`\n**Message:** {custom_message}",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @autosend_group.command(name="help")
    async def autosend_help(self, ctx):
        embed = discord.Embed(title="🤖 AutoSend Help", color=discord.Color.blue())
        embed.add_field(name="Set", value="`!autosend @user [amount] [message]`", inline=False)
        embed.add_field(name="Stop", value="`!autosendoff @user`", inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="autosendoff")
    @commands.has_permissions(manage_messages=True)
    async def autosend_off(self, ctx, member: discord.Member):
        key = (ctx.guild.id, member.id)
        if key in self.active_tasks:
            del self.active_tasks[key]
            await ctx.send(f"🛑 **{member.display_name}** ke liye AutoSend turn off kar diya gaya hai.")
        else:
            await ctx.send(f"⚠️ **{member.display_name}** ke liye koi Active AutoSend nahi hai.")

async def setup(bot):
    await bot.add_cog(AutoSend(bot))
            

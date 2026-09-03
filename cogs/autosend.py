import discord
from discord.ext import commands

class AutoSend(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
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
                await message.channel.send(f"✅ {message.author.mention} ke liye AutoSend process complete aur auto-off ho gaya hai!")

    @commands.group(name="autosend", invoke_without_command=True)
    @commands.has_permissions(manage_messages=True)
    async def autosend_group(self, ctx, member: discord.Member = None, amount: int = None, *, custom_message: str = None):
        if not member or not amount or not custom_message:
            await ctx.send("❓ Incorrect Usage! Proper Format: `!autosend @user [amount] [message]`\nHelp ke liye type karein: `!autosend help`")
            return

        if amount <= 0:
            await ctx.send("❌ Amount 1 ya usse zyada (positive number) honi chahiye!")
            return

        key = (ctx.guild.id, member.id)
        self.active_tasks[key] = {
            "amount": amount,
            "message": custom_message
        }

        embed = discord.Embed(
            title="🚀 AutoSend Activated!",
            description=f"**Target Member:** {member.mention}\n**Total Target Count:** `{amount}` Messages\n**Auto Message:** {custom_message}",
            color=discord.Color.green()
        )
        embed.set_footer(text=f"Turn off karne ke liye '!autosendoff {member.display_name}' type karein.")
        await ctx.send(embed=embed)

    @autosend_group.command(name="help")
    async def autosend_help(self, ctx):
        embed = discord.Embed(
            title="🤖 AutoSend System — Guide & Commands",
            description="Is system se kisi specific member par automated continuous message cycle set kar sakte hain.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📥 Set AutoSend",
            value="• `!autosend @user [amount] [message]`\n*Example:* `!autosend @Rahul 5 Suno bhai!`\nTarget member jitne baar msg karega, bot unhe counter khatam hone tak set message bhejta rahega.",
            inline=False
        )
        embed.add_field(
            name="🛑 Stop AutoSend",
            value="• `!autosendoff @user`\nTarget member ke active auto-send cycle ko force stop kar deta hai.",
            inline=False
        )
        embed.add_field(
            name="❓ Help Guide",
            value="• `!autosend help` — Open this guide.",
            inline=False
        )
        embed.set_footer(text="Requires 'Manage Messages' permission.")
        await ctx.send(embed=embed)

    @commands.command(name="autosendoff")
    @commands.has_permissions(manage_messages=True)
    async def autosend_off(self, ctx, member: discord.Member):
        key = (ctx.guild.id, member.id)

        if key in self.active_tasks:
            del self.active_tasks[key]
            embed = discord.Embed(
                title="🛑 AutoSend Stopped!",
                description=f"**{member.mention}** ke liye AutoSend process turn off kar diya gaya hai.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"⚠️ **{member.display_name}** ke liye koi Active AutoSend process nahi chal raha.")


async def setup(bot):
    await bot.add_cog(AutoSend(bot))
    

import discord
from discord.ext import commands

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @property
    def welcome_col(self):
        if self.bot.async_db is not None:
            return self.bot.async_db["welcome_settings"]
        return None

    @commands.group(name="welcome", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def welcome(self, ctx):
        embed = discord.Embed(
            title="👋 Welcome System Setup",
            description=(
                "`!welcome setup #channel` - Welcome channel set karein\n"
                "`!welcome msg <text>` - Custom message set karein (`{user}`, `{server}`, `{count}`)\n"
                "`!welcome image <url>` - Embed Image set karein\n"
                "`!welcome test` - Welcome message test karein\n"
                "`!welcome reset` - Setup remove karein"
            ),
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @welcome.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup_cmd(self, ctx, channel: discord.TextChannel):
        if self.welcome_col is None:
            return await ctx.send("❌ Database connection error!")

        await self.welcome_col.update_one(
            {"guild_id": ctx.guild.id},
            {"$set": {"guild_id": ctx.guild.id, "channel_id": channel.id}},
            upsert=True
        )
        await ctx.send(f"✅ Welcome channel successfully set to {channel.mention}")

    @welcome.command(name="msg")
    @commands.has_permissions(administrator=True)
    async def set_msg(self, ctx, *, message: str):
        if self.welcome_col is None:
            return await ctx.send("❌ Database connection error!")

        await self.welcome_col.update_one(
            {"guild_id": ctx.guild.id},
            {"$set": {"description": message}},
            upsert=True
        )
        await ctx.send(f"✅ Custom Welcome Message Saved:\n> {message}")

    @welcome.command(name="image")
    @commands.has_permissions(administrator=True)
    async def set_image(self, ctx, url: str):
        if self.welcome_col is None:
            return await ctx.send("❌ Database connection error!")

        await self.welcome_col.update_one(
            {"guild_id": ctx.guild.id},
            {"$set": {"image_url": url}},
            upsert=True
        )
        await ctx.send("✅ Welcome Image URL saved successfully!")

    @welcome.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def reset_welcome(self, ctx):
        if self.welcome_col is None:
            return await ctx.send("❌ Database connection error!")

        result = await self.welcome_col.delete_one({"guild_id": ctx.guild.id})
        if result.deleted_count > 0:
            await ctx.send("🗑️ Welcome settings successfully deleted!")
        else:
            await ctx.send("⚠️ No active welcome setup found to delete.")

    @welcome.command(name="test")
    @commands.has_permissions(administrator=True)
    async def test_cmd(self, ctx):
        if self.welcome_col is None:
            return await ctx.send("❌ Database connection error!")

        data = await self.welcome_col.find_one({"guild_id": ctx.guild.id})
        if not data or "channel_id" not in data:
            return await ctx.send("❌ Channel set nahi hai! Pehle `!welcome setup #channel` run karein.")

        channel = ctx.guild.get_channel(int(data["channel_id"]))
        if not channel:
            return await ctx.send("❌ Saved channel server par nahi mila!")

        await self.send_welcome_embed(ctx.author, channel, data)
        await ctx.send("✅ Test welcome message sent!")

    async def send_welcome_embed(self, member, channel, data):
        raw_desc = data.get("description") or "Welcome {user} to **{server}**!\nTotal Members: #{count}"
        
        formatted_desc = raw_desc.replace("{user}", member.mention)\
                                 .replace("{server}", member.guild.name)\
                                 .replace("{count}", str(member.guild.member_count))

        embed = discord.Embed(
            title="✦ WELCOME ✦",
            description=formatted_desc,
            color=discord.Color.blue()
        )
        
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)

        if data.get("image_url"):
            embed.set_image(url=data["image_url"])

        await channel.send(content=member.mention, embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if self.welcome_col is None:
            return

        data = await self.welcome_col.find_one({"guild_id": member.guild.id})
        if not data or "channel_id" not in data:
            return

        channel = member.guild.get_channel(int(data["channel_id"]))
        if channel:
            try:
                await self.send_welcome_embed(member, channel, data)
            except Exception as e:
                print(f"Welcome Event Error: {e}")

async def setup(bot):
    await bot.add_cog(Welcome(bot))
    

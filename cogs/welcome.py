import discord
from discord.ext import commands
from motor.motor_asyncio import AsyncIOMotorClient

# MongoDB Atlas URI yahan daalein
MONGO_URI = "mongodb+srv://<username>:<password>@cluster0.xxx.mongodb.net/?retryWrites=true&w=majority"

mongo_client = AsyncIOMotorClient(MONGO_URI)
db = mongo_client["discord_bot"]
welcome_col = db["welcome_settings"]

class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="welcome", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def welcome(self, ctx):
        embed = discord.Embed(
            title="👋 Welcome System",
            description=(
                "`!welcome setup #channel` - Welcome channel set karein\n"
                "`!welcome msg <text>` - Custom message set karein\n"
                "`!welcome image <url>` - Background image set karein\n"
                "`!welcome test` - Welcome embed test karein\n"
                "`!welcome reset` - Welcome system delete karein"
            ),
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @welcome.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup_cmd(self, ctx, channel: discord.TextChannel):
        await welcome_col.update_one(
            {"guild_id": ctx.guild.id},
            {"$set": {"channel_id": channel.id}},
            upsert=True
        )
        await ctx.send(f"✅ Welcome channel set to {channel.mention}")

    @welcome.command(name="msg")
    @commands.has_permissions(administrator=True)
    async def set_msg(self, ctx, *, message: str):
        await welcome_col.update_one(
            {"guild_id": ctx.guild.id},
            {"$set": {"description": message}},
            upsert=True
        )
        await ctx.send(f"✅ Welcome Message saved!\n> {message}")

    @welcome.command(name="image")
    @commands.has_permissions(administrator=True)
    async def set_image(self, ctx, url: str):
        await welcome_col.update_one(
            {"guild_id": ctx.guild.id},
            {"$set": {"image_url": url}},
            upsert=True
        )
        await ctx.send("✅ Image URL saved!")

    @welcome.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def reset_cmd(self, ctx):
        await welcome_col.delete_one({"guild_id": ctx.guild.id})
        await ctx.send("🗑️ Welcome settings reset successfully!")

    @welcome.command(name="test")
    @commands.has_permissions(administrator=True)
    async def test_cmd(self, ctx):
        data = await welcome_col.find_one({"guild_id": ctx.guild.id})
        if not data or "channel_id" not in data:
            return await ctx.send("❌ Channel set nahi hai! Pehle `!welcome setup #channel` karein.")

        channel = ctx.guild.get_channel(data["channel_id"])
        if channel:
            await self.send_welcome_embed(ctx.author, channel, data)
            await ctx.send("✅ Test message sent!")

    async def send_welcome_embed(self, member, channel, data):
        raw_desc = data.get("description") or "Welcome {user} to **{server}**!"
        formatted_desc = raw_desc.replace("{user}", member.mention).replace("{server}", member.guild.name)

        embed = discord.Embed(
            title="✦ WELCOME ✦",
            description=formatted_desc,
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        if data.get("image_url"):
            embed.set_image(url=data["image_url"])

        await channel.send(content=member.mention, embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        data = await welcome_col.find_one({"guild_id": member.guild.id})
        if data and "channel_id" in data:
            channel = member.guild.get_channel(data["channel_id"])
            if channel:
                await self.send_welcome_embed(member, channel, data)

async def setup(bot):
    await bot.add_cog(Welcome(bot))
    

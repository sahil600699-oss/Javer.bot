from datetime import datetime
import discord
from discord.ext import commands

# ----------------- UI Select Menu Handler -----------------
class DirectChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, cog, guild_id):
        self.cog = cog
        self.guild_id = guild_id
        super().__init__(
            channel_types=[discord.ChannelType.text], 
            placeholder="Select Welcome Text Channel..."
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        channel = self.values[0]
        
        cursor = self.cog.db.cursor()
        cursor.execute("""
            INSERT INTO welcome_settings (guild_id, channel_id, show_member_count, show_boost_count, show_account_age)
            VALUES (?, ?, 1, 1, 1)
            ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id
        """, (self.guild_id, channel.id))
        self.cog.db.commit()

        embed = discord.Embed(
            title="✅ Welcome Channel Configured!",
            description=(
                f"Welcome messages will now be sent to {channel.mention}.\n\n"
                "**Optional Edits & Customization Commands:**\n"
                "• `!welcome desc <text>` - Set custom message\n"
                "• `!welcome image <URL>` - Set banner image (`none` to remove)\n"
                "• `!welcome showmembers <on/off>` - Toggle Member Count\n"
                "• `!welcome showboosts <on/off>` - Toggle Boost Count\n"
                "• `!welcome showaccount <on/off>` - Toggle Account Creation Date\n"
                "• `!welcome test` - Test welcome message\n"
                "• `!welcome disable` - Turn off system"
            ),
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


class DirectChannelView(discord.ui.View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=180)
        self.add_item(DirectChannelSelect(cog, guild_id))


# ----------------- Main Cog Class -----------------
class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.init_db()

    def init_db(self):
        cursor = self.db.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS welcome_settings (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER,
                description TEXT DEFAULT NULL,
                image_url TEXT DEFAULT NULL,
                show_member_count INTEGER DEFAULT 1,
                show_boost_count INTEGER DEFAULT 1,
                show_account_age INTEGER DEFAULT 1
            )
        """)
        
        try:
            cursor.execute("ALTER TABLE welcome_settings ADD COLUMN show_account_age INTEGER DEFAULT 1")
        except Exception:
            pass 
            
        self.db.commit()

    def get_settings(self, guild_id):
        cursor = self.db.cursor()
        cursor.execute("""
            SELECT channel_id, description, image_url, show_member_count, show_boost_count, show_account_age 
            FROM welcome_settings WHERE guild_id = ?
        """, (guild_id,))
        data = cursor.fetchone()
        return data

    def update_setting(self, guild_id, column, value):
        cursor = self.db.cursor()
        cursor.execute("""
            INSERT INTO welcome_settings (guild_id, show_member_count, show_boost_count, show_account_age)
            VALUES (?, 1, 1, 1)
            ON CONFLICT(guild_id) DO NOTHING
        """, (guild_id,))
        cursor.execute(f"UPDATE welcome_settings SET {column} = ? WHERE guild_id = ?", (value, guild_id))
        self.db.commit()

    @commands.group(name="welcome", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def welcome(self, ctx):
        await ctx.invoke(self.welcome_help)

    @welcome.command(name="help")
    @commands.has_permissions(administrator=True)
    async def welcome_help(self, ctx):
        embed = discord.Embed(
            title="⚙️ Welcome System Commands & Help",
            description="Sabhi welcome setup aur customization commands ki list:",
            color=discord.Color.blurple()
        )
        embed.add_field(
            name="🛠️ Setup Commands",
            value=(
                "• `!welcome setup` - Dropdown menu se channel select karein\n"
                "• `!welcome setup #channel` - Direct channel mention karke set karein\n"
                "• `!welcome channel #channel` - Channel update karne ke liye"
            ),
            inline=False
        )
        embed.add_field(
            name="🎨 Customization Commands",
            value=(
                "• `!welcome desc <text>` - Custom description text (`{user}`, `{server}`, `{count}`)\n"
                "• `!welcome image <URL>` - Banner image URL (`none` to remove)\n"
                "• `!welcome showmembers <on/off>` - Member count show/hide\n"
                "• `!welcome showboosts <on/off>` - Boost count show/hide\n"
                "• `!welcome showaccount <on/off>` - Account creation date show/hide"
            ),
            inline=False
        )
        embed.add_field(
            name="🧪 Utility Commands",
            value=(
                "• `!welcome test` - Test welcome embed in channel\n"
                "• `!welcome disable` - Disable welcome system & clear data"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @welcome.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def setup_cmd(self, ctx, channel: discord.TextChannel = None):
        if channel:
            self.update_setting(ctx.guild.id, "channel_id", channel.id)
            embed = discord.Embed(
                title="✅ Welcome Channel Configured!",
                description=(
                    f"Welcome channel has been set to {channel.mention}.\n\n"
                    "**Available Edits:**\n"
                    "• `!welcome desc <text>` - Edit custom description\n"
                    "• `!welcome image <URL>` - Add/Remove banner\n"
                    "• `!welcome showmembers <on/off>` - Toggle Member Count\n"
                    "• `!welcome showboosts <on/off>` - Toggle Boost Count\n"
                    "• `!welcome showaccount <on/off>` - Toggle Account Creation Date\n"
                    "• `!welcome test` - Send test message"
                ),
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
        else:
            view = DirectChannelView(self, ctx.guild.id)
            embed = discord.Embed(
                title="📢 Select Welcome Channel",
                description="Neeche dropdown menu se channel select karein jahan welcome messages bhejne hain:",
                color=discord.Color.blurple()
            )
            await ctx.send(embed=embed, view=view)

    @welcome.command(name="channel")
    @commands.has_permissions(administrator=True)
    async def set_channel(self, ctx, channel: discord.TextChannel):
        self.update_setting(ctx.guild.id, "channel_id", channel.id)
        await ctx.send(f"✅ Welcome channel updated to {channel.mention}")

    @welcome.command(name="desc")
    @commands.has_permissions(administrator=True)
    async def set_desc(self, ctx, *, text: str):
        self.update_setting(ctx.guild.id, "description", text)
        await ctx.send("✅ Custom description updated successfully!")

    @welcome.command(name="image")
    @commands.has_permissions(administrator=True)
    async def set_image(self, ctx, url: str):
        image_val = None if url.lower() == "none" else url
        self.update_setting(ctx.guild.id, "image_url", image_val)
        await ctx.send("✅ Custom image/banner updated successfully!")

    @welcome.command(name="showmembers")
    @commands.has_permissions(administrator=True)
    async def toggle_members(self, ctx, status: str):
        val = 1 if status.lower() in ["on", "enable", "true", "yes"] else 0
        self.update_setting(ctx.guild.id, "show_member_count", val)
        await ctx.send(f"✅ Member Count visibility set to: **{'ON' if val == 1 else 'OFF'}**")

    @welcome.command(name="showboosts")
    @commands.has_permissions(administrator=True)
    async def toggle_boosts(self, ctx, status: str):
        val = 1 if status.lower() in ["on", "enable", "true", "yes"] else 0
        self.update_setting(ctx.guild.id, "show_boost_count", val)
        await ctx.send(f"✅ Boost Count visibility set to: **{'ON' if val == 1 else 'OFF'}**")

    @welcome.command(name="showaccount")
    @commands.has_permissions(administrator=True)
    async def toggle_account_age(self, ctx, status: str):
        val = 1 if status.lower() in ["on", "enable", "true", "yes"] else 0
        self.update_setting(ctx.guild.id, "show_account_age", val)
        await ctx.send(f"✅ Account Created Date visibility set to: **{'ON' if val == 1 else 'OFF'}**")

    @welcome.command(name="disable")
    @commands.has_permissions(administrator=True)
    async def disable_welcome(self, ctx):
        cursor = self.db.cursor()
        cursor.execute("DELETE FROM welcome_settings WHERE guild_id = ?", (ctx.guild.id,))
        self.db.commit()
        await ctx.send("❌ Welcome system completely disabled.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        settings = self.get_settings(guild.id)

        if settings and settings[0]:
            channel_id, custom_desc, image_url, show_members, show_boosts, show_account = settings
            channel = guild.get_channel(channel_id)

            if channel:
                show_members = 1 if show_members is None else show_members
                show_boosts = 1 if show_boosts is None else show_boosts
                show_account = 1 if show_account is None else show_account

                if custom_desc:
                    desc_body = custom_desc.replace("{user}", member.mention).replace("{server}", guild.name).replace("{count}", str(guild.member_count))
                else:
                    desc_body = (
                        f"Hey {member.mention}, welcome to **{guild.name}**! 🎉\n\n"
                        f"We are super thrilled to have you here! Kick back, relax, enjoy gaming, "
                        f"and feel free to hang out with the community. 🎮✨"
                    )

                if show_members == 1:
                    desc_body += f"\n\n👥 **Member Count:** #{guild.member_count}"
                if show_boosts == 1:
                    desc_body += f"\n🚀 **Server Boosts:** {guild.premium_subscription_count}"
                if show_account == 1:
                    desc_body += f"\n📅 **Account Created:** <t:{int(member.created_at.timestamp())}:R>"

                embed = discord.Embed(
                    title="✦ WELCOME TO THE SERVER ✦",
                    description=desc_body,
                    color=discord.Color.from_rgb(114, 137, 218),
                    timestamp=datetime.utcnow()
                )

                embed.set_thumbnail(url=member.display_avatar.url)

                if image_url:
                    embed.set_image(url=image_url)

                if guild.icon:
                    embed.set_author(name=guild.name, icon_url=guild.icon.url)
                else:
                    embed.set_author(name=guild.name)

                embed.set_footer(text=f"User ID: {member.id}")

                await channel.send(content=f"Welcome {member.mention}!", embed=embed)

    @welcome.command(name="test")
    @commands.has_permissions(administrator=True)
    async def test_welcome(self, ctx):
        settings = self.get_settings(ctx.guild.id)
        if not settings or not settings[0]:
            return await ctx.send("❌ Pehle `!welcome setup` karke channel select karein!")

        await self.on_member_join(ctx.author)
        await ctx.send("✅ Test welcome message sent!")

async def setup(bot):
    await bot.add_cog(Welcome(bot))
                

import discord
from discord.ext import commands
from datetime import datetime, timedelta

# --- INTERACTIVE DROPDOWN MENU ---
class MsgCommandSelect(discord.ui.Select):
    def __init__(self, bot, target_user=None):
        self.bot = bot
        self.target_user = target_user
        options = [
            discord.SelectOption(label="24h Top Members", value="msg_top", description="Pichle 24 hours ke top 20 members", emoji="🏆"),
            discord.SelectOption(label="Weekly Top Members", value="msgw_top", description="Pichle 7 days ke top members", emoji="⭐"),
            discord.SelectOption(label="User 24h Stats", value="msg_user", description="Selected user ki 24h channel breakdown", emoji="📊"),
            discord.SelectOption(label="User Weekly Combined", value="msgw_user", description="User ke 24h + 7 Days total stats", emoji="📈"),
            discord.SelectOption(label="Message Help Guide", value="msg_help", description="All message tracking commands info", emoji="❓")
        ]
        super().__init__(placeholder="⚡ Select Command to Execute...", min_values=1, max_values=1, options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        cog = self.bot.get_cog("MsgTracker")
        if not cog:
            await interaction.followup.send("❌ Error: MsgTracker Cog active nahi hai!", ephemeral=True)
            return

        user = self.target_user or interaction.user
        val = self.values[0]

        if val == "msg_top":
            embed, view = await cog.get_msg_top_data(interaction.guild, interaction.user)
            await interaction.followup.send(embed=embed, view=view)
        elif val == "msgw_top":
            embed, view = await cog.get_msgw_top_data(interaction.guild, interaction.user)
            await interaction.followup.send(embed=embed, view=view)
        elif val == "msg_user":
            embed, view = await cog.get_msg_user_data(interaction.guild, user)
            await interaction.followup.send(embed=embed, view=view)
        elif val == "msgw_user":
            embed, view = await cog.get_msgw_user_data(interaction.guild, user)
            await interaction.followup.send(embed=embed, view=view)
        elif val == "msg_help":
            embed, view = await cog.get_msg_help_data(interaction.user)
            await interaction.followup.send(embed=embed, view=view)


# --- PAGINATION & DROPDOWN COMBINED VIEW ---
class MsgTopPaginationView(discord.ui.View):
    def __init__(self, bot, author, rows, guild):
        super().__init__(timeout=180)
        self.bot = bot
        self.author = author
        self.rows = rows
        self.guild = guild
        self.current_page = 1
        
        self.add_item(MsgCommandSelect(bot))
        self.update_buttons()

    def update_buttons(self):
        self.prev_btn.disabled = (self.current_page == 1)
        self.next_btn.disabled = (self.current_page == 2 or len(self.rows) <= 10)

    def create_embed(self):
        embed = discord.Embed(
            title="TOP 10 CHAT MEMBERS",
            color=discord.Color.gold()
        )

        if self.current_page == 1:
            page_rows = self.rows[:10]
            start_rank = 1
        else:
            page_rows = self.rows[10:20]
            start_rank = 11

        lines = []
        for idx, (user_id, count) in enumerate(page_rows, start_rank):
            member = self.guild.get_member(user_id)
            name = member.display_name if member else f"User `{user_id}`"
            lines.append(f"**{idx}.** `{name[:15]}`: **{count}** msgs")

        page_text = "\n".join(lines) if lines else "No Data"
        embed.description = page_text
        embed.set_footer(text=f"Page {self.current_page}/2 • Requested by {self.author.display_name}", icon_url=self.author.display_avatar.url)

        return embed

    @discord.ui.button(label="◀️ Prev", style=discord.ButtonStyle.primary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌ Yeh action aapke liye nahi hai!", ephemeral=True)
        
        self.current_page = 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.primary, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author.id:
            return await interaction.response.send_message("❌ Yeh action aapke liye nahi hai!", ephemeral=True)
        
        self.current_page = 2
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)


class MsgDropdownView(discord.ui.View):
    def __init__(self, bot, author, target_user=None):
        super().__init__(timeout=180)
        self.add_item(MsgCommandSelect(bot, target_user))


# --- MAIN COG CLASS ---
class MsgTracker(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.init_db()

    def init_db(self):
        cursor = self.db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS message_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id INTEGER,
                channel_id INTEGER,
                user_id INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.db.commit()

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        cursor = self.db.cursor()
        cursor.execute(
            "INSERT INTO message_logs (guild_id, channel_id, user_id) VALUES (?, ?, ?)",
            (message.guild.id, message.channel.id, message.author.id)
        )
        self.db.commit()

    async def get_msg_top_data(self, guild, author):
        time_24h_ago = datetime.utcnow() - timedelta(hours=24)
        
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT user_id, COUNT(*) as msg_count 
            FROM message_logs 
            WHERE guild_id = ? AND timestamp >= ? 
            GROUP BY user_id 
            ORDER BY msg_count DESC 
            LIMIT 20
        ''', (guild.id, time_24h_ago))
        rows = cursor.fetchall()

        if not rows:
            embed = discord.Embed(
                title="TOP 10 CHAT MEMBERS",
                description="⚠️ Pichle 24 ghante me koi message data available nahi hai.",
                color=discord.Color.gold()
            )
            return embed, MsgDropdownView(self.bot, author)

        view = MsgTopPaginationView(self.bot, author, rows, guild)
        embed = view.create_embed()

        return embed, view

    async def get_msgw_top_data(self, guild, author):
        time_7d_ago = datetime.utcnow() - timedelta(days=7)
        
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT user_id, COUNT(*) as msg_count 
            FROM message_logs 
            WHERE guild_id = ? AND timestamp >= ? 
            GROUP BY user_id 
            ORDER BY msg_count DESC 
            LIMIT 10
        ''', (guild.id, time_7d_ago))
        rows = cursor.fetchall()

        embed = discord.Embed(
            title="⭐ Top Members Leaderboard (Weekly / 7 Days)",
            color=discord.Color.purple()
        )

        if not rows:
            embed.description = "⚠️ Is week koi message record nahi mila."
        else:
            description_lines = []
            for idx, (user_id, count) in enumerate(rows, 1):
                member = guild.get_member(user_id)
                name = member.mention if member else f"User `{user_id}`"
                description_lines.append(f"**#{idx}** {name} — **{count}** Messages")
            embed.description = "\n".join(description_lines)

        embed.set_footer(text=f"Requested by {author.display_name}", icon_url=author.display_avatar.url)
        return embed, MsgDropdownView(self.bot, author)

    async def get_msg_user_data(self, guild, target_user):
        time_24h_ago = datetime.utcnow() - timedelta(hours=24)
        
        cursor = self.db.cursor()
        cursor.execute('''
            SELECT channel_id, COUNT(*) as msg_count 
            FROM message_logs 
            WHERE guild_id = ? AND user_id = ? AND timestamp >= ? 
            GROUP BY channel_id 
            ORDER BY msg_count DESC
        ''', (guild.id, target_user.id, time_24h_ago))
        rows = cursor.fetchall()

        embed = discord.Embed(
            title=f"📊 24h Message Breakdown — {target_user.display_name}",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)

        total_24h = sum(count for _, count in rows)
        
        if not rows:
            embed.description = "⚠️ Pichle 24 ghante me is user ne ek bhi message nahi bheja hai."
        else:
            channel_breakdown = []
            for ch_id, count in rows:
                ch = guild.get_channel(ch_id)
                ch_name = ch.mention if ch else f"#deleted-channel"
                channel_breakdown.append(f"• {ch_name}: **{count}** msgs")

            embed.description = "**Channel Activity List:**\n" + "\n".join(channel_breakdown)

        embed.add_field(name="📈 Total 24h Messages", value=f"**{total_24h}** Messages", inline=False)
        embed.set_footer(text=f"User ID: {target_user.id}")

        return embed, MsgDropdownView(self.bot, target_user, target_user)

    async def get_msgw_user_data(self, guild, target_user):
        time_24h_ago = datetime.utcnow() - timedelta(hours=24)
        time_7d_ago = datetime.utcnow() - timedelta(days=7)

        cursor = self.db.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) FROM message_logs 
            WHERE guild_id = ? AND user_id = ? AND timestamp >= ?
        ''', (guild.id, target_user.id, time_24h_ago))
        count_24h = cursor.fetchone()[0]

        cursor.execute('''
            SELECT COUNT(*) FROM message_logs 
            WHERE guild_id = ? AND user_id = ? AND timestamp >= ?
        ''', (guild.id, target_user.id, time_7d_ago))
        count_7d = cursor.fetchone()[0]

        embed = discord.Embed(
            title=f"📈 Overview Stats — {target_user.display_name}",
            color=discord.Color.teal()
        )
        embed.set_thumbnail(url=target_user.display_avatar.url)
        embed.add_field(name="⏰ Last 24 Hours", value=f"**{count_24h}** Messages", inline=True)
        embed.add_field(name="📅 Last 7 Days (Weekly)", value=f"**{count_7d}** Messages", inline=True)
        embed.set_footer(text=f"User ID: {target_user.id}")

        return embed, MsgDropdownView(self.bot, target_user, target_user)

    async def get_msg_help_data(self, author):
        embed = discord.Embed(
            title="❓ Message Tracking System — Commands Guide",
            description="Aap neeche likhi commands type karke ya dropdown menu se select karke use kar sakte hain:",
            color=discord.Color.green()
        )
        embed.add_field(name="🔹 !msg top", value="Pichle 24 Hours ke Top 20 Active Members ki list (Page 1: 1-10 | Page 2: 11-20).", inline=False)
        embed.add_field(name="🔹 !msg @user", value="Targeted member ki 24h ki Channel-wise breakdown & Total Messages.", inline=False)
        embed.add_field(name="🔹 !msgw top", value="Pichle 7 Days (Weekly) ke Top Message senders ki Leaderboard.", inline=False)
        embed.add_field(name="🔹 !msgw @user", value="Member ke 24h aur 7 Days (Weekly) ka overall summary calculation.", inline=False)
        embed.add_field(name="🔹 !msg help", value="Ye Help Menu UI display karega.", inline=False)
        
        embed.set_footer(text="⚡ Select commands from the dropdown menu below!")
        return embed, MsgDropdownView(self.bot, author)

    @commands.group(name="msg", invoke_without_command=True)
    async def msg_group(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        embed, view = await self.get_msg_user_data(ctx.guild, target)
        await ctx.send(embed=embed, view=view)

    @msg_group.command(name="top")
    async def msg_top(self, ctx):
        embed, view = await self.get_msg_top_data(ctx.guild, ctx.author)
        await ctx.send(embed=embed, view=view)

    @msg_group.command(name="help")
    async def msg_help_cmd(self, ctx):
        embed, view = await self.get_msg_help_data(ctx.author)
        await ctx.send(embed=embed, view=view)

    @commands.group(name="msgw", invoke_without_command=True)
    async def msgw_group(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        embed, view = await self.get_msgw_user_data(ctx.guild, target)
        await ctx.send(embed=embed, view=view)

    @msgw_group.command(name="top")
    async def msgw_top(self, ctx):
        embed, view = await self.get_msgw_top_data(ctx.guild, ctx.author)
        await ctx.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(MsgTracker(bot))
            

import discord
from discord.ext import commands
import json
import os
from datetime import datetime

CONFIG_FILE = "log_channels.json"

def load_log_channels():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {}

def save_log_channels(data):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=4)

# --- INTERACTIVE SETUP UI COMPONENTS ---

class LogTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Message Logs", value="message_logs", description="Deleted & Edited Messages", emoji="💬"),
            discord.SelectOption(label="Mod Action Logs", value="mod_action_logs", description="Kick, Ban, Mute, Warn Actions", emoji="🛡️"),
            discord.SelectOption(label="Member Logs", value="member_logs", description="Member Join & Leave Updates", emoji="👥"),
            discord.SelectOption(label="VC Logs", value="vc_logs", description="Voice Channel Join/Leave & Duration", emoji="🔊"),
            discord.SelectOption(label="Invite Logs", value="invite_logs", description="Track Kisne Kis User Ko Invite Kiya", emoji="✉️")
        ]
        super().__init__(placeholder="1️⃣ Log Type Select Karein...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_log_type = self.values[0]
        await interaction.response.send_message(f"✅ Selected Log: **{self.values[0].replace('_', ' ').title()}**. Ab niche channel select karke Confirm karein!", ephemeral=True)


class ChannelSelectMenu(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(
            placeholder="2️⃣ Channel Select Karein...",
            channel_types=[discord.ChannelType.text],
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_channel = self.values[0]
        await interaction.response.send_message(f"✅ Channel Selected: {self.values[0].mention}. Ab 'Save & Setup' button dabayein!", ephemeral=True)


class SetupInteractiveView(discord.ui.View):
    def __init__(self, cog, author):
        super().__init__(timeout=120)
        self.cog = cog
        self.author = author
        self.selected_log_type = None
        self.selected_channel = None

        self.add_item(LogTypeSelect())
        self.add_item(ChannelSelectMenu())

    @discord.ui.button(label="✅ Save & Setup", style=discord.ButtonStyle.green, row=2)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("❌ Yeh menu aapke liye nahi hai!", ephemeral=True)
            return

        if not self.selected_log_type or not self.selected_channel:
            await interaction.response.send_message("⚠️ Kripya Log Type aur Channel **dono** select karein!", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        if guild_id not in self.cog.log_channels:
            self.cog.log_channels[guild_id] = {}

        # Save to Memory & File
        self.cog.log_channels[guild_id][self.selected_log_type] = self.selected_channel.id
        save_log_channels(self.cog.log_channels)

        log_name = self.selected_log_type.replace('_', ' ').title()
        embed = discord.Embed(
            title="🎉 Log Channel Successfully Set!",
            description=f"**Log Category:** {log_name}\n**Target Channel:** {self.selected_channel.mention}",
            color=discord.Color.green()
        )
        
        # Disable view items after saving
        for child in self.children:
            child.disabled = True
            
        await interaction.response.edit_message(embed=embed, view=self)
        self.stop()


# --- COG MAIN CLASS ---

class ModLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_channels = load_log_channels()
        self.vc_sessions = {}
        self.invites = {}

    def get_log_channel(self, guild_id, log_type):
        guild_str = str(guild_id)
        if guild_str in self.log_channels and log_type in self.log_channels[guild_str]:
            channel_id = self.log_channels[guild_str][log_type]
            return self.bot.get_channel(channel_id)
        return None

    async def update_invite_cache(self, guild):
        try:
            invites = await guild.invites()
            self.invites[guild.id] = {invite.code: invite.uses for invite in invites}
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self.update_invite_cache(guild)

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        await self.update_invite_cache(invite.guild)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        await self.update_invite_cache(invite.guild)

    # --- COMMANDS ---

    @commands.group(name="log", invoke_without_command=True)
    async def log_group(self, ctx):
        await ctx.send("❓ Galat command format! Easy Setup ke liye **`!log setup`** ya guide ke liye **`!log help`** type karein.")

    @log_group.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def log_interactive_setup(self, ctx):
        """Interactive Setup UI Menu"""
        view = SetupInteractiveView(self, ctx.author)
        embed = discord.Embed(
            title="⚙️ Interactive Log Setup Menu",
            description=(
                "Niche diye gaye Dropdowns aur Selectors ka use karke setup karein:\n\n"
                "1️⃣ **Select Log Type** (Dropdown se log category chunein)\n"
                "2️⃣ **Select Channel** (Channel selector se channel chunein)\n"
                "3️⃣ **Click 'Save & Setup'** button!"
            ),
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=view)

    @log_group.command(name="help")
    async def log_help(self, ctx):
        embed = discord.Embed(
            title="📜 Moderation & Activity Logging — Guide",
            description="Server par hone wali sabhi activities ko channels me log karein.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="⚙️ Main Setup Command",
            value="• `!log setup` — **Interactive Menu** open karega jisse bina command ke log setup hoga!",
            inline=False
        )
        embed.add_field(
            name="🔍 View Configuration",
            value="• `!log status` — Dekhein ki kaunse logs kis channel me active hain.",
            inline=False
        )
        embed.set_footer(text="Strict Audit Security • Powered by Bot")
        await ctx.send(embed=embed)

    @log_group.command(name="status")
    @commands.has_permissions(administrator=True)
    async def log_status(self, ctx):
        guild_id = str(ctx.guild.id)
        data = self.log_channels.get(guild_id, {})
        
        embed = discord.Embed(title="📊 Log Channels Status", color=discord.Color.gold())
        
        mod_ch = f"<#{data.get('mod_action_logs')}>" if data.get('mod_action_logs') else "❌ Not Set"
        msg_ch = f"<#{data.get('message_logs')}>" if data.get('message_logs') else "❌ Not Set"
        mem_ch = f"<#{data.get('member_logs')}>" if data.get('member_logs') else "❌ Not Set"
        vc_ch = f"<#{data.get('vc_logs')}>" if data.get('vc_logs') else "❌ Not Set"
        inv_ch = f"<#{data.get('invite_logs')}>" if data.get('invite_logs') else "❌ Not Set"

        embed.add_field(name="🛡️ Mod Action Logs", value=mod_ch, inline=False)
        embed.add_field(name="💬 Message Logs", value=msg_ch, inline=False)
        embed.add_field(name="👥 Member Logs", value=mem_ch, inline=False)
        embed.add_field(name="🔊 Voice (VC) Logs", value=vc_ch, inline=False)
        embed.add_field(name="✉️ Invite Logs", value=inv_ch, inline=False)
        
        await ctx.send(embed=embed)

    # --- EVENT LISTENERS ---

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not message.guild:
            return
        log_ch = self.get_log_channel(message.guild.id, "message_logs")
        if not log_ch:
            return

        embed = discord.Embed(title="🗑️ Message Deleted", color=discord.Color.red())
        embed.add_field(name="Author", value=f"{message.author.mention} ({message.author.id})", inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Content", value=message.content or "*[No Text / Attachment]*", inline=False)
        await log_ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.bot or not before.guild or before.content == after.content:
            return
        log_ch = self.get_log_channel(before.guild.id, "message_logs")
        if not log_ch:
            return

        embed = discord.Embed(title="✏️ Message Edited", color=discord.Color.orange())
        embed.add_field(name="Author", value=f"{before.author.mention} ({before.author.id})", inline=True)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Before", value=before.content or "*Empty*", inline=False)
        embed.add_field(name="After", value=after.content or "*Empty*", inline=False)
        await log_ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        
        mem_log_ch = self.get_log_channel(guild.id, "member_logs")
        if mem_log_ch:
            embed = discord.Embed(title="📥 Member Joined", color=discord.Color.green())
            embed.add_field(name="User", value=f"{member.mention} ({member.tag})", inline=True)
            embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
            embed.set_thumbnail(url=member.display_avatar.url)
            await mem_log_ch.send(embed=embed)

        inv_log_ch = self.get_log_channel(guild.id, "invite_logs")
        if not inv_log_ch:
            return

        inviter_user = None
        used_invite = None
        try:
            old_invites = self.invites.get(guild.id, {})
            new_invites = await guild.invites()

            for invite in new_invites:
                if invite.code in old_invites and invite.uses > old_invites[invite.code]:
                    inviter_user = invite.inviter
                    used_invite = invite
                    break

            self.invites[guild.id] = {inv.code: inv.uses for inv in new_invites}
        except discord.Forbidden:
            pass

        embed = discord.Embed(title="📨 Invite Log — Naya Member Joined!", color=discord.Color.teal())
        embed.add_field(name="Joined Member", value=f"{member.mention} (`{member.display_name}`)", inline=False)
        
        if inviter_user and used_invite:
            embed.add_field(name="Invited By", value=f"{inviter_user.mention} (`{inviter_user.tag}`)", inline=True)
            embed.add_field(name="Invite Code", value=f"`{used_invite.code}`", inline=True)
            embed.add_field(name="Total Uses", value=f"📊 **{used_invite.uses}** uses", inline=True)
        else:
            embed.add_field(name="Invited By", value="❓ Unknown / Custom URL / Bot Integration", inline=False)

        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"User ID: {member.id}")
        await inv_log_ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        log_ch = self.get_log_channel(member.guild.id, "member_logs")
        if not log_ch:
            return

        embed = discord.Embed(title="📤 Member Left", color=discord.Color.dark_grey())
        embed.add_field(name="User", value=f"{member.mention} ({member.tag})", inline=True)
        embed.set_thumbnail(url=member.display_avatar.url)
        await log_ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        if member.bot:
            return

        log_ch = self.get_log_channel(member.guild.id, "vc_logs")
        if not log_ch:
            return

        now = datetime.now()
        date_str = now.strftime("%d %B %Y")
        time_str = now.strftime("%I:%M:%S %p")

        if before.channel is None and after.channel is not None:
            self.vc_sessions[member.id] = now
            embed = discord.Embed(title="🔊 Joined Voice Channel", color=discord.Color.green())
            embed.add_field(name="User", value=f"{member.mention} ({member.display_name})", inline=True)
            embed.add_field(name="Channel", value=f"🔊 {after.channel.name}", inline=True)
            embed.add_field(name="Date & Time", value=f"📅 {date_str}\n⏰ {time_str}", inline=False)
            embed.set_thumbnail(url=member.display_avatar.url)
            await log_ch.send(embed=embed)

        elif before.channel is not None and after.channel is None:
            join_time = self.vc_sessions.pop(member.id, None)
            duration_text = "Unknown"
            if join_time:
                duration = now - join_time
                minutes, seconds = divmod(int(duration.total_seconds()), 60)
                hours, minutes = divmod(minutes, 60)
                duration_text = f"{hours}h {minutes}m {seconds}s"

            embed = discord.Embed(title="🔇 Left Voice Channel", color=discord.Color.red())
            embed.add_field(name="User", value=f"{member.mention} ({member.display_name})", inline=True)
            embed.add_field(name="Channel", value=f"🔇 {before.channel.name}", inline=True)
            embed.add_field(name="Total Duration", value=f"⏱️ **{duration_text}**", inline=False)
            embed.add_field(name="Leave Time", value=f"📅 {date_str}\n⏰ {time_str}", inline=False)
            embed.set_thumbnail(url=member.display_avatar.url)
            await log_ch.send(embed=embed)

        elif before.channel is not None and after.channel is not None and before.channel.id != after.channel.id:
            embed = discord.Embed(title="🔄 Switched Voice Channel", color=discord.Color.blue())
            embed.add_field(name="User", value=f"{member.mention} ({member.display_name})", inline=True)
            embed.add_field(name="From", value=f"🔊 {before.channel.name}", inline=True)
            embed.add_field(name="To", value=f"🔊 {after.channel.name}", inline=True)
            embed.add_field(name="Date & Time", value=f"📅 {date_str}\n⏰ {time_str}", inline=False)
            embed.set_thumbnail(url=member.display_avatar.url)
            await log_ch.send(embed=embed)

    async def log_mod_action(self, guild, action_type, target, moderator, reason):
        log_ch = self.get_log_channel(guild.id, "mod_action_logs")
        if not log_ch:
            return

        embed = discord.Embed(title=f"🔨 Mod Action: {action_type}", color=discord.Color.dark_red())
        embed.add_field(name="Target User", value=f"{target.mention} ({target.id})", inline=True)
        embed.add_field(name="Moderator", value=f"{moderator.mention}", inline=True)
        embed.add_field(name="Reason", value=reason or "No reason provided", inline=False)
        await log_ch.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ModLogs(bot))

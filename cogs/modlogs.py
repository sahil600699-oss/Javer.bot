import discord
from discord.ext import commands
import json, os
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

class LogTypeSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Message Logs", value="message_logs", emoji="💬"),
            discord.SelectOption(label="Mod Action Logs", value="mod_action_logs", emoji="🛡️"),
            discord.SelectOption(label="Member Logs", value="member_logs", emoji="👥"),
            discord.SelectOption(label="VC Logs", value="vc_logs", emoji="🔊"),
            discord.SelectOption(label="Invite Logs", value="invite_logs", emoji="✉️")
        ]
        super().__init__(placeholder="1️⃣ Select Log Type...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_log_type = self.values[0]
        await interaction.response.send_message(f"✅ Selected: **{self.values[0]}**", ephemeral=True)

class ChannelSelectMenu(discord.ui.ChannelSelect):
    def __init__(self):
        super().__init__(placeholder="2️⃣ Select Channel...", channel_types=[discord.ChannelType.text], min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        self.view.selected_channel = self.values[0]
        await interaction.response.send_message(f"✅ Selected: {self.values[0].mention}", ephemeral=True)

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
            return await interaction.response.send_message("❌ Not allowed!", ephemeral=True)
        if not self.selected_log_type or not self.selected_channel:
            return await interaction.response.send_message("⚠️ Select Log Type & Channel first!", ephemeral=True)

        guild_id = str(interaction.guild.id)
        if guild_id not in self.cog.log_channels:
            self.cog.log_channels[guild_id] = {}

        self.cog.log_channels[guild_id][self.selected_log_type] = self.selected_channel.id
        save_log_channels(self.cog.log_channels)

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="🎉 Log Channel Saved!", view=self)

class ModLogs(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.log_channels = load_log_channels()
        self.vc_sessions = {}

    def get_log_channel(self, guild_id, log_type):
        guild_str = str(guild_id)
        if guild_str in self.log_channels and log_type in self.log_channels[guild_str]:
            return self.bot.get_channel(self.log_channels[guild_str][log_type])
        return None

    @commands.group(name="log", invoke_without_command=True)
    async def log_group(self, ctx):
        await ctx.send("Use `!log setup` or `!log status`")

    @log_group.command(name="setup")
    @commands.has_permissions(administrator=True)
    async def log_interactive_setup(self, ctx):
        view = SetupInteractiveView(self, ctx.author)
        await ctx.send("⚙️ Select Log Options:", view=view)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.author.bot or not message.guild:
            return
        log_ch = self.get_log_channel(message.guild.id, "message_logs")
        if log_ch:
            embed = discord.Embed(title="🗑️ Message Deleted", color=discord.Color.red())
            embed.add_field(name="User", value=message.author.mention)
            embed.add_field(name="Content", value=message.content or "Attachment/Embed")
            await log_ch.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ModLogs(bot))
    

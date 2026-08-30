import discord
from discord.ext import commands

# -------------------------------------------------------------
# 1. PUBLIC HELP PAGINATION & DROPDOWN MENU
# -------------------------------------------------------------
class PublicHelpSelectMenu(discord.ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view
        options = [
            discord.SelectOption(label="1. Main Menu", value="0", description="Help System Main Overview", emoji="🏠"),
            discord.SelectOption(label="2. Moderation", value="1", description="Kick, Ban, Mute, Clear, Roles, Nickname", emoji="🛡️"),
            discord.SelectOption(label="3. VC Helper & Controls", value="2", description="Pull, Mute All, Drag, Deafen", emoji="🎙️"),
            discord.SelectOption(label="4. Voice Tracker", value="3", description="Top VC, User VC Stats, Weekly Tracking", emoji="📊"),
            discord.SelectOption(label="5. Message Tracker", value="4", description="Top Chatters, User Chat Stats, Weekly Stats", emoji="💬"),
            discord.SelectOption(label="6. Music System", value="5", description="Play, Pause, Queue, Seek, Volume, Join", emoji="🎵"),
            discord.SelectOption(label="7. Welcome Setup", value="6", description="Channel Setup, Test, Disable Welcome", emoji="🎉"),
            discord.SelectOption(label="8. Log Channels Setup", value="7", description="Interactive Log Setup, Status", emoji="⚙️"),
            discord.SelectOption(label="9. Utility Commands", value="8", description="Avatar, Banner Info", emoji="🖼️"),
            discord.SelectOption(label="10. Premium Features", value="9", description="Server Customization & Perks Info", emoji="💎"),
            discord.SelectOption(label="11. GIF & Action Fun", value="10", description="Slap, Punch, Boss GIF Commands", emoji="🎭"),
            discord.SelectOption(label="12. Among Us / Imposter", value="11", description="Imposter & Mini-Game Commands", emoji="🔪"),
        ]
        super().__init__(placeholder="📑 Select a Page to Jump Directly...", min_values=1, max_values=1, options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        page_num = int(self.values[0])
        self.parent_view.current_page = page_num
        self.parent_view.update_buttons()
        embed = self.parent_view.get_embed(page_num)
        await interaction.response.edit_message(embed=embed, view=self.parent_view)


class PublicHelpPaginationView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.current_page = 0
        self.total_pages = 12

        self.add_item(PublicHelpSelectMenu(self))
        self.update_buttons()

    def update_buttons(self):
        self.prev_btn.disabled = (self.current_page == 0)
        self.next_btn.disabled = (self.current_page == self.total_pages - 1)

    def get_embed(self, page_index: int) -> discord.Embed:
        embeds = [
            # PAGE 0: MAIN MENU
            discord.Embed(
                title="📖 MAIN HELP MENU",
                description=(
                    "**Welcome to the Server Bot Help Directory!** 🎉\n\n"
                    "Use the **Buttons** or **Dropdown Menu** below to navigate.\n\n"
                    "**📚 Available Categories:**\n"
                    "1️⃣ `Moderation` — Server Protection\n"
                    "2️⃣ `VC Helper` — Voice Channel Mass Controls\n"
                    "3️⃣ `Voice Tracker` — VC Leaderboards\n"
                    "4️⃣ `Message Tracker` — Chat Leaderboards\n"
                    "5️⃣ `Music System` — Music Player Commands\n"
                    "6️⃣ `Welcome System` — Dynamic Welcome Cards\n"
                    "7️⃣ `Log System` — Audit & Activity Logs\n"
                    "8️⃣ `Utility` — Profile & Server Commands\n"
                    "9️⃣ `Premium Features` — Special Premium Perks\n"
                    "🔟 `GIF & Fun Actions` — Expressive Roleplay Commands\n"
                    "1️⃣1️⃣ `Among Us / Imposter` — Minigames"
                ),
                color=discord.Color.gold()
            ),
            # PAGE 1: MODERATION
            discord.Embed(
                title="🛡️ MODERATION PAGE",
                description=(
                    "• `!kick @user [reason]` — Kick a member\n"
                    "• `!ban @user [reason]` — Ban a member\n"
                    "• `!clear <amount>` — Purge messages\n"
                    "• `!change nick @user <new_name>` — Change nickname\n"
                    "• `!mute @user` — Voice Mute\n"
                    "• `!def @user` — Voice Deafen\n"
                    "• `!move @user <vc_name>` — Move member\n"
                    "• `!roleg @user <role_name>` — Manage roles"
                ),
                color=discord.Color.red()
            ),
            # PAGE 2: VC HELPER
            discord.Embed(
                title="🎙️ VC HELPER PAGE",
                description=(
                    "• `!pull` — Drag members to current VC\n"
                    "• `!pull s` — Interactive VC Pull Menu\n"
                    "• `!vcm drag` — Source to Target VC Drag Menu\n"
                    "• `!vcm mute all` / `!vcm unmute all` — Mass Voice Mute/Unmute\n"
                    "• `!vcm def all` / `!vcm undef all` — Mass Voice Deafen/Undeafen\n"
                    "• `!vcm kick all` — Mass VC Disconnect"
                ),
                color=discord.Color.blue()
            ),
            # PAGE 3: VOICE TRACKER
            discord.Embed(
                title="📊 VOICE TRACKER PAGE",
                description=(
                    "• `!vc top` — Top 20 24h VC Users\n"
                    "• `!vc [@user]` — User VC Breakdown\n"
                    "• `!vcw top` — 7-Day VC Leaderboard\n"
                    "• `!vcw [@user]` — Combined Weekly Stats"
                ),
                color=discord.Color.purple()
            ),
            # PAGE 4: MESSAGE TRACKER
            discord.Embed(
                title="💬 MESSAGE TRACKER PAGE",
                description=(
                    "• `!msg top` — Top 20 24h Chatters\n"
                    "• `!msg [@user]` — User Chat Breakdown\n"
                    "• `!msgw top` — 7-Day Chat Leaderboard\n"
                    "• `!msgw [@user]` — Combined Weekly Chat Stats"
                ),
                color=discord.Color.teal()
            ),
            # PAGE 5: MUSIC
            discord.Embed(
                title="🎵 MUSIC SYSTEM PAGE",
                description=(
                    "• `!play <song/URL>` — Play music\n"
                    "• `!pause` / `!resume` — Pause/Resume Track\n"
                    "• `!skip` — Skip current song\n"
                    "• `!queue` — View queue\n"
                    "• `!stop` — Stop & clear queue\n"
                    "• `!join` / `!leave` — VC Connection"
                ),
                color=discord.Color.blurple()
            ),
            # PAGE 6: WELCOME SETUP
            discord.Embed(
                title="🎉 WELCOME SETUP PAGE",
                description=(
                    "• `!welcome channel #channel` — Set Welcome Channel\n"
                    "• `!welcome test` — Test Card\n"
                    "• `!welcome disable` — Disable System"
                ),
                color=discord.Color.green()
            ),
            # PAGE 7: LOG SYSTEM
            discord.Embed(
                title="⚙️ LOG SYSTEM PAGE",
                description=(
                    "• `!log setup` — Interactive UI Config\n"
                    "• `!log status` — Check Active Channels"
                ),
                color=discord.Color.dark_teal()
            ),
            # PAGE 8: UTILITY
            discord.Embed(
                title="🖼️ UTILITY PAGE",
                description=(
                    "• `!av [@user]` — Display User Avatar\n"
                    "• `!banner [@user]` — Display User Banner"
                ),
                color=discord.Color.blue()
            ),
            # PAGE 9: PREMIUM FEATURES (PUBLIC INFO)
            discord.Embed(
                title="💎 PREMIUM FEATURES PAGE",
                description=(
                    "**Exclusive Premium Commands:**\n\n"
                    "• `!serverpfp <URL/Attach>` — Change bot avatar for this server\n"
                    "• `!servernick <name>` — Change bot nickname for this server\n"
                    "• `!serverb <URL/Attach>` — Change bot profile banner\n\n"
                    "📌 **Note:** *In commands ko use karne ke liye Premium lene ki zaroorat padegi. Premium buy karne ke liye Bot ki Bio me diye gaye Server Link se humare Official Support Server ko Join karein!*"
                ),
                color=discord.Color.gold()
            ),
            # PAGE 10: GIF & FUN
            discord.Embed(
                title="🎭 GIF & ACTION FUN PAGE",
                description=(
                    "• `!slap @user` — Slap someone\n"
                    "• `!punch @user` — Punch someone\n"
                    "• `!boss @user` — Boss GIF\n"
                    "• `!hug @user` / `!kiss @user` — Interactive GIFs"
                ),
                color=discord.Color.magenta()
            ),
            # PAGE 11: AMONG US / IMPOSTER
            discord.Embed(
                title="🔪 AMONG US & IMPOSTER PAGE",
                description=(
                    "• `!imposter @user` — Imposter Test\n"
                    "• `!eject @user` — Eject user\n"
                    "• `!emergency` — Call Emergency Meeting"
                ),
                color=discord.Color.dark_red()
            ),
        ]

        embed = embeds[page_index]
        embed.set_footer(
            text=f"Page {page_index + 1}/{self.total_pages} • Requested by {self.ctx.author.display_name}",
            icon_url=self.ctx.author.display_avatar.url
        )
        return embed

    @discord.ui.button(label="◀️ Back", style=discord.ButtonStyle.primary, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("❌ Dynamic controls represent your own session!", ephemeral=True)
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(self.current_page), view=self)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.primary, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("❌ Dynamic controls represent your own session!", ephemeral=True)
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(self.current_page), view=self)


# -------------------------------------------------------------
# 2. OWNER PRIVATE HELP PAGINATION (`!ownerhelp`)
# -------------------------------------------------------------
class OwnerHelpPaginationView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.current_page = 0
        self.total_pages = 2
        self.update_buttons()

    def update_buttons(self):
        self.prev_btn.disabled = (self.current_page == 0)
        self.next_btn.disabled = (self.current_page == self.total_pages - 1)

    def get_embed(self, page_index: int) -> discord.Embed:
        embeds = [
            # PAGE 0: OWNER PLAN CREATION & PERMS
            discord.Embed(
                title="👑 OWNER PRIVATE HELP — PART 1",
                description=(
                    "**Premium Plan & Permissions Management:**\n\n"
                    "• `!pcreate <plan_name>` — Interactive UI to create new premium tiers\n"
                    "• `!pcommand <plan> <perm>` — Bind specific command access to plans\n"
                    "• `!plist` — View all configured plans & permission mappings\n"
                    "• `!pdelete <plan>` — Delete a plan tier"
                ),
                color=discord.Color.dark_gold()
            ),
            # PAGE 1: OWNER GRANT, LICENSING & SPAM
            discord.Embed(
                title="👑 OWNER PRIVATE HELP — PART 2",
                description=(
                    "**License Granting & Owner Private Controls:**\n\n"
                    "• `!pgive user @user <time> <plan>` — Grant global user premium\n"
                    "• `!pgive server <plan> [time]` — Grant full guild-wide premium\n"
                    "• `!pgive su @user <plan> [time]` — Grant guild-specific user premium\n"
                    "• `!premove <user/server>` — Revoke active premium access\n\n"
                    "**⚡ Exclusive Owner Utilities:**\n"
                    "• `!spam <count> <text>` — Start custom text spamming process\n"
                    "• `!spamstop` — Force stop ongoing spam process"
                ),
                color=discord.Color.dark_purple()
            )
        ]

        embed = embeds[page_index]
        embed.set_footer(
            text=f"Owner Menu Page {page_index + 1}/{self.total_pages} • Strictly Restricted",
            icon_url=self.ctx.author.display_avatar.url
        )
        return embed

    @discord.ui.button(label="◀️ Back", style=discord.ButtonStyle.danger, row=0)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("❌ Restricted Panel!", ephemeral=True)
        self.current_page -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(self.current_page), view=self)

    @discord.ui.button(label="Next ▶️", style=discord.ButtonStyle.danger, row=0)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("❌ Restricted Panel!", ephemeral=True)
        self.current_page += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.get_embed(self.current_page), view=self)


# -------------------------------------------------------------
# 3. HELP COG REGISTRATION
# -------------------------------------------------------------
class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot.remove_command("help")

    @commands.command(name="help")
    async def help_command(self, ctx):
        view = PublicHelpPaginationView(ctx)
        embed = view.get_embed(0)
        await ctx.send(embed=embed, view=view)

    # PRIVATE OWNER ONLY COMMAND (Renamed to ownerhelp to avoid overlap with premium cog)
    @commands.command(name="ownerhelp", aliases=["phelp_menu"])
    @commands.is_owner()
    async def owner_help_command(self, ctx):
        view = OwnerHelpPaginationView(ctx)
        embed = view.get_embed(0)
        await ctx.send(embed=embed, view=view)

    @owner_help_command.error
    async def owner_help_error(self, ctx, error):
        if isinstance(error, commands.NotOwner):
            await ctx.send("⛔ **Access Denied:** Only the Bot Owner can view the Owner Panel!")

    # Direct shortcuts for public pages (Renamed to avoid conflict with imposter cog)
    @commands.command(name="modhelp")
    async def mod_help_direct(self, ctx):
        view = PublicHelpPaginationView(ctx)
        view.current_page = 1
        view.update_buttons()
        await ctx.send(embed=view.get_embed(1), view=view)

    @commands.command(name="vcpage", aliases=["vchelp"])
    async def vc_help_direct(self, ctx):
        view = PublicHelpPaginationView(ctx)
        view.current_page = 2
        view.update_buttons()
        await ctx.send(embed=view.get_embed(2), view=view)

    @commands.command(name="funhelp", aliases=["gifpage"])
    async def gif_help_direct(self, ctx):
        view = PublicHelpPaginationView(ctx)
        view.current_page = 10
        view.update_buttons()
        await ctx.send(embed=view.get_embed(10), view=view)

    @commands.command(name="imposterhelp", aliases=["amonguspage"])
    async def imposter_help_direct(self, ctx):
        view = PublicHelpPaginationView(ctx)
        view.current_page = 11
        view.update_buttons()
        await ctx.send(embed=view.get_embed(11), view=view)


async def setup(bot):
    await bot.add_cog(Help(bot))

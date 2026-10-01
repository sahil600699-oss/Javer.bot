import discord
from discord.ext import commands
import json
import os

DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "welcome_settings.json")

DEFAULTS = {
    "welcome": {"enabled": False, "channel_id": None, "message": "Welcome to {server}, {user}!", "tag_enabled": True, "tag_message": "Welcome to {server}", "title_enabled": True, "title": "✦ WELCOME ✦", "image_enabled": True, "image_url": None, "avatar_enabled": True, "servericon_enabled": True, "inviter_enabled": False, "members_enabled": True, "username_enabled": False, "userid_enabled": False, "account_enabled": False, "joined_enabled": False, "color": "blurple"},
    "goodbye": {"enabled": False, "channel_id": None, "message": "Goodbye {user}! We will miss you.", "tag_enabled": False, "tag_message": "Goodbye", "title_enabled": True, "title": "✦ GOODBYE ✦", "image_enabled": True, "image_url": None, "avatar_enabled": True, "servericon_enabled": True, "members_enabled": True, "username_enabled": False, "userid_enabled": False, "account_enabled": False, "joined_enabled": False, "color": "red"}
}

COLOR_NAMES = ["blue", "red", "green", "yellow", "orange", "purple", "pink", "cyan", "teal", "magenta", "gold", "white", "black", "grey", "gray", "blurple", "dark_blue", "dark_red", "dark_green", "dark_purple", "dark_magenta", "dark_orange", "dark_teal", "dark_gold", "dark_grey", "light_grey", "aqua", "fuchsia", "lime", "navy", "maroon", "olive"]


def clone_defaults():
    return json.loads(json.dumps(DEFAULTS))


def load_data():
    os.makedirs(DATA_DIR, exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4)
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_data(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    temp = DATA_FILE + ".tmp"
    with open(temp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    os.replace(temp, DATA_FILE)


def guild_data(data, guild_id):
    key = str(guild_id)
    if key not in data:
        data[key] = clone_defaults()
    for section in ("welcome", "goodbye"):
        data[key].setdefault(section, {})
        for k, v in DEFAULTS[section].items():
            data[key][section].setdefault(k, v)
    return data[key]


def get_color(value):
    value = str(value).lower().strip()
    if value.startswith("#"):
        try:
            return discord.Color(int(value[1:], 16))
        except ValueError:
            return None
    named = {
        "blue": discord.Color.blue, "red": discord.Color.red, "green": discord.Color.green,
        "yellow": discord.Color.yellow, "orange": discord.Color.orange, "purple": discord.Color.purple,
        "pink": discord.Color.fuchsia, "cyan": discord.Color.teal, "teal": discord.Color.teal,
        "magenta": discord.Color.magenta, "gold": discord.Color.gold, "white": lambda: discord.Color.from_rgb(255,255,255),
        "black": lambda: discord.Color.from_rgb(0,0,0), "grey": discord.Color.greyple, "gray": discord.Color.greyple,
        "blurple": discord.Color.blurple, "dark_blue": discord.Color.dark_blue, "dark_red": discord.Color.dark_red,
        "dark_green": discord.Color.dark_green, "dark_purple": discord.Color.dark_purple,
        "dark_magenta": discord.Color.dark_magenta, "dark_orange": discord.Color.dark_orange,
        "dark_teal": discord.Color.dark_teal, "dark_gold": discord.Color.dark_gold,
        "dark_grey": discord.Color.dark_grey, "light_grey": discord.Color.light_grey,
        "aqua": discord.Color.teal, "fuchsia": discord.Color.magenta, "lime": discord.Color.green,
        "navy": discord.Color.dark_blue, "maroon": discord.Color.dark_red, "olive": discord.Color.dark_green,
    }
    fn = named.get(value)
    return fn() if fn else None


def fmt(text, member, inviter=None):
    replacements = {
        "{user}": member.mention, "{username}": member.display_name,
        "{server}": member.guild.name, "{count}": str(member.guild.member_count or 0),
        "{userid}": str(member.id),
        "{account}": discord.utils.format_dt(member.created_at, "F"),
        "{joined}": discord.utils.format_dt(member.joined_at, "F") if member.joined_at else "Unknown",
        "{inviter}": inviter.mention if inviter else "Unknown"
    }
    for key, value in replacements.items():
        text = text.replace(key, value)
    return text


class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data = load_data()

    def settings(self, guild_id):
        return guild_data(self.data, guild_id)

    def save(self):
        save_data(self.data)

    async def build_embed(self, member, cfg, inviter=None):
        embed = discord.Embed(description=fmt(cfg["message"], member, inviter), color=get_color(cfg["color"]) or discord.Color.blurple())
        if cfg["title_enabled"]:
            embed.title = cfg["title"]
        if cfg["avatar_enabled"]:
            embed.set_thumbnail(url=member.display_avatar.url)
        if cfg["image_enabled"] and cfg.get("image_url"):
            embed.set_image(url=cfg["image_url"])
        if cfg["servericon_enabled"] and member.guild.icon:
            embed.set_author(name=member.guild.name, icon_url=member.guild.icon.url)
        if cfg["username_enabled"]:
            embed.add_field(name="Username", value=member.display_name, inline=True)
        if cfg["userid_enabled"]:
            embed.add_field(name="User ID", value=str(member.id), inline=True)
        if cfg["members_enabled"]:
            embed.add_field(name="Members", value=str(member.guild.member_count or 0), inline=True)
        if cfg["account_enabled"]:
            embed.add_field(name="Account Created", value=discord.utils.format_dt(member.created_at, "R"), inline=True)
        if cfg["joined_enabled"] and member.joined_at:
            embed.add_field(name="Joined", value=discord.utils.format_dt(member.joined_at, "R"), inline=True)
        if cfg["inviter_enabled"]:
            embed.add_field(name="Invited By", value=inviter.mention if inviter else "Unknown", inline=True)
        embed.set_footer(text=member.guild.name)
        return embed

    async def send_message(self, member, cfg, channel, inviter=None):
        embed = await self.build_embed(member, cfg, inviter)
        content = fmt(cfg["tag_message"], member, inviter).strip() if cfg["tag_enabled"] else None
        await channel.send(content=content or None, embed=embed, allowed_mentions=discord.AllowedMentions(users=True, roles=False, everyone=False))

    async def help_page(self, ctx, section):
        prefix = ctx.prefix
        lines = [
            f"`{prefix}{section} on/off`", f"`{prefix}{section} setup #channel`", f"`{prefix}{section} msg <text>`",
            f"`{prefix}{section} tag on/off`", f"`{prefix}{section} tagmsg <text>`", f"`{prefix}{section} title on/off`",
            f"`{prefix}{section} title <text>`", f"`{prefix}{section} image <url/off>`", f"`{prefix}{section} avatar on/off`",
            f"`{prefix}{section} servericon on/off`", f"`{prefix}{section} members on/off`", f"`{prefix}{section} username on/off`",
            f"`{prefix}{section} userid on/off`", f"`{prefix}{section} account on/off`", f"`{prefix}{section} joined on/off`",
            f"`{prefix}{section} color <name/#hex>`", f"`{prefix}{section} settings`", f"`{prefix}{section} test`",
            f"`{prefix}{section} reset`"
        ]
        if section == "welcome":
            lines.insert(9, f"`{prefix}welcome inviter on/off`")
        embed = discord.Embed(title=f"{section.title()} Commands", description="\n".join(lines), color=discord.Color.blurple())
        await ctx.send(embed=embed)

    @commands.group(name="welcome", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def welcome(self, ctx):
        await self.help_page(ctx, "welcome")

    @welcome.command(name="help")
    async def welcome_help(self, ctx): await self.help_page(ctx, "welcome")

    @welcome.command(name="on")
    async def welcome_on(self, ctx): self.settings(ctx.guild.id)["welcome"]["enabled"] = True; self.save(); await ctx.send("✅ Welcome system is now **ON**.")

    @welcome.command(name="off")
    async def welcome_off(self, ctx): self.settings(ctx.guild.id)["welcome"]["enabled"] = False; self.save(); await ctx.send("✅ Welcome system is now **OFF**.")

    @welcome.command(name="setup")
    async def welcome_setup(self, ctx, channel: discord.TextChannel): self.settings(ctx.guild.id)["welcome"]["channel_id"] = channel.id; self.save(); await ctx.send(f"✅ Welcome channel set to {channel.mention}")

    @welcome.command(name="msg")
    async def welcome_msg(self, ctx, *, message: str): self.settings(ctx.guild.id)["welcome"]["message"] = message; self.save(); await ctx.send("✅ Welcome embed message saved.")

    @welcome.command(name="tag")
    async def welcome_tag(self, ctx, state: str):
        if state.lower() not in ("on", "off"): return await ctx.send("Use `!welcome tag on` or `!welcome tag off`.")
        self.settings(ctx.guild.id)["welcome"]["tag_enabled"] = state.lower() == "on"; self.save(); await ctx.send(f"✅ Welcome tag is now **{state.upper()}**.")

    @welcome.command(name="tagmsg")
    async def welcome_tagmsg(self, ctx, *, message: str): self.settings(ctx.guild.id)["welcome"]["tag_message"] = message; self.save(); await ctx.send("✅ Welcome tag message saved.")

    @welcome.command(name="title")
    async def welcome_title(self, ctx, *args):
        cfg = self.settings(ctx.guild.id)["welcome"]
        if not args: return await ctx.send("Use `!welcome title on`, `off`, or `!welcome title <text>`.")
        if len(args) == 1 and args[0].lower() in ("on", "off"): cfg["title_enabled"] = args[0].lower() == "on"
        else: cfg["title"] = " ".join(args); cfg["title_enabled"] = True
        self.save(); await ctx.send("✅ Welcome title updated.")

    @welcome.command(name="image")
    async def welcome_image(self, ctx, value: str):
        cfg = self.settings(ctx.guild.id)["welcome"]
        if value.lower() == "off": cfg["image_enabled"] = False
        else: cfg["image_url"] = value; cfg["image_enabled"] = True
        self.save(); await ctx.send("✅ Welcome image updated.")

    async def toggle(self, ctx, section, key, label, state):
        if state.lower() not in ("on", "off"): return await ctx.send(f"Use `{ctx.prefix}{section} {key.replace('_enabled','')} on/off`.")
        self.settings(ctx.guild.id)[section][key] = state.lower() == "on"; self.save(); await ctx.send(f"✅ {label} is now **{state.upper()}**.")

    @welcome.command(name="avatar")
    async def welcome_avatar(self, ctx, state): await self.toggle(ctx, "welcome", "avatar_enabled", "Avatar", state)
    @welcome.command(name="servericon")
    async def welcome_servericon(self, ctx, state): await self.toggle(ctx, "welcome", "servericon_enabled", "Server icon", state)
    @welcome.command(name="inviter")
    async def welcome_inviter(self, ctx, state): await self.toggle(ctx, "welcome", "inviter_enabled", "Inviter", state)
    @welcome.command(name="members")
    async def welcome_members(self, ctx, state): await self.toggle(ctx, "welcome", "members_enabled", "Member count", state)
    @welcome.command(name="username")
    async def welcome_username(self, ctx, state): await self.toggle(ctx, "welcome", "username_enabled", "Username", state)
    @welcome.command(name="userid")
    async def welcome_userid(self, ctx, state): await self.toggle(ctx, "welcome", "userid_enabled", "User ID", state)
    @welcome.command(name="account")
    async def welcome_account(self, ctx, state): await self.toggle(ctx, "welcome", "account_enabled", "Account info", state)
    @welcome.command(name="joined")
    async def welcome_joined(self, ctx, state): await self.toggle(ctx, "welcome", "joined_enabled", "Join date", state)

    @welcome.command(name="color")
    async def welcome_color(self, ctx, value: str):
        if not get_color(value): return await ctx.send("❌ Invalid color. Use a named color or hex like `#5865F2`.")
        self.settings(ctx.guild.id)["welcome"]["color"] = value.lower(); self.save(); await ctx.send(f"✅ Welcome color set to **{value}**.")

    @welcome.command(name="settings")
    async def welcome_settings(self, ctx): await self.show_settings(ctx, "welcome")

    async def show_settings(self, ctx, section):
        cfg = self.settings(ctx.guild.id)[section]
        channel = ctx.guild.get_channel(cfg.get("channel_id"))
        embed = discord.Embed(title=f"{section.title()} Settings", color=get_color(cfg["color"]) or discord.Color.blurple())
        values = [("Status", cfg["enabled"]), ("Channel", channel.mention if channel else "Not set"), ("Tag", cfg["tag_enabled"]), ("Title", cfg["title_enabled"]), ("Image", cfg["image_enabled"]), ("Avatar", cfg["avatar_enabled"]), ("Server Icon", cfg["servericon_enabled"]), ("Members", cfg["members_enabled"]), ("Username", cfg["username_enabled"]), ("User ID", cfg["userid_enabled"]), ("Account", cfg["account_enabled"]), ("Joined", cfg["joined_enabled"]), ("Color", cfg["color"])]
        if section == "welcome": values.insert(7, ("Inviter", cfg["inviter_enabled"]))
        for name, value in values: embed.add_field(name=name, value=("ON" if value is True else "OFF" if value is False else str(value)), inline=True)
        await ctx.send(embed=embed)

    @welcome.command(name="test")
    async def welcome_test(self, ctx):
        cfg = self.settings(ctx.guild.id)["welcome"]; channel = ctx.guild.get_channel(cfg.get("channel_id"))
        if not channel: return await ctx.send("❌ First set a channel using `!welcome setup #channel`.")
        await self.send_message(ctx.author, cfg, channel); await ctx.send("✅ Test welcome message sent.")

    @welcome.command(name="reset")
    async def welcome_reset(self, ctx): self.settings(ctx.guild.id)["welcome"] = clone_defaults()["welcome"]; self.save(); await ctx.send("🗑️ Welcome settings reset.")

    @commands.group(name="goodbye", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def goodbye(self, ctx): await self.help_page(ctx, "goodbye")

    @goodbye.command(name="help")
    async def goodbye_help(self, ctx): await self.help_page(ctx, "goodbye")

    @goodbye.command(name="on")
    async def goodbye_on(self, ctx): self.settings(ctx.guild.id)["goodbye"]["enabled"] = True; self.save(); await ctx.send("✅ Goodbye system is now **ON**.")
    @goodbye.command(name="off")
    async def goodbye_off(self, ctx): self.settings(ctx.guild.id)["goodbye"]["enabled"] = False; self.save(); await ctx.send("✅ Goodbye system is now **OFF**.")
    @goodbye.command(name="setup")
    async def goodbye_setup(self, ctx, channel: discord.TextChannel): self.settings(ctx.guild.id)["goodbye"]["channel_id"] = channel.id; self.save(); await ctx.send(f"✅ Goodbye channel set to {channel.mention}")
    @goodbye.command(name="msg")
    async def goodbye_msg(self, ctx, *, message: str): self.settings(ctx.guild.id)["goodbye"]["message"] = message; self.save(); await ctx.send("✅ Goodbye embed message saved.")
    @goodbye.command(name="tag")
    async def goodbye_tag(self, ctx, state): await self.toggle(ctx, "goodbye", "tag_enabled", "Goodbye tag", state)
    @goodbye.command(name="tagmsg")
    async def goodbye_tagmsg(self, ctx, *, message: str): self.settings(ctx.guild.id)["goodbye"]["tag_message"] = message; self.save(); await ctx.send("✅ Goodbye tag message saved.")

    @goodbye.command(name="title")
    async def goodbye_title(self, ctx, *args):
        cfg = self.settings(ctx.guild.id)["goodbye"]
        if not args: return await ctx.send("Use `!goodbye title on`, `off`, or `!goodbye title <text>`.")
        if len(args) == 1 and args[0].lower() in ("on", "off"): cfg["title_enabled"] = args[0].lower() == "on"
        else: cfg["title"] = " ".join(args); cfg["title_enabled"] = True
        self.save(); await ctx.send("✅ Goodbye title updated.")

    @goodbye.command(name="image")
    async def goodbye_image(self, ctx, value: str):
        cfg = self.settings(ctx.guild.id)["goodbye"]
        if value.lower() == "off": cfg["image_enabled"] = False
        else: cfg["image_url"] = value; cfg["image_enabled"] = True
        self.save(); await ctx.send("✅ Goodbye image updated.")

    @goodbye.command(name="avatar")
    async def goodbye_avatar(self, ctx, state): await self.toggle(ctx, "goodbye", "avatar_enabled", "Avatar", state)
    @goodbye.command(name="servericon")
    async def goodbye_servericon(self, ctx, state): await self.toggle(ctx, "goodbye", "servericon_enabled", "Server icon", state)
    @goodbye.command(name="members")
    async def goodbye_members(self, ctx, state): await self.toggle(ctx, "goodbye", "members_enabled", "Member count", state)
    @goodbye.command(name="username")
    async def goodbye_username(self, ctx, state): await self.toggle(ctx, "goodbye", "username_enabled", "Username", state)
    @goodbye.command(name="userid")
    async def goodbye_userid(self, ctx, state): await self.toggle(ctx, "goodbye", "userid_enabled", "User ID", state)
    @goodbye.command(name="account")
    async def goodbye_account(self, ctx, state): await self.toggle(ctx, "goodbye", "account_enabled", "Account info", state)
    @goodbye.command(name="joined")
    async def goodbye_joined(self, ctx, state): await self.toggle(ctx, "goodbye", "joined_enabled", "Join date", state)

    @goodbye.command(name="color")
    async def goodbye_color(self, ctx, value):
        if not get_color(value): return await ctx.send("❌ Invalid color. Use a named color or hex like `#FF0000`.")
        self.settings(ctx.guild.id)["goodbye"]["color"] = value.lower(); self.save(); await ctx.send(f"✅ Goodbye color set to **{value}**.")
    @goodbye.command(name="settings")
    async def goodbye_settings(self, ctx): await self.show_settings(ctx, "goodbye")
    @goodbye.command(name="test")
    async def goodbye_test(self, ctx):
        cfg = self.settings(ctx.guild.id)["goodbye"]; channel = ctx.guild.get_channel(cfg.get("channel_id"))
        if not channel: return await ctx.send("❌ First set a channel using `!goodbye setup #channel`.")
        await self.send_message(ctx.author, cfg, channel); await ctx.send("✅ Test goodbye message sent.")
    @goodbye.command(name="reset")
    async def goodbye_reset(self, ctx): self.settings(ctx.guild.id)["goodbye"] = clone_defaults()["goodbye"]; self.save(); await ctx.send("🗑️ Goodbye settings reset.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        cfg = self.settings(member.guild.id)["welcome"]
        if not cfg["enabled"] or not cfg.get("channel_id"): return
        channel = member.guild.get_channel(cfg["channel_id"])
        if channel:
            try: await self.send_message(member, cfg, channel)
            except Exception as e: print(f"[Welcome Error] {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        cfg = self.settings(member.guild.id)["goodbye"]
        if not cfg["enabled"] or not cfg.get("channel_id"): return
        channel = member.guild.get_channel(cfg["channel_id"])
        if channel:
            try: await self.send_message(member, cfg, channel)
            except Exception as e: print(f"[Goodbye Error] {e}")


async def setup(bot):
    await bot.add_cog(Welcome(bot))

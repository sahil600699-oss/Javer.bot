import discord
from discord.ext import commands
import datetime
import asyncio

class AntiNuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_tracker = {}  # {guild_id: {user_id: [timestamps]}}
        self.dup_tracker = {}   # {guild_id: {user_id: {"last_msg": str, "count": int}}}

    # Helper: Get Server Config
    def get_config(self, guild_id):
        if self.bot.db is None:
            return None
        db = self.bot.db['antinuke_config']
        config = db.find_one({"guild_id": str(guild_id)})
        if not config:
            config = {
                "guild_id": str(guild_id),
                "enabled": False,
                "whitelist": [],
                "bot_whitelist": [],
                "anti_bot": {"enabled": True, "action": "ban"},
                "spam": {"enabled": True, "timeout_limit": 5, "timeout_duration": 5, "ban_limit": 10},
                "dup_spam": {"enabled": True, "limit": 3, "action": "timeout", "duration": 10},
                "mass_ping": {"enabled": True, "limit": 5, "action": "timeout", "duration": 15},
                "links": {"enabled": True, "allow_discord": False, "action": "timeout", "duration": 5},
                "channel_create": {"enabled": True, "limit": 3, "action": "timeout", "duration": 15},
                "channel_delete": {"enabled": True, "limit": 2, "action": "ban", "duration": 0},
                "role_delete": {"enabled": True, "limit": 2, "action": "ban", "duration": 0},
                "mass_ban": {"enabled": True, "limit": 3, "action": "ban", "duration": 0},
                "mass_kick": {"enabled": True, "limit": 3, "action": "ban", "duration": 0},
                "webhook_create": {"enabled": True, "action": "ban"}
            }
            db.insert_one(config)
        return config

    def update_config(self, guild_id, data):
        if self.bot.db is not None:
            db = self.bot.db['antinuke_config']
            db.update_one({"guild_id": str(guild_id)}, {"$set": data}, upsert=True)

    def is_whitelisted(self, guild, user_id):
        if user_id == guild.owner_id or user_id == self.bot.user.id:
            return True
        config = self.get_config(guild.id)
        if config and str(user_id) in config.get("whitelist", []):
            return True
        return False

    async def apply_punishment(self, guild, member, action, duration=0, reason="Anti-Nuke Protection Triggered"):
        try:
            if action == "timeout" and duration > 0:
                until = discord.utils.utcnow() + datetime.timedelta(minutes=duration)
                await member.timeout(until, reason=reason)
            elif action == "kick":
                await member.kick(reason=reason)
            elif action == "ban":
                await member.ban(reason=reason)
            elif action == "strip_roles":
                roles_to_remove = [r for r in member.roles if r != guild.default_role and not r.managed]
                await member.remove_roles(*roles_to_remove, reason=reason)
        except Exception:
            pass

    # ---------------- EVENT LISTENERS ----------------

    # 1. Anti-Bot Join & Whitelist System
    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        config = self.get_config(guild.id)
        if not config or not config.get("enabled", False):
            return

        if member.bot:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.BOT_ADD, limit=1):
                inviter = entry.user
                if not self.is_whitelisted(guild, inviter.id):
                    # Kick unauthorized bot
                    await member.kick(reason="[ANTI-NUKE] Unauthorized bot joined.")
                    # Punish the inviter
                    await self.apply_punishment(guild, inviter, config["anti_bot"]["action"], reason="Added unauthorized bot to server.")
                    break

    # 2. Anti-Spam & Chat Protection
    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return
        guild = message.guild
        config = self.get_config(guild.id)
        if not config or not config.get("enabled", False) or self.is_whitelisted(guild, message.author.id):
            return

        now = datetime.datetime.utcnow().timestamp()
        uid = str(message.author.id)
        gid = str(guild.id)

        # Chat Spam
        if config["spam"]["enabled"]:
            if gid not in self.spam_tracker: self.spam_tracker[gid] = {}
            if uid not in self.spam_tracker[gid]: self.spam_tracker[gid][uid] = []
            
            self.spam_tracker[gid][uid] = [t for t in self.spam_tracker[gid][uid] if now - t < 5]
            self.spam_tracker[gid][uid].append(now)

            msg_count = len(self.spam_tracker[gid][uid])
            if msg_count >= config["spam"]["ban_limit"]:
                await message.channel.purge(limit=msg_count, check=lambda m: m.author == message.author)
                await self.apply_punishment(guild, message.author, "ban", reason="Automated Chat Spam (Ban Limit)")
                return
            elif msg_count >= config["spam"]["timeout_limit"]:
                await message.channel.purge(limit=msg_count, check=lambda m: m.author == message.author)
                await self.apply_punishment(guild, message.author, "timeout", config["spam"]["timeout_duration"], reason="Automated Chat Spam")
                return

        # Links & Invites
        if config["links"]["enabled"]:
            content = message.content.lower()
            if "discord.gg/" in content or "discord.com/invite/" in content or "http://" in content or "https://" in content:
                await message.delete()
                await self.apply_punishment(guild, message.author, config["links"]["action"], config["links"]["duration"], reason="Unauthorized Link Sharing")
                return

        # Mass Pings
        if config["mass_ping"]["enabled"]:
            if len(message.mentions) >= config["mass_ping"]["limit"] or message.mention_everyone:
                await message.delete()
                await self.apply_punishment(guild, message.author, config["mass_ping"]["action"], config["mass_ping"]["duration"], reason="Mass Mention Spam")
                return

    # 3. Channel Protection
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel):
        guild = channel.guild
        config = self.get_config(guild.id)
        if not config or not config.get("enabled", False): return

        async for entry in guild.audit_logs(action=discord.AuditLogAction.CHANNEL_DELETE, limit=1):
            executor = entry.user
            if self.is_whitelisted(guild, executor.id): return

            await self.apply_punishment(guild, executor, config["channel_delete"]["action"], config["channel_delete"]["duration"], reason="Unauthorized Channel Delete")
            await channel.clone(reason="[ANTI-NUKE] Auto-restored deleted channel.")

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel):
        guild = channel.guild
        config = self.get_config(guild.id)
        if not config or not config.get("enabled", False): return

        async for entry in guild.audit_logs(action=discord.AuditLogAction.CHANNEL_CREATE, limit=1):
            executor = entry.user
            if self.is_whitelisted(guild, executor.id): return

            await channel.delete(reason="[ANTI-NUKE] Unauthorized channel creation.")
            await self.apply_punishment(guild, executor, config["channel_create"]["action"], config["channel_create"]["duration"], reason="Mass Channel Creation")

    # 4. Role & Webhook Protection
    @commands.Cog.listener()
    async def on_guild_role_delete(self, role):
        guild = role.guild
        config = self.get_config(guild.id)
        if not config or not config.get("enabled", False): return

        async for entry in guild.audit_logs(action=discord.AuditLogAction.ROLE_DELETE, limit=1):
            executor = entry.user
            if self.is_whitelisted(guild, executor.id): return
            await self.apply_punishment(guild, executor, config["role_delete"]["action"], config["role_delete"]["duration"], reason="Unauthorized Role Delete")

    @commands.Cog.listener()
    async def on_webhooks_update(self, channel):
        guild = channel.guild
        config = self.get_config(guild.id)
        if not config or not config.get("enabled", False): return

        async for entry in guild.audit_logs(action=discord.AuditLogAction.WEBHOOK_CREATE, limit=1):
            executor = entry.user
            if self.is_whitelisted(guild, executor.id): return
            await self.apply_punishment(guild, executor, config["webhook_create"]["action"], reason="Unauthorized Webhook Creation")

    # ---------------- COMMANDS ----------------

    @commands.group(name="antinuke", aliases=["protect"], invoke_without_command=True)
    async def antinuke(self, ctx):
        embed = discord.Embed(
            title="🛡️ Server Anti-Nuke & Protection Framework",
            description="Complete system configuration menu for server security.",
            color=0x2ECC71
        )
        embed.add_field(
            name="⚙️ System Controls",
            value="`!antinuke enable` - Turn ON anti-nuke protection\n"
                  "`!antinuke disable` - Turn OFF anti-nuke protection\n"
                  "`!antinuke settings` - View current security thresholds",
            inline=False
        )
        embed.add_field(
            name="👑 Whitelist Commands",
            value="`!antinuke whitelist @user` - Whitelist an admin/bot\n"
                  "`!antinuke unwhitelist @user` - Remove from whitelist",
            inline=False
        )
        embed.add_field(
            name="🛠️ Protection Configurations",
            value="`!antinuke setspam <timeout_limit> <ban_limit> <timeout_mins>`\n"
                  "`!antinuke setbot <action>` - (Action: kick/ban/timeout)\n"
                  "`!antinuke setchannel <create_limit> <action> <duration_mins>`\n"
                  "`!antinuke setlink <action> <duration_mins>`",
            inline=False
        )
        await ctx.send(embed=embed)

    @antinuke.command(name="enable", aliases=["on"])
    async def enable_system(self, ctx):
        if ctx.author.id != ctx.guild.owner_id:
            return await ctx.send("❌ Only the **Server Owner** can toggle Anti-Nuke system!")
        self.update_config(ctx.guild.id, {"enabled": True})
        await ctx.send("✅ **Anti-Nuke Protection Framework is now ACTIVE!**")

    @antinuke.command(name="disable", aliases=["off"])
    async def disable_system(self, ctx):
        if ctx.author.id != ctx.guild.owner_id:
            return await ctx.send("❌ Only the **Server Owner** can toggle Anti-Nuke system!")
        self.update_config(ctx.guild.id, {"enabled": False})
        await ctx.send("⚠️ **Anti-Nuke Protection Framework has been DISABLED!**")

    @antinuke.command(name="whitelist", aliases=["wl"])
    async def whitelist_user(self, ctx, member: discord.Member):
        if ctx.author.id != ctx.guild.owner_id:
            return await ctx.send("❌ Only the **Server Owner** can manage whitelist!")
        config = self.get_config(ctx.guild.id)
        wl = config.get("whitelist", [])
        if str(member.id) not in wl:
            wl.append(str(member.id))
            self.update_config(ctx.guild.id, {"whitelist": wl})
        await ctx.send(f"✅ **{member.display_name}** is now whitelisted and will bypass security checks.")

    @antinuke.command(name="unwhitelist", aliases=["unwl"])
    async def unwhitelist_user(self, ctx, member: discord.Member):
        if ctx.author.id != ctx.guild.owner_id:
            return await ctx.send("❌ Only the **Server Owner** can manage whitelist!")
        config = self.get_config(ctx.guild.id)
        wl = config.get("whitelist", [])
        if str(member.id) in wl:
            wl.remove(str(member.id))
            self.update_config(ctx.guild.id, {"whitelist": wl})
        await ctx.send(f"⚠️ **{member.display_name}** removed from whitelist.")

    @antinuke.command(name="setspam")
    async def config_spam(self, ctx, timeout_limit: int, ban_limit: int, timeout_mins: int):
        if ctx.author.id != ctx.guild.owner_id: return
        self.update_config(ctx.guild.id, {
            "spam.timeout_limit": timeout_limit,
            "spam.ban_limit": ban_limit,
            "spam.timeout_duration": timeout_mins
        })
        await ctx.send(f"✅ **Spam Configured:** `{timeout_limit}` msgs = `{timeout_mins}m` Timeout | `{ban_limit}` msgs = Ban.")

    @antinuke.command(name="setbot")
    async def config_bot(self, ctx, action: str):
        if ctx.author.id != ctx.guild.owner_id: return
        if action not in ["kick", "ban", "timeout"]:
            return await ctx.send("❌ Invalid Action! Choose: `kick`, `ban`, or `timeout`.")
        self.update_config(ctx.guild.id, {"anti_bot.action": action})
        await ctx.send(f"✅ **Anti-Bot Action Updated:** Inviter will face `{action}` for unauthorized bot additions.")

    @antinuke.command(name="settings", aliases=["config"])
    async def view_settings(self, ctx):
        config = self.get_config(ctx.guild.id)
        embed = discord.Embed(title=f"🛡️ Security Settings - {ctx.guild.name}", color=0x3498DB)
        embed.add_field(name="System Status", value=f"`{'ENABLED' if config['enabled'] else 'DISABLED'}`", inline=False)
        embed.add_field(name="Spam Thresholds", value=f"Timeout: `{config['spam']['timeout_limit']} msgs` | Ban: `{config['spam']['ban_limit']} msgs`", inline=True)
        embed.add_field(name="Anti-Bot Action", value=f"`{config['anti_bot']['action'].upper()}`", inline=True)
        embed.add_field(name="Whitelisted Users", value=f"`{len(config.get('whitelist', []))}` Members", inline=True)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AntiNuke(bot))
          

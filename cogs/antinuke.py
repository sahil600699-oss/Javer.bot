import discord
from discord.ext import commands
import datetime
import re
import asyncio

class AntiNuke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.spam_tracker = {}  # {guild_id: {user_id: [timestamps]}}
        self.ban_tracker = {}   # {guild_id: {user_id: [timestamps]}}
        self.url_regex = re.compile(r'https?://[^\s]+|discord\.gg/[^\s]+|discord\.com/invite/[^\s]+')

    @property
    def db(self):
        return getattr(self.bot, "async_db", None)

    @property
    def config_col(self):
        return self.db["antinuke_config"] if self.db is not None else None

    # Helper: Fetch Guild Config from MongoDB
    async def get_config(self, guild_id):
        if self.config_col is None:
            return None
        config = await self.config_col.find_one({"guild_id": str(guild_id)})
        if not config:
            config = {
                "guild_id": str(guild_id),
                "whitelist": [],
                "log_channel_id": None,
                "spam": {"amount": 5, "action": "timeout", "duration": "5m"},
                "url": {"enabled": False, "action": "timeout", "duration": "5m"},
                "ban_protect": {"amount": 2, "action": "timeout", "duration": "1m"},
                "app": {"enabled": False}
            }
            await self.config_col.insert_one(config)
        return config

    # Helper: Parse Duration String into Seconds
    def parse_duration(self, duration_str: str) -> int:
        if not duration_str:
            return 300  # Default 5m
        match = re.match(r"^(\d+)(s|m|d|w|month)$", str(duration_str).lower().strip())
        if not match:
            return 300
        val, unit = int(match.group(1)), match.group(2)
        if unit == "s": return val
        elif unit == "m": return val * 60
        elif unit == "d": return val * 86400
        elif unit == "w": return val * 604800
        elif unit == "month": return val * 2592000
        return 300

    # Helper: Check Whitelist / Owner
    async def is_whitelisted(self, guild, user_id):
        if user_id == guild.owner_id:
            return True
        config = await self.get_config(guild.id)
        if config and str(user_id) in config.get("whitelist", []):
            return True
        return False

    # Helper: Send Audit Logs
    async def send_log(self, guild, embed):
        config = await self.get_config(guild.id)
        if config and config.get("log_channel_id"):
            channel = guild.get_channel(int(config["log_channel_id"]))
            if channel:
                try:
                    await channel.send(embed=embed)
                except Exception:
                    pass

    # Helper: Apply Punishment
    async def apply_punishment(self, guild, member, action, duration_str="5m", reason="AntiNuke Security Triggered"):
        try:
            sec = self.parse_duration(duration_str)
            if action == "timeout":
                until = discord.utils.utcnow() + datetime.timedelta(seconds=sec)
                await member.timeout(until, reason=reason)
            elif action == "ban":
                await member.ban(reason=reason)
        except Exception as e:
            print(f"Punishment Error: {e}")

    # ---------------- EVENT LISTENERS ----------------

    # 1. Anti App / Bot Add
    @commands.Cog.listener()
    async def on_member_join(self, member):
        if not member.bot or not member.guild:
            return
        guild = member.guild
        config = await self.get_config(guild.id)
        if not config or not config.get("app", {}).get("enabled", False):
            return

        async for entry in guild.audit_logs(action=discord.AuditLogAction.BOT_ADD, limit=1):
            inviter = entry.user
            if not await self.is_whitelisted(guild, inviter.id):
                # Kick unauthorized bot
                await member.kick(reason="AntiNuke: Unauthorized bot added")
                
                embed = discord.Embed(
                    title="AntiNuke Action: Unauthorized Bot Kicked",
                    description=f"Bot: {member.mention} ({member.id})\nAdded By: {inviter.mention} ({inviter.id})\nAction: Bot Kicked",
                    color=discord.Color.red()
                )
                await self.send_log(guild, embed)
                break

    # 2. Anti Spam & Anti URL
    @commands.Cog.listener()
    async def on_message(self, message):
        if not message.guild or message.author.bot:
            return
        guild = message.guild
        if await self.is_whitelisted(guild, message.author.id):
            return

        config = await self.get_config(guild.id)
        if not config:
            return

        now = datetime.datetime.utcnow().timestamp()
        uid = str(message.author.id)
        gid = str(guild.id)

        # Anti URL
        if config.get("url", {}).get("enabled", False):
            if self.url_regex.search(message.content):
                try:
                    await message.delete()
                except Exception:
                    pass
                action = config["url"].get("action", "timeout")
                dur = config["url"].get("duration", "5m")
                await self.apply_punishment(guild, message.author, action, dur, "AntiNuke: Unauthorized URL")
                
                embed = discord.Embed(
                    title="AntiNuke Action: URL Blocked",
                    description=f"User: {message.author.mention}\nAction: {action.upper()} ({dur})\nContent: `{message.content[:200]}`",
                    color=discord.Color.orange()
                )
                await self.send_log(guild, embed)
                return

        # Anti Spam
        spam_cfg = config.get("spam", {})
        limit = spam_cfg.get("amount", 5)
        if limit > 0:
            if gid not in self.spam_tracker: self.spam_tracker[gid] = {}
            if uid not in self.spam_tracker[gid]: self.spam_tracker[gid][uid] = []

            self.spam_tracker[gid][uid] = [t for t in self.spam_tracker[gid][uid] if now - t < 5]
            self.spam_tracker[gid][uid].append(now)

            if len(self.spam_tracker[gid][uid]) >= limit:
                self.spam_tracker[gid][uid] = []
                action = spam_cfg.get("action", "timeout")
                dur = spam_cfg.get("duration", "5m")
                await self.apply_punishment(guild, message.author, action, dur, "AntiNuke: Message Spam")

                embed = discord.Embed(
                    title="AntiNuke Action: Spam Detected",
                    description=f"User: {message.author.mention}\nAction: {action.upper()} ({dur})\nTrigger: Sent {limit} messages in 5 seconds",
                    color=discord.Color.red()
                )
                await self.send_log(guild, embed)

    # 3. Anti Mass Ban
    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        async for entry in guild.audit_logs(action=discord.AuditLogAction.BAN, limit=1):
            executor = entry.user
            if executor.bot or await self.is_whitelisted(guild, executor.id):
                return

            config = await self.get_config(guild.id)
            if not config: return

            ban_cfg = config.get("ban_protect", {})
            limit = ban_cfg.get("amount", 2)
            now = datetime.datetime.utcnow().timestamp()
            gid, uid = str(guild.id), str(executor.id)

            if gid not in self.ban_tracker: self.ban_tracker[gid] = {}
            if uid not in self.ban_tracker[gid]: self.ban_tracker[gid][uid] = []

            self.ban_tracker[gid][uid] = [t for t in self.ban_tracker[gid][uid] if now - t < 60]
            self.ban_tracker[gid][uid].append(now)

            if len(self.ban_tracker[gid][uid]) >= limit:
                self.ban_tracker[gid][uid] = []
                action = ban_cfg.get("action", "timeout")
                dur = ban_cfg.get("duration", "1m")
                await self.apply_punishment(guild, executor, action, dur, "AntiNuke: Mass Ban Limit Reached")

                embed = discord.Embed(
                    title="AntiNuke Action: Mass Ban Detected",
                    description=f"Executor: {executor.mention}\nAction: {action.upper()} ({dur})\nTrigger: Banned {limit} members in 60s",
                    color=discord.Color.dark_red()
                )
                await self.send_log(guild, embed)

    # ---------------- COMMANDS ----------------

    @commands.group(name="antinuke", aliases=["nuke"], invoke_without_command=True)
    async def antinuke_group(self, ctx):
        embed = discord.Embed(
            title="AntiNuke System Commands & Help",
            description="Manage server security filters and punishments easily.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Spam Filter", value="`!nuke spam <amount> <ban/timeout> [duration]`\nExample: `!nuke spam 5 timeout 5m`", inline=False)
        embed.add_field(name="URL Protection", value="`!nuke url <on/off>`\n`!nuke url action <ban/timeout> [duration]`\nExample: `!nuke url action timeout 10m`", inline=False)
        embed.add_field(name="Ban Protection", value="`!nuke ban <amount> <ban/timeout> [duration]`\nExample: `!nuke ban 2 timeout 1m`", inline=False)
        embed.add_field(name="App Protection", value="`!nuke app <on/off>`", inline=False)
        embed.add_field(name="Whitelist Management", value="`!nuke whitelist @user`\n`!nuke whitelistuser`", inline=False)
        embed.add_field(name="Logs & Overview", value="`!nuke logs #channel`\n`!nuke list`", inline=False)
        await ctx.send(embed=embed)

    @antinuke_group.command(name="spam")
    @commands.has_permissions(administrator=True)
    async def set_spam(self, ctx, amount: int, action: str, duration: str = "5m"):
        if action.lower() not in ["ban", "timeout"]:
            return await ctx.send("Invalid action! Choose `ban` or `timeout`.")
        await self.config_col.update_one(
            {"guild_id": str(ctx.guild.id)},
            {"$set": {"spam": {"amount": amount, "action": action.lower(), "duration": duration}}},
            upsert=True
        )
        await ctx.send(f"Spam filter configured: {amount} messages trigger **{action.lower()}** ({duration}).")

    @antinuke_group.group(name="url", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def url_group(self, ctx, status: str = None):
        if status and status.lower() in ["on", "off"]:
            enabled = status.lower() == "on"
            await self.config_col.update_one(
                {"guild_id": str(ctx.guild.id)},
                {"$set": {"url.enabled": enabled}},
                upsert=True
            )
            return await ctx.send(f"URL Protection is now **{'ENABLED' if enabled else 'DISABLED'}**.")
        await ctx.send("Usage: `!nuke url <on/off>` or `!nuke url action <ban/timeout> [duration]`")

    @url_group.command(name="action")
    @commands.has_permissions(administrator=True)
    async def set_url_action(self, ctx, action: str, duration: str = "5m"):
        if action.lower() not in ["ban", "timeout"]:
            return await ctx.send("Invalid action! Choose `ban` or `timeout`.")
        await self.config_col.update_one(
            {"guild_id": str(ctx.guild.id)},
            {"$set": {"url.action": action.lower(), "url.duration": duration}},
            upsert=True
        )
        await ctx.send(f"URL Protection action configured: **{action.lower()}** ({duration}).")

    @antinuke_group.command(name="ban")
    @commands.has_permissions(administrator=True)
    async def set_ban_protect(self, ctx, amount: int, action: str, duration: str = "1m"):
        if action.lower() not in ["ban", "timeout"]:
            return await ctx.send("Invalid action! Choose `ban` or `timeout`.")
        await self.config_col.update_one(
            {"guild_id": str(ctx.guild.id)},
            {"$set": {"ban_protect": {"amount": amount, "action": action.lower(), "duration": duration}}},
            upsert=True
        )
        await ctx.send(f"Ban protection configured: {amount} bans trigger **{action.lower()}** ({duration}).")

    @antinuke_group.command(name="app")
    @commands.has_permissions(administrator=True)
    async def set_app_protect(self, ctx, status: str):
        if status.lower() not in ["on", "off"]:
            return await ctx.send("Usage: `!nuke app <on/off>`")
        enabled = status.lower() == "on"
        await self.config_col.update_one(
            {"guild_id": str(ctx.guild.id)},
            {"$set": {"app.enabled": enabled}},
            upsert=True
        )
        await ctx.send(f"App/Bot Protection is now **{'ENABLED' if enabled else 'DISABLED'}**.")

    @antinuke_group.command(name="whitelist")
    @commands.has_permissions(administrator=True)
    async def toggle_whitelist(self, ctx, member: discord.Member):
        config = await self.get_config(ctx.guild.id)
        wl = config.get("whitelist", [])
        mid = str(member.id)
        if mid in wl:
            wl.remove(mid)
            msg = f"{member.mention} removed from AntiNuke whitelist."
        else:
            wl.append(mid)
            msg = f"{member.mention} added to AntiNuke whitelist."
        await self.config_col.update_one({"guild_id": str(ctx.guild.id)}, {"$set": {"whitelist": wl}}, upsert=True)
        await ctx.send(msg)

    @commands.command(name="whitelistuser", aliases=["auntinuke_whitelistuser"])
    @commands.has_permissions(administrator=True)
    async def list_whitelisted_users(self, ctx):
        config = await self.get_config(ctx.guild.id)
        wl = config.get("whitelist", [])
        if not wl:
            return await ctx.send("No users are currently whitelisted.")
        users_str = "\n".join([f"• <@{uid}> (`{uid}`)" for uid in wl])
        embed = discord.Embed(title="Whitelisted Users", description=users_str, color=discord.Color.green())
        await ctx.send(embed=embed)

    @antinuke_group.command(name="logs")
    @commands.has_permissions(administrator=True)
    async def set_logs_channel(self, ctx, channel: discord.TextChannel):
        await self.config_col.update_one(
            {"guild_id": str(ctx.guild.id)},
            {"$set": {"log_channel_id": str(channel.id)}},
            upsert=True
        )
        await ctx.send(f"AntiNuke log channel set to {channel.mention}.")

    @antinuke_group.command(name="list")
    @commands.has_permissions(administrator=True)
    async def show_list_setup(self, ctx):
        c = await self.get_config(ctx.guild.id)
        embed = discord.Embed(title=f"AntiNuke Active Configuration - {ctx.guild.name}", color=discord.Color.gold())
        
        spam = c.get("spam", {})
        embed.add_field(name="Spam Filter", value=f"Limit: `{spam.get('amount', 5)}`\nAction: `{spam.get('action', 'timeout').upper()}`\nDuration: `{spam.get('duration', '5m')}`", inline=True)
        
        url = c.get("url", {})
        embed.add_field(name="URL Protection", value=f"Status: `{ 'ENABLED' if url.get('enabled') else 'DISABLED' }`\nAction: `{url.get('action', 'timeout').upper()}`\nDuration: `{url.get('duration', '5m')}`", inline=True)
        
        ban = c.get("ban_protect", {})
        embed.add_field(name="Ban Protection", value=f"Limit: `{ban.get('amount', 2)}`\nAction: `{ban.get('action', 'timeout').upper()}`\nDuration: `{ban.get('duration', '1m')}`", inline=True)
        
        app = c.get("app", {})
        embed.add_field(name="App Protection", value=f"Status: `{ 'ENABLED' if app.get('enabled') else 'DISABLED' }`", inline=True)
        
        log_ch = f"<#{c.get('log_channel_id')}>" if c.get('log_channel_id') else "Not Set"
        embed.add_field(name="Log Channel", value=log_ch, inline=True)
        embed.add_field(name="Whitelisted Users", value=f"`{len(c.get('whitelist', []))}` Members", inline=True)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(AntiNuke(bot))
            

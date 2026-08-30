import discord
from discord.ext import commands
import asyncio
from cogs.premium import has_premium_access

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Active spam tasks tracker: guild_id -> asyncio.Task
        self.active_spam_tasks = {}

    # ==========================================
    # 🔒 GLOBAL PERMISSION ERROR HANDLER
    # ==========================================
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Agar user ke paas permission na ho to alert message bheje"""
        if isinstance(error, commands.MissingPermissions):
            perms = ", ".join(error.missing_permissions).replace("_", " ").title()
            embed = discord.Embed(
                title="⛔ Permission Denied!",
                description=f"Aapke paas is command ko chalane ke liye **`{perms}`** permission nahi hai.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
        elif isinstance(error, commands.BotMissingPermissions):
            perms = ", ".join(error.missing_permissions).replace("_", " ").title()
            await ctx.send(f"❌ Mera (Bot) role chhota hai ya permission missing hai: **`{perms}`**")

    # ==========================================
    # 1. BAN, KICK & CLEAR COMMANDS
    # ==========================================
    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick_user(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        if member == ctx.author:
            await ctx.send("❌ Aap khud ko kick nahi kar sakte!")
            return
        try:
            await member.kick(reason=reason)
            await ctx.send(f"👢 **{member.display_name}** ko kick kar diya gaya! | Reason: {reason}")
        except Exception as e:
            await ctx.send(f"❌ Kick error: {e}")

    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban_user(self, ctx, member: discord.Member, *, reason: str = "No reason provided"):
        if member == ctx.author:
            await ctx.send("❌ Aap khud ko ban nahi kar sakte!")
            return
        try:
            await member.ban(reason=reason)
            await ctx.send(f"🔨 **{member.display_name}** ko ban kar diya gaya! | Reason: {reason}")
        except Exception as e:
            await ctx.send(f"❌ Ban error: {e}")

    @commands.command(name="clear", aliases=["purge"])
    @commands.has_permissions(manage_messages=True)
    async def clear_messages(self, ctx, amount: int):
        if amount <= 0:
            await ctx.send("❌ Amount 1 ya usse zyada honi chahiye!")
            return
        try:
            deleted = await ctx.channel.purge(limit=amount + 1)
            msg = await ctx.send(f"🧹 **{len(deleted)-1}** messages clear kar diye gaye!")
            await asyncio.sleep(3)
            await msg.delete()
        except Exception as e:
            await ctx.send(f"❌ Clear error: {e}")

    # ==========================================
    # 2. CHANGE NICKNAME (!change nick @user [name])
    # ==========================================
    @commands.group(name="change", invoke_without_command=True)
    @commands.has_permissions(manage_nicknames=True)
    async def change_group(self, ctx):
        await ctx.send("❓ Galat Format! Standard Use: `!change nick @user [new_nickname]`")

    @change_group.command(name="nick")
    @commands.has_permissions(manage_nicknames=True)
    async def change_nickname(self, ctx, member: discord.Member, *, new_nick: str):
        try:
            old_nick = member.display_name
            await member.edit(nick=new_nick)
            await ctx.send(f"✅ **{old_nick}** ka nickname badal kar **{new_nick}** kar diya gaya!")
        except Exception as e:
            await ctx.send(f"❌ Nickname change karne me error: {e}")

    # ==========================================
    # 3. MUTE & DEAFEN IN VC (!mute & !def)
    # ==========================================
    @commands.command(name="mute")
    @commands.has_permissions(mute_members=True)
    async def mute_vc(self, ctx, member: discord.Member):
        if not member.voice or not member.voice.channel:
            await ctx.send(f"❌ {member.mention} kisi Voice Channel me nahi hai!")
            return
        try:
            is_muted = not member.voice.mute
            await member.edit(mute=is_muted)
            status = "Muted 🔕" if is_muted else "Unmuted 🔔"
            await ctx.send(f"✅ {member.mention} ko VC me **{status}** kar diya gaya!")
        except Exception as e:
            await ctx.send(f"❌ Mute action fail ho gaya: {e}")

    @commands.command(name="def")
    @commands.has_permissions(deafen_members=True)
    async def deafen_vc(self, ctx, member: discord.Member):
        if not member.voice or not member.voice.channel:
            await ctx.send(f"❌ {member.mention} kisi Voice Channel me nahi hai!")
            return
        try:
            is_deaf = not member.voice.deafen
            await member.edit(deafen=is_deaf)
            status = "Deafened 🔇" if is_deaf else "Undeafened 🔊"
            await ctx.send(f"✅ {member.mention} ko VC me **{status}** kar diya gaya!")
        except Exception as e:
            await ctx.send(f"❌ Deafen action fail ho gaya: {e}")

    # ==========================================
    # 4. MOVE USER TO ANOTHER VC (!move @user [vc name])
    # ==========================================
    @commands.command(name="move")
    @commands.has_permissions(move_members=True)
    async def move_vc(self, ctx, member: discord.Member, *, vc_name: str):
        if not member.voice or not member.voice.channel:
            await ctx.send(f"❌ {member.mention} kisi Voice Channel me nahi hai!")
            return

        target_vc = discord.utils.get(ctx.guild.voice_channels, name=vc_name)
        if not target_vc:
            await ctx.send(f"❌ VC Channel **'{vc_name}'** nahi mila! Naame exact waisa hi likhein.")
            return

        try:
            await member.move_to(target_vc)
            await ctx.send(f"🚚 {member.mention} ko **{target_vc.name}** me shift kar diya gaya!")
        except Exception as e:
            await ctx.send(f"❌ VC Move karne me error aaya: {e}")

    # ==========================================
    # 5. GIVE/REMOVE ROLE (!roleg @user [role name])
    # ==========================================
    @commands.command(name="roleg")
    @commands.has_permissions(manage_roles=True)
    async def give_role(self, ctx, member: discord.Member, *, role_name: str):
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role:
            await ctx.send(f"❌ Server me **'{role_name}'** naam ka koi role nahi mila!")
            return

        try:
            if role in member.roles:
                await member.remove_roles(role)
                await ctx.send(f"➖ {member.mention} se **{role.name}** role hata diya gaya.")
            else:
                await member.add_roles(role)
                await ctx.send(f"➕ {member.mention} ko **{role.name}** role de diya gaya!")
        except Exception as e:
            await ctx.send(f"❌ Role assign karne me error: {e}")

    # ==========================================
    # 6. SPAM & SPAMSTOP (Strictly Premium Only)
    # ==========================================
    async def run_spam(self, ctx, amount: int, message_text: str):
        try:
            for i in range(amount):
                await ctx.send(message_text)
                await asyncio.sleep(0.4)
        except asyncio.CancelledError:
            await ctx.send("🛑 **Spam Task ko beech me rok diya gaya!**")
        finally:
            self.active_spam_tasks.pop(ctx.guild.id, None)

    @commands.command(name="spam")
    async def start_spam(self, ctx, amount: int, *, message_text: str):
        # Premium Check (Server Admin/Owner cannot bypass this)
        if not has_premium_access(ctx.author.id, ctx.guild.id if ctx.guild else 0, "spam"):
            embed = discord.Embed(
                title="👑 Premium Only Command!",
                description="❌ **Access Denied!** Ye command sirf unhi ke liye hai jinke paas **`spam`** permission wala Premium Plan active hai.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        if ctx.guild.id in self.active_spam_tasks:
            await ctx.send("⚠️ Server me pehle se ek Spam task chal raha hai! Stop karne ke liye `!spamstop` use karein.")
            return

        await ctx.send(f"🚀 Spam task start ho raha hai ({amount} messages)... Rokne ke liye `!spamstop` type karein.")
        task = asyncio.create_task(self.run_spam(ctx, amount, message_text))
        self.active_spam_tasks[ctx.guild.id] = task

    @commands.command(name="spamstop")
    async def stop_spam(self, ctx):
        # Premium Check (Server Admin/Owner cannot bypass this)
        if not has_premium_access(ctx.author.id, ctx.guild.id if ctx.guild else 0, "spam"):
            embed = discord.Embed(
                title="👑 Premium Only Command!",
                description="❌ **Access Denied!** Spam stop karne ke liye bhi **`spam`** Premium permission zaroori hai.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        task = self.active_spam_tasks.get(ctx.guild.id)
        if task:
            task.cancel()
            await ctx.send("🛑 Active spam command cancel kar di gayi hai.")
        else:
            await ctx.send("❓ Abhi koi Active Spam process nahi chal raha.")

    # ==========================================
    # 7. SERVER INFO (!serverinfo & !si)
    # ==========================================
    @commands.command(name="serverinfo", aliases=["si"])
    async def server_info(self, ctx):
        guild = ctx.guild
        owner = guild.owner
        created_at = guild.created_at.strftime("%d %B %Y (%I:%M %p)")
        
        members_count = guild.member_count
        bots_count = sum(1 for m in guild.members if m.bot)
        humans_count = members_count - bots_count

        embed = discord.Embed(
            title=f"📊 Server Info — {guild.name}",
            color=discord.Color.gold()
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)

        embed.add_field(name="👑 Server Owner", value=f"{owner.mention} (`{owner.id}`)", inline=False)
        embed.add_field(name="📅 Created On", value=created_at, inline=False)
        embed.add_field(name="👥 Members Count", value=f"• Total: **{members_count}**\n• Humans: **{humans_count}**\n• Bots: **{bots_count}**", inline=True)
        embed.add_field(name="🚀 Boost Status", value=f"• Boosts: **{guild.premium_subscription_count}**\n• Level: **Tier {guild.premium_tier}**", inline=True)
        embed.add_field(name="💬 Channels", value=f"• Text: **{len(guild.text_channels)}**\n• Voice: **{len(guild.voice_channels)}**", inline=True)
        
        embed.set_footer(text=f"Server ID: {guild.id}")
        await ctx.send(embed=embed)

    # ==========================================
    # 8. VANITY LINK LISTENER ("vanity" in chat)
    # ==========================================
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        if message.content.lower().strip() == "vanity":
            try:
                if message.guild.vanity_url_code:
                    await message.channel.send(f"🔗 **Server Permanent Vanity Link:** https://discord.gg/{message.guild.vanity_url_code}")
                    return

                invites = await message.guild.invites()
                permanent_invite = None
                for inv in invites:
                    if inv.max_age == 0 and inv.max_uses == 0:
                        permanent_invite = inv
                        break

                if not permanent_invite:
                    permanent_invite = await message.channel.create_invite(max_age=0, max_uses=0, reason="Vanity Link Listener Triggered")

                await message.channel.send(f"🔗 **Server Never-Expiring Invite Link:** {permanent_invite.url}")
            except Exception:
                await message.channel.send("❌ Bot ke paas `Create Invite` ya `Manage Server` ki permission nahi hai.")

async def setup(bot):
    await bot.add_cog(Moderation(bot))

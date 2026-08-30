import discord
from discord.ext import commands
import sqlite3
import datetime
import config

DB_NAME = "premium_system.db"

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS premium_plans (
            plan_name TEXT PRIMARY KEY,
            allowed_commands TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS premium_holders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_type TEXT,
            target_id INTEGER,
            guild_id INTEGER,
            plan_name TEXT,
            expires_at TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS locked_commands (
            command_name TEXT PRIMARY KEY,
            required_plan TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- HELPER FUNCTIONS ---
def parse_duration(time_str: str):
    if time_str.lower() in ["perm", "permanent", "inf", "forever"]:
        return None
    unit = time_str[-1].lower()
    try:
        val = int(time_str[:-1])
    except ValueError:
        return -1
    now = datetime.datetime.utcnow()
    if unit == 'd':
        return now + datetime.timedelta(days=val)
    elif unit == 'm':
        return now + datetime.timedelta(days=val * 30)
    elif unit == 'y':
        return now + datetime.timedelta(days=val * 365)
    return -1

def is_owner_check(ctx):
    return ctx.author.id == getattr(config, "OWNER_ID", None)

def has_premium_access(user_id: int, guild_id: int, command_name: str) -> bool:
    if user_id == getattr(config, "OWNER_ID", None):
        return True
        
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now = datetime.datetime.utcnow()

    cursor.execute("SELECT plan_name, allowed_commands FROM premium_plans")
    plans = cursor.fetchall()
    
    for plan_name, cmds_str in plans:
        allowed_cmds = [c.strip().lower() for c in cmds_str.split(",")]
        if command_name.lower() in allowed_cmds or "*" in allowed_cmds:
            cursor.execute('''
                SELECT expires_at FROM premium_holders 
                WHERE plan_name = ? AND (
                    (target_type = 'user' AND target_id = ?) OR
                    (target_type = 'server' AND guild_id = ?) OR
                    (target_type = 'su' AND target_id = ? AND guild_id = ?)
                )
            ''', (plan_name, user_id, guild_id, user_id, guild_id))
            
            rows = cursor.fetchall()
            for (exp_str,) in rows:
                if exp_str is None:
                    conn.close()
                    return True
                exp_dt = datetime.datetime.fromisoformat(exp_str)
                if exp_dt > now:
                    conn.close()
                    return True

    conn.close()
    return False

# --- INTERACTIVE COMPONENTS ---

class CommandSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="🌟 All Commands (*)", value="*", description="Full access to ALL Premium commands"),
            discord.SelectOption(label="Spam Command", value="spam", description="Permission for Spam & Spamstop commands"),
            discord.SelectOption(label="Bot Customization", value="botprofile", description="Permission for !serverpfp, !servernick, !serverb"),
            discord.SelectOption(label="Mass Unban", value="massunban", description="Permission for Mass Unban command")
        ]
        # Multi-select fixed: max_values dynamically set to len(options)
        super().__init__(placeholder="Permissions select karein...", min_values=1, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        self.view.selected_cmds = self.values

class PlanCreateView(discord.ui.View):
    def __init__(self, plan_name, owner_id):
        super().__init__(timeout=120)
        self.plan_name = plan_name
        self.owner_id = owner_id
        self.selected_cmds = []
        self.add_item(CommandSelect())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ Access Denied!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm & Save Plan", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.selected_cmds:
            return await interaction.response.send_message("❌ Pehle permission select karein!", ephemeral=True)

        cmds_str = ",".join(self.selected_cmds)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO premium_plans (plan_name, allowed_commands) 
            VALUES (?, ?)
            ON CONFLICT(plan_name) DO UPDATE SET allowed_commands = excluded.allowed_commands
        ''', (self.plan_name, cmds_str))
        conn.commit()
        conn.close()

        embed = discord.Embed(
            title="✅ Premium Plan Created!",
            description=f"Plan **`{self.plan_name}`** saved with permissions:\n`{cmds_str}`",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)

# --- PREMIUM COG CLASS ---

class PremiumSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if not is_owner_check(ctx):
            await ctx.send("❌ **Access Denied!** Ye command sirf Bot Owner run kar sakta hai.")
            return False
        return True

    # 1. CREATE PLAN VIA UI
    @commands.command(name="pcreate", aliases=["pp"])
    async def pcreate(self, ctx, plan_name: str = None):
        if not plan_name:
            return await ctx.send("❌ Usage: `!pcreate <plan_name>`")
        
        view = PlanCreateView(plan_name.lower(), ctx.author.id)
        embed = discord.Embed(
            title=f"🔨 Creating Premium Plan: {plan_name}",
            description="Dropdown menu se permissions select karein (Multi-select enabled ya `*` select karein) aur Confirm click karein.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed, view=view)

    # 2. ADD COMMAND TO PLAN DIRECTLY VIA TEXT COMMAND
    @commands.command(name="pcommand")
    async def pcommand(self, ctx, plan_name: str = None, command_name: str = None):
        if not plan_name or not command_name:
            return await ctx.send("❌ Usage: `!pcommand <plan_name> <command_permission>`\nExample: `!pcommand diamond botprofile`")

        plan = plan_name.lower()
        cmd = command_name.lower()

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT allowed_commands FROM premium_plans WHERE plan_name = ?", (plan,))
        row = cursor.fetchone()

        if row:
            existing_cmds = [c.strip() for c in row[0].split(",") if c.strip()]
            if cmd not in existing_cmds:
                existing_cmds.append(cmd)
            new_cmds_str = ",".join(existing_cmds)
            cursor.execute("UPDATE premium_plans SET allowed_commands = ? WHERE plan_name = ?", (new_cmds_str, plan))
            msg = f"✅ Plan **`{plan}`** me **`{cmd}`** command permission add kar di gayi!\nExisting Permissions: `{new_cmds_str}`"
        else:
            cursor.execute("INSERT INTO premium_plans (plan_name, allowed_commands) VALUES (?, ?)", (plan, cmd))
            msg = f"✅ Naya Plan **`{plan}`** banaya gaya aur usme **`{cmd}`** permission add kar di gayi!"

        conn.commit()
        conn.close()
        await ctx.send(msg)

    # 3. GIVE PREMIUM ACCESS
    @commands.group(name="pgive", invoke_without_command=True)
    async def pgive(self, ctx):
        await ctx.send("❌ Usage:\n• `!pgive user @user <time> <plan>`\n• `!pgive server <plan> [time]`\n• `!pgive su @user <plan> [time]`")

    @pgive.command(name="user")
    async def pgive_user(self, ctx, member: discord.Member = None, time_str: str = None, plan_name: str = None):
        if not member or not time_str or not plan_name:
            return await ctx.send("❌ Usage: `!pgive user @user <time> <plan_name>`")
        
        exp_dt = parse_duration(time_str)
        if exp_dt == -1:
            return await ctx.send("❌ Invalid Time Format! (Use: `1d`, `1m`, `1y`, or `perm`)")

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO premium_holders (target_type, target_id, plan_name, expires_at) VALUES ('user', ?, ?, ?)",
                       (member.id, plan_name.lower(), exp_dt.isoformat() if exp_dt else None))
        conn.commit()
        conn.close()

        await ctx.send(f"✅ **{member.display_name}** ko Global Premium **`{plan_name}`** de diya gaya hai.")

    @pgive.command(name="server")
    async def pgive_server(self, ctx, plan_name: str = None, time_str: str = "perm"):
        if not plan_name:
            return await ctx.send("❌ Usage: `!pgive server <plan_name> [time]`")

        exp_dt = parse_duration(time_str)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO premium_holders (target_type, guild_id, plan_name, expires_at) VALUES ('server', ?, ?, ?)",
                       (ctx.guild.id, plan_name.lower(), exp_dt.isoformat() if exp_dt else None))
        conn.commit()
        conn.close()

        await ctx.send(f"🎉 Server **{ctx.guild.name}** ko Premium **`{plan_name}`** de diya gaya hai!")

    @pgive.command(name="su")
    async def pgive_su(self, ctx, member: discord.Member = None, plan_name: str = None, time_str: str = "perm"):
        if not member or not plan_name:
            return await ctx.send("❌ Usage: `!pgive su @user <plan_name> [time]`")

        exp_dt = parse_duration(time_str)
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO premium_holders (target_type, target_id, guild_id, plan_name, expires_at) VALUES ('su', ?, ?, ?, ?)",
                       (member.id, ctx.guild.id, plan_name.lower(), exp_dt.isoformat() if exp_dt else None))
        conn.commit()
        conn.close()

        await ctx.send(f"✅ **{member.display_name}** ko Single-Server Premium **`{plan_name}`** de diya gaya.")

    # 4. LIST PLANS
    @commands.command(name="plist")
    async def plist(self, ctx):
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT plan_name, allowed_commands FROM premium_plans")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return await ctx.send("📑 Koi Premium Plan nahi hai!")

        embed = discord.Embed(title="📜 Premium Plans List", color=discord.Color.purple())
        for name, cmds in rows:
            embed.add_field(name=f"🔹 {name.upper()}", value=f"**Permissions:** `{cmds}`", inline=False)
        await ctx.send(embed=embed)

    # 5. FULL PREMIUM HELP COMMAND
    @commands.command(name="phelp")
    async def phelp(self, ctx):
        embed = discord.Embed(
            title="👑 Premium System Management Help",
            description="Bot Owner Premium commands aur unka exact usage details niche diye gaye hain:",
            color=discord.Color.gold()
        )
        embed.add_field(
            name="🔨 `!pcreate <plan_name>`",
            value="Dropdown UI se plan create karta hai aur permissions assign karta hai.\n*Supports All Commands (`*`) or multiple selections.*",
            inline=False
        )
        embed.add_field(
            name="➕ `!pcommand <plan_name> <perm>`",
            value="Direct command se kisi plan me extra permission add karta hai.\n*Example:* `!pcommand diamond botprofile` or `!pcommand diamond *`",
            inline=False
        )
        embed.add_field(
            name="🎁 `!pgive user @user <time> <plan>`",
            value="Kisi specific User ko poore Bot ke har server ke liye Global Premium deta hai.\n*Time Format:* `1d`, `1m`, `1y`, `perm`",
            inline=False
        )
        embed.add_field(
            name="🏰 `!pgive server <plan> [time]`",
            value="Jis Server me command run hoga, us poore server ke sabhi members ko premium feature ka access de deta hai.",
            inline=False
        )
        embed.add_field(
            name="👤 `!pgive su @user <plan> [time]`",
            value="Single User (SU) ko SIRF specific server me access deta hai.",
            inline=False
        )
        embed.add_field(
            name="📜 `!plist`",
            value="Database me majood saare Premium Plans aur unki Command Permissions ki list dikhata hai.",
            inline=False
        )
        embed.add_field(
            name="🔑 Available Permission Keys",
            value="• `spam` : For !spam & !spamstop\n• `botprofile` : For !serverpfp, !servernick, !serverb\n• `*` : All commands access",
            inline=False
        )
        embed.set_footer(text="Bot Owner Only Commands", icon_url=self.bot.user.display_avatar.url)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(PremiumSystem(bot))

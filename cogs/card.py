import random
import os
import discord
from discord.ext import commands
from pymongo import MongoClient

# MongoDB Connection
MONGO_URI = os.getenv("MONGO_URI")
cluster = MongoClient(MONGO_URI)
db = cluster["discord_bot"]
card_config = db["card_config"]

# Male & Female Auto Titles / Descriptions
MALE_TITLES = [
    "HANDSOME BOY LEGEND",
    "SEXY BOY MONSTER",
    "SMARTEST KING",
    "CHAD SUPREME",
    "ULTIMATE ALPHA"
]

FEMALE_TITLES = [
    "PRETTY DIVA QUEEN",
    "CUTE BADDIE LEGEND",
    "ROYAL PRINCESS",
    "CHARMING ANGEL",
    "AESTHETIC GODDESS"
]

# Dropdown Menu to Select Role for Male/Female Configuration
class RoleSelectDropdown(discord.ui.Select):
    def __init__(self, roles: list, gender_type: str):
        self.gender_type = gender_type
        options = [
            discord.SelectOption(
                label=r.name[:100],
                value=str(r.id),
                description=f"ID: {r.id}"
            ) for r in roles[:25]
        ]
        super().__init__(
            placeholder=f"Select {gender_type.capitalize()} Role...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        role_id = int(self.values[0])
        role = interaction.guild.get_role(role_id)
        
        # Save to Database
        card_config.update_one(
            {"guild_id": interaction.guild.id},
            {"$set": {f"{self.gender_type}_role": role_id}},
            upsert=True
        )
        
        await interaction.response.send_message(
            f"✅ **{self.gender_type.capitalize()} Role** updated to: {role.mention}", 
            ephemeral=True
        )


class RoleSelectView(discord.ui.View):
    def __init__(self, roles: list, gender_type: str):
        super().__init__(timeout=60)
        self.add_item(RoleSelectDropdown(roles, gender_type))


# Main Card Cog
class ProfileCard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(name="card", invoke_without_command=True)
    async def card_group(self, ctx, member: discord.Member = None):
        member = member or ctx.author

        # Fetch Server Config from Database
        config = card_config.find_one({"guild_id": ctx.guild.id}) or {}
        male_role_id = config.get("male_role")
        female_role_id = config.get("female_role")

        # Check Gender Role
        user_role_ids = [r.id for r in member.roles]
        
        is_female = female_role_id in user_role_ids if female_role_id else False
        is_male = male_role_id in user_role_ids if male_role_id else False

        # Build Card Formatting based on Gender
        if is_female:
            title = f"✨ {random.choice(FEMALE_TITLES)} ✨"
            role_text = "FEMALE"
            color = 0xFF1493  # Beautiful Deep Pink / Rose Gold
        elif is_male:
            title = f"🔥 {random.choice(MALE_TITLES)} 🔥"
            role_text = "MALE"
            color = 0xD4AF37  # Dark Metallic Gold
        else:
            title = "⭐ MEMBER CARD ⭐"
            role_text = "NOT SET"
            color = 0x2B2D31  # Neutral Dark

        # Create Embed Card
        embed = discord.Embed(
            title=f"```\n{title}\n```",
            color=color
        )
        
        # User Avatar
        embed.set_thumbnail(url=member.display_avatar.url)
        
        # Details Field (Sirf Server Display Name)
        embed.add_field(
            name="📋 MEMBER DETAILS",
            value=f"**NAME:** {member.display_name}\n**ROLE:** {role_text}",
            inline=False
        )

        # Footer me Server Name (Jahan Image me Her Empire tha)
        embed.set_footer(
            text=f"👑 {ctx.guild.name.upper()}", 
            icon_url=ctx.guild.icon.url if ctx.guild.icon else None
        )

        await ctx.send(embed=embed)

    # Admin Setup Commands
    @card_group.group(name="role", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def role_group(self, ctx):
        await ctx.send("Usage: `!card role male` or `!card role female`")

    @role_group.command(name="male")
    @commands.has_permissions(administrator=True)
    async def set_male_role(self, ctx):
        roles = [r for r in ctx.guild.roles if not r.is_default() and not r.managed]
        if not roles:
            return await ctx.send("❌ No roles found!")

        view = RoleSelectView(roles, "male")
        await ctx.send("Select the Server **MALE** Role from menu:", view=view)

    @role_group.command(name="female")
    @commands.has_permissions(administrator=True)
    async def set_female_role(self, ctx):
        roles = [r for r in ctx.guild.roles if not r.is_default() and not r.managed]
        if not roles:
            return await ctx.send("❌ No roles found!")

        view = RoleSelectView(roles, "female")
        await ctx.send("Select the Server **FEMALE** Role from menu:", view=view)


async def setup(bot):
    await bot.add_cog(ProfileCard(bot))

import asyncio
import discord
from discord.ext import commands
import wavelink
import config

states = {}

class MusicState:
    def __init__(self):
        self.queue = []
        self.current = None
        self.text_channel = None
        self.volume = 100

def get_state(guild_id):
    if guild_id not in states:
        states[guild_id] = MusicState()
    return states[guild_id]

class MusicControls(discord.ui.View):
    def __init__(self, cog, guild_id):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild or interaction.guild.id != self.guild_id:
            await interaction.response.send_message("This music panel belongs to another server.", ephemeral=True)
            return False
        if not interaction.user.voice:
            await interaction.response.send_message("You must be in a voice channel to use the music controls.", ephemeral=True)
            return False
        vc = interaction.guild.voice_client
        if not vc:
            await interaction.response.send_message("I am not connected to a voice channel.", ephemeral=True)
            return False
        if interaction.user.voice.channel != vc.channel:
            await interaction.response.send_message("You must be in my voice channel to use these controls.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Resume", style=discord.ButtonStyle.secondary, row=0)
    async def resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        await vc.pause(False)
        await interaction.response.send_message("▶️ Resumed.", ephemeral=True)

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.secondary, row=0)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        await vc.pause(True)
        await interaction.response.send_message("⏸️ Paused.", ephemeral=True)

    @discord.ui.button(label="Toggle", style=discord.ButtonStyle.secondary, row=0)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        await vc.pause(not vc.paused)
        await interaction.response.send_message("▶️ Resumed." if vc.paused is False else "⏸️ Paused.", ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, row=1)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.skip_track(interaction.guild)
        await interaction.response.send_message("⏭️ Skipped.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.secondary, row=1)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        state = get_state(interaction.guild.id)
        state.queue.clear()
        state.current = None
        await vc.stop()
        await interaction.response.send_message("⏹️ Stopped and queue cleared.", ephemeral=True)

    @discord.ui.button(label="Queue", style=discord.ButtonStyle.secondary, row=2)
    async def queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = get_state(interaction.guild.id)
        if not state.queue:
            text = "📋 The queue is empty."
        else:
            lines = [f"**{i}.** {track.title}" for i, track in enumerate(state.queue[:10], 1)]
            text = "📋 **Queue**\n" + "\n".join(lines)
            if len(state.queue) > 10:
                text += f"\n…and {len(state.queue) - 10} more."
        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(label="Vol +10", style=discord.ButtonStyle.secondary, row=2)
    async def volume_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = get_state(interaction.guild.id)
        state.volume = min(200, state.volume + 10)
        await interaction.guild.voice_client.set_volume(state.volume)
        await interaction.response.send_message(f"🔊 Volume: **{state.volume}%**", ephemeral=True)

    @discord.ui.button(label="Vol -10", style=discord.ButtonStyle.secondary, row=2)
    async def volume_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = get_state(interaction.guild.id)
        state.volume = max(0, state.volume - 10)
        await interaction.guild.voice_client.set_volume(state.volume)
        await interaction.response.send_message(f"🔉 Volume: **{state.volume}%**", ephemeral=True)

    @discord.ui.button(label="10s Back", style=discord.ButtonStyle.secondary, row=3)
    async def back_10(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        position = max(0, vc.position - 10_000)
        await vc.seek(position)
        await interaction.response.send_message("⏪ 10 seconds back.", ephemeral=True)

    @discord.ui.button(label="10s Forward", style=discord.ButtonStyle.secondary, row=3)
    async def forward_10(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        duration = getattr(vc.current, "length", 0) or 0
        position = min(duration, vc.position + 10_000) if duration else vc.position + 10_000
        await vc.seek(position)
        await interaction.response.send_message("⏩ 10 seconds forward.", ephemeral=True)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.loop.create_task(self.setup_lavalink())

    async def setup_lavalink(self):
        await self.bot.wait_until_ready()

        host = getattr(config, 'LAVALINK_HOST', 'in-1.visihost.in')
        port = getattr(config, 'LAVALINK_PORT', 3002)
        password = getattr(config, 'LAVALINK_PASSWORD', 'pvt@1211')

        node_uri = f"http://{host}:{port}"
        node = wavelink.Node(identifier="VisihostNode", uri=node_uri, password=password)

        try:
            await wavelink.Pool.connect(nodes=[node], client=self.bot)
        except Exception as e:
            print(f"Lavalink connect call error: {e}")

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f"✅ Node {payload.node.identifier} READY!")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player = payload.player
        if not player or not player.guild:
            return
        state = get_state(player.guild.id)
        if state.queue:
            track = state.queue.pop(0)
            state.current = track
            await player.play(track)
            if state.text_channel:
                await self.send_now_playing(state.text_channel, track, state)
        else:
            state.current = None

    async def skip_track(self, guild):
        vc = guild.voice_client
        if not vc:
            return
        state = get_state(guild.id)
        if state.queue:
            track = state.queue.pop(0)
            state.current = track
            await vc.play(track)
            if state.text_channel:
                await self.send_now_playing(state.text_channel, track, state)
        else:
            state.current = None
            await vc.stop()

    async def send_now_playing(self, channel, track, state):
        embed = discord.Embed(title=track.title, color=discord.Color.red())
        artwork = getattr(track, "artwork_url", None)
        if artwork:
            embed.set_image(url=artwork)
        embed.set_footer(text=f"Volume: {state.volume}% • Use the buttons below to control playback")
        await channel.send(embed=embed, view=MusicControls(self, channel.guild.id))

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str):
        if not ctx.author.voice:
            return await ctx.send("❌ You must be in a voice channel!")

        if not wavelink.Pool.nodes:
            return await ctx.send("❌ Lavalink pool is empty. Node connect nahi hua hai.")

        vc: wavelink.Player = ctx.voice_client
        if not vc:
            try:
                vc = await ctx.author.voice.channel.connect(cls=wavelink.Player, self_deaf=True)
            except Exception as e:
                return await ctx.send(f"❌ Join error: `{e}`")

        state = get_state(ctx.guild.id)
        state.text_channel = ctx.channel

        try:
            tracks: wavelink.Search = await wavelink.Playable.search(query)
            if not tracks:
                return await ctx.send("❌ No tracks found!")

            track = tracks[0] if not isinstance(tracks, wavelink.Playlist) else tracks.tracks[0]

            if not vc.current:
                state.current = track
                await vc.play(track)
                await vc.set_volume(state.volume)
                await self.send_now_playing(ctx.channel, track, state)
            else:
                state.queue.append(track)
                await ctx.send(f"📋 Added to queue: **{track.title}**")

        except Exception as e:
            await ctx.send(f"❌ Play Error: `{e}`")

async def setup(bot):
    await bot.add_cog(Music(bot))

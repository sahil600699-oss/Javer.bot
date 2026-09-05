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

class MusicControlView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="Pause/Resume", style=discord.ButtonStyle.primary, emoji="⏯️")
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.current:
            return await interaction.response.send_message("❌ Nothing is playing!", ephemeral=True)

        await vc.pause(not vc.paused)
        status = "paused" if vc.paused else "resumed"
        await interaction.response.send_message(f"▶️ Playback {status}!", ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, emoji="⏭️")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.current:
            return await interaction.response.send_message("❌ Nothing to skip!", ephemeral=True)
        await vc.skip()
        await interaction.response.send_message("⏩ Skipped!", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc: wavelink.Player = interaction.guild.voice_client
        state = get_state(self.guild_id)
        state.queue.clear()
        state.current = None
        if vc:
            await vc.disconnect()
        await interaction.response.send_message("⏹️ Playback stopped!", ephemeral=True)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        asyncio.create_task(self.connect_lavalink())

    async def connect_lavalink(self):
        host = getattr(config, 'LAVALINK_HOST', 'in-1.visihost.in')
        port = getattr(config, 'LAVALINK_PORT', 3002)
        password = getattr(config, 'LAVALINK_PASSWORD', 'pvt@1211')
        secure = getattr(config, 'LAVALINK_SECURE', False)

        protocol = "https" if secure else "http"
        node_uri = f"{protocol}://{host}:{port}"
        
        nodes = [wavelink.Node(uri=node_uri, password=password)]
        try:
            await wavelink.Pool.connect(nodes=nodes, client=self.bot, inactive_player_timeout=300)
        except Exception as e:
            print(f"⚠️ Lavalink connection attempt error: {e}")

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f"✅ Lavalink Node '{payload.node.identifier}' is ready and connected!")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player = payload.player
        if not player or not player.guild:
            return
        
        state = get_state(player.guild.id)
        if state.queue:
            next_track = state.queue.pop(0)
            state.current = next_track
            await player.play(next_track)

            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"**[{next_track.title}]({next_track.uri})**",
                color=discord.Color.blurple()
            )
            if state.text_channel:
                await state.text_channel.send(embed=embed, view=MusicControlView(player.guild.id))
        else:
            state.current = None

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str):
        if not ctx.author.voice:
            return await ctx.send("❌ You must be in a voice channel!")

        vc: wavelink.Player = ctx.voice_client
        if not vc:
            try:
                vc = await ctx.author.voice.channel.connect(cls=wavelink.Player, self_deaf=True)
            except Exception as e:
                return await ctx.send(f"❌ Failed to join voice channel: {e}")

        state = get_state(ctx.guild.id)
        state.text_channel = ctx.channel

        try:
            # Wavelink 3.x Search
            tracks: wavelink.Search = await wavelink.Playable.search(query)
            if not tracks:
                return await ctx.send("❌ No results found for your query!")

            if isinstance(tracks, wavelink.Playlist):
                added_count = len(tracks.tracks)
                if not vc.current:
                    first_track = tracks.tracks[0]
                    state.queue.extend(tracks.tracks[1:])
                    state.current = first_track
                    await vc.play(first_track)
                    await ctx.send(f"🎶 Playing: **{first_track.title}** (Added {added_count - 1} tracks to queue)", view=MusicControlView(ctx.guild.id))
                else:
                    state.queue.extend(tracks.tracks)
                    await ctx.send(f"📋 Added **{added_count} tracks** to the queue!")
            else:
                track = tracks[0]
                if not vc.current:
                    state.current = track
                    await vc.play(track)
                    await ctx.send(f"🎶 Now Playing: **{track.title}**", view=MusicControlView(ctx.guild.id))
                else:
                    state.queue.append(track)
                    await ctx.send(f"📋 Added to queue: **{track.title}**")

        except Exception as e:
            await ctx.send(f"❌ Music Error: `{str(e)}`")

    @commands.command(name="stop")
    async def stop(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        state = get_state(ctx.guild.id)
        state.queue.clear()
        state.current = None
        if vc:
            await vc.disconnect()
        await ctx.send("⏹️ Stopped playback and cleared queue!")

    @commands.command(name="skip", aliases=["s"])
    async def skip(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        if not vc or not vc.current:
            return await ctx.send("❌ Nothing playing right now!")
        await vc.skip()
        await ctx.send("⏩ Skipped!")

async def setup(bot):
    await bot.add_cog(Music(bot))
    

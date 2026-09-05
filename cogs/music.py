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
        self.playing = False
        self.paused = False

def get_state(guild_id):
    if guild_id not in states:
        states[guild_id] = MusicState()
    return states[guild_id]

class MusicControlView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.primary, emoji="⏸️")
    async def pause_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc: wavelink.Player = interaction.guild.voice_client
        state = get_state(self.guild_id)
        if not vc or not vc.current:
            return await interaction.response.send_message("❌ Nothing is playing!", ephemeral=True)

        if vc.paused:
            await vc.pause(False)
            state.paused = False
            button.label = "Pause"
            button.emoji = "⏸️"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("▶️ Playback resumed!", ephemeral=True)
        else:
            await vc.pause(True)
            state.paused = True
            button.label = "Resume"
            button.emoji = "▶️"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("⏸️ Playback paused!", ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, emoji="⏭️")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc: wavelink.Player = interaction.guild.voice_client
        if not vc or not vc.current:
            return await interaction.response.send_message("❌ Nothing to skip!", ephemeral=True)
        await vc.skip()
        await interaction.response.send_message("⏩ Skipped!", ephemeral=True)

    @discord.ui.button(label="Queue", style=discord.ButtonStyle.secondary, emoji="📋")
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = get_state(self.guild_id)
        if not state.queue:
            return await interaction.response.send_message("📋 Queue is empty!", ephemeral=True)
        description = "\n".join(f"**{i+1}.** {x.title}" for i, x in enumerate(state.queue[:25]))
        await interaction.response.send_message(
            embed=discord.Embed(title="🎶 Music Queue", description=description, color=discord.Color.blurple()),
            ephemeral=True
        )

    @discord.ui.button(label="Vol -", style=discord.ButtonStyle.secondary, emoji="🔉")
    async def volume_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = get_state(self.guild_id)
        vc: wavelink.Player = interaction.guild.voice_client
        state.volume = max(0, state.volume - 10)
        if vc:
            await vc.set_volume(state.volume)
        await interaction.response.send_message(f"🔉 Volume: **{state.volume}%**", ephemeral=True)

    @discord.ui.button(label="Vol +", style=discord.ButtonStyle.secondary, emoji="🔊")
    async def volume_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = get_state(self.guild_id)
        vc: wavelink.Player = interaction.guild.voice_client
        state.volume = min(200, state.volume + 10)
        if vc:
            await vc.set_volume(state.volume)
        await interaction.response.send_message(f"🔊 Volume: **{state.volume}%**", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = get_state(self.guild_id)
        vc: wavelink.Player = interaction.guild.voice_client
        state.queue.clear()
        state.current = None
        state.playing = False
        state.paused = False
        if vc:
            await vc.disconnect()
        await interaction.response.send_message("⏹️ Playback stopped and disconnected!", ephemeral=True)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # Event loop ko freeze hone se bachane ke liye background task chalaya hai
        asyncio.create_task(self.connect_lavalink())

    async def connect_lavalink(self):
        host = getattr(config, 'LAVALINK_HOST', '127.0.0.1')
        port = getattr(config, 'LAVALINK_PORT', 2333)
        password = getattr(config, 'LAVALINK_PASSWORD', 'youshallnotpass')
        secure = getattr(config, 'LAVALINK_SECURE', False)

        protocol = "https" if secure else "http"
        node_uri = f"{protocol}://{host}:{port}"
        
        nodes = [wavelink.Node(uri=node_uri, password=password)]
        
        try:
            await wavelink.Pool.connect(nodes=nodes, client=self.bot, inactive_player_timeout=300)
            print("✅ Lavalink pool initialized.")
        except Exception as e:
            print(f"⚠️ Lavalink failed to connect: {e}")

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f"✅ Lavalink Node '{payload.node.identifier}' connected successfully!")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        player = payload.player
        if not player or not player.guild:
            return
        state = get_state(player.guild.id)
        
        if state.queue:
            next_track = state.queue.pop(0)
            state.current = next_track
            state.playing = True
            await player.play(next_track)

            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"**[{next_track.title}]({next_track.uri})**",
                color=discord.Color.blurple()
            )
            embed.add_field(name="👤 Author", value=getattr(next_track, "author", "Unknown"), inline=True)
            if hasattr(next_track, "artwork") and next_track.artwork:
                embed.set_thumbnail(url=next_track.artwork)

            if state.text_channel:
                await state.text_channel.send(embed=embed, view=MusicControlView(player.guild.id))
        else:
            state.playing = False
            state.current = None

    @commands.command(name="join")
    async def join(self, ctx):
        if not ctx.author.voice:
            return await ctx.send("❌ You must join a voice channel first!")
        if ctx.voice_client:
            return await ctx.send("⚠️ I am already connected!")
        await ctx.author.voice.channel.connect(cls=wavelink.Player, self_deaf=True)
        await ctx.send(f"🔊 Joined **{ctx.author.voice.channel.name}**!")

    @commands.command(name="leave")
    async def leave(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        if not vc:
            return await ctx.send("❌ I am not in a voice channel!")
        state = get_state(ctx.guild.id)
        state.queue.clear()
        state.current = None
        state.playing = False
        state.paused = False
        await vc.disconnect()
        await ctx.send("👋 Disconnected from voice channel!")

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx, *, query: str):
        if not ctx.author.voice:
            return await ctx.send("❌ You must join a voice channel first!")
        
        vc: wavelink.Player = ctx.voice_client
        if not vc:
            vc = await ctx.author.voice.channel.connect(cls=wavelink.Player, self_deaf=True)
        elif vc.channel != ctx.author.voice.channel:
            return await ctx.send("❌ You must be in my voice channel!")

        state = get_state(ctx.guild.id)
        state.text_channel = ctx.channel

        await ctx.send("🔎 Searching on Lavalink...")
        tracks: wavelink.Search = await wavelink.Playable.search(query)
        if not tracks:
            return await ctx.send("❌ No playable track or playlist found!")

        if isinstance(tracks, wavelink.Playlist):
            added_count = len(tracks.tracks)
            if not vc.current and not state.playing:
                first_track = tracks.tracks[0]
                state.queue.extend(tracks.tracks[1:])
                state.current = first_track
                state.playing = True
                await vc.play(first_track)
                await vc.set_volume(state.volume)
                
                embed = discord.Embed(
                    title="🎵 Now Playing",
                    description=f"**[{first_track.title}]({first_track.uri})**",
                    color=discord.Color.blurple()
                )
                embed.add_field(name="👤 Author", value=getattr(first_track, "author", "Unknown"), inline=True)
                if hasattr(first_track, "artwork") and first_track.artwork:
                    embed.set_thumbnail(url=first_track.artwork)
                await ctx.send(embed=embed, view=MusicControlView(ctx.guild.id))
            else:
                state.queue.extend(tracks.tracks)

            return await ctx.send(f"📋 Added **{added_count} tracks** from the playlist to queue!")

        track = tracks[0]
        if not vc.current and not state.playing:
            state.current = track
            state.playing = True
            await vc.play(track)
            await vc.set_volume(state.volume)

            embed = discord.Embed(
                title="🎵 Now Playing",
                description=f"**[{track.title}]({track.uri})**",
                color=discord.Color.blurple()
            )
            embed.add_field(name="👤 Author", value=getattr(track, "author", "Unknown"), inline=True)
            if hasattr(track, "artwork") and track.artwork:
                embed.set_thumbnail(url=track.artwork)
            await ctx.send(embed=embed, view=MusicControlView(ctx.guild.id))
        else:
            state.queue.append(track)
            await ctx.send(f"📋 Added to queue: **{track.title}**")

    @commands.command(name="pause")
    async def pause(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        if not vc or not vc.current:
            return await ctx.send("❌ Nothing is playing!")
        await vc.pause(True)
        get_state(ctx.guild.id).paused = True
        await ctx.send("⏸️ Playback paused!")

    @commands.command(name="resume")
    async def resume(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        if not vc or not vc.paused:
            return await ctx.send("❌ Playback is not paused!")
        await vc.pause(False)
        get_state(ctx.guild.id).paused = False
        await ctx.send("▶️ Playback resumed!")

    @commands.command(name="skip", aliases=["s"])
    async def skip(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        if not vc or not vc.current:
            return await ctx.send("❌ Nothing to skip!")
        await vc.skip()
        await ctx.send("⏩ Skipped to the next track!")

    @commands.command(name="stop")
    async def stop(self, ctx):
        vc: wavelink.Player = ctx.voice_client
        state = get_state(ctx.guild.id)
        if not vc:
            return await ctx.send("❌ I am not connected!")
        state.queue.clear()
        state.current = None
        state.playing = False
        state.paused = False
        await vc.disconnect()
        await ctx.send("⏹️ Stopped playback and disconnected!")

    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx):
        state = get_state(ctx.guild.id)
        if not state.queue:
            return await ctx.send("📋 The queue is currently empty!")
        description = "\n".join(f"**{i+1}.** {x.title}" for i, x in enumerate(state.queue[:25]))
        await ctx.send(embed=discord.Embed(title="🎶 Music Queue", description=description, color=discord.Color.blurple()))

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying(self, ctx):
        state = get_state(ctx.guild.id)
        vc: wavelink.Player = ctx.voice_client
        if not vc or not vc.current:
            return await ctx.send("❌ Nothing is currently playing!")
        track = vc.current
        embed = discord.Embed(
            title="🎵 Now Playing",
            description=f"**[{track.title}]({track.uri})**",
            color=discord.Color.blurple()
        )
        embed.add_field(name="👤 Author", value=getattr(track, "author", "Unknown"), inline=True)
        embed.add_field(name="🔊 Volume", value=f"{state.volume}%", inline=True)
        if hasattr(track, "artwork") and track.artwork:
            embed.set_thumbnail(url=track.artwork)
        await ctx.send(embed=embed)

    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx, amount: int):
        if not 0 <= amount <= 200:
            return await ctx.send("❌ Volume must be between **0% and 200%**.")
        state = get_state(ctx.guild.id)
        state.volume = amount
        vc: wavelink.Player = ctx.voice_client
        if vc:
            await vc.set_volume(amount)
        await ctx.send(f"🔊 Volume set to **{amount}%**!")

    @commands.command(name="clearqueue", aliases=["cq"])
    async def clearqueue(self, ctx):
        state = get_state(ctx.guild.id)
        count = len(state.queue)
        state.queue.clear()
        await ctx.send(f"🗑️ Cleared **{count} tracks** from the queue!")

    @commands.command(name="musichelp", aliases=["mhelp"])
    async def musichelp(self, ctx):
        embed = discord.Embed(
            title="🎵 Music Commands (Lavalink Powered)",
            description="`!join` — Join voice channel\n`!leave` — Leave voice channel\n`!play <song/URL>` — Search/Play song or playlist\n`!pause` — Pause\n`!resume` — Resume\n`!skip` — Skip\n`!stop` — Stop and disconnect\n`!queue` — Queue\n`!nowplaying` — Current song\n`!volume <0-200>` — Volume\n`!clearqueue` — Clear queue",
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Music(bot))
                

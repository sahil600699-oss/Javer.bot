import asyncio
import re
import base64
import discord
from discord.ext import commands
import yt_dlp
import aiohttp

YTDLP_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "source_address": "0.0.0.0",
}

YTDLP_PLAYLIST_OPTIONS = {
    "extract_flat": True,
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "ignoreerrors": True,
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

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

def is_youtube_playlist(url):
    return ("youtube.com/playlist" in url or
            ("youtube.com/watch" in url and "list=" in url) or
            ("youtu.be/" in url and "list=" in url))

def is_spotify_url(url):
    return "open.spotify.com/" in url

def spotify_type_and_id(url):
    match = re.search(r"open\.spotify\.com/(track|playlist|album)/([A-Za-z0-9]+)", url)
    return (match.group(1), match.group(2)) if match else (None, None)

async def get_audio(query):
    loop = asyncio.get_running_loop()
    def extract():
        options = dict(YTDLP_OPTIONS)
        if not query.startswith(("http://", "https://")):
            options["default_search"] = "ytsearch1"
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(query, download=False)
            if not info:
                return None
            if "entries" in info:
                entries = [x for x in info["entries"] if x]
                if not entries:
                    return None
                info = entries[0]
            return {
                "title": info.get("title", "Unknown"),
                "url": info.get("url"),
                "webpage_url": info.get("webpage_url", query),
                "thumbnail": info.get("thumbnail"),
                "duration": info.get("duration", 0) or 0,
                "author": info.get("uploader", "Unknown"),
            }
    return await loop.run_in_executor(None, extract)

async def get_youtube_playlist(url):
    loop = asyncio.get_running_loop()
    def extract_playlist():
        with yt_dlp.YoutubeDL(YTDLP_PLAYLIST_OPTIONS) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return []
            result = []
            for entry in info.get("entries", []):
                if not entry:
                    continue
                video_id = entry.get("id")
                webpage_url = entry.get("url")
                if video_id:
                    webpage_url = f"https://www.youtube.com/watch?v={video_id}"
                if webpage_url:
                    result.append({"title": entry.get("title", "Unknown"), "webpage_url": webpage_url})
            return result
    return await loop.run_in_executor(None, extract_playlist)

async def get_spotify_token():
    try:
        import config
        client_id = getattr(config, "SPOTIFY_CLIENT_ID", None)
        client_secret = getattr(config, "SPOTIFY_CLIENT_SECRET", None)
        if not client_id or not client_secret:
            return None
        auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://accounts.spotify.com/api/token",
                headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
                data={"grant_type": "client_credentials"}
            ) as response:
                if response.status != 200:
                    return None
                return (await response.json()).get("access_token")
    except Exception as e:
        print(f"Spotify token error: {e}")
        return None

async def get_spotify_tracks(url):
    item_type, item_id = spotify_type_and_id(url)
    if not item_type or not item_id:
        return []
    token = await get_spotify_token()
    if not token:
        return []
    headers = {"Authorization": f"Bearer {token}"}
    tracks = []
    async with aiohttp.ClientSession() as session:
        if item_type == "track":
            endpoint = f"https://api.spotify.com/v1/tracks/{item_id}"
            async with session.get(endpoint, headers=headers) as response:
                if response.status != 200:
                    return []
                data = await response.json()
                artists = ", ".join(a["name"] for a in data.get("artists", []))
                if data.get("name"):
                    tracks.append(f"{data['name']} {artists}")
        elif item_type == "playlist":
            endpoint = f"https://api.spotify.com/v1/playlists/{item_id}/tracks?limit=100"
            while endpoint:
                async with session.get(endpoint, headers=headers) as response:
                    if response.status != 200:
                        break
                    data = await response.json()
                    for item in data.get("items", []):
                        track = item.get("track")
                        if not track:
                            continue
                        name = track.get("name", "")
                        artists = ", ".join(a["name"] for a in track.get("artists", []))
                        if name:
                            tracks.append(f"{name} {artists}")
                    endpoint = data.get("next")
        elif item_type == "album":
            endpoint = f"https://api.spotify.com/v1/albums/{item_id}/tracks?limit=50"
            while endpoint:
                async with session.get(endpoint, headers=headers) as response:
                    if response.status != 200:
                        break
                    data = await response.json()
                    for track in data.get("items", []):
                        name = track.get("name", "")
                        artists = ", ".join(a["name"] for a in track.get("artists", []))
                        if name:
                            tracks.append(f"{name} {artists}")
                    endpoint = data.get("next")
    return tracks

class AudioSource(discord.PCMVolumeTransformer):
    def __init__(self, source, volume=1.0):
        super().__init__(source, volume=volume)

class MusicControlView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.primary, emoji="⏸️")
    async def pause_button(self, interaction, button):
        state = get_state(self.guild_id)
        vc = interaction.guild.voice_client
        if not vc or not state.current:
            return await interaction.response.send_message("❌ Nothing is playing!", ephemeral=True)
        if vc.is_paused():
            vc.resume(); state.paused = False; button.label = "Pause"; button.emoji = "⏸️"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("▶️ Playback resumed!", ephemeral=True)
        elif vc.is_playing():
            vc.pause(); state.paused = True; button.label = "Resume"; button.emoji = "▶️"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send("⏸️ Playback paused!", ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, emoji="⏭️")
    async def skip_button(self, interaction, button):
        vc = interaction.guild.voice_client
        if not vc or not vc.is_playing():
            return await interaction.response.send_message("❌ Nothing to skip!", ephemeral=True)
        vc.stop()
        await interaction.response.send_message("⏩ Skipped!", ephemeral=True)

    @discord.ui.button(label="Queue", style=discord.ButtonStyle.secondary, emoji="📋")
    async def queue_button(self, interaction, button):
        state = get_state(self.guild_id)
        if not state.queue:
            return await interaction.response.send_message("📋 Queue is empty!", ephemeral=True)
        description = "\n".join(f"**{i+1}.** {x['title']}" for i, x in enumerate(state.queue[:25]))
        await interaction.response.send_message(embed=discord.Embed(title="🎶 Music Queue", description=description, color=discord.Color.blurple()), ephemeral=True)

    @discord.ui.button(label="Vol -", style=discord.ButtonStyle.secondary, emoji="🔉")
    async def volume_down(self, interaction, button):
        state = get_state(self.guild_id); vc = interaction.guild.voice_client
        state.volume = max(0, state.volume - 10)
        if vc and vc.source and hasattr(vc.source, "volume"):
            vc.source.volume = state.volume / 100
        await interaction.response.send_message(f"🔉 Volume: **{state.volume}%**", ephemeral=True)

    @discord.ui.button(label="Vol +", style=discord.ButtonStyle.secondary, emoji="🔊")
    async def volume_up(self, interaction, button):
        state = get_state(self.guild_id); vc = interaction.guild.voice_client
        state.volume = min(200, state.volume + 10)
        if vc and vc.source and hasattr(vc.source, "volume"):
            vc.source.volume = state.volume / 100
        await interaction.response.send_message(f"🔊 Volume: **{state.volume}%**", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️")
    async def stop_button(self, interaction, button):
        state = get_state(self.guild_id); vc = interaction.guild.voice_client
        state.queue.clear(); state.current = None; state.playing = False; state.paused = False
        if vc:
            vc.stop()
            await vc.disconnect()
        await interaction.response.send_message("⏹️ Playback stopped and disconnected!", ephemeral=True)

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def play_next(self, guild):
        state = get_state(guild.id)
        vc = guild.voice_client
        if not vc:
            state.playing = False; state.current = None; return
        if not state.queue:
            state.playing = False; state.current = None; state.paused = False
            return
        track = state.queue.pop(0)
        state.current = track; state.playing = True; state.paused = False
        try:
            fresh = await get_audio(track["webpage_url"])
            if not fresh or not fresh.get("url"):
                raise RuntimeError("Could not access audio source")
            state.current = fresh
            source = AudioSource(discord.FFmpegPCMAudio(fresh["url"], **FFMPEG_OPTIONS), state.volume / 100)
            def after_play(error):
                if error:
                    print(f"FFmpeg error: {error}")
                asyncio.run_coroutine_threadsafe(self.play_next(guild), self.bot.loop)
            vc.play(source, after=after_play)
            embed = discord.Embed(title="🎵 Now Playing", description=f"**[{fresh['title']}]({fresh['webpage_url']})**", color=discord.Color.blurple())
            embed.add_field(name="👤 Author", value=fresh.get("author", "Unknown"), inline=True)
            if fresh.get("thumbnail"):
                embed.set_thumbnail(url=fresh["thumbnail"])
            if state.text_channel:
                await state.text_channel.send(embed=embed, view=MusicControlView(guild.id))
        except Exception as e:
            print(f"Playback error: {type(e).__name__}: {e}")
            state.playing = False; state.current = None
            if state.text_channel:
                await state.text_channel.send("❌ I couldn't play that track. Trying the next song...")
            await self.play_next(guild)

    @commands.command(name="join")
    async def join(self, ctx):
        if not ctx.author.voice:
            return await ctx.send("❌ You must join a voice channel first!")
        if ctx.voice_client:
            return await ctx.send("⚠️ I am already connected!")
        await ctx.author.voice.channel.connect(self_deaf=True)
        await ctx.send(f"🔊 Joined **{ctx.author.voice.channel.name}**!")

    @commands.command(name="leave")
    async def leave(self, ctx):
        vc = ctx.voice_client
        if not vc:
            return await ctx.send("❌ I am not in a voice channel!")
        state = get_state(ctx.guild.id)
        state.queue.clear(); state.current = None; state.playing = False; state.paused = False
        vc.stop(); await vc.disconnect()
        await ctx.send("👋 Disconnected from voice channel!")

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx, *, query):
        if not ctx.author.voice:
            return await ctx.send("❌ You must join a voice channel first!")
        vc = ctx.voice_client
        if not vc:
            vc = await ctx.author.voice.channel.connect(self_deaf=True)
        elif vc.channel != ctx.author.voice.channel:
            return await ctx.send("❌ You must be in my voice channel!")
        state = get_state(ctx.guild.id)
        state.text_channel = ctx.channel
        query = query.strip()

        if is_spotify_url(query):
            await ctx.send("🔎 Reading Spotify playlist...")
            spotify_tracks = await get_spotify_tracks(query)
            if not spotify_tracks:
                return await ctx.send("❌ Spotify could not be read. Add Spotify API credentials to `config.py`.")
            added = 0
            for text in spotify_tracks:
                try:
                    track = await get_audio(text)
                    if track:
                        state.queue.append(track); added += 1
                except Exception as e:
                    print(f"Spotify track error: {e}")
            if not state.playing and state.queue:
                await self.play_next(ctx.guild)
            return await ctx.send(f"🎵 Added **{added}** Spotify tracks to the queue!")

        if query.startswith(("http://", "https://")) and is_youtube_playlist(query):
            await ctx.send("📋 Loading YouTube playlist...")
            playlist = await get_youtube_playlist(query)
            if not playlist:
                return await ctx.send("❌ No tracks found in this playlist!")
            added = 0
            for item in playlist:
                try:
                    track = await get_audio(item["webpage_url"])
                    if track:
                        state.queue.append(track); added += 1
                except Exception as e:
                    print(f"Playlist track error: {e}")
            if not state.playing and state.queue:
                await self.play_next(ctx.guild)
            return await ctx.send(f"📋 Added **{added} tracks** from the YouTube playlist!")

        await ctx.send("🔎 Searching...")
        try:
            track = await get_audio(query)
        except Exception as e:
            print(f"Search error: {type(e).__name__}: {e}")
            return await ctx.send("❌ I couldn't find or access that audio source.")
        if not track or not track.get("url"):
            return await ctx.send("❌ No playable track found!")
        state.queue.append(track)
        if state.playing:
            await ctx.send(f"📋 Added to queue: **{track['title']}**")
        else:
            await self.play_next(ctx.guild)

    @commands.command(name="pause")
    async def pause(self, ctx):
        vc = ctx.voice_client
        if not vc or not vc.is_playing():
            return await ctx.send("❌ Nothing is playing!")
        vc.pause(); get_state(ctx.guild.id).paused = True
        await ctx.send("⏸️ Playback paused!")

    @commands.command(name="resume")
    async def resume(self, ctx):
        vc = ctx.voice_client
        if not vc or not vc.is_paused():
            return await ctx.send("❌ Playback is not paused!")
        vc.resume(); get_state(ctx.guild.id).paused = False
        await ctx.send("▶️ Playback resumed!")

    @commands.command(name="skip", aliases=["s"])
    async def skip(self, ctx):
        vc = ctx.voice_client
        if not vc or not vc.is_playing():
            return await ctx.send("❌ Nothing to skip!")
        vc.stop()
        await ctx.send("⏩ Skipped to the next track!")

    @commands.command(name="stop")
    async def stop(self, ctx):
        vc = ctx.voice_client; state = get_state(ctx.guild.id)
        if not vc:
            return await ctx.send("❌ I am not connected!")
        state.queue.clear(); state.current = None; state.playing = False; state.paused = False
        vc.stop(); await vc.disconnect()
        await ctx.send("⏹️ Stopped playback and disconnected!")

    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx):
        state = get_state(ctx.guild.id)
        if not state.queue:
            return await ctx.send("📋 The queue is currently empty!")
        description = "\n".join(f"**{i+1}.** {x['title']}" for i, x in enumerate(state.queue[:25]))
        await ctx.send(embed=discord.Embed(title="🎶 Music Queue", description=description, color=discord.Color.blurple()))

    @commands.command(name="nowplaying", aliases=["np"])
    async def nowplaying(self, ctx):
        state = get_state(ctx.guild.id)
        if not state.current:
            return await ctx.send("❌ Nothing is currently playing!")
        track = state.current
        embed = discord.Embed(title="🎵 Now Playing", description=f"**[{track['title']}]({track['webpage_url']})**", color=discord.Color.blurple())
        embed.add_field(name="👤 Author", value=track.get("author", "Unknown"), inline=True)
        embed.add_field(name="🔊 Volume", value=f"{state.volume}%", inline=True)
        if track.get("thumbnail"):
            embed.set_thumbnail(url=track["thumbnail"])
        await ctx.send(embed=embed)

    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx, amount: int):
        if not 0 <= amount <= 200:
            return await ctx.send("❌ Volume must be between **0% and 200%**.")
        state = get_state(ctx.guild.id); state.volume = amount
        vc = ctx.voice_client
        if vc and vc.source and hasattr(vc.source, "volume"):
            vc.source.volume = amount / 100
        await ctx.send(f"🔊 Volume set to **{amount}%**!")

    @commands.command(name="clearqueue", aliases=["cq"])
    async def clearqueue(self, ctx):
        state = get_state(ctx.guild.id); count = len(state.queue); state.queue.clear()
        await ctx.send(f"🗑️ Cleared **{count} tracks** from the queue!")

    @commands.command(name="musichelp", aliases=["mhelp"])
    async def musichelp(self, ctx):
        embed = discord.Embed(
            title="🎵 Music Commands",
            description="`!join` — Join voice channel\n`!leave` — Leave voice channel\n`!play <song>` — Search and play\n`!play <URL>` — Play URL\n`!play <YouTube playlist>` — Full playlist\n`!play <Spotify playlist>` — Load Spotify playlist\n`!pause` — Pause\n`!resume` — Resume\n`!skip` — Skip\n`!stop` — Stop and disconnect\n`!queue` — Queue\n`!nowplaying` — Current song\n`!volume <0-200>` — Volume\n`!clearqueue` — Clear queue",
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Music(bot))

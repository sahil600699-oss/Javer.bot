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

def get_state(guild_id):
    if guild_id not in states:
        states[guild_id] = MusicState()
    return states[guild_id]

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Bot startup ke baad hi node connect hoga
        self.bot.loop.create_task(self.connect_lavalink())

    async def connect_lavalink(self):
        await self.bot.wait_until_ready()
        
        host = getattr(config, 'LAVALINK_HOST', 'in-1.visihost.in')
        port = getattr(config, 'LAVALINK_PORT', 3002)
        password = getattr(config, 'LAVALINK_PASSWORD', 'pvt@1211')

        node_uri = f"http://{host}:{port}"
        node = wavelink.Node(identifier="MainNode", uri=node_uri, password=password)

        while True:
            try:
                if not wavelink.Pool.nodes:
                    await wavelink.Pool.connect(nodes=[node], client=self.bot, inactive_player_timeout=300)
                    print(f"✅ Lavalink Connected: {node_uri}")
                break
            except Exception as e:
                print(f"🔄 Retrying Lavalink Connection in 5s... ({e})")
                await asyncio.sleep(5)

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str):
        if not ctx.author.voice:
            return await ctx.send("❌ You must be in a voice channel!")

        # Check if node is ready before connecting player
        if not wavelink.Pool.nodes or not any(n.status == wavelink.NodeStatus.CONNECTED for n in wavelink.Pool.nodes.values()):
            return await ctx.send("⏳ Lavalink Node is still connecting, please try again in 5 seconds...")

        vc: wavelink.Player = ctx.voice_client
        if not vc:
            try:
                vc = await ctx.author.voice.channel.connect(cls=wavelink.Player, self_deaf=True)
            except Exception as e:
                return await ctx.send(f"❌ Voice Connect Error: `{e}`")

        state = get_state(ctx.guild.id)
        state.text_channel = ctx.channel

        try:
            tracks: wavelink.Search = await wavelink.Playable.search(query)
            if not tracks:
                return await ctx.send("❌ No results found!")

            track = tracks[0] if not isinstance(tracks, wavelink.Playlist) else tracks.tracks[0]
            
            if not vc.current:
                state.current = track
                await vc.play(track)
                await ctx.send(f"🎶 Now Playing: **{track.title}**")
            else:
                state.queue.append(track)
                await ctx.send(f"📋 Added to queue: **{track.title}**")

        except Exception as e:
            await ctx.send(f"❌ Play Error: `{e}`")

async def setup(bot):
    await bot.add_cog(Music(bot))
    

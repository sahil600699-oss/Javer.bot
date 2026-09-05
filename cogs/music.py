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

    async def cog_load(self):
        # Direct async task setup without blocking
        self.bot.loop.create_task(self.setup_lavalink())

    async def setup_lavalink(self):
        await self.bot.wait_until_ready()

        host = getattr(config, 'LAVALINK_HOST', 'in-1.visihost.in')
        port = getattr(config, 'LAVALINK_PORT', 3002)
        password = getattr(config, 'LAVALINK_PASSWORD', 'pvt@1211')

        node_uri = f"http://{host}:{port}"
        
        node = wavelink.Node(
            identifier="VisihostNode",
            uri=node_uri,
            password=password
        )

        try:
            await wavelink.Pool.connect(nodes=[node], client=self.bot)
        except Exception as e:
            print(f"Lavalink connect call error: {e}")

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f"✅ Node {payload.node.identifier} READY!")

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str):
        if not ctx.author.voice:
            return await ctx.send("❌ You must be in a voice channel!")

        # Dynamic check across all pool nodes
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
                await ctx.send(f"🎶 Playing: **{track.title}**")
            else:
                state.queue.append(track)
                await ctx.send(f"📋 Added to queue: **{track.title}**")

        except Exception as e:
            await ctx.send(f"❌ Play Error: `{e}`")

async def setup(bot):
    await bot.add_cog(Music(bot))
    

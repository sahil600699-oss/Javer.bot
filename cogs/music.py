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
        self.panel_message = None
        self.volume = 100


def get_state(guild_id):
    if guild_id not in states:
        states[guild_id] = MusicState()
    return states[guild_id]


class MusicControls(discord.ui.View):
    def __init__(self, cog, guild_id, paused=False):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild_id = guild_id
        self.paused = paused
        self._sync_pause_button()

    def _sync_pause_button(self):
        self.pause_resume.label = "Resume" if self.paused else "Pause"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not interaction.guild or interaction.guild.id != self.guild_id:
            await interaction.response.send_message(
                "This music panel belongs to another server.", ephemeral=True
            )
            return False
        if not interaction.user.voice:
            await interaction.response.send_message(
                "You must be in a voice channel to use the music controls.", ephemeral=True
            )
            return False
        vc = interaction.guild.voice_client
        if not vc:
            await interaction.response.send_message(
                "I am not connected to a voice channel.", ephemeral=True
            )
            return False
        if interaction.user.voice.channel != vc.channel:
            await interaction.response.send_message(
                "You must be in my voice channel to use these controls.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.secondary, row=0)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        paused = await self.cog.toggle_track(interaction.guild)
        self.paused = paused
        self._sync_pause_button()
        await self.cog.update_panel(interaction.guild, self)
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, row=1)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.skip_track(interaction.guild)
        await interaction.response.send_message("Skipped.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.secondary, row=1)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.stop_track(interaction.guild)
        await interaction.response.send_message("Stopped and queue cleared.", ephemeral=True)

    @discord.ui.button(label="Queue", style=discord.ButtonStyle.secondary, row=2)
    async def queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = get_state(interaction.guild.id)
        if not state.queue:
            text = "The queue is empty."
        else:
            lines = [f"**{i}.** {track.title}" for i, track in enumerate(state.queue[:10], 1)]
            text = "**Queue**\n" + "\n".join(lines)
            if len(state.queue) > 10:
                text += f"\n…and {len(state.queue) - 10} more."
        await interaction.response.send_message(text, ephemeral=True)

    @discord.ui.button(label="Vol +10", style=discord.ButtonStyle.secondary, row=2)
    async def volume_up(self, interaction: discord.Interaction, button: discord.ui.Button):
        volume = await self.cog.change_volume(interaction.guild, 10)
        await self.cog.update_panel(interaction.guild, self)
        await interaction.response.send_message(f"Volume: **{volume}%**", ephemeral=True)

    @discord.ui.button(label="Vol -10", style=discord.ButtonStyle.secondary, row=2)
    async def volume_down(self, interaction: discord.Interaction, button: discord.ui.Button):
        volume = await self.cog.change_volume(interaction.guild, -10)
        await self.cog.update_panel(interaction.guild, self)
        await interaction.response.send_message(f"Volume: **{volume}%**", ephemeral=True)

    @discord.ui.button(label="10s Back", style=discord.ButtonStyle.secondary, row=3)
    async def back_10(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.seek_track(interaction.guild, -10)
        await interaction.response.send_message("10 seconds back.", ephemeral=True)

    @discord.ui.button(label="10s Forward", style=discord.ButtonStyle.secondary, row=3)
    async def forward_10(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.seek_track(interaction.guild, 10)
        await interaction.response.send_message("10 seconds forward.", ephemeral=True)


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        self.bot.loop.create_task(self.setup_lavalink())

    async def setup_lavalink(self):
        await self.bot.wait_until_ready()
        host = getattr(config, "LAVALINK_HOST", "in-1.visihost.in")
        port = getattr(config, "LAVALINK_PORT", 3002)
        password = getattr(config, "LAVALINK_PASSWORD", "pvt@1211")
        try:
            node = wavelink.Node(
                identifier="VisihostNode",
                uri=f"http://{host}:{port}",
                password=password,
            )
            await wavelink.Pool.connect(nodes=[node], client=self.bot)
        except Exception as e:
            print(f"Lavalink connect call error: {e}")

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f"Node {payload.node.identifier} READY!")

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
            await player.set_volume(state.volume)
            if state.text_channel:
                await self.send_now_playing(state.text_channel, track, state)
        else:
            state.current = None
            state.panel_message = None

    async def resume_track(self, guild):
        vc = guild.voice_client
        if vc:
            await vc.pause(False)

    async def pause_track(self, guild):
        vc = guild.voice_client
        if vc:
            await vc.pause(True)

    async def toggle_track(self, guild):
        vc = guild.voice_client
        if not vc:
            return False
        new_paused = not bool(vc.paused)
        await vc.pause(new_paused)
        return new_paused

    async def skip_track(self, guild):
        vc = guild.voice_client
        if not vc:
            return

        state = get_state(guild.id)
        if state.queue:
            track = state.queue.pop(0)
            state.current = track
            await vc.play(track)
            await vc.set_volume(state.volume)
            if state.text_channel:
                await self.send_now_playing(state.text_channel, track, state)
        else:
            state.current = None
            await vc.stop()

    async def stop_track(self, guild):
        vc = guild.voice_client
        state = get_state(guild.id)
        state.queue.clear()
        state.current = None
        state.panel_message = None
        if vc:
            await vc.stop()

    async def change_volume(self, guild, amount):
        state = get_state(guild.id)
        state.volume = max(0, min(200, state.volume + amount))
        vc = guild.voice_client
        if vc:
            await vc.set_volume(state.volume)
        return state.volume

    async def seek_track(self, guild, seconds):
        vc = guild.voice_client
        if not vc:
            return
        position = max(0, int(getattr(vc, "position", 0) or 0) + (seconds * 1000))
        duration = getattr(getattr(vc, "current", None), "length", 0) or 0
        if duration:
            position = min(position, int(duration))
        await vc.seek(position)

    def get_artwork(self, track):
        artwork = getattr(track, "artwork_url", None)
        if artwork:
            return artwork

        identifier = getattr(track, "identifier", None)
        if identifier:
            return f"https://i.ytimg.com/vi/{identifier}/hqdefault.jpg"
        return None

    def make_embed(self, track, state, paused=False):
        # Discord's embed layout naturally places the title above the large image.
        embed = discord.Embed(
            title=str(getattr(track, "title", "Unknown Track")),
            color=discord.Color.red(),
        )
        artwork = self.get_artwork(track)
        if artwork:
            embed.set_image(url=artwork)
        embed.add_field(
            name="Volume",
            value=f"**{state.volume}%**",
            inline=False,
        )
        embed.set_footer(text="Paused • Music controls" if paused else "Playing • Music controls")
        return embed

    async def update_panel(self, guild, view=None):
        state = get_state(guild.id)
        message = state.panel_message
        if not message:
            return

        vc = guild.voice_client
        paused = bool(getattr(vc, "paused", False)) if vc else False
        if view is None:
            view = MusicControls(self, guild.id, paused=paused)
        else:
            view.paused = paused
            view._sync_pause_button()

        if state.current:
            try:
                await message.edit(embed=self.make_embed(state.current, state, paused), view=view)
            except (discord.NotFound, discord.HTTPException):
                state.panel_message = None

    async def send_queue_added(self, channel, track, count=1):
        embed = discord.Embed(
            title=str(getattr(track, "title", "Unknown Track")),
            description=(f"Added to queue • {count} track(s)" if count > 1 else "Added to queue"),
            color=discord.Color.red(),
        )
        artwork = self.get_artwork(track)
        if artwork:
            embed.set_image(url=artwork)
        try:
            message = await channel.send(embed=embed)
            await message.delete(delay=3)
        except discord.HTTPException:
            pass

    async def send_now_playing(self, channel, track, state):
        vc = channel.guild.voice_client
        paused = bool(getattr(vc, "paused", False)) if vc else False
        view = MusicControls(self, channel.guild.id, paused=paused)
        embed = self.make_embed(track, state, paused)
        try:
            message = await channel.send(embed=embed, view=view)
            state.panel_message = message
        except discord.HTTPException:
            state.panel_message = None

    async def ensure_player(self, ctx):
        if not ctx.author.voice:
            await ctx.send("You must be in a voice channel!")
            return None

        vc = ctx.guild.voice_client
        target = ctx.author.voice.channel
        if vc:
            if vc.channel != target:
                try:
                    await vc.move_to(target)
                except Exception:
                    await ctx.send("I cannot move to your voice channel.")
                    return None
            return vc

        try:
            return await target.connect(cls=wavelink.Player, self_deaf=True)
        except Exception as e:
            await ctx.send(f"Join error: `{e}`")
            return None

    @commands.command(name="join")
    async def join(self, ctx):
        vc = await self.ensure_player(ctx)
        if vc:
            await ctx.send(f"Joined **{vc.channel.name}**.")

    @commands.command(name="leave", aliases=["disconnect", "dc"])
    async def leave(self, ctx):
        vc = ctx.guild.voice_client
        if not vc:
            return await ctx.send("I am not in a voice channel.")
        state = get_state(ctx.guild.id)
        state.queue.clear()
        state.current = None
        state.panel_message = None
        await vc.disconnect()
        await ctx.send("Left the voice channel and cleared the queue.")

    @commands.command(name="play", aliases=["p"])
    async def play(self, ctx: commands.Context, *, query: str):
        if not wavelink.Pool.nodes:
            return await ctx.send("Lavalink pool is empty. Please check the Lavalink node.")

        # Automatically joins/moves to the voice channel the user is currently in.
        vc = await self.ensure_player(ctx)
        if not vc:
            return

        state = get_state(ctx.guild.id)
        state.text_channel = ctx.channel
        try:
            tracks = await wavelink.Playable.search(query)
            if not tracks:
                return await ctx.send("No tracks found!")

            if isinstance(tracks, wavelink.Playlist):
                track_list = list(tracks.tracks)
                if not track_list:
                    return await ctx.send("No tracks found!")
                if not vc.current:
                    track = track_list.pop(0)
                    state.current = track
                    state.queue.extend(track_list)
                    await vc.play(track)
                    await vc.set_volume(state.volume)
                    await self.send_now_playing(ctx.channel, track, state)
                else:
                    state.queue.extend(track_list)
                    await self.send_queue_added(ctx.channel, track_list[0], len(track_list))
                return

            track = tracks[0]
            if not vc.current:
                state.current = track
                await vc.play(track)
                await vc.set_volume(state.volume)
                await self.send_now_playing(ctx.channel, track, state)
            else:
                state.queue.append(track)
                await self.send_queue_added(ctx.channel, track)
        except Exception as e:
            await ctx.send(f"Play Error: `{e}`")

    @commands.command(name="resume")
    async def resume(self, ctx):
        if not await self.ensure_player(ctx):
            return
        await self.resume_track(ctx.guild)
        await self.update_panel(ctx.guild)
        await ctx.send("Resumed.")

    @commands.command(name="pause")
    async def pause(self, ctx):
        if not await self.ensure_player(ctx):
            return
        await self.pause_track(ctx.guild)
        await self.update_panel(ctx.guild)
        await ctx.send("Paused.")

    @commands.command(name="toggle")
    async def toggle(self, ctx):
        if not await self.ensure_player(ctx):
            return
        paused = await self.toggle_track(ctx.guild)
        await self.update_panel(ctx.guild)
        await ctx.send("Paused." if paused else "Resumed.")

    @commands.command(name="skip")
    async def skip(self, ctx):
        if not await self.ensure_player(ctx):
            return
        await self.skip_track(ctx.guild)
        await ctx.send("Skipped.")

    @commands.command(name="stop")
    async def stop(self, ctx):
        if not await self.ensure_player(ctx):
            return
        await self.stop_track(ctx.guild)
        await ctx.send("Stopped and queue cleared.")

    @commands.command(name="queue", aliases=["q"])
    async def queue_cmd(self, ctx):
        state = get_state(ctx.guild.id)
        if not state.queue:
            return await ctx.send("The queue is empty.")
        lines = [f"**{i}.** {track.title}" for i, track in enumerate(state.queue, 1)]
        await ctx.send("**Queue**\n" + "\n".join(lines[:25]))

    @commands.command(name="vol", aliases=["volume"])
    async def vol(self, ctx, amount: str = None):
        if not await self.ensure_player(ctx):
            return
        state = get_state(ctx.guild.id)
        if amount is None:
            return await ctx.send(f"Current volume: **{state.volume}%**")
        try:
            if amount.startswith(("+", "-")):
                change = int(amount)
                state.volume = max(0, min(200, state.volume + change))
            else:
                state.volume = max(0, min(200, int(amount)))
        except ValueError:
            return await ctx.send("Use `!vol 100`, `!vol +10`, or `!vol -10`.")
        await ctx.guild.voice_client.set_volume(state.volume)
        await self.update_panel(ctx.guild)
        await ctx.send(f"Volume: **{state.volume}%**")

    @commands.command(name="back10", aliases=["back", "seekback"])
    async def back10(self, ctx):
        if not await self.ensure_player(ctx):
            return
        await self.seek_track(ctx.guild, -10)
        await ctx.send("10 seconds back.")

    @commands.command(name="forward10", aliases=["forward", "fwd10", "seekforward"])
    async def forward10(self, ctx):
        if not await self.ensure_player(ctx):
            return
        await self.seek_track(ctx.guild, 10)
        await ctx.send("10 seconds forward.")


async def setup(bot):
    await bot.add_cog(Music(bot))
    

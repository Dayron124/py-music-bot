from discord.ext import commands
import discord
import asyncio
import youtube_dl
import logging
from urllib import request
from video import Video

async def audio_playing(ctx):
    """Checks that audio is currently playing before continuing."""
    client = ctx.guild.voice_client
    if client and client.channel and client.source:
        return True
    else:
        raise commands.CommandError("Not currently playing any audio.")
class Music:
    """Bot commands to help play music."""
    def __init__(self, bot):
        self.bot = bot
        self.states = {}

    def get_state(self, guild):
        """Gets the state for `guild`, creating it if it does not exist."""
        if guild.id in self.states:
            return self.states[guild.id]
        else:
            self.states[guild.id] = GuildState()
            return self.states[guild.id]

    @commands.command(aliases=["stop"])
    @commands.guild_only()
    async def leave(self, ctx):
        """Leaves the voice channel, if currently in one."""
        client = ctx.guild.voice_client
        state = self.get_state(ctx.guild)
        if client and client.channel:
            await client.disconnect()
            state.playlist = []
            state.now_playing = None
        else:
            raise commands.CommandError("Not in a voice channel.")


    @commands.command(aliases=["resume", "p"])
    @commands.guild_only()
    @commands.check(audio_playing)
    async def pause(self, ctx):
        """Pauses any currently playing audio."""
        client = ctx.guild.voice_client
        self._pause_audio(client)

    def _pause_audio(self, client):
        if client.is_paused():
            client.resume()
        else:
            client.pause()

    @commands.command(aliases=["vol", "v"])
    @commands.guild_only()
    @commands.check(audio_playing)
    async def volume(self, ctx, volume: int):
        """Change the volume of currently playing audio (values 0-250)."""
        state = self.get_state(ctx.guild)

        # clamp volume to [0, 250]
        if volume < 0:
            volume = 0
        elif volume > 250:
            volume = 250

        client = ctx.guild.voice_client

        state.volume = float(volume) / 100.0
        client.source.volume = state.volume # update the AudioSource's volume to match

    @commands.command()
    @commands.guild_only()
    @commands.check(audio_playing)
    async def skip(self, ctx):
        """Skips the currently-playing song."""
        state = self.get_state(ctx.guild)
        client = ctx.guild.voice_client
        client.stop()

    def _play_song(self, client, state, song):
        state.now_playing = song
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(song.stream_url), volume=state.volume)
        def after_playing(err):
            if len(state.playlist) > 0:
                next_song = state.playlist.pop(0)
                self._play_song(client, state, next_song)
            else:
                asyncio.run_coroutine_threadsafe(client.disconnect(), self.bot.loop)

        client.play(source, after=after_playing)

    @commands.command(aliases=["np"])
    @commands.guild_only()
    @commands.check(audio_playing)
    async def nowplaying(self, ctx):
        """Displays information about the current song."""
        state = self.get_state(ctx.guild)
        message = await ctx.send("", embed=state.now_playing.get_embed())
        await self._add_reaction_controls(message)

    @commands.command(aliases=["q", "playlist"])
    @commands.guild_only()
    @commands.check(audio_playing)
    async def queue(self, ctx):
        """Display the current play queue."""
        state = self.get_state(ctx.guild)
        if len(state.playlist) > 0:
            message = [f"{len(state.playlist)} songs in queue:"]
            message += [f"  {index+1}. **{song.title}** (requested by **{song.requested_by.name}**)" for (index, song) in enumerate(state.playlist)] # add individual songs
            await ctx.send("\n".join(message))
        else:
            await ctx.send("The play queue is empty.")
        
    @commands.command(brief="Plays audio from <url>.")
    @commands.guild_only()
    async def play(self, ctx, *, url):
        """Plays audio hosted at <url> (or performs a search for <url> and plays the first result)."""

        client = ctx.guild.voice_client
        state = self.get_state(ctx.guild) # get the guild's state

        if client and client.channel:
            try:
                video = Video(url, ctx.author)
            except youtube_dl.DownloadError as e:
                await ctx.send("There was an error downloading your video, sorry.") 
                return
            state.playlist.append(video)
            message = await ctx.send("Added to queue.", embed=video.get_embed())
            await self._add_reaction_controls(message)
        else:
            if ctx.author.voice != None and ctx.author.voice.channel != None:
                channel = ctx.author.voice.channel
                try:
                    video = Video(url, ctx.author)
                except youtube_dl.DownloadError as e:
                    await ctx.send("There was an error downloading your video, sorry.") 
                    return
                client = await channel.connect()
                self._play_song(client, state, video)
                message = await ctx.send("", embed=video.get_embed())
                await self._add_reaction_controls(message)
                logging.info(f"Now playing '{video.title}'")
            else:
                raise commands.CommandError("You need to be in a voice channel to do that.")

    async def on_reaction_add(self, reaction, user):
        message = reaction.message
        if user != self.bot.user and message.author == self.bot.user:
            await message.remove_reaction(reaction, user)
            if message.guild and message.guild.voice_client:
                guild = message.guild
                client = message.guild.voice_client
                state = self.get_state(guild)
                if reaction.emoji == "⏯":
                    # pause audio
                    self._pause_audio(client)
                elif reaction.emoji == "⏭":
                    # skip audio
                    client.stop()
                elif reaction.emoji == "⏮":
                    state.playlist.insert(0, state.now_playing) # insert current song at beginning of playlist
                elif reaction.emoji == "❌":
                    await client.disconnect()
                    state.playlist = []
                    state.now_playing = None
    async def _add_reaction_controls(self, message):
        """Adds a 'control-panel' of reactions to a message that can be used to control the bot."""
        CONTROLS = ["❌", "⏮", "⏯", "⏭"]
        for control in CONTROLS:
            await message.add_reaction(control)

class GuildState:
    """Helper class managing per-guild state."""
    def __init__(self):
        self.volume = 1.0
        self.playlist = []
        self.now_playing = None
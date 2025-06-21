import discord
from discord.ext import commands
import asyncio
import yt_dlp
import functools
import random

# Suppress noise about console usage from errors
yt_dlp.utils.bug_reports_message = lambda: ''

# YTDL options
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192',
    }],
}

ffmpeg_options = {
    'options': '-vn',
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('webpage_url')
        self.duration = data.get('duration')
        self.uploader = data.get('uploader')
        self.thumbnail = data.get('thumbnail')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        # Use functools.partial to run blocking ytdl operation in executor
        partial_extract = functools.partial(ytdl.extract_info, url, download=not stream)
        data = await loop.run_in_executor(None, partial_extract)

        if 'entries' in data:
            # take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

    @classmethod
    async def search(cls, query, *, loop=None, limit=5):
        loop = loop or asyncio.get_event_loop()
        partial_search = functools.partial(ytdl.extract_info, f"ytsearch{limit}:{query}", download=False)
        data = await loop.run_in_executor(None, partial_search)
        return data.get('entries', [])


class MusicQueue:
    def __init__(self):
        self._queue = []
        self._lock = asyncio.Lock()

    async def get(self):
        async with self._lock:
            if not self._queue:
                return None
            return self._queue.pop(0)

    async def put(self, item):
        async with self._lock:
            self._queue.append(item)

    async def clear(self):
        async with self._lock:
            self._queue.clear()

    async def shuffle(self):
        async with self._lock:
            random.shuffle(self._queue)

    async def remove(self, index):
        async with self._lock:
            if 0 <= index < len(self._queue):
                return self._queue.pop(index)
            return None

    def __len__(self):
        return len(self._queue)

    def __getitem__(self, index):
        return self._queue[index]

    def is_empty(self):
        return not self._queue


class MusicCog(commands.Cog, name="Music"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.voice_states = {}  # guild_id: VoiceState

    async def get_voice_state(self, ctx: commands.Context):
        state = self.voice_states.get(ctx.guild.id)
        # A VoiceState is considered stale/dead if its audio_player task is done
        # (meaning it's no longer running, possibly due to an error or normal completion like idle disconnect)
        # and it's not properly connected to a voice channel anymore, or if it simply doesn't exist.
        if not state or (state.audio_player and state.audio_player.done()):
            if state:  # If a stale state exists
                print(f"Stale VoiceState found for guild {ctx.guild.id}. Attempting cleanup and creating new state.")
                # Ensure the old task is definitely cancelled and voice is disconnected if somehow stuck.
                if state.audio_player and not state.audio_player.done():
                    state.audio_player.cancel()
                if state.voice and state.voice.is_connected():
                    await state.voice.disconnect()
                # It's possible state.stop() was already called if it exited cleanly (e.g. idle),
                # but this is a fallback.

            # Create a new VoiceState
            state = VoiceState(self.bot, ctx)
            self.voice_states[ctx.guild.id] = state

        # Potentially update the _ctx of an existing state if needed,
        # though VoiceState mostly uses it for sending messages to the original channel.
        # For now, this is not strictly necessary as commands use their own ctx.
        # state._ctx = ctx

        return state

    def cog_unload(self):
        for state in self.voice_states.values():
            self.bot.loop.create_task(state.stop())

    async def cog_before_invoke(self, ctx: commands.Context):
        ctx.voice_state = await self.get_voice_state(ctx)

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        await ctx.send(f'An error occurred: {str(error)}')

    @commands.hybrid_command(name='join', aliases=['connect'], description="Joins your current voice channel.")
    async def join(self, ctx: commands.Context):
        """Joins the voice channel of the command author."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("You are not connected to a voice channel.", ephemeral=True)
            return

        channel = ctx.author.voice.channel
        if ctx.voice_client: # If the bot is already in a voice channel
            if ctx.voice_client.channel == channel: # If it's the same channel the user is in
                await ctx.send(f"Already connected to {channel.mention}.", ephemeral=True)
            else: # If it's a different channel
                await ctx.voice_client.move_to(channel)
                await ctx.send(f"Moved to {channel.mention}.", ephemeral=True)
        else: # If the bot is not in a voice channel
            vc = await channel.connect()
            ctx.voice_state.voice = vc # Store the voice client in the state
            await ctx.send(f"Connected to {channel.mention}.", ephemeral=True)

    @commands.hybrid_command(name='leave', aliases=['disconnect', 'dc'], description="Disconnects the bot from the voice channel.")
    async def leave(self, ctx: commands.Context):
        """Clears the queue and leaves the voice channel."""
        if not ctx.voice_client:
            await ctx.send("Not connected to any voice channel.", ephemeral=True)
            return

        await ctx.voice_state.stop()
        del self.voice_states[ctx.guild.id] # Remove state
        await ctx.send("Disconnected.", ephemeral=True)

    @commands.hybrid_command(name='play', aliases=['p'], description="Plays a song or adds to queue.")
    async def play(self, ctx: commands.Context, *, search: str):
        """Plays a song from URL or search query.
        If a song is already playing, adds to queue.
        """
        if not ctx.voice_client:
            if ctx.author.voice and ctx.author.voice.channel:
                await ctx.author.voice.channel.connect()
                ctx.voice_state.voice = ctx.voice_client # Update voice client in state
            else:
                await ctx.send("You are not connected to a voice channel, and I'm not either.", ephemeral=True)
                return
        elif not ctx.author.voice or ctx.author.voice.channel != ctx.voice_client.channel:
            await ctx.send("You need to be in my current voice channel to play songs.", ephemeral=True)
            return

        async with ctx.typing():
            try:
                source = await YTDLSource.from_url(search, loop=self.bot.loop, stream=True)
            except yt_dlp.utils.DownloadError as e:
                await ctx.send(f"Could not find anything for `{search}` or it's not a valid URL. Error: {e}", ephemeral=True)
                return
            except Exception as e:
                await ctx.send(f"An error occurred while trying to process the song: {e}", ephemeral=True)
                return

        await ctx.voice_state.songs.put(source)
        if ctx.voice_state.current is None and not ctx.voice_client.is_playing():
            await ctx.send(f"Enqueued **{source.title}** and starting playback.", ephemeral=True)
            # The audio_player_task will pick it up
        else:
            await ctx.send(f"Enqueued **{source.title}**.", ephemeral=True)


    @commands.hybrid_command(name='pause', description="Pauses the current song.")
    async def pause(self, ctx: commands.Context):
        """Pauses the currently playing song."""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await ctx.send("Paused.", ephemeral=True)
        else:
            await ctx.send("Not playing anything to pause.", ephemeral=True)

    @commands.hybrid_command(name='resume', description="Resumes the paused song.")
    async def resume(self, ctx: commands.Context):
        """Resumes the currently paused song."""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send("Resumed.", ephemeral=True)
        else:
            await ctx.send("Nothing paused to resume.", ephemeral=True)

    @commands.hybrid_command(name='stop', description="Stops the music and clears the queue.")
    async def stop_cmd(self, ctx: commands.Context): # Renamed to stop_cmd to avoid conflict with VoiceState.stop
        """Stops playing, clears queue and leaves voice channel."""
        if not ctx.voice_client:
            await ctx.send("Not connected to a voice channel.", ephemeral=True)
            return

        # Clear queue and stop player
        await ctx.voice_state.songs.clear()
        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            ctx.voice_client.stop() # This will trigger the 'after' in play and thus the next song logic
        # The audio_player_task will see an empty queue and current=None, effectively stopping.
        # We don't want to call VoiceState.stop() here as that also disconnects.
        # If the user wants to disconnect, they should use 'leave'.
        # Clearing the now_playing_message if it exists
        if ctx.voice_state.now_playing_message:
            try:
                await ctx.voice_state.now_playing_message.delete()
                ctx.voice_state.now_playing_message = None
            except discord.HTTPException:
                pass # Message already deleted
        await ctx.send("Music stopped and queue cleared.", ephemeral=True)


    @commands.hybrid_command(name='skip', aliases=['s'], description="Skips the current song.")
    async def skip(self, ctx: commands.Context):
        """Skips the current song."""
        if not ctx.voice_client or not (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            await ctx.send("Not playing anything to skip.", ephemeral=True)
            return
        if ctx.voice_state.current is None: # Should not happen if playing, but as a safeguard
             await ctx.send("No current song to skip.", ephemeral=True)
             return

        # Vote skip can be implemented here if desired. For now, direct skip.
        await ctx.send(f"Skipped **{ctx.voice_state.current.title}**.", ephemeral=True)
        ctx.voice_client.stop() # This triggers 'after' in play, which calls next.set()

    @commands.hybrid_command(name='queue', aliases=['q', 'playlist'], description="Shows the current song queue.")
    async def queue_cmd(self, ctx: commands.Context): # Renamed to queue_cmd
        """Displays the current song queue."""
        if ctx.voice_state.songs.is_empty() and ctx.voice_state.current is None:
            await ctx.send("The queue is empty and nothing is playing.", ephemeral=True)
            return

        embed = discord.Embed(title="Music Queue", color=discord.Color.purple())
        if ctx.voice_state.current:
            embed.add_field(name="Now Playing", value=f"[{ctx.voice_state.current.title}]({ctx.voice_state.current.url})", inline=False)

        if not ctx.voice_state.songs.is_empty():
            queue_list = []
            for i, song in enumerate(ctx.voice_state.songs):
                if i >= 10: # Limit display to 10 upcoming songs
                    queue_list.append(f"...and {len(ctx.voice_state.songs) - i} more.")
                    break
                queue_list.append(f"{i + 1}. [{song.title}]({song.url})")
            if queue_list:
                embed.add_field(name="Up Next", value="\n".join(queue_list), inline=False)
        else:
            embed.add_field(name="Up Next", value="The queue is empty.", inline=False)

        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name='nowplaying', aliases=['np', 'current'], description="Shows the currently playing song.")
    async def nowplaying(self, ctx: commands.Context):
        """Displays the currently playing song."""
        if ctx.voice_state.current and ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            song = ctx.voice_state.current
            embed = discord.Embed(title="Now Playing", description=f"[{song.title}]({song.url})", color=discord.Color.green())
            if hasattr(song, 'thumbnail') and song.thumbnail:
                embed.set_thumbnail(url=song.thumbnail)
            if hasattr(song, 'uploader') and song.uploader:
                 embed.add_field(name="Uploader", value=song.uploader, inline=True)
            if hasattr(song, 'duration') and song.duration:
                m, s = divmod(song.duration, 60)
                h, m = divmod(m, 60)
                duration_str = f"{m:02d}:{s:02d}"
                if h > 0:
                    duration_str = f"{h:02d}:{duration_str}"
                embed.add_field(name="Duration", value=duration_str, inline=True)

            # Progress bar (simple text based)
            vc = ctx.voice_client
            if isinstance(vc.source, discord.PCMVolumeTransformer) and vc.source.original:
                 # This is a bit hacky and depends on how FFmpegPCMAudio is implemented
                 # and if we can get progress. For simplicity, we might omit a live progress bar
                 # or use a simpler representation.
                 # Let's assume for now we just show total duration.
                 pass


            await ctx.send(embed=embed, ephemeral=True)
        else:
            await ctx.send("Not playing anything right now.", ephemeral=True)

    @commands.hybrid_command(name='volume', aliases=['vol'], description="Changes the player volume (0-100).")
    async def volume(self, ctx: commands.Context, volume: int = None):
        """Changes the player's volume. Range: 0-100."""
        if not ctx.voice_client or not ctx.voice_client.source:
            return await ctx.send("Not playing anything.", ephemeral=True)

        if volume is None:
            return await ctx.send(f"Current volume is **{int(ctx.voice_state.volume * 100)}%**.", ephemeral=True)

        if not 0 <= volume <= 100:
            return await ctx.send("Volume must be between 0 and 100.", ephemeral=True)

        ctx.voice_state.volume = volume / 100
        ctx.voice_client.source.volume = ctx.voice_state.volume
        await ctx.send(f"Volume set to **{volume}%**.", ephemeral=True)

    @commands.hybrid_command(name='autoplay', description="Toggles autoplay of related songs when queue ends.")
    async def autoplay_cmd(self, ctx: commands.Context):
        """Toggles autoplay. When enabled, related songs will be added if queue is empty."""
        if not ctx.voice_client:
            return await ctx.send("Not connected to a voice channel.", ephemeral=True)

        ctx.voice_state.autoplay = not ctx.voice_state.autoplay
        status = "enabled" if ctx.voice_state.autoplay else "disabled"
        await ctx.send(f"Autoplay is now **{status}**.", ephemeral=True)

    @commands.hybrid_command(name='suggest', description="Suggests songs based on query (max 5).")
    async def suggest(self, ctx: commands.Context, *, query: str):
        """Searches for songs and provides a list of suggestions."""
        async with ctx.typing():
            try:
                entries = await YTDLSource.search(query, loop=self.bot.loop, limit=5)
            except Exception as e:
                await ctx.send(f"Error during search: {e}", ephemeral=True)
                return

            if not entries:
                await ctx.send(f"No suggestions found for `{query}`.", ephemeral=True)
                return

            embed = discord.Embed(title=f"Suggestions for '{query}'", color=discord.Color.orange())
            description_lines = []
            for i, entry in enumerate(entries):
                title = entry.get('title', 'Unknown Title')
                url = entry.get('webpage_url', '#')
                uploader = entry.get('uploader', 'Unknown Uploader')
                duration_seconds = entry.get('duration')
                duration_str = ""
                if duration_seconds:
                    m, s = divmod(duration_seconds, 60)
                    h, m_rem = divmod(m, 60)
                    if h > 0:
                        duration_str = f" [{h:02d}:{m_rem:02d}:{s:02d}]"
                    else:
                        duration_str = f" [{m:02d}:{s:02d}]"

                description_lines.append(f"{i+1}. [{title}]({url}){duration_str} - *{uploader}*")

            embed.description = "\n".join(description_lines)
            embed.set_footer(text="Use the play command with the song title or URL to play a suggestion.")
            await ctx.send(embed=embed, ephemeral=True)

    # Note: A full "autoqueue" feature that automatically adds suggestions
    # when the queue is low is more complex and would best be part of the
    # VoiceState's audio_player_task logic, similar to autoplay.
    # For this step, we'll focus on the `autoplay` toggle and `suggest` command.
    # A simple toggle for auto-queuing based on suggestions is harder to make intuitive
    # without a persistent "suggestion context" or complex background logic.
    # The current `autoplay` already serves a similar purpose for *related* songs.


class VoiceState:
    def __init__(self, bot: commands.Bot, ctx: commands.Context): # ctx here is the initial context that created the state
        self.bot = bot
        self._ctx = ctx
        self.current = None
        self.voice = ctx.guild.voice_client # Initial voice client
        self.next = asyncio.Event()
        self.songs = MusicQueue()
        self.autoplay = False
        self.volume = 0.5
        self.loop = False
        self.loop_queue = False
        self.now_playing_message = None
        self.idle_timer = None # For auto-disconnect

        self.audio_player = bot.loop.create_task(self.audio_player_task())

    async def audio_player_task(self):
        try:
            while True:
                self.next.clear()

                song_to_play = None
                if self.loop and self.current:
                    song_to_play = self.current
                elif self.loop_queue and self.current: # Check if current exists before putting it back
                    await self.songs.put(self.current)
                    song_to_play = await self.songs.get()
                else:
                    song_to_play = await self.songs.get()

                if song_to_play is None and self.autoplay and self.current: # Check if current exists for autoplay
                    if not self._ctx or not self._ctx.channel:
                        await asyncio.sleep(5)
                        continue
                    original_channel = self._ctx.channel
                    try:
                        related_query = self.current.title
                        if hasattr(self.current, 'uploader') and self.current.uploader:
                            related_query += f" {self.current.uploader}"
                        entries = await YTDLSource.search(related_query, loop=self.bot.loop, limit=3)
                        if entries:
                            chosen_entry = next((e for e in entries if e.get('webpage_url') != self.current.url), entries[0])
                            source = await YTDLSource.from_url(chosen_entry['webpage_url'], loop=self.bot.loop, stream=True)
                            source.title = chosen_entry.get('title', 'Unknown Title')
                            source.uploader = chosen_entry.get('uploader')
                            source.duration = chosen_entry.get('duration')
                            source.thumbnail = chosen_entry.get('thumbnail')
                            await self.songs.put(source)
                            song_to_play = await self.songs.get()
                            embed = discord.Embed(title="Autoplay", description=f"Queued: [{source.title}]({source.url})", color=discord.Color.random())
                            if source.thumbnail: embed.set_thumbnail(url=source.thumbnail)
                            if original_channel: # Check if channel still exists
                                await original_channel.send(embed=embed)
                        else:
                            await asyncio.sleep(5) # Wait before next check if no song found
                            continue
                    except Exception as e:
                        print(f"Error in autoplay: {e}")
                        if original_channel: # Check if channel still exists
                            try: await original_channel.send(f"Error trying to autoplay: {e}", delete_after=30)
                            except Exception: pass
                        await asyncio.sleep(5) # Wait before next check on error
                        continue

                if song_to_play is None:
                    if self.voice and self.voice.is_connected() and len(self.voice.channel.members) == 1:
                        if self.idle_timer is None:
                            self.idle_timer = self.bot.loop.time()
                        elif (self.bot.loop.time() - self.idle_timer) > 300: # 5 minutes (300 seconds)
                            music_cog = self.bot.get_cog("Music")
                            if music_cog and self._ctx and self._ctx.channel:
                                try:
                                    await self._ctx.channel.send(f"Leaving {self.voice.channel.mention} due to inactivity.")
                                except discord.HTTPException:  pass
                            await self.stop()
                            return
                    else:
                        self.idle_timer = None # Reset if conditions not met (e.g. more members, or not connected)
                    await asyncio.sleep(5)
                    continue

                self.idle_timer = None
                self.current = song_to_play

                if not self.voice or not self.voice.is_connected():
                    # Attempt to rejoin/reconnect if user is in a channel
                    if self._ctx.author.voice and self._ctx.author.voice.channel:
                        try:
                            self.voice = await self._ctx.author.voice.channel.connect()
                            music_cog = self.bot.get_cog("Music")
                            if music_cog: music_cog.voice_states[self._ctx.guild.id].voice = self.voice
                        except Exception as e:
                            print(f"Failed to reconnect to voice channel: {e}")
                            self.current = None; await asyncio.sleep(5); continue
                    else: # User not in a voice channel, cannot auto-reconnect
                        print(f"Voice client for guild {self._ctx.guild.id} disconnected, user not in channel. Player stopping.")
                        self.current = None;
                        # Consider calling self.stop() or parts of it if this state should trigger full cleanup
                        await asyncio.sleep(5); continue

                try:
                    self.voice.play(self.current, after=lambda e: self.bot.loop.call_soon_threadsafe(self.next.set))
                except discord.ClientException as e: # E.g., already playing
                    print(f"Error playing audio (ClientException): {e}"); self.current = None; await asyncio.sleep(1); continue
                except Exception as e: # Other errors
                    print(f"Unhandled error during play: {e}"); self.current = None; await asyncio.sleep(1); continue

                channel_to_send = self._ctx.channel
                if self.now_playing_message: # Delete old now playing message
                    try: await self.now_playing_message.delete()
                    except discord.HTTPException: pass

                embed = discord.Embed(title="Now Playing", description=f"[{self.current.title}]({self.current.url})", color=discord.Color.green())
                if hasattr(self.current, 'thumbnail') and self.current.thumbnail: embed.set_thumbnail(url=self.current.thumbnail)
                if hasattr(self.current, 'uploader') and self.current.uploader: embed.add_field(name="Uploader", value=self.current.uploader, inline=True)
                if hasattr(self.current, 'duration') and self.current.duration:
                    m, s = divmod(self.current.duration, 60); h, m_rem = divmod(m, 60)
                    duration_str = f"{m_rem:02d}:{s:02d}";
                    if h > 0: duration_str = f"{h:02d}:{duration_str}"
                    embed.add_field(name="Duration", value=duration_str, inline=True)

                if channel_to_send: # Check if channel still exists
                    try: self.now_playing_message = await channel_to_send.send(embed=embed)
                    except discord.Forbidden: print(f"Missing permissions to send message in {channel_to_send.name if channel_to_send else 'unknown channel'}")
                    except discord.HTTPException as e: print(f"Failed to send Now Playing message: {e}")

                await self.next.wait()

                if self.current: self.current.cleanup() # Cleanup the source
                self.current = None # Clear current song

                if not self.loop and self.now_playing_message: # Delete NP message if not looping current song
                    try: await self.now_playing_message.delete(); self.now_playing_message = None
                    except discord.HTTPException: pass
        except asyncio.CancelledError:
            print(f"Audio player task for guild {self._ctx.guild.id if self._ctx else 'Unknown'} cancelled.")
        except Exception as e:
            print(f"Unexpected error in audio_player_task for guild {self._ctx.guild.id if self._ctx else 'Unknown'}: {e}")
        finally:
            # This finally block ensures that if the task exits for any reason (cancelled or unhandled exception),
            # we attempt some cleanup.
            if self.current: self.current.cleanup()
            # The VoiceState itself should be cleaned up by MusicCog if the task ends unexpectedly.
            # For example, cog_unload or a leave command would trigger state.stop() which cancels this task.
            print(f"Audio player task for guild {self._ctx.guild.id if self._ctx else 'Unknown'} has conclusively ended.")


    async def stop(self):
        await self.songs.clear()
        if self.audio_player and not self.audio_player.done(): # Check if task exists and not already done
            self.audio_player.cancel()

        if self.voice and self.voice.is_connected():
            await self.voice.disconnect()
        self.voice = None

        if self.now_playing_message:
            try:
                await self.now_playing_message.delete()
            except discord.HTTPException:
                pass
            self.now_playing_message = None

        # The VoiceState object itself is removed from MusicCog.voice_states
        # by the command/event that calls stop (e.g., `leave` command or `cog_unload`).
        # If stop() is called internally by the audio_player_task (e.g. idle disconnect),
        # then the MusicCog also needs to be notified to remove this VoiceState.
        # The `leave` command in MusicCog already handles `del self.voice_states[ctx.guild.id]`.
        # `cog_unload` iterates and calls stop, but doesn't explicitly delete from dict (gc should handle).
        # For idle disconnect, the MusicCog needs a way to remove the state.
        # One way: audio_player_task, upon stopping for idle, calls a method on MusicCog.
        # Simpler: The `stop` command in MusicCog or `leave` command should be the primary way users/cog stop things.
        # The idle disconnect is an internal stop.
        # For now, let's assume that if audio_player_task calls self.stop(), the state object might linger
        # in MusicCog.voice_states until a new command for that guild creates a new state or cog unloads.
        # This is generally fine, but for immediate cleanup, MusicCog would need to be involved.
        # A simple fix in MusicCog.get_voice_state: if state.audio_player.done(), recreate.
        # This is handled by `MusicCog.leave` and `cog_unload` which call this `stop` method.
        # The `del self.voice_states[ctx.guild.id]` is correctly placed in `MusicCog.leave`.
        # In `cog_unload`, the states will be stopped and then the cog instance is destroyed.
        # The key is that `audio_player_task` calls `self.stop()` upon idle, and then `return`s, ending the task.
        # The `VoiceState` object itself will be cleaned up by Python's GC if no longer referenced by `MusicCog.voice_states`.
        # If `MusicCog.get_voice_state` is called again for this guild, and finds a "dead" state (task done), it should replace it.
        # Let's refine `get_voice_state` for this.
        pass # No change to this line, just comments.


async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))

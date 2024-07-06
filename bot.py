import json
import os
import sys
from time import time, gmtime, strftime
import random
import platform
from glob import glob

import discord
from discord import Status, ActivityType, ButtonStyle
from discord.ext import commands
from discord.ext.pages import Paginator, Page, PaginatorButton
from dotenv import load_dotenv
from flask import Flask
from threading import Thread
import psutil
import pytube
from pytube.innertube import _default_clients

start_time = time()
_default_clients["ANDROID_MUSIC"] = _default_clients["ANDROID_CREATOR"]

load_dotenv()
TOKEN = os.getenv("TEST_TOKEN")
ADMIN_IDS = json.loads(os.getenv("ADMIN_IDS"))
PORT = os.getenv("PORT")
PREFIX = os.getenv("PREFIX")
PRESENCE = os.getenv("PRESENCE")
STORAGE_PATH = "storage"

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)
bot.voice_channel = None
bot.queue_box = []
bot.queue_box_index = 0
bot.queue_loop = False
bot.loading_play = False

bot.custom_buttons = [
    PaginatorButton("first", label="<<", style=ButtonStyle.gray),
    PaginatorButton("prev", label="<", style=ButtonStyle.gray),
    PaginatorButton("page_indicator", style=ButtonStyle.gray, disabled=True),
    PaginatorButton("next", label=">", style=ButtonStyle.gray),
    PaginatorButton("last", label=">>", style=ButtonStyle.gray),
]

if not os.path.exists(STORAGE_PATH):
    os.makedirs(STORAGE_PATH)

@bot.event
async def on_ready():
    activity = discord.Activity(type=ActivityType.listening, name=PRESENCE)
    await bot.change_presence(status=Status.dnd, activity=activity)
    print(f"{bot.user} is ready")

@bot.command(aliases=["a"])
async def add(ctx, *, query):
    
    async with ctx.typing():
        try:
            if "https://" not in query:
                videos = pytube.Search(query).results[:1]
            elif "watch" in query:
                videos = [pytube.YouTube(query)]
            elif "playlist" in query:
                playlist = pytube.Playlist(query)
                videos = playlist.videos
            else:
                raise
        except Exception:
            await ctx.send("**:anger: | Invalid YouTube query!**")
            return
    
        for video in videos:
            bot.queue_box.append([video.title, video.author, video.watch_url])
        
    if len(videos) == 1:
        await ctx.send(f"**:eject: | Added to music box:\n`{videos[0].title}`\nby `{videos[0].author}`**")
    else:
        await ctx.send(f"**:eject: | Added `{len(videos)}` songs to music box!**")
    
@bot.command(aliases=["r"])
async def remove(ctx, index: int = None):
    
    if not bot.queue_box:
        await ctx.send("**:anger: | The music box is empty!**")
        return
    
    try:
        index = int(index)
        if not 0 <= index < len(bot.queue_box):
            raise ValueError
    except (ValueError, TypeError):
        await ctx.send(f"**:anger: | Invalid index query!\nIt must be a number that ranges from 0 to {len(bot.queue_box) - 1}!**")
        return

    video = bot.queue_box.pop(index)
    await ctx.send(f"**:wastebasket: | `[{index:02}]` Removed from music box:\n`{video[0]}`\nby `{video[1]}`**")
    
@bot.command(aliases=["sh"])
async def shuffle(ctx):
    
    if not bot.queue_box:
        await ctx.send("**:anger: | The music box is empty! how about you shuffle deez nuts?**")
        return
    
    if len(bot.queue_box) == 1:
        await ctx.send("**:anger: | Shuffling 1 song for you!**")
        return
    
    random.shuffle(bot.queue_box)
    await ctx.send("**:twisted_rightwards_arrows: | Successfully shuffled the music box!**")
    
@bot.command(aliases=["cq"])
async def clear_queue(ctx):
    
    if not bot.queue_box:
        await ctx.send("**:thinking: | The music box is already empty!**")
        return
    
    bot.queue_box = []
    await ctx.send("**:wastebasket: | Destroyed the music box!**")

@bot.command(aliases=["l"])
async def loop(ctx):
    bot.queue_loop = not bot.queue_loop
    
    if bot.queue_loop:
        await ctx.send("**:repeat: | The music box is now looping!**")
    else:
        await ctx.send("**:fast_forward: | Music box is no longer looping!**")

@bot.command(aliases=["q"])
async def queue(ctx):
    
    async with ctx.typing():
        queue_list = []
        for index, video in enumerate(bot.queue_box):
            queue_list.append(f"**`[{index:02}]` - {video[0]}\nby {video[1]}**")
        
        if not queue_list:
            await ctx.send("**:o: | Music box is empty :(**")
            return
    
        chunks = [queue_list[i:i + 10] for i in range(0, len(queue_list), 10)]
        pages = []
        loop_status = "looping" if bot.queue_loop else "not looping"
        index_status = f"{bot.queue_box_index}/{len(bot.queue_box)-1}"
        header = f"({loop_status}) `[{index_status}]`"
        
        for chunk in chunks:
            content = "\n".join(chunk)
            page = Page(content=f"**:notes: | Music Box {header}**\n{content}")
            pages.append(page)
        
    await Paginator(
        pages=pages,
        custom_buttons=bot.custom_buttons,
        show_indicator=True,
        use_default_buttons=False
        ).send(ctx)
    
@bot.command(aliases=["np"])
async def now_playing(ctx):
    
    if not bot.voice_channel:
        await ctx.send("**:anger: | I'm not even connected to a voice channel!**")
        return
    
    if not bot.voice_channel.is_playing():
        await ctx.send("**:anger: | I'm not playing anything!**")
        return
    
    current_video = bot.queue_box[bot.queue_box_index]
    index_status = f"`[{bot.queue_box_index}/{len(bot.queue_box)}]`"
    await ctx.send(f"**:musical_note: | Currently playing {index_status}:\n{current_video[0]}\nby `{current_video[1]}`**")
    
@bot.command(aliases=["p"])
async def play(ctx):
    
    if not ctx.author.voice:
        await ctx.send("**:anger: | You need to be in a voice channel to use this command!**")
        return

    voice_channel = ctx.author.voice.channel
    
    if not bot.voice_channel:
        await ctx.send("**:musical_note: | Joining the voice chat!**")
        bot.voice_channel = await voice_channel.connect()
    
    if bot.voice_channel.is_playing() or bot.loading_play:
        await ctx.send("**:anger: | I'm already playing the music box!**")
        return
    
    if not bot.queue_box:
        await ctx.send("**:anger: | Music box is empty!**")
        return
    
    await play_next_video(ctx)
    
@bot.command(aliases=["s"])
async def skip(ctx, index: int = None):

    if not bot.queue_box:
        await ctx.send("**:anger: | Music box is empty!**")
        return 

    if not ctx.voice_client:
        await ctx.send("**:anger: | I'm not in a voice channel!**")
        return 

    if not ctx.voice_client.is_playing():
        await ctx.send("**:anger: | I'm not playing anything!**")
        return 

    if index is not None:
        if not isinstance(index, int) or not 0 <= index < len(bot.queue_box):
            index_range = f"0 to {len(bot.queue_box) - 1}"
            await ctx.send(f"**:anger: | Invalid index query!\nIt must be a number that ranges from {index_range}!**")
            return
        bot.queue_box_index = index - 1

    await ctx.send("**:fast_forward: | Skipped the current song!**")
    ctx.voice_client.stop()

@bot.command(aliases=["dc"])
async def disconnect(ctx):
    
    if not bot.voice_channel:
        await ctx.send("**:anger: | I'm not in a voice channel!**")
    
    bot.queue_box = []
    bot.queue_box_index = 0
    await bot.voice_channel.disconnect()
    await ctx.send("**:ballot_box_with_check: | Disconnected! (And destroyed the music box)**")

async def play_next_video(ctx):
    bot.loading_play = True
        
    if not bot.queue_box or not bot.voice_channel:
        bot.loading_play = False
        return 
    
    if (bot.queue_box_index > len(bot.queue_box) - 1) and (not bot.queue_loop):
        await bot.voice_channel.disconnect()
        bot.voice_channel = None
        bot.queue_box_index = 0
        bot.loading_play = False
        await ctx.send("**:ballot_box_with_check: | Queue finished! leaving the voice channel...**")
        return
    
    if (not bot.queue_box_index) and bot.queue_loop:
        bot.queue_loop = False
        bot.loading_play = False
        await ctx.send("**:anger: | The queue is empty! I'm disabling the loop now**")
        return
    
    if bot.queue_box_index > len(bot.queue_box) - 1 and bot.queue_loop:
        await ctx.send("**:ballot_box_with_check: | Queue finished! Looping to index 0...**")
        bot.queue_box_index = 0
    
    async with ctx.typing():
        current_video = pytube.YouTube(bot.queue_box[bot.queue_box_index][2])
        audio_stream = current_video.streams.filter(only_audio=True).order_by("abr").desc().first()
        audio_file = audio_stream.download(output_path=STORAGE_PATH)
        #bot.voice_channel.play(discord.FFmpegPCMAudio(audio_stream.url))
    
    message = await ctx.send(f"**:musical_note: | Now playing:\n`{current_video.title}` by `{current_video.author}`**")
    await bot.voice_channel.play(discord.FFmpegPCMAudio(audio_file), wait_finish=True)
    
    await message.delete()
    os.remove(audio_file)
    bot.queue_box_index += 1
    bot.loading_play = False
    await play_next_video(ctx)

@bot.check
async def not_in_dm(ctx):
    return ctx.guild is not None
    
async def is_bot_admin(ctx):
    return ctx.author.id in ADMIN_IDS
    
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        if await not_in_dm(ctx) is False:
            return
        elif not await is_bot_admin(ctx):
            await ctx.send("You're not a bot admin", delete_after=30)
    else:
        raise error

@bot.command(aliases=["rr"])
@commands.check(is_bot_admin)
async def restart_bot(ctx):
    await ctx.send("bot restarting")
    os.execv(sys.executable, ["python"] + sys.argv)

@bot.command(aliases=["ss"])
@commands.check(is_bot_admin)
async def stats(ctx):
    uname = platform.uname()
    uptime = time() - start_time
    uptime_str = strftime("%H:%M:%S", gmtime(uptime))
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    
    cpu_info = f"Physical cores: {psutil.cpu_count(logical=False)}, Total cores: {psutil.cpu_count(logical=True)}, Max Frequency: {psutil.cpu_freq().max:.2f}Mhz"
    
    stats_message = (
        f"**System Information**\n"
        f"**OS**: {uname.system} {uname.release} ({uname.version})\n"
        f"**Node**: {uname.node}\n"
        f"**Machine**: {uname.machine}\n"
        f"**Processor**: {uname.processor}\n"
        f"**CPU**: {cpu_info}\n"
        f"**Uptime**: {uptime_str}\n"
        f"**Memory**: {mem.total / (1024 ** 3):.2f} GB\n"
        f"**Memory Used**: {mem.used / (1024 ** 3):.2f} GB ({mem.percent}%)\n"
        f"**Disk**: {disk.total / (1024 ** 3):.2f} GB\n"
        f"**Disk Used**: {disk.used / (1024 ** 3):.2f} GB ({disk.percent}%)"
    )
    
    await ctx.send(stats_message)

@bot.command(aliases=["ls"])
@commands.check(is_bot_admin)
async def list_files(ctx):
    files = glob(STORAGE_PATH + "/*.webm")
    files_list = "\n".join([file for file in files]) or "empty"
    await ctx.send(f"Files in {STORAGE_PATH}:\n```\n{files_list}\n```")

@bot.command(aliases=["lsd"])
@commands.check(is_bot_admin)
async def delete_files(ctx):
    files = glob(STORAGE_PATH + "/*.webm")
    for file in files:
        os.remove(file)
    await ctx.send(f"All files in {STORAGE_PATH} have been deleted")

app = Flask(__name__)

@app.route("/")
def home():
    return "<b> <center> Shoundobot :) </center> </b>"

def run():
    app.run(host="0.0.0.0", port=PORT)

def keep_alive():
    t = Thread(target=run)
    t.start()
    
keep_alive()
bot.run(TOKEN)

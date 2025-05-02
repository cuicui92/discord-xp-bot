import discord
from discord.ext import commands, tasks
import json
import time
import os
import asyncio
import firebase_admin
from firebase_admin import credentials, db
from collections import deque
from datetime import datetime, timedelta

from web import keep_alive

# Initialisation Firebase
cred = credentials.Certificate("firebase_config.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://xp-bot-f4291-default-rtdb.firebaseio.com/'
})

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

xp_dict = {}
vocal_start_times = {}
save_queue = deque()

# File d'attente pour sauvegarde Firebase
async def save_worker():
    while True:
        if save_queue:
            data_to_save = save_queue.popleft()
            ref = db.reference('xp_data')
            ref.set(data_to_save)
        await asyncio.sleep(2)

@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user.name}")
    bot.loop.create_task(save_worker())

# Chargement données XP
def load_xp_data():
    ref = db.reference('xp_data')
    return ref.get() or {}

# Sauvegarde asynchrone via file
def save_xp_data():
    save_queue.append(xp_dict.copy())

# Calculs niveaux
def calculate_text_level(messages):
    if messages < 150:
        return messages // 15
    elif messages < 500:
        return 10 + (messages - 150) // 20
    elif messages < 1250:
        return 25 + (messages - 500) // 25
    elif messages < 2250:
        return 50 + (messages - 1250) // 30
    elif messages <= 3500:
        return 75 + (messages - 2250) // 35
    else:
        return 100

def calculate_total_level(user_id):
    data = xp_dict.get(user_id, {})
    messages = data.get("messages", 0)
    vocal_levels = data.get("vocal_levels", 0)
    return calculate_text_level(messages) + vocal_levels

def get_progress_bar(messages):
    if messages < 150:
        current, total = messages % 15, 15
    elif messages < 500:
        current, total = (messages - 150) % 20, 20
    elif messages < 1250:
        current, total = (messages - 500) % 25, 25
    elif messages < 2250:
        current, total = (messages - 1250) % 30, 30
    else:
        current, total = (messages - 2250) % 35, 35

    percent = current / total
    bars = int(percent * 10)
    bar_display = "[" + "█" * bars + "░" * (10 - bars) + f"] {int(percent * 100)}%"
    return bar_display

AUTHORIZED_CHANNEL_NAME = "🪜・level"

@bot.command()
async def mystats(ctx):
    if ctx.channel.name != AUTHORIZED_CHANNEL_NAME:
        return await ctx.send(f"{ctx.author.mention}, utilise cette commande dans #{AUTHORIZED_CHANNEL_NAME}.")

    user_id = str(ctx.author.id)
    if user_id not in xp_dict:
        xp_dict[user_id] = {"messages": 0, "vocal_levels": 0}

    data = xp_dict[user_id]
    total_level = calculate_total_level(user_id)
    progress_bar = get_progress_bar(data["messages"])

    embed = discord.Embed(title=f"Statistiques de {ctx.author.name}", color=discord.Color.green())
    embed.set_thumbnail(url=ctx.author.avatar.url)
    embed.add_field(name="Niveau total", value=total_level, inline=False)
    embed.add_field(name="Messages envoyés", value=data['messages'], inline=True)
    embed.add_field(name="Niveaux vocaux", value=data['vocal_levels'], inline=True)
    embed.add_field(name="Progression", value=progress_bar, inline=False)

    await ctx.send(embed=embed)
    await ctx.message.delete()

@bot.command()
async def rank(ctx):
    if ctx.channel.name != AUTHORIZED_CHANNEL_NAME:
        return await ctx.send(f"{ctx.author.mention}, utilise cette commande dans #{AUTHORIZED_CHANNEL_NAME}.")

    leaderboard = [(uid, calculate_total_level(uid)) for uid in xp_dict]
    leaderboard.sort(key=lambda x: x[1], reverse=True)

    embed = discord.Embed(title="🏆 Classement des niveaux", color=discord.Color.gold())

    for i, (user_id, level) in enumerate(leaderboard[:10], start=1):
        try:
            user = await bot.fetch_user(int(user_id))
            embed.add_field(name=f"{i}. {user.name}", value=f"**Niveau** : {level}", inline=False)
        except:
            continue

    embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else ctx.author.avatar.url)
    await ctx.send(embed=embed)
    await ctx.message.delete()

@bot.event
async def on_message(message):
    if message.author.bot or "Verified" not in [role.name for role in message.author.roles]:
        return

    user_id = str(message.author.id)
    if user_id not in xp_dict:
        xp_dict[user_id] = {"messages": 0, "vocal_levels": 0}

    old_level = calculate_total_level(user_id)
    xp_dict[user_id]["messages"] += 1
    save_xp_data()
    new_level = calculate_total_level(user_id)

    if new_level > old_level:
        msg = await message.channel.send(f"🎉 {message.author.mention} est passé niveau {new_level} !")
        await msg.delete(delay=10)

    await bot.process_commands(message)

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot or "Verified" not in [role.name for role in member.roles]:
        return

    user_id = str(member.id)
    if user_id not in xp_dict:
        xp_dict[user_id] = {"messages": 0, "vocal_levels": 0}

    now = time.time()
    if after.channel and not before.channel:
        vocal_start_times[user_id] = now
    elif not after.channel and before.channel and user_id in vocal_start_times:
        duration = now - vocal_start_times.pop(user_id)
        if duration >= 2 * 3600:
            xp_dict[user_id]["vocal_levels"] += 1
            save_xp_data()
            await member.guild.text_channels[0].send(f"🎧 {member.mention} a gagné un niveau vocal !")

# Démarrage
xp_dict = load_xp_data()
keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))

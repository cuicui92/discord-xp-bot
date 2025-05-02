import discord 
from discord.ext import commands, tasks
import json
import time
import os
import firebase_admin
from firebase_admin import credentials, db

# IMPORT DU KEEP_ALIVE pour garder le bot actif
from web import keep_alive

# Initialisation de Firebase
cred = credentials.Certificate("firebase_config.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://xp-bot-f4291-default-rtdb.firebaseio.com/'
})

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Dictionnaire pour stocker l'XP des utilisateurs
xp_dict = {}
vocal_start_times = {}  # Pour stocker le temps d'entrée en vocal

# Charger les données d'XP depuis Firebase
def load_xp_data():
    ref = db.reference('xp_data')
    return ref.get() or {}

# Sauvegarder les données d'XP dans Firebase
def save_xp_data():
    ref = db.reference('xp_data')
    ref.set(xp_dict)

# Calculer le niveau texte
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

# Calculer le total
def calculate_total_level(user_id):
    data = xp_dict.get(user_id, {})
    messages = data.get("messages", 0)
    vocal_levels = data.get("vocal_levels", 0)
    text_level = calculate_text_level(messages)
    return text_level + vocal_levels

# Progression vers le prochain niveau
def get_progress_bar(messages):
    if messages < 150:
        current = messages % 15
        total = 15
    elif messages < 500:
        current = (messages - 150) % 20
        total = 20
    elif messages < 1250:
        current = (messages - 500) % 25
        total = 25
    elif messages < 2250:
        current = (messages - 1250) % 30
        total = 30
    else:
        current = (messages - 2250) % 35
        total = 35

    percent = current / total
    bars = int(percent * 10)

    # Création de la barre avec 🟩 pour progression, 🟧 pour la position actuelle et ⬜ pour les cases restantes
    bar_display = "[" + "🟩" * (bars - 1) + "🟧" + "⬜" * (10 - bars) + f"] {int(percent * 100)}%"
    return bar_display

AUTHORIZED_CHANNEL_NAME = "🪜・level"

# Commandes
@bot.command()
async def level(ctx):
    if ctx.channel.name != AUTHORIZED_CHANNEL_NAME:
        return await ctx.send(f"{ctx.author.mention}, tu peux utiliser cette commande uniquement dans #{AUTHORIZED_CHANNEL_NAME} !")

    user_id = str(ctx.author.id)
    if user_id not in xp_dict:
        xp_dict[user_id] = {"messages": 0, "vocal_levels": 0}
    total_level = calculate_total_level(user_id)
    progress_bar = get_progress_bar(xp_dict[user_id]["messages"])

    embed = discord.Embed(title=f"{ctx.author.name}'s Niveau", description=f"**Niveau** : {total_level}\n**Progression** : {progress_bar}", color=discord.Color.blue())
    embed.set_thumbnail(url=ctx.author.avatar.url)
    await ctx.send(embed=embed)
    await ctx.message.delete()

@bot.command()
async def rank(ctx):
    if ctx.channel.name != AUTHORIZED_CHANNEL_NAME:
        return await ctx.send(f"{ctx.author.mention}, tu peux utiliser cette commande uniquement dans #{AUTHORIZED_CHANNEL_NAME} !")

    leaderboard = [(uid, calculate_total_level(uid)) for uid in xp_dict]
    leaderboard.sort(key=lambda x: x[1], reverse=True)

    embed = discord.Embed(title="🏆 Classement des niveaux", color=discord.Color.gold())

    for i, (user_id, level) in enumerate(leaderboard[:10], start=1):
        try:
            user = await bot.fetch_user(int(user_id))
            embed.add_field(name=f"{i}. {user.name}", value=f"Niveau {level}", inline=False)
        except:
            continue

    author_id = str(ctx.author.id)
    for i, (user_id, _) in enumerate(leaderboard, start=1):
        if user_id == author_id and i > 10:
            total_level = calculate_total_level(author_id)
            embed.add_field(name="🏅 Ta position", value=f"{i}ᵉ — {ctx.author.name} (Niveau {total_level})", inline=False)
            break

    embed.set_thumbnail(url=ctx.author.avatar.url)
    await ctx.send(embed=embed)
    await ctx.message.delete()

@bot.command()
async def mystats(ctx):
    if ctx.channel.name != AUTHORIZED_CHANNEL_NAME:
        return await ctx.send(f"{ctx.author.mention}, tu peux utiliser cette commande uniquement dans #{AUTHORIZED_CHANNEL_NAME} !")

    user_id = str(ctx.author.id)
    if user_id not in xp_dict:
        xp_dict[user_id] = {"messages": 0, "vocal_levels": 0}
    total_level = calculate_total_level(user_id)
    progress_bar = get_progress_bar(xp_dict[user_id]["messages"])

    embed = discord.Embed(title=f"Statistiques de {ctx.author.name}", description=f"**Niveau** : {total_level}\n**Progression** : {progress_bar}", color=discord.Color.green())
    embed.set_thumbnail(url=ctx.author.avatar.url)
    await ctx.send(embed=embed)
    await ctx.message.delete()

@bot.command()
async def topvocal(ctx):
    if ctx.channel.name != AUTHORIZED_CHANNEL_NAME:
        return await ctx.send(f"{ctx.author.mention}, tu peux utiliser cette commande uniquement dans #{AUTHORIZED_CHANNEL_NAME} !")

    leaderboard = sorted(xp_dict.items(), key=lambda item: item[1].get("vocal_levels", 0), reverse=True)

    embed = discord.Embed(title="🏆 Classement des niveaux vocaux", color=discord.Color.blue())
    for i, (user_id, data) in enumerate(leaderboard[:10], start=1):
        try:
            user = await bot.fetch_user(int(user_id))
            embed.add_field(name=f"{i}. {user.name}", value=f"Niveau vocal {data['vocal_levels']}", inline=False)
        except:
            continue
    embed.set_thumbnail(url=ctx.author.avatar.url)
    await ctx.send(embed=embed)
    await ctx.message.delete()

@bot.command()
async def topmessages(ctx):
    if ctx.channel.name != AUTHORIZED_CHANNEL_NAME:
        return await ctx.send(f"{ctx.author.mention}, tu peux utiliser cette commande uniquement dans #{AUTHORIZED_CHANNEL_NAME} !")

    leaderboard = sorted(xp_dict.items(), key=lambda item: item[1].get("messages", 0), reverse=True)

    embed = discord.Embed(title="🏆 Classement des messages", color=discord.Color.green())
    for i, (user_id, data) in enumerate(leaderboard[:10], start=1):
        try:
            user = await bot.fetch_user(int(user_id))
            embed.add_field(name=f"{i}. {user.name}", value=f"{data['messages']} messages", inline=False)
        except:
            continue
    embed.set_thumbnail(url=ctx.author.avatar.url)
    await ctx.send(embed=embed)
    await ctx.message.delete()

# Gestion des messages
@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if "Verified" not in [role.name for role in message.author.roles]:
        return

    user_id = str(message.author.id)
    if user_id not in xp_dict:
        xp_dict[user_id] = {"messages": 0, "vocal_levels": 0}

    old_level = calculate_total_level(user_id)
    xp_dict[user_id]["messages"] += 1
    save_xp_data()
    new_level = calculate_total_level(user_id)

    if new_level > old_level:
        level_up_msg = await message.channel.send(f"🎉 {message.author.mention} vient de monter au niveau {new_level} !")
        await level_up_msg.delete(delay=10)

    await bot.process_commands(message)

# Gestion du vocal
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    if "Verified" not in [role.name for role in member.roles]:
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
            old_level = xp_dict[user_id]["vocal_levels"]
            xp_dict[user_id]["vocal_levels"] += 1
            save_xp_data()
            new_level = xp_dict[user_id]["vocal_levels"]
            if new_level > old_level:
                await member.guild.text_channels[0].send(f"🎧 {member.mention} vient de monter de niveau vocal à {new_level} !")

# Keep Alive + Run Bot
keep_alive()
bot.run(os.getenv("DISCORD_TOKEN"))

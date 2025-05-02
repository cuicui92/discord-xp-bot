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
cred = credentials.Certificate("firebase_config.json")  # Assure-toi que le fichier firebase_config.json est dans le même dossier que ton script
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://xp-bot-f4291-default-rtdb.firebaseio.com/'  # Ton URL Firebase
})

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Dictionnaire pour stocker l'XP des utilisateurs
xp_dict = {}

# Charger les données d'XP depuis Firebase
def load_xp_data():
    ref = db.reference('xp_data')
    return ref.get() or {}

# Sauvegarder les données d'XP dans Firebase
def save_xp_data():
    ref = db.reference('xp_data')
    ref.set(xp_dict)

# Calculer le niveau texte selon le nombre de messages
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

# Calculer le total (texte + vocal)
def calculate_total_level(user_id):
    data = xp_dict.get(user_id, {})
    messages = data.get("messages", 0)
    vocal_levels = data.get("vocal_levels", 0)
    text_level = calculate_text_level(messages)
    return text_level + vocal_levels

# Calculer la progression vers prochain niveau
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
    bar_display = f"🟩" * bars + f"⬜" * (10 - bars) + f" {int(percent * 100)}%"
    return bar_display

AUTHORIZED_CHANNEL_NAME = "🪜・level"

@bot.command()
async def level(ctx):
    if ctx.channel.name != AUTHORIZED_CHANNEL_NAME:
        return await ctx.send(f"{ctx.author.mention}, tu peux utiliser cette commande uniquement dans #{AUTHORIZED_CHANNEL_NAME} !")

    user_id = str(ctx.author.id)
    if user_id not in xp_dict:
        xp_dict[user_id] = {"messages": 0, "vocal_levels": 0}
    total_level = calculate_total_level(user_id)
    progress_bar = get_progress_bar(xp_dict[user_id]["messages"])
    await ctx.send(f"{ctx.author.mention}, tu es niveau {total_level} !\nProgression : {progress_bar}")
    await ctx.message.delete()

@bot.command()
async def rank(ctx):
    if ctx.channel.name != AUTHORIZED_CHANNEL_NAME:
        return await ctx.send(f"{ctx.author.mention}, tu peux utiliser cette commande uniquement dans #{AUTHORIZED_CHANNEL_NAME} !")

    leaderboard = []

    for user_id, data in xp_dict.items():
        total_level = calculate_total_level(user_id)
        leaderboard.append((user_id, total_level))

    leaderboard.sort(key=lambda x: x[1], reverse=True)

    embed = discord.Embed(title="🏆 Classement des niveaux", color=discord.Color.gold())

    for i, (user_id, total_level) in enumerate(leaderboard[:10], start=1):
        try:
            user = await bot.fetch_user(int(user_id))
            embed.add_field(name=f"{i}. {user.name}", value=f"Niveau {total_level}", inline=False)
            embed.set_thumbnail(url=user.avatar_url)  # Ajout de l'avatar de l'utilisateur
        except:
            continue

    author_id = str(ctx.author.id)
    author_position = None
    for i, (user_id, _) in enumerate(leaderboard, start=1):
        if user_id == author_id:
            author_position = i
            break

    if author_position and author_position > 10:
        total_level = calculate_total_level(author_id)
        embed.add_field(
            name="🏅 Ta position",
            value=f"{author_position}ᵉ — {ctx.author.name} (Niveau {total_level})",
            inline=False
        )

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

    embed = discord.Embed(title=f"📊 Statistiques de {ctx.author.name}", color=discord.Color.blue())
    embed.add_field(name="Niveau total", value=total_level, inline=False)
    embed.add_field(name="Messages envoyés", value=xp_dict[user_id]["messages"], inline=False)
    embed.add_field(name="Niveau vocal", value=xp_dict[user_id]["vocal_levels"], inline=False)
    embed.add_field(name="Progression", value=progress_bar, inline=False)
    embed.set_thumbnail(url=ctx.author.avatar_url)  # Ajout de la photo de profil de l'utilisateur

    await ctx.send(embed=embed)
    await ctx.message.delete()

@bot.command()
async def topvocal(ctx):
    if ctx.channel.name != AUTHORIZED_CHANNEL_NAME:
        return await ctx.send(f"{ctx.author.mention}, tu peux utiliser cette commande uniquement dans #{AUTHORIZED_CHANNEL_NAME} !")

    vocal_leaderboard = []

    for user_id, data in xp_dict.items():
        vocal_level = data.get("vocal_levels", 0)
        vocal_leaderboard.append((user_id, vocal_level))

    vocal_leaderboard.sort(key=lambda x: x[1], reverse=True)

    embed = discord.Embed(title="🏆 Classement des niveaux vocaux", color=discord.Color.blue())

    for i, (user_id, vocal_level) in enumerate(vocal_leaderboard[:10], start=1):
        try:
            user = await bot.fetch_user(int(user_id))
            embed.add_field(name=f"{i}. {user.name}", value=f"Niveau vocal {vocal_level}", inline=False)
            embed.set_thumbnail(url=user.avatar_url)  # Ajout de l'avatar de l'utilisateur
        except:
            continue

    await ctx.send(embed=embed)
    await ctx.message.delete()

@bot.command()
async def topmessages(ctx):
    if ctx.channel.name != AUTHORIZED_CHANNEL_NAME:
        return await ctx.send(f"{ctx.author.mention}, tu peux utiliser cette commande uniquement dans #{AUTHORIZED_CHANNEL_NAME} !")

    messages_leaderboard = []

    for user_id, data in xp_dict.items():
        messages_count = data.get("messages", 0)
        messages_leaderboard.append((user_id, messages_count))

    messages_leaderboard.sort(key=lambda x: x[1], reverse=True)

    embed = discord.Embed(title="🏆 Classement des messages", color=discord.Color.green())

    for i, (user_id, messages_count) in enumerate(messages_leaderboard[:10], start=1):
        try:
            user = await bot.fetch_user(int(user_id))
            embed.add_field(name=f"{i}. {user.name}", value=f"{messages_count} messages", inline=False)
            embed.set_thumbnail(url=user.avatar_url)  # Ajout de l'avatar de l'utilisateur
        except:
            continue

    await ctx.send(embed=embed)
    await ctx.message.delete()

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    user_id = str(message.author.id)
    if "Verified" not in [role.name for role in message.author.roles]:
        return

    if user_id not in xp_dict:
        xp_dict[user_id] = {"messages": 0, "vocal_levels": 0}

    old_level = calculate_total_level(user_id)
    xp_dict[user_id]["messages"] += 1
    new_level = calculate_total_level(user_id)

    save_xp_data()

    await bot.process_commands(message)
    
keep_alive()
bot.run('YOUR_BOT_TOKEN')

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

# Charger les données d'XP depuis Firebase pour un serveur donné
def load_xp_data(guild_id):
    ref = db.reference(f'xp_data/{guild_id}')
    return ref.get() or {}

# Sauvegarder les données d'XP pour un serveur donné dans Firebase
def save_xp_data(guild_id, xp_dict):
    ref = db.reference(f'xp_data/{guild_id}')
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
def calculate_total_level(user_id, guild_id, xp_dict):
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
    bar_display = "[" + "█" * bars + "░" * (10 - bars) + f"] {int(percent * 100)}%"
    return bar_display

AUTHORIZED_CHANNEL_NAME = "level"

@bot.command()
async def level(ctx):
    guild_id = str(ctx.guild.id)  # Récupérer l'ID du serveur
    xp_dict = load_xp_data(guild_id)

    if ctx.channel.name != AUTHORIZED_CHANNEL_NAME:
        return await ctx.send(f"{ctx.author.mention}, tu peux utiliser cette commande uniquement dans #{AUTHORIZED_CHANNEL_NAME} !")

    user_id = str(ctx.author.id)
    if user_id not in xp_dict:
        xp_dict[user_id] = {"messages": 0, "vocal_levels": 0}
    total_level = calculate_total_level(user_id, guild_id, xp_dict)
    progress_bar = get_progress_bar(xp_dict[user_id]["messages"])
    await ctx.send(f"{ctx.author.mention}, tu es niveau {total_level} !\nProgression : {progress_bar}")

@bot.command()
async def rank(ctx):
    guild_id = str(ctx.guild.id)  # Récupérer l'ID du serveur
    xp_dict = load_xp_data(guild_id)

    if ctx.channel.name != AUTHORIZED_CHANNEL_NAME:
        return await ctx.send(f"{ctx.author.mention}, tu peux utiliser cette commande uniquement dans #{AUTHORIZED_CHANNEL_NAME} !")

    leaderboard = []

    for user_id, data in xp_dict.items():
        total_level = calculate_total_level(user_id, guild_id, xp_dict)
        leaderboard.append((user_id, total_level))

    leaderboard.sort(key=lambda x: x[1], reverse=True)

    embed = discord.Embed(title="🏆 Classement des niveaux", color=discord.Color.gold())

    for i, (user_id, total_level) in enumerate(leaderboard[:10], start=1):
        try:
            user = await bot.fetch_user(int(user_id))
            embed.add_field(name=f"{i}. {user.name}", value=f"Niveau {total_level}", inline=False)
        except:
            continue

    author_id = str(ctx.author.id)
    author_position = None
    for i, (user_id, _) in enumerate(leaderboard, start=1):
        if user_id == author_id:
            author_position = i
            break

    if author_position and author_position > 10:
        total_level = calculate_total_level(author_id, guild_id, xp_dict)
        embed.add_field(
            name="🏅 Ta position",
            value=f"{author_position}ᵉ — {ctx.author.name} (Niveau {total_level})",
            inline=False
        )

    await ctx.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    guild_id = str(message.guild.id)  # Récupérer l'ID du serveur
    xp_dict = load_xp_data(guild_id)

    user_id = str(message.author.id)
    if "Verified" not in [role.name for role in message.author.roles]:
        return

    if user_id not in xp_dict:
        xp_dict[user_id] = {"messages": 0, "vocal_levels": 0}

    old_level = calculate_total_level(user_id, guild_id, xp_dict)
    xp_dict[user_id]["messages"] += 1
    save_xp_data(guild_id, xp_dict)
    new_level = calculate_total_level(user_id, guild_id, xp_dict)

    if new_level > old_level:
        await message.channel.send(f"🎉 {message.author.mention} vient de monter au niveau {new_level} ! GG à lui !")

    await bot.process_commands(message)

@tasks.loop(minutes=10)
async def voice_activity_check():
    for guild in bot.guilds:
        for member in guild.members:
            if member.bot:
                continue
            if "Verified" in [role.name for role in member.roles]:
                if member.voice and member.voice.channel:
                    user_id = str(member.id)
                    guild_id = str(guild.id)  # Récupérer l'ID du serveur
                    xp_dict = load_xp_data(guild_id)

                    if user_id not in xp_dict:
                        xp_dict[user_id] = {"messages": 0, "vocal_levels": 0}

                    last_time = xp_dict.get(f"{user_id}_voice_time", time.time())
                    current_time = time.time()

                    if current_time - last_time >= 7200:
                        xp_dict[user_id]["vocal_levels"] += 1
                        xp_dict[f"{user_id}_voice_time"] = current_time
                        save_xp_data(guild_id, xp_dict)

@bot.event
async def on_ready():
    print(f"{bot.user} est prêt !")
    voice_activity_check.start()

# LANCER LE SERVEUR FLASK POUR RENDER (keep-alive)
keep_alive()

# LANCER LE BOT DISCORD
bot.run(os.getenv("DISCORD_TOKEN"))



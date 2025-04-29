import discord
from discord.ext import commands, tasks
import json
import time
import os

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Dictionnaire pour stocker l'XP des utilisateurs
xp_dict = {}

# Fichier pour enregistrer l'XP
xp_file = "xp_data.json"
if not os.path.exists(xp_file):
    with open(xp_file, "w") as f:
        json.dump({}, f)

# Charger les données d'XP
def load_xp_data():
    with open(xp_file, "r") as f:
        return json.load(f)

# Sauvegarder les données d'XP
def save_xp_data():
    with open(xp_file, "w") as f:
        json.dump(xp_dict, f)

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
    bar_display = "[" + "█" * bars + "░" * (10 - bars) + f"] {int(percent * 100)}%"
    return bar_display

# Nom du salon où les commandes sont autorisées
AUTHORIZED_CHANNEL_NAME = "level"

# Commande pour voir son niveau
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

# Commande pour voir le classement
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

# Gérer les messages envoyés
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
    save_xp_data()
    new_level = calculate_total_level(user_id)

    if new_level > old_level:
        await message.channel.send(f"🎉 {message.author.mention} vient de monter au niveau {new_level} ! GG à lui !")

    await bot.process_commands(message)

# Gérer le vocal toutes les 10 minutes
@tasks.loop(minutes=10)
async def voice_activity_check():
    for guild in bot.guilds:
        for member in guild.members:
            if member.bot:
                continue
            if "Verified" in [role.name for role in member.roles]:
                if member.voice and member.voice.channel:
                    user_id = str(member.id)
                    if user_id not in xp_dict:
                        xp_dict[user_id] = {"messages": 0, "vocal_levels": 0}

                    last_time = xp_dict.get(f"{user_id}_voice_time", time.time())
                    current_time = time.time()

                    if current_time - last_time >= 7200:
                        xp_dict[user_id]["vocal_levels"] += 1
                        xp_dict[f"{user_id}_voice_time"] = current_time
                        save_xp_data()

# Quand le bot est prêt
@bot.event
async def on_ready():
    print(f"{bot.user} est prêt !")
    voice_activity_check.start()

# Lancer le bot
bot.run("MTM2NjIzMDY0ODMyNjQ1OTQ2NQ.GiWQGE.bLw6hHKTsilVYTEqUEtXUPZ9Jz0GarLoZFMpOk")

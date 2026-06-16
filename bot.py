import discord
from discord.ext import commands
import os
from anime_rp_system import setup_rp

# ============================
# BOT INTENTS
# ============================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

# ============================
# BOT SETUP
# ============================

bot = commands.Bot(
    command_prefix="!",
    intents=intents
)

OWNER_ID = 1405193599984861255  # Leon

# ============================
# READY EVENT
# ============================

@bot.event
async def on_ready():
    print(f"Bot ist online als {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Slash Commands synchronisiert: {len(synced)}")
    except Exception as e:
        print(f"Fehler beim Sync: {e}")

# ============================
# OWNER CHECK
# ============================

def is_owner():
    async def predicate(ctx):
        return ctx.author.id == OWNER_ID
    return commands.check(predicate)

# ============================
# SIMPLE OWNER COMMAND
# ============================

@bot.command()
@is_owner()
async def shutdown(ctx):
    await ctx.send("🔌 Bot wird heruntergefahren...")
    await bot.close()

# ============================
# LOAD ANIME RP SYSTEM
# ============================

setup_rp(bot)

# ============================
# BOT TOKEN START
# ============================

TOKEN = "DEIN_TOKEN_HIER"
bot.run(TOKEN)

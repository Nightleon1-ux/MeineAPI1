import discord
import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

chat_verlaeufe = {}

async def groq_anfrage(messages, modell="llama-3.3-70b-versatile", max_tokens=1000):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": modell,
        "messages": messages,
        "max_tokens": max_tokens
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(GROQ_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise Exception(f"Groq Fehler ({resp.status}): {data}")
            return data["choices"][0]["message"]["content"]

@bot.event
async def on_ready():
    print(f"✅ Bot ist online als {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    inhalt = message.content
    user_id = str(message.author.id)

    # ─── !ki Befehl ────────────────────────────────────────
    if inhalt.startswith("!ki "):
        frage = inhalt[4:]
        async with message.channel.typing():
            try:
                if user_id not in chat_verlaeufe:
                    chat_verlaeufe[user_id] = []

                chat_verlaeufe[user_id].append({"role": "user", "content": frage})

                if len(chat_verlaeufe[user_id]) > 20:
                    chat_verlaeufe[user_id] = chat_verlaeufe[user_id][-20:]

                messages = [{"role": "system", "content": "Du bist ein hilfreicher Assistent."}] + chat_verlaeufe[user_id]

                antwort_text = await groq_anfrage(messages)
                chat_verlaeufe[user_id].append({"role": "assistant", "content": antwort_text})

                if len(antwort_text) > 2000:
                    antwort_text = antwort_text[:1997] + "..."

                await message.reply(f"🤖 {antwort_text}")
            except Exception as e:
                await message.reply(f"❌ Fehler: {repr(e)}")

    # ─── !übersetzen Befehl ────────────────────────────────
    elif inhalt.startswith("!übersetzen "):
        text = inhalt[12:]
        async with message.channel.typing():
            try:
                messages = [
                    {"role": "system", "content": "Du bist ein Übersetzer. Antworte NUR mit der Übersetzung auf Englisch."},
                    {"role": "user", "content": text}
                ]
                antwort_text = await groq_anfrage(messages, modell="llama-3.1-8b-instant", max_tokens=500)
                await message.reply(f"🌍 **Übersetzung:** {antwort_text}")
            except Exception as e:
                await message.reply(f"❌ Fehler: {repr(e)}")

    # ─── !zusammenfassen Befehl ────────────────────────────
    elif inhalt.startswith("!zusammenfassen "):
        text = inhalt[16:]
        async with message.channel.typing():
            try:
                messages = [
                    {"role": "system", "content": "Du fasst Texte kurz und präzise zusammen."},
                    {"role": "user", "content": text}
                ]
                antwort_text = await groq_anfrage(messages, modell="llama-3.1-8b-instant", max_tokens=500)
                await message.reply(f"📝 **Zusammenfassung:** {antwort_text}")
            except Exception as e:
                await message.reply(f"❌ Fehler: {repr(e)}")

    # ─── !reset Befehl ─────────────────────────────────────
    elif inhalt == "!reset":
        chat_verlaeufe[user_id] = []
        await message.reply("🗑️ Dein Chat Verlauf wurde gelöscht!")

    # ─── !hilfe Befehl ─────────────────────────────────────
    elif inhalt == "!hilfe":
        embed = discord.Embed(title="🤖 Bot Befehle", color=0x3498DB)
        embed.add_field(name="!ki [frage]", value="KI beantwortet deine Frage", inline=False)
        embed.add_field(name="!übersetzen [text]", value="Übersetzt Text auf Englisch 🌍", inline=False)
        embed.add_field(name="!zusammenfassen [text]", value="Fasst einen Text zusammen 📝", inline=False)
        embed.add_field(name="!reset", value="Löscht deinen Chat Verlauf 🗑️", inline=False)
        await message.reply(embed=embed)

bot.run(DISCORD_TOKEN)

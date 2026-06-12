import discord
import aiohttp
import os
import io
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client_groq = Groq(api_key=GROQ_API_KEY)

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

chat_verlaeufe = {}

@bot.event
async def on_ready():
    print(f"✅ Bot ist online als {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    inhalt = message.content
    user_id = str(message.author.id)

    if inhalt.startswith("!ki "):
        frage = inhalt[4:]
        async with message.channel.typing():
            try:
                if user_id not in chat_verlaeufe:
                    chat_verlaeufe[user_id] = []
                
                chat_verlaeufe[user_id].append({"role": "user", "content": frage})
                
                if len(chat_verlaeufe[user_id]) > 20:
                    chat_verlaeufe[user_id] = chat_verlaeufe[user_id][-20:]

                antwort = client_groq.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": "Du bist ein hilfreicher Assistent."}
                    ] + chat_verlaeufe[user_id],
                    max_tokens=1000
                )
                antwort_text = antwort.choices[0].message.content
                chat_verlaeufe[user_id].append({"role": "assistant", "content": antwort_text})

                if len(antwort_text) > 2000:
                    antwort_text = antwort_text[:1997] + "..."

                await message.reply(f"🤖 {antwort_text}")
            except Exception as e:
                await message.reply(f"❌ Fehler: {str(e)}")

    elif inhalt.startswith("!bild "):
        beschreibung = inhalt[6:]
        async with message.channel.typing():
            try:
                url_beschreibung = beschreibung.replace(" ", "%20")
                bild_url = f"https://image.pollinations.ai/prompt/{url_beschreibung}?width=1024&height=1024&nologo=true"
                await message.reply(f"🎨 Generiere Bild: **{beschreibung}**\nWarte kurz...")
                async with aiohttp.ClientSession() as session:
                    async with session.get(bild_url, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                        if resp.status == 200:
                            bild_daten = await resp.read()
                            datei = discord.File(io.BytesIO(bild_daten), filename="bild.png")
                            await message.channel.send(f"✅ Fertig!", file=datei)
                        else:
                            await message.channel.send("❌ Bild konnte nicht erstellt werden!")
            except Exception as e:
                await message.channel.send(f"❌ Fehler: {str(e)}")

    elif inhalt.startswith("!übersetzen "):
        text = inhalt[12:]
        async with message.channel.typing():
            try:
                antwort = client_groq.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": "Du bist ein Übersetzer. Antworte NUR mit der Übersetzung auf Englisch."},
                        {"role": "user", "content": text}
                    ],
                    max_tokens=500
                )
                await message.reply(f"🌍 **Übersetzung:** {antwort.choices[0].message.content}")
            except Exception as e:
                await message.reply(f"❌ Fehler: {str(e)}")

    elif inhalt.startswith("!zusammenfassen "):
        text = inhalt[16:]
        async with message.channel.typing():
            try:
                antwort = client_groq.chat.completions.create(
                    model="llama-3.1-8b-instant",
                    messages=[
                        {"role": "system", "content": "Du fasst Texte kurz und präzise zusammen."},
                        {"role": "user", "content": text}
                    ],
                    max_tokens=500
                )
                await message.reply(f"📝 **Zusammenfassung:** {antwort.choices[0].message.content}")
            except Exception as e:
                await message.reply(f"❌ Fehler: {str(e)}")

    elif inhalt == "!reset":
        chat_verlaeufe[user_id] = []
        await message.reply("🗑️ Dein Chat Verlauf wurde gelöscht!")

    elif inhalt == "!hilfe":
        embed = discord.Embed(title="🤖 Bot Befehle", color=0x3498DB)
        embed.add_field(name="!ki [frage]", value="KI beantwortet deine Frage", inline=False)
        embed.add_field(name="!bild [beschreibung]", value="Erstellt ein KI Bild 🎨", inline=False)
        embed.add_field(name="!übersetzen [text]", value="Übersetzt Text auf Englisch 🌍", inline=False)
        embed.add_field(name="!zusammenfassen [text]", value="Fasst einen Text zusammen 📝", inline=False)
        embed.add_field(name="!reset", value="Löscht deinen Chat Verlauf 🗑️", inline=False)
        await message.reply(embed=embed)

bot.run(DISCORD_TOKEN)

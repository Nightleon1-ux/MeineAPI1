import discord
import aiohttp
import os
import io
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
# Wenn auf Railway gehostet, nutze die Railway URL statt localhost
API_URL = os.getenv("API_URL", "http://localhost:8000")
API_KEY = "mein-geheimer-key-123"

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot ist online als {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    inhalt = message.content

    if inhalt.startswith("!ki "):
        frage = inhalt[4:]
        async with message.channel.typing():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{API_URL}/chat",
                        json={
                            "nachricht": frage,
                            "session_id": str(message.author.id),
                            "modell": "gut"
                        },
                        headers={"api-key": API_KEY}
                    ) as response:
                        data = await response.json()
                        antwort = data.get("antwort", "Fehler!")
                        if len(antwort) > 2000:
                            antwort = antwort[:1997] + "..."
                        await message.reply(f"🤖 {antwort}")
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
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{API_URL}/chat",
                        json={
                            "nachricht": f"Übersetze diesen Text auf Englisch: {text}",
                            "system": "Du bist ein Übersetzer. Antworte NUR mit der Übersetzung.",
                            "modell": "schnell"
                        },
                        headers={"api-key": API_KEY}
                    ) as response:
                        data = await response.json()
                        antwort = data.get("antwort", "Fehler!")
                        await message.reply(f"🌍 **Übersetzung:** {antwort}")
            except Exception as e:
                await message.reply(f"❌ Fehler: {str(e)}")

    elif inhalt.startswith("!zusammenfassen "):
        text = inhalt[16:]
        async with message.channel.typing():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{API_URL}/chat",
                        json={
                            "nachricht": f"Fasse diesen Text kurz zusammen: {text}",
                            "system": "Du fasst Texte kurz und präzise zusammen.",
                            "modell": "schnell"
                        },
                        headers={"api-key": API_KEY}
                    ) as response:
                        data = await response.json()
                        antwort = data.get("antwort", "Fehler!")
                        await message.reply(f"📝 **Zusammenfassung:** {antwort}")
            except Exception as e:
                await message.reply(f"❌ Fehler: {str(e)}")

    elif inhalt == "!reset":
        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    f"{API_URL}/verlauf/{message.author.id}/loeschen",
                    headers={"api-key": API_KEY}
                ) as response:
                    await message.reply("🗑️ Dein Chat Verlauf wurde gelöscht!")
        except Exception as e:
            await message.reply(f"❌ Fehler: {str(e)}")

    elif inhalt == "!hilfe":
        embed = discord.Embed(title="🤖 Bot Befehle", color=0x3498DB)
        embed.add_field(name="!ki [frage]", value="KI beantwortet deine Frage", inline=False)
        embed.add_field(name="!bild [beschreibung]", value="Erstellt ein KI Bild 🎨", inline=False)
        embed.add_field(name="!übersetzen [text]", value="Übersetzt Text auf Englisch 🌍", inline=False)
        embed.add_field(name="!zusammenfassen [text]", value="Fasst einen Text zusammen 📝", inline=False)
        embed.add_field(name="!reset", value="Löscht deinen Chat Verlauf 🗑️", inline=False)
        await message.reply(embed=embed)

bot.run(DISCORD_TOKEN)

import discord
import aiohttp
import os
import random
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

chat_verlaeufe = {}      # Chat Verlauf pro User
persoenlichkeit = {}     # Gewählte Persönlichkeit pro User
merkliste = {}           # Gemerkte Fakten pro User
levels = {}              # XP / Level pro User
rate_spiel = {}          # Laufende Zahlenrate-Spiele

# ─── Persönlichkeiten ──────────────────────────────────────
PERSONAS = {
    "anwalt": "Du bist ein seriöser, sachlicher Anwalt. Du antwortest präzise, formell und nutzt gerne Fachbegriffe, erklärst aber alles verständlich. Du sprichst den User mit 'Sie' an.",
    "mädel": "Du bist eine freche, lustige und herzliche Freundin. Du redest locker, nutzt Emojis 😊✨ und Umgangssprache. Du sprichst den User mit 'du' an.",
    "lehrer": "Du bist ein geduldiger, motivierender Lehrer. Du erklärst Dinge Schritt für Schritt, einfach und ermutigend. Du lobst Fortschritte.",
    "pirat": "Du bist ein wilder Pirat! Du sprichst wie ein Pirat (Arrr, Landratte, Schatzkiste etc.), bist abenteuerlustig und übertrieben dramatisch.",
    "standard": "Du bist ein hilfreicher Assistent."
}

PERSONA_EMOJIS = {
    "anwalt": "🧑‍⚖️", "mädel": "👧", "lehrer": "👨‍🏫", "pirat": "🏴‍☠️", "standard": "🤖"
}

async def groq_anfrage(messages, modell="llama-3.3-70b-versatile", max_tokens=1000):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": modell, "messages": messages, "max_tokens": max_tokens}
    async with aiohttp.ClientSession() as session:
        async with session.post(GROQ_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise Exception(f"Groq Fehler ({resp.status}): {data}")
            return data["choices"][0]["message"]["content"]

def xp_geben(user_id, menge=5):
    if user_id not in levels:
        levels[user_id] = {"xp": 0, "level": 1}
    levels[user_id]["xp"] += menge
    benoetigt = levels[user_id]["level"] * 100
    aufgestiegen = False
    if levels[user_id]["xp"] >= benoetigt:
        levels[user_id]["xp"] -= benoetigt
        levels[user_id]["level"] += 1
        aufgestiegen = True
    return aufgestiegen

@bot.event
async def on_ready():
    print(f"✅ Bot ist online als {bot.user}")

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    inhalt = message.content
    inhalt_lower = inhalt.lower()
    user_id = str(message.author.id)
    user_name = message.author.display_name

    # ─── Zahlenrate-Spiel: Tipp abgeben ────────────────────
    if user_id in rate_spiel and inhalt.strip().lstrip("-").isdigit():
        tipp = int(inhalt.strip())
        ziel = rate_spiel[user_id]["zahl"]
        rate_spiel[user_id]["versuche"] += 1
        if tipp == ziel:
            versuche = rate_spiel[user_id]["versuche"]
            del rate_spiel[user_id]
            xp_geben(user_id, 20)
            await message.reply(f"🎉 Richtig! Die Zahl war **{ziel}**! Du hast {versuche} Versuche gebraucht. +20 XP!")
        elif tipp < ziel:
            await message.reply("📈 Höher!")
        else:
            await message.reply("📉 Niedriger!")
        return

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

                persona_key = persoenlichkeit.get(user_id, "standard")
                system_text = PERSONAS[persona_key]

                if user_id in merkliste and merkliste[user_id]:
                    fakten = "; ".join(merkliste[user_id])
                    system_text += f" Wichtige Infos über den User, die du dir merken sollst: {fakten}."

                messages = [{"role": "system", "content": system_text}] + chat_verlaeufe[user_id]

                antwort_text = await groq_anfrage(messages)
                chat_verlaeufe[user_id].append({"role": "assistant", "content": antwort_text})

                if len(antwort_text) > 2000:
                    antwort_text = antwort_text[:1997] + "..."

                emoji = PERSONA_EMOJIS.get(persona_key, "🤖")
                xp_geben(user_id, 5)
                await message.reply(f"{emoji} {antwort_text}")
            except Exception as e:
                await message.reply(f"❌ Fehler: {repr(e)}")

    # ─── !persönlichkeit Befehl ────────────────────────────
    elif inhalt.startswith("!persönlichkeit"):
        teile = inhalt.split(" ")
        if len(teile) < 2:
            optionen = ", ".join(f"`{k}`" for k in PERSONAS.keys())
            await message.reply(f"ℹ️ Nutze: `!persönlichkeit [option]`\nVerfügbar: {optionen}")
        else:
            wahl = teile[1].lower()
            if wahl in PERSONAS:
                persoenlichkeit[user_id] = wahl
                begruessungen = {
                    "anwalt": "🧑‍⚖️ Persönlichkeit gewechselt: **Anwalt** — Wie kann ich Ihnen behilflich sein?",
                    "mädel": "👧 Persönlichkeit gewechselt: **Mädel** — Heyyy, na was geht ab? 😊✨",
                    "lehrer": "👨‍🏫 Persönlichkeit gewechselt: **Lehrer** — Guten Tag! Womit kann ich dir heute helfen?",
                    "pirat": "🏴‍☠️ Persönlichkeit gewechselt: **Pirat** — Arrr! Bereit für ein Abenteuer, Landratte?",
                    "standard": "🤖 Persönlichkeit zurückgesetzt auf Standard!"
                }
                await message.reply(begruessungen[wahl])
            else:
                optionen = ", ".join(f"`{k}`" for k in PERSONAS.keys())
                await message.reply(f"❌ Unbekannte Persönlichkeit! Verfügbar: {optionen}")

    # ─── !merke Befehl ──────────────────────────────────────
    elif inhalt.startswith("!merke "):
        info = inhalt[7:]
        if user_id not in merkliste:
            merkliste[user_id] = []
        merkliste[user_id].append(info)
        await message.reply(f"🧠 Ich merke mir: *{info}*")

    # ─── !merkliste Befehl ──────────────────────────────────
    elif inhalt == "!merkliste":
        if user_id in merkliste and merkliste[user_id]:
            liste = "\n".join(f"• {x}" for x in merkliste[user_id])
            await message.reply(f"🧠 **Das merke ich mir über dich:**\n{liste}")
        else:
            await message.reply("🧠 Ich weiß noch nichts über dich! Nutze `!merke [info]`")

    # ─── !vergiss Befehl ────────────────────────────────────
    elif inhalt == "!vergiss":
        merkliste[user_id] = []
        await message.reply("🗑️ Alles vergessen, was ich mir über dich gemerkt habe!")

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

    # ─── !rechne Befehl ──────────────────────────────────────
    elif inhalt.startswith("!rechne "):
        text = inhalt[8:]
        try:
            erlaubt = set("0123456789+-*/(). ")
            if all(c in erlaubt for c in text):
                ergebnis = eval(text)
                await message.reply(f"🧮 **{text} = {ergebnis}**")
            else:
                await message.reply("❌ Nur Zahlen und + - * / ( ) erlaubt!")
        except Exception:
            await message.reply("❌ Das konnte ich nicht berechnen!")

    # ─── !würfel Befehl ──────────────────────────────────────
    elif inhalt.startswith("!würfel"):
        teile = inhalt.split(" ")
        seiten = 6
        if len(teile) > 1 and teile[1].isdigit():
            seiten = int(teile[1])
        ergebnis = random.randint(1, seiten)
        await message.reply(f"🎲 Du hast eine **{ergebnis}** gewürfelt! (1-{seiten})")

    # ─── !münze Befehl ────────────────────────────────────────
    elif inhalt == "!münze":
        ergebnis = random.choice(["Kopf 🪙", "Zahl 🪙"])
        await message.reply(f"🪙 **{ergebnis}**")

    # ─── !rate Befehl (Spiel starten) ─────────────────────────
    elif inhalt.startswith("!rate"):
        teile = inhalt.split(" ")
        maxz = 100
        if len(teile) > 1 and teile[1].isdigit():
            maxz = int(teile[1])
        rate_spiel[user_id] = {"zahl": random.randint(1, maxz), "versuche": 0}
        await message.reply(f"🔢 Ich denke an eine Zahl zwischen **1 und {maxz}**! Schreib einfach eine Zahl um zu raten!")

    # ─── !witz Befehl ────────────────────────────────────────
    elif inhalt == "!witz":
        async with message.channel.typing():
            try:
                messages = [
                    {"role": "system", "content": "Erzähle einen kurzen, lustigen Witz auf Deutsch. Nur den Witz, keine Einleitung."},
                    {"role": "user", "content": "Erzähl mir einen Witz"}
                ]
                antwort_text = await groq_anfrage(messages, modell="llama-3.1-8b-instant", max_tokens=200)
                await message.reply(f"😂 {antwort_text}")
            except Exception as e:
                await message.reply(f"❌ Fehler: {repr(e)}")

    # ─── !zitat Befehl ───────────────────────────────────────
    elif inhalt == "!zitat":
        async with message.channel.typing():
            try:
                messages = [
                    {"role": "system", "content": "Gib ein kurzes, motivierendes Zitat auf Deutsch aus. Nenne auch einen (ggf. erfundenen, aber plausiblen) Autor. Format: 'Zitat' - Autor"},
                    {"role": "user", "content": "Gib mir ein Zitat"}
                ]
                antwort_text = await groq_anfrage(messages, modell="llama-3.1-8b-instant", max_tokens=150)
                await message.reply(f"💬 {antwort_text}")
            except Exception as e:
                await message.reply(f"❌ Fehler: {repr(e)}")

    # ─── !geschichte Befehl ────────────────────────────────────
    elif inhalt.startswith("!geschichte "):
        thema = inhalt[12:]
        async with message.channel.typing():
            try:
                messages = [
                    {"role": "system", "content": "Schreibe eine kurze, kreative Geschichte (max 150 Wörter) auf Deutsch zum gegebenen Thema."},
                    {"role": "user", "content": thema}
                ]
                antwort_text = await groq_anfrage(messages, modell="llama-3.3-70b-versatile", max_tokens=400)
                await message.reply(f"📖 **Geschichte über '{thema}':**\n{antwort_text}")
            except Exception as e:
                await message.reply(f"❌ Fehler: {repr(e)}")

    # ─── !level / !rang Befehl ──────────────────────────────────
    elif inhalt == "!level" or inhalt == "!rang":
        daten = levels.get(user_id, {"xp": 0, "level": 1})
        benoetigt = daten["level"] * 100
        balken_voll = int((daten["xp"] / benoetigt) * 10)
        balken = "🟩" * balken_voll + "⬜" * (10 - balken_voll)
        await message.reply(f"⭐ **{user_name}**\nLevel: **{daten['level']}**\nXP: {daten['xp']}/{benoetigt}\n{balken}")

    # ─── !rangliste Befehl ───────────────────────────────────────
    elif inhalt == "!rangliste":
        if not levels:
            await message.reply("📊 Noch keine Daten vorhanden!")
        else:
            sortiert = sorted(levels.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)[:10]
            text = ""
            for i, (uid, daten) in enumerate(sortiert, 1):
                try:
                    user = await bot.fetch_user(int(uid))
                    name = user.display_name
                except Exception:
                    name = f"User {uid}"
                text += f"{i}. **{name}** — Level {daten['level']} ({daten['xp']} XP)\n"
            embed = discord.Embed(title="🏆 Rangliste", description=text, color=0xF1C40F)
            await message.reply(embed=embed)

    # ─── !reset Befehl ─────────────────────────────────────
    elif inhalt == "!reset":
        chat_verlaeufe[user_id] = []
        await message.reply("🗑️ Dein Chat Verlauf wurde gelöscht!")

    # ─── !hilfe Befehl ─────────────────────────────────────
    elif inhalt == "!hilfe":
        embed = discord.Embed(title="🤖 Bot Befehle", color=0x3498DB)
        embed.add_field(name="🗣️ KI", value=(
            "`!ki [frage]` - KI antwortet\n"
            "`!persönlichkeit [anwalt/mädel/lehrer/pirat/standard]` - Persönlichkeit wechseln\n"
            "`!reset` - Chat Verlauf löschen"
        ), inline=False)
        embed.add_field(name="🧠 Gedächtnis", value=(
            "`!merke [info]` - Info merken\n"
            "`!merkliste` - Gemerkte Infos zeigen\n"
            "`!vergiss` - Alles vergessen"
        ), inline=False)
        embed.add_field(name="✍️ Text", value=(
            "`!übersetzen [text]` - Auf Englisch übersetzen\n"
            "`!zusammenfassen [text]` - Text zusammenfassen\n"
            "`!geschichte [thema]` - Kurze Geschichte schreiben"
        ), inline=False)
        embed.add_field(name="🎮 Spaß & Spiele", value=(
            "`!witz` - Witz erzählen\n"
            "`!zitat` - Motivierendes Zitat\n"
            "`!würfel [seiten]` - Würfeln\n"
            "`!münze` - Münze werfen\n"
            "`!rate [max]` - Zahlenratespiel starten\n"
            "`!rechne [rechnung]` - Taschenrechner"
        ), inline=False)
        embed.add_field(name="⭐ Level", value=(
            "`!level` / `!rang` - Dein Level anzeigen\n"
            "`!rangliste` - Top 10 Server"
        ), inline=False)
        await message.reply(embed=embed)

bot.run(DISCORD_TOKEN)

import discord
import aiohttp
import os
import random
import asyncio
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)

chat_verlaeufe = {}
persoenlichkeit = {}
merkliste = {}
levels = {}
rate_spiel = {}
todo_listen = {}

# ─── Farben & Design ───────────────────────────────────────
FARBE_KI = 0x5865F2        # Discord Blau-Violett
FARBE_ERFOLG = 0x57F287    # Grün
FARBE_FEHLER = 0xED4245     # Rot
FARBE_SPIEL = 0xFEE75C      # Gelb
FARBE_TOOL = 0xEB459E       # Pink
FARBE_INFO = 0x5DADE2       # Hellblau

# ─── Persönlichkeiten ──────────────────────────────────────
PERSONAS = {
    "anwalt": "Du bist ein seriöser, sachlicher Anwalt. Du antwortest präzise, formell und nutzt gerne Fachbegriffe, erklärst aber alles verständlich. Du sprichst den User mit 'Sie' an.",
    "mädel": "Du bist eine freche, lustige und herzliche Freundin. Du redest locker, nutzt Emojis 😊✨ und Umgangssprache. Du sprichst den User mit 'du' an.",
    "lehrer": "Du bist ein geduldiger, motivierender Lehrer. Du erklärst Dinge Schritt für Schritt, einfach und ermutigend. Du lobst Fortschritte.",
    "pirat": "Du bist ein wilder Pirat! Du sprichst wie ein Pirat (Arrr, Landratte, Schatzkiste etc.), bist abenteuerlustig und übertrieben dramatisch.",
    "standard": "Du bist ein hilfreicher Assistent."
}

PERSONA_INFO = {
    "anwalt": {"emoji": "🧑‍⚖️", "farbe": 0x2C3E50, "name": "Anwalt"},
    "mädel": {"emoji": "👧", "farbe": 0xFF6B9D, "name": "Mädel"},
    "lehrer": {"emoji": "👨‍🏫", "farbe": 0x27AE60, "name": "Lehrer"},
    "pirat": {"emoji": "🏴‍☠️", "farbe": 0x8B4513, "name": "Pirat"},
    "standard": {"emoji": "🤖", "farbe": FARBE_KI, "name": "Standard"}
}

# ─── Hilfsfunktion: Fehler-Embed ───────────────────────────
def fehler_embed(text):
    embed = discord.Embed(description=f"❌ {text}", color=FARBE_FEHLER)
    return embed

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

def parse_zeit(text):
    einheit = text[-1].lower()
    try:
        zahl = int(text[:-1])
    except ValueError:
        return None
    if einheit == "s":
        return zahl
    elif einheit == "m":
        return zahl * 60
    elif einheit == "h":
        return zahl * 3600
    return None

@bot.event
async def on_ready():
    print(f"✅ Bot ist online als {bot.user}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="!hilfe"))

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    inhalt = message.content
    user_id = str(message.author.id)
    user_name = message.author.display_name
    avatar_url = message.author.display_avatar.url

    # ─── Zahlenrate-Spiel: Tipp abgeben ────────────────────
    if user_id in rate_spiel and inhalt.strip().lstrip("-").isdigit():
        tipp = int(inhalt.strip())
        ziel = rate_spiel[user_id]["zahl"]
        rate_spiel[user_id]["versuche"] += 1
        if tipp == ziel:
            versuche = rate_spiel[user_id]["versuche"]
            del rate_spiel[user_id]
            xp_geben(user_id, 20)
            embed = discord.Embed(title="🎉 Richtig geraten!", description=f"Die Zahl war **{ziel}**!\nDu hast **{versuche}** Versuche gebraucht.", color=FARBE_ERFOLG)
            embed.add_field(name="Belohnung", value="+20 XP ⭐")
            await message.reply(embed=embed)
        elif tipp < ziel:
            await message.add_reaction("📈")
        else:
            await message.add_reaction("📉")
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
                p_info = PERSONA_INFO[persona_key]

                if user_id in merkliste and merkliste[user_id]:
                    fakten = "; ".join(merkliste[user_id])
                    system_text += f" Wichtige Infos über den User, die du dir merken sollst: {fakten}."

                messages = [{"role": "system", "content": system_text}] + chat_verlaeufe[user_id]

                antwort_text = await groq_anfrage(messages)
                chat_verlaeufe[user_id].append({"role": "assistant", "content": antwort_text})

                if len(antwort_text) > 4000:
                    antwort_text = antwort_text[:3997] + "..."

                aufgestiegen = xp_geben(user_id, 5)

                embed = discord.Embed(description=antwort_text, color=p_info["farbe"])
                embed.set_author(name=f"{p_info['emoji']} {p_info['name']}", icon_url=bot.user.display_avatar.url)
                embed.set_footer(text=f"Gefragt von {user_name} · +5 XP" + (" · 🎉 LEVEL UP!" if aufgestiegen else ""), icon_url=avatar_url)
                await message.reply(embed=embed)
            except Exception as e:
                await message.reply(embed=fehler_embed(f"Fehler: {repr(e)}"))

    # ─── !persönlichkeit Befehl ────────────────────────────
    elif inhalt.startswith("!persönlichkeit"):
        teile = inhalt.split(" ")
        if len(teile) < 2:
            embed = discord.Embed(title="🎭 Persönlichkeiten", color=FARBE_INFO)
            for key, info in PERSONA_INFO.items():
                embed.add_field(name=f"{info['emoji']} {info['name']}", value=f"`!persönlichkeit {key}`", inline=True)
            await message.reply(embed=embed)
        else:
            wahl = teile[1].lower()
            if wahl in PERSONAS:
                persoenlichkeit[user_id] = wahl
                p_info = PERSONA_INFO[wahl]
                begruessungen = {
                    "anwalt": "Wie kann ich Ihnen behilflich sein?",
                    "mädel": "Heyyy, na was geht ab? 😊✨",
                    "lehrer": "Guten Tag! Womit kann ich dir heute helfen?",
                    "pirat": "Arrr! Bereit für ein Abenteuer, Landratte?",
                    "standard": "Zurück zum Standard-Modus!"
                }
                embed = discord.Embed(
                    title=f"{p_info['emoji']} Persönlichkeit gewechselt",
                    description=f"**{p_info['name']}**\n\n*{begruessungen[wahl]}*",
                    color=p_info['farbe']
                )
                await message.reply(embed=embed)
            else:
                await message.reply(embed=fehler_embed("Unbekannte Persönlichkeit! Nutze `!persönlichkeit` für die Liste."))

    # ─── !merke Befehl ──────────────────────────────────────
    elif inhalt.startswith("!merke "):
        info = inhalt[7:]
        if user_id not in merkliste:
            merkliste[user_id] = []
        merkliste[user_id].append(info)
        embed = discord.Embed(description=f"🧠 Ich merke mir: *{info}*", color=FARBE_ERFOLG)
        await message.reply(embed=embed)

    # ─── !merkliste Befehl ──────────────────────────────────
    elif inhalt == "!merkliste":
        if user_id in merkliste and merkliste[user_id]:
            liste = "\n".join(f"• {x}" for x in merkliste[user_id])
            embed = discord.Embed(title="🧠 Das merke ich mir über dich", description=liste, color=FARBE_INFO)
            embed.set_thumbnail(url=avatar_url)
            await message.reply(embed=embed)
        else:
            await message.reply(embed=discord.Embed(description="🧠 Ich weiß noch nichts über dich! Nutze `!merke [info]`", color=FARBE_INFO))

    # ─── !vergiss Befehl ────────────────────────────────────
    elif inhalt == "!vergiss":
        merkliste[user_id] = []
        await message.reply(embed=discord.Embed(description="🗑️ Alles vergessen, was ich mir über dich gemerkt habe!", color=FARBE_ERFOLG))

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
                embed = discord.Embed(title="🌍 Übersetzung", color=FARBE_TOOL)
                embed.add_field(name="Original (DE)", value=text, inline=False)
                embed.add_field(name="Englisch", value=antwort_text, inline=False)
                await message.reply(embed=embed)
            except Exception as e:
                await message.reply(embed=fehler_embed(f"Fehler: {repr(e)}"))

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
                embed = discord.Embed(title="📝 Zusammenfassung", description=antwort_text, color=FARBE_TOOL)
                await message.reply(embed=embed)
            except Exception as e:
                await message.reply(embed=fehler_embed(f"Fehler: {repr(e)}"))

    # ─── !rechne Befehl ──────────────────────────────────────
    elif inhalt.startswith("!rechne "):
        text = inhalt[8:]
        try:
            erlaubt = set("0123456789+-*/(). ")
            if all(c in erlaubt for c in text):
                ergebnis = eval(text)
                embed = discord.Embed(title="🧮 Taschenrechner", color=FARBE_TOOL)
                embed.add_field(name="Rechnung", value=f"`{text}`", inline=True)
                embed.add_field(name="Ergebnis", value=f"**{ergebnis}**", inline=True)
                await message.reply(embed=embed)
            else:
                await message.reply(embed=fehler_embed("Nur Zahlen und + - * / ( ) erlaubt!"))
        except Exception:
            await message.reply(embed=fehler_embed("Das konnte ich nicht berechnen!"))

    # ─── !würfel Befehl ──────────────────────────────────────
    elif inhalt.startswith("!würfel"):
        teile = inhalt.split(" ")
        seiten = 6
        if len(teile) > 1 and teile[1].isdigit():
            seiten = int(teile[1])
        ergebnis = random.randint(1, seiten)
        embed = discord.Embed(title="🎲 Würfelwurf", description=f"# {ergebnis}\n(1-{seiten})", color=FARBE_SPIEL)
        await message.reply(embed=embed)

    # ─── !münze Befehl ────────────────────────────────────────
    elif inhalt == "!münze":
        ergebnis = random.choice(["Kopf", "Zahl"])
        emoji = "👑" if ergebnis == "Kopf" else "🔢"
        embed = discord.Embed(title="🪙 Münzwurf", description=f"## {emoji} {ergebnis}", color=FARBE_SPIEL)
        await message.reply(embed=embed)

    # ─── !rate Befehl (Spiel starten) ─────────────────────────
    elif inhalt.startswith("!rate"):
        teile = inhalt.split(" ")
        maxz = 100
        if len(teile) > 1 and teile[1].isdigit():
            maxz = int(teile[1])
        rate_spiel[user_id] = {"zahl": random.randint(1, maxz), "versuche": 0}
        embed = discord.Embed(title="🔢 Zahlenraten gestartet!", description=f"Ich denke an eine Zahl zwischen **1 und {maxz}**!\nSchreib einfach eine Zahl in den Chat um zu raten!", color=FARBE_SPIEL)
        await message.reply(embed=embed)

    # ─── !ssp Befehl (Schere Stein Papier) ─────────────────────
    elif inhalt.startswith("!ssp "):
        wahl_user = inhalt[5:].strip().lower()
        optionen = {"schere": "✂️", "stein": "🪨", "papier": "📄"}
        if wahl_user not in optionen:
            await message.reply(embed=fehler_embed("Nutze: `!ssp schere`, `!ssp stein` oder `!ssp papier`"))
        else:
            wahl_bot = random.choice(list(optionen.keys()))
            if wahl_user == wahl_bot:
                ergebnis, farbe = "🤝 Unentschieden!", FARBE_INFO
            elif (wahl_user == "schere" and wahl_bot == "papier") or \
                 (wahl_user == "stein" and wahl_bot == "schere") or \
                 (wahl_user == "papier" and wahl_bot == "stein"):
                ergebnis, farbe = "🎉 Du gewinnst! (+10 XP)", FARBE_ERFOLG
                xp_geben(user_id, 10)
            else:
                ergebnis, farbe = "😢 Du verlierst!", FARBE_FEHLER
            embed = discord.Embed(title="✂️ Schere Stein Papier", color=farbe)
            embed.add_field(name="Du", value=f"{optionen[wahl_user]}\n{wahl_user}", inline=True)
            embed.add_field(name="Bot", value=f"{optionen[wahl_bot]}\n{wahl_bot}", inline=True)
            embed.add_field(name="Ergebnis", value=ergebnis, inline=False)
            await message.reply(embed=embed)

    # ─── !witz Befehl ────────────────────────────────────────
    elif inhalt == "!witz":
        async with message.channel.typing():
            try:
                messages = [
                    {"role": "system", "content": "Erzähle einen kurzen, lustigen Witz auf Deutsch. Nur den Witz, keine Einleitung."},
                    {"role": "user", "content": "Erzähl mir einen Witz"}
                ]
                antwort_text = await groq_anfrage(messages, modell="llama-3.1-8b-instant", max_tokens=200)
                embed = discord.Embed(title="😂 Witz des Tages", description=antwort_text, color=FARBE_SPIEL)
                await message.reply(embed=embed)
            except Exception as e:
                await message.reply(embed=fehler_embed(f"Fehler: {repr(e)}"))

    # ─── !zitat Befehl ───────────────────────────────────────
    elif inhalt == "!zitat":
        async with message.channel.typing():
            try:
                messages = [
                    {"role": "system", "content": "Gib ein kurzes, motivierendes Zitat auf Deutsch aus. Nenne auch einen (ggf. erfundenen, aber plausiblen) Autor. Format: 'Zitat' - Autor"},
                    {"role": "user", "content": "Gib mir ein Zitat"}
                ]
                antwort_text = await groq_anfrage(messages, modell="llama-3.1-8b-instant", max_tokens=150)
                embed = discord.Embed(title="💬 Zitat des Tages", description=f"*{antwort_text}*", color=0xF39C12)
                await message.reply(embed=embed)
            except Exception as e:
                await message.reply(embed=fehler_embed(f"Fehler: {repr(e)}"))

    # ─── !fakt Befehl ───────────────────────────────────────
    elif inhalt == "!fakt":
        async with message.channel.typing():
            try:
                messages = [
                    {"role": "system", "content": "Gib einen kurzen, interessanten und überraschenden Fakt auf Deutsch aus. Nur den Fakt, keine Einleitung."},
                    {"role": "user", "content": "Gib mir einen Fakt"}
                ]
                antwort_text = await groq_anfrage(messages, modell="llama-3.1-8b-instant", max_tokens=150)
                embed = discord.Embed(title="💡 Wusstest du schon?", description=antwort_text, color=0x1ABC9C)
                await message.reply(embed=embed)
            except Exception as e:
                await message.reply(embed=fehler_embed(f"Fehler: {repr(e)}"))

    # ─── !kompliment Befehl ───────────────────────────────────
    elif inhalt == "!kompliment":
        async with message.channel.typing():
            try:
                messages = [
                    {"role": "system", "content": f"Gib ein kurzes, herzliches und kreatives Kompliment auf Deutsch an eine Person namens {user_name}. Nur das Kompliment."},
                    {"role": "user", "content": "Gib mir ein Kompliment"}
                ]
                antwort_text = await groq_anfrage(messages, modell="llama-3.1-8b-instant", max_tokens=100)
                embed = discord.Embed(description=f"💖 {antwort_text}", color=0xFF6B9D)
                embed.set_thumbnail(url=avatar_url)
                await message.reply(embed=embed)
            except Exception as e:
                await message.reply(embed=fehler_embed(f"Fehler: {repr(e)}"))

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
                embed = discord.Embed(title=f"📖 {thema}", description=antwort_text, color=0x8E44AD)
                embed.set_footer(text="✨ KI-generierte Geschichte")
                await message.reply(embed=embed)
            except Exception as e:
                await message.reply(embed=fehler_embed(f"Fehler: {repr(e)}"))

    # ─── !reim Befehl ─────────────────────────────────────────
    elif inhalt.startswith("!reim "):
        thema = inhalt[6:]
        async with message.channel.typing():
            try:
                messages = [
                    {"role": "system", "content": "Schreibe ein kurzes, lustiges 4-zeiliges Gedicht/Reim auf Deutsch zum gegebenen Thema."},
                    {"role": "user", "content": thema}
                ]
                antwort_text = await groq_anfrage(messages, modell="llama-3.1-8b-instant", max_tokens=200)
                embed = discord.Embed(title=f"🎤 Reim: {thema}", description=antwort_text, color=0x8E44AD)
                await message.reply(embed=embed)
            except Exception as e:
                await message.reply(embed=fehler_embed(f"Fehler: {repr(e)}"))

    # ─── !umfrage Befehl ────────────────────────────────────────
    elif inhalt.startswith("!umfrage "):
        frage = inhalt[9:]
        embed = discord.Embed(title="📊 Umfrage", description=f"## {frage}", color=FARBE_TOOL)
        embed.set_footer(text=f"Erstellt von {user_name} · Reagiere mit 👍 👎 oder 🤷", icon_url=avatar_url)
        umfrage_msg = await message.channel.send(embed=embed)
        await umfrage_msg.add_reaction("👍")
        await umfrage_msg.add_reaction("👎")
        await umfrage_msg.add_reaction("🤷")

    # ─── !erinnere Befehl ────────────────────────────────────────
    elif inhalt.startswith("!erinnere "):
        teile = inhalt[10:].split(" ", 1)
        if len(teile) < 2:
            await message.reply(embed=fehler_embed("Nutze: `!erinnere 10m Pizza aus dem Ofen holen`\n(s=Sekunden, m=Minuten, h=Stunden)"))
        else:
            sekunden = parse_zeit(teile[0])
            erinnerung_text = teile[1]
            if sekunden is None:
                await message.reply(embed=fehler_embed("Ungültige Zeit! Nutze z.B. `10m`, `30s`, `1h`"))
            elif sekunden > 86400:
                await message.reply(embed=fehler_embed("Maximal 24 Stunden!"))
            else:
                embed = discord.Embed(title="⏰ Erinnerung gesetzt", description=f"In **{teile[0]}** erinnere ich dich an:\n*{erinnerung_text}*", color=FARBE_TOOL)
                await message.reply(embed=embed)
                await asyncio.sleep(sekunden)
                erinnerung_embed = discord.Embed(title="🔔 Erinnerung!", description=erinnerung_text, color=0xF39C12)
                await message.channel.send(content=message.author.mention, embed=erinnerung_embed)

    # ─── !todo Befehl ────────────────────────────────────────────
    elif inhalt.startswith("!todo"):
        teile = inhalt.split(" ", 2)
        if user_id not in todo_listen:
            todo_listen[user_id] = []

        if len(teile) == 1 or teile[1] == "liste":
            if not todo_listen[user_id]:
                await message.reply(embed=discord.Embed(description="📋 Deine To-Do Liste ist leer! Füge etwas hinzu mit `!todo add [aufgabe]`", color=FARBE_TOOL))
            else:
                liste = "\n".join(f"**{i+1}.** {x}" for i, x in enumerate(todo_listen[user_id]))
                embed = discord.Embed(title="📋 Deine To-Do Liste", description=liste, color=FARBE_TOOL)
                embed.set_footer(text="Erledigt? Nutze !todo done [nummer]")
                await message.reply(embed=embed)
        elif teile[1] == "add" and len(teile) > 2:
            todo_listen[user_id].append(teile[2])
            await message.reply(embed=discord.Embed(description=f"✅ Hinzugefügt: *{teile[2]}*", color=FARBE_ERFOLG))
        elif teile[1] == "done" and len(teile) > 2 and teile[2].isdigit():
            idx = int(teile[2]) - 1
            if 0 <= idx < len(todo_listen[user_id]):
                erledigt = todo_listen[user_id].pop(idx)
                await message.reply(embed=discord.Embed(description=f"🎉 Erledigt: *{erledigt}*", color=FARBE_ERFOLG))
            else:
                await message.reply(embed=fehler_embed("Ungültige Nummer!"))
        elif teile[1] == "clear":
            todo_listen[user_id] = []
            await message.reply(embed=discord.Embed(description="🗑️ To-Do Liste geleert!", color=FARBE_ERFOLG))
        else:
            await message.reply(embed=fehler_embed("Nutze:\n`!todo add [aufgabe]`\n`!todo liste`\n`!todo done [nummer]`\n`!todo clear`"))

    # ─── !level / !rang Befehl ──────────────────────────────────
    elif inhalt == "!level" or inhalt == "!rang":
        daten = levels.get(user_id, {"xp": 0, "level": 1})
        benoetigt = daten["level"] * 100
        balken_voll = int((daten["xp"] / benoetigt) * 10)
        balken = "🟩" * balken_voll + "⬜" * (10 - balken_voll)
        embed = discord.Embed(title=f"⭐ Level von {user_name}", color=0xF1C40F)
        embed.set_thumbnail(url=avatar_url)
        embed.add_field(name="Level", value=f"**{daten['level']}**", inline=True)
        embed.add_field(name="XP", value=f"{daten['xp']}/{benoetigt}", inline=True)
        embed.add_field(name="Fortschritt", value=balken, inline=False)
        await message.reply(embed=embed)

    # ─── !rangliste Befehl ───────────────────────────────────────
    elif inhalt == "!rangliste":
        if not levels:
            await message.reply(embed=discord.Embed(description="📊 Noch keine Daten vorhanden!", color=FARBE_INFO))
        else:
            sortiert = sorted(levels.items(), key=lambda x: (x[1]["level"], x[1]["xp"]), reverse=True)[:10]
            text = ""
            medaillen = ["🥇", "🥈", "🥉"]
            for i, (uid, daten) in enumerate(sortiert):
                try:
                    user = await bot.fetch_user(int(uid))
                    name = user.display_name
                except Exception:
                    name = f"User {uid}"
                rang = medaillen[i] if i < 3 else f"**{i+1}.**"
                text += f"{rang} {name} — Level **{daten['level']}** ({daten['xp']} XP)\n"
            embed = discord.Embed(title="🏆 Rangliste", description=text, color=0xF1C40F)
            await message.reply(embed=embed)

    # ─── !reset Befehl ─────────────────────────────────────
    elif inhalt == "!reset":
        chat_verlaeufe[user_id] = []
        await message.reply(embed=discord.Embed(description="🗑️ Dein Chat Verlauf wurde gelöscht!", color=FARBE_ERFOLG))

    # ─── !hilfe Befehl ─────────────────────────────────────
    elif inhalt == "!hilfe":
        embed = discord.Embed(
            title="🤖 Bot Befehle",
            description="Hier sind alle verfügbaren Befehle, übersichtlich sortiert:",
            color=FARBE_KI
        )
        embed.set_thumbnail(url=bot.user.display_avatar.url)
        embed.add_field(name="🗣️ KI & Chat", value=(
            "`!ki [frage]` — KI antwortet\n"
            "`!persönlichkeit` — Charakter wechseln\n"
            "`!reset` — Verlauf löschen"
        ), inline=False)
        embed.add_field(name="🧠 Gedächtnis", value=(
            "`!merke [info]` · `!merkliste` · `!vergiss`"
        ), inline=False)
        embed.add_field(name="✍️ Text & Kreativ", value=(
            "`!übersetzen [text]` · `!zusammenfassen [text]`\n"
            "`!geschichte [thema]` · `!reim [thema]`"
        ), inline=False)
        embed.add_field(name="🎮 Spaß & Spiele", value=(
            "`!witz` · `!zitat` · `!fakt` · `!kompliment`\n"
            "`!würfel [seiten]` · `!münze` · `!rate [max]`\n"
            "`!ssp [schere/stein/papier]` · `!rechne [rechnung]`"
        ), inline=False)
        embed.add_field(name="🛠️ Tools", value=(
            "`!umfrage [frage]` · `!erinnere [zeit] [text]`\n"
            "`!todo add/liste/done/clear`"
        ), inline=False)
        embed.add_field(name="⭐ Level", value=(
            "`!level` · `!rangliste`"
        ), inline=False)
        embed.set_footer(text=f"Angefordert von {user_name}", icon_url=avatar_url)
        await message.reply(embed=embed)

bot.run(DISCORD_TOKEN)

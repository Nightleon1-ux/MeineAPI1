import discord
from discord import app_commands
import aiohttp
import os
import random
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

chat_verlaeufe = {}
persoenlichkeit = {}
merkliste = {}
levels = {}
rate_spiel = {}
todo_listen = {}
warnungen = {}           # Verwarnungen pro User
server_config = {}       # Welcome/Autorole Einstellungen pro Server
ttt_spiele = {}          # Tic-Tac-Toe pro Channel
hangman_spiele = {}      # Galgenmännchen pro Channel
quiz_aktiv = {}          # Aktives Quiz pro Channel
BOT_START = datetime.utcnow()

HANGMAN_WOERTER = ["PYTHON", "DISCORD", "COMPUTER", "TASTATUR", "BILDSCHIRM", "INTERNET", "PROGRAMM", "ROBOTER", "GALAXIE", "FUSSBALL", "PIZZA", "GITARRE", "ELEFANT", "REGENBOGEN", "ASTRONAUT"]

QUIZ_FRAGEN = [
    {"frage": "Wie viele Beine hat eine Spinne?", "antwort": "8"},
    {"frage": "Was ist die Hauptstadt von Deutschland?", "antwort": "Berlin"},
    {"frage": "Wie viele Kontinente gibt es?", "antwort": "7"},
    {"frage": "Welcher Planet ist der Sonne am nächsten?", "antwort": "Merkur"},
    {"frage": "Wie viele Saiten hat eine Standard-Gitarre?", "antwort": "6"},
    {"frage": "Was ist 7 mal 8?", "antwort": "56"},
    {"frage": "In welchem Land steht der Eiffelturm?", "antwort": "Frankreich"},
    {"frage": "Wie viele Tage hat ein Schaltjahr?", "antwort": "366"},
    {"frage": "Was ist die größte Zahl: Million, Milliarde oder Billion?", "antwort": "Billion"},
    {"frage": "Wie viele Spieler hat eine Fußballmannschaft auf dem Feld?", "antwort": "11"},
    {"frage": "Welches Tier ist das größte Landtier der Welt?", "antwort": "Elefant"},
    {"frage": "Wie viele Farben hat ein Regenbogen?", "antwort": "7"},
]

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

# ─── Tic-Tac-Toe Hilfsfunktionen ────────────────────────────
def ttt_anzeigen(board):
    anzeige = [b if b != " " else "⬜" for b in board]
    zahlen_overlay = []
    for i, feld in enumerate(anzeige):
        if feld == "⬜":
            nummern = ["1️⃣","2️⃣","3️⃣","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣"]
            zahlen_overlay.append(nummern[i])
        else:
            zahlen_overlay.append(feld)
    rows = [zahlen_overlay[i:i+3] for i in range(0, 9, 3)]
    return "\n".join("".join(row) for row in rows)

def ttt_check(board):
    gewinn_linien = [
        [0,1,2],[3,4,5],[6,7,8],
        [0,3,6],[1,4,7],[2,5,8],
        [0,4,8],[2,4,6]
    ]
    for linie in gewinn_linien:
        werte = [board[i] for i in linie]
        if werte[0] != " " and werte[0] == werte[1] == werte[2]:
            return werte[0]
    if " " not in board:
        return "unentschieden"
    return None

def ttt_bot_zug(board):
    # Versuche zu gewinnen oder zu blocken, sonst zufällig
    for symbol in ["⭕", "❌"]:
        for i in range(9):
            if board[i] == " ":
                test = board.copy()
                test[i] = symbol
                if ttt_check(test) == symbol:
                    return i
    freie = [i for i, v in enumerate(board) if v == " "]
    return random.choice(freie)

def bau_hilfe_embed(user):
    embed = discord.Embed(
        title="🤖 Bot-Befehle Übersicht",
        description=(
            "**Alle Befehle gibt es als `!befehl` ODER als `/befehl`!**\n"
            "Tippe `/` in Discord ein und du siehst alle Befehle mit Erklärung. 😊"
        ),
        color=FARBE_KI
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)

    embed.add_field(name="🗣️ ── KI & Chat ── 🗣️", value=(
        "**`ki [frage]`** — Stelle der KI eine Frage\n"
        "**`persönlichkeit [typ]`** — Charakter wechseln (anwalt/mädel/lehrer/pirat)\n"
        "**`reset`** — Chat-Verlauf löschen *(nur als `!`)*"
    ), inline=False)

    embed.add_field(name="🧠 ── Gedächtnis ── 🧠 *(nur als `!`)*", value=(
        "**`!merke [info]`** — Bot merkt sich etwas über dich\n"
        "**`!merkliste`** — Zeigt gemerkte Infos\n"
        "**`!vergiss`** — Löscht alle gemerkten Infos"
    ), inline=False)

    embed.add_field(name="✍️ ── Text & Kreativ ── ✍️", value=(
        "**`übersetzen [text]`** — Ins Englische übersetzen\n"
        "**`zusammenfassen [text]`** — Text kürzen\n"
        "**`geschichte [thema]`** — Kurze Geschichte schreiben\n"
        "**`reim [thema]`** — Kleines Gedicht schreiben"
    ), inline=False)

    embed.add_field(name="🎉 ── Spaß ── 🎉", value=(
        "**`witz`** · **`zitat`** · **`fakt`** · **`kompliment`**"
    ), inline=False)

    embed.add_field(name="🎮 ── Spiele ── 🎮 *(nur als `!`)*", value=(
        "**`!würfel [seiten]`** · **`!münze`**\n"
        "**`!rate [max]`** — Zahlenraten\n"
        "**`!ssp [schere/stein/papier]`** — gegen den Bot\n"
        "**`!ttt`** — Tic-Tac-Toe · **`!hangman`** — Galgenmännchen\n"
        "**`!quiz`** — Allgemeinwissen"
    ), inline=False)

    embed.add_field(name="🧮 ── Tools ── 🧮", value=(
        "**`rechne [rechnung]`** — Taschenrechner\n"
        "**`!umfrage [frage]`** — Umfrage mit Reaktionen *(nur `!`)*\n"
        "**`!erinnere [zeit] [text]`** — z.B. `10m Pizza checken` *(nur `!`)*\n"
        "**`!todo add/liste/done/clear`** — eigene To-Do-Liste *(nur `!`)*"
    ), inline=False)

    embed.add_field(name="⭐ ── Level-System ── ⭐", value=(
        "**`level`** — Dein Level & XP\n"
        "**`rangliste`** — Top 10 des Servers\n"
        "*Du bekommst XP für `ki`, Spiele gewinnen, Quiz etc.*"
    ), inline=False)

    embed.add_field(name="ℹ️ ── Info ── ℹ️", value=(
        "**`ping`** · **`uptime`** · **`avatar [@user]`**\n"
        "**`userinfo [@user]`** · **`serverinfo`**"
    ), inline=False)

    embed.add_field(name="🛡️ ── Moderation (braucht Rechte) ── 🛡️", value=(
        "**`kick`** · **`ban`** · **`mute`** · **`unmute`** · **`warn`** · **`clear`**\n"
        "*(als `!` zusätzlich: `unban`, `warnungen`, `entwarnen`, `lock`, `unlock`, `slowmode`, `ankündigung`)*"
    ), inline=False)

    embed.add_field(name="⚙️ ── Server-Einstellungen (braucht Rechte) ── ⚙️ *(nur `!`)*", value=(
        "**`!setwelcome #kanal [text]`** — Willkommensnachricht (Platzhalter: `{user}`, `{server}`)\n"
        "**`!removewelcome`** · **`!autorole @rolle`** · **`!removeautorole`**"
    ), inline=False)

    embed.set_footer(text=f"Angefordert von {user.display_name}", icon_url=user.display_avatar.url)
    return embed

@bot.event
async def on_ready():
    print(f"✅ Bot ist online als {bot.user}")
    await tree.sync()
    print("✅ Slash-Befehle synchronisiert")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/hilfe oder !hilfe"))

@bot.event
async def on_member_join(member):
    guild_id = str(member.guild.id)
    config = server_config.get(guild_id, {})

    # Auto-Rolle vergeben
    if "autorole" in config:
        rolle = member.guild.get_role(config["autorole"])
        if rolle:
            try:
                await member.add_roles(rolle)
            except discord.Forbidden:
                pass

    # Willkommensnachricht senden
    if "welcome_channel" in config:
        kanal = member.guild.get_channel(config["welcome_channel"])
        if kanal:
            text = config.get("welcome_msg", "Willkommen {user} auf **{server}**! 🎉")
            text = text.replace("{user}", member.mention).replace("{server}", member.guild.name)
            embed = discord.Embed(title="🎉 Neues Mitglied!", description=text, color=FARBE_ERFOLG)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"Mitglied #{member.guild.member_count}")
            await kanal.send(embed=embed)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    inhalt = message.content
    user_id = str(message.author.id)
    user_name = message.author.display_name
    avatar_url = message.author.display_avatar.url

    channel_id = str(message.channel.id)

    # ─── Tic-Tac-Toe: Zug verarbeiten ───────────────────────
    if channel_id in ttt_spiele and inhalt.strip().isdigit():
        spiel = ttt_spiele[channel_id]
        if user_id != spiel["spieler"]:
            return
        pos = int(inhalt.strip()) - 1
        if 0 <= pos <= 8 and spiel["board"][pos] == " ":
            spiel["board"][pos] = "❌"
            gewinner = ttt_check(spiel["board"])
            if gewinner is None and " " in spiel["board"]:
                bot_zug = ttt_bot_zug(spiel["board"])
                spiel["board"][bot_zug] = "⭕"
                gewinner = ttt_check(spiel["board"])

            brett_text = ttt_anzeigen(spiel["board"])
            if gewinner == "❌":
                embed = discord.Embed(title="❌⭕ Tic-Tac-Toe", description=f"{brett_text}\n\n🎉 **Du gewinnst!** +15 XP", color=FARBE_ERFOLG)
                xp_geben(user_id, 15)
                del ttt_spiele[channel_id]
            elif gewinner == "⭕":
                embed = discord.Embed(title="❌⭕ Tic-Tac-Toe", description=f"{brett_text}\n\n🤖 **Ich gewinne!**", color=FARBE_FEHLER)
                del ttt_spiele[channel_id]
            elif gewinner == "unentschieden":
                embed = discord.Embed(title="❌⭕ Tic-Tac-Toe", description=f"{brett_text}\n\n🤝 **Unentschieden!**", color=FARBE_INFO)
                del ttt_spiele[channel_id]
            else:
                embed = discord.Embed(title="❌⭕ Tic-Tac-Toe", description=f"{brett_text}\n\nDu bist ❌ — schreib eine Zahl (1-9)!", color=FARBE_SPIEL)
            await message.reply(embed=embed)
            return

    # ─── Hangman: Buchstabe raten ────────────────────────────
    if channel_id in hangman_spiele and len(inhalt.strip()) == 1 and inhalt.strip().isalpha():
        spiel = hangman_spiele[channel_id]
        buchstabe = inhalt.strip().upper()
        if buchstabe in spiel["geraten"]:
            return
        spiel["geraten"].add(buchstabe)
        if buchstabe not in spiel["wort"]:
            spiel["leben"] -= 1

        anzeige = " ".join(b if b in spiel["geraten"] else "_" for b in spiel["wort"])
        verloren = spiel["leben"] <= 0
        gewonnen = "_" not in anzeige

        if gewonnen:
            embed = discord.Embed(title="🪦 Galgenmännchen", description=f"**{anzeige}**\n\n🎉 Gewonnen! Das Wort war **{spiel['wort']}**! +15 XP", color=FARBE_ERFOLG)
            xp_geben(user_id, 15)
            del hangman_spiele[channel_id]
        elif verloren:
            embed = discord.Embed(title="🪦 Galgenmännchen", description=f"**{anzeige}**\n\n💀 Verloren! Das Wort war **{spiel['wort']}**", color=FARBE_FEHLER)
            del hangman_spiele[channel_id]
        else:
            herzen = "❤️" * spiel["leben"] + "🖤" * (6 - spiel["leben"])
            geraten_text = ", ".join(sorted(spiel["geraten"])) if spiel["geraten"] else "—"
            embed = discord.Embed(title="🪦 Galgenmännchen", description=f"**{anzeige}**\n\nLeben: {herzen}\nGeraten: {geraten_text}", color=FARBE_SPIEL)
        await message.reply(embed=embed)
        return

    # ─── Quiz: Antwort prüfen ─────────────────────────────────
    if channel_id in quiz_aktiv:
        richtige_antwort = quiz_aktiv[channel_id]["antwort"].strip().lower()
        if inhalt.strip().lower() == richtige_antwort:
            xp_geben(user_id, 15)
            embed = discord.Embed(title="✅ Richtig!", description=f"Die Antwort war **{quiz_aktiv[channel_id]['antwort']}**!\n{user_name} bekommt **+15 XP** ⭐", color=FARBE_ERFOLG)
            del quiz_aktiv[channel_id]
            await message.reply(embed=embed)
            return


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

    # ════════════════════════════════════════════════════════
    # 🛡️ MODERATIONS-BEFEHLE (keine API nötig, unbegrenzt!)
    # ════════════════════════════════════════════════════════

    # ─── !clear / !purge Befehl ─────────────────────────────
    elif inhalt.startswith("!clear ") or inhalt.startswith("!purge "):
        if not message.author.guild_permissions.manage_messages:
            await message.reply(embed=fehler_embed("Du brauchst die Berechtigung **Nachrichten verwalten**!"))
        else:
            teile = inhalt.split(" ")
            try:
                anzahl = int(teile[1])
                if anzahl < 1 or anzahl > 100:
                    await message.reply(embed=fehler_embed("Bitte eine Zahl zwischen 1 und 100 angeben!"))
                else:
                    deleted = await message.channel.purge(limit=anzahl + 1)  # +1 für den Befehl selbst
                    embed = discord.Embed(description=f"🧹 **{len(deleted)-1}** Nachrichten gelöscht!", color=FARBE_ERFOLG)
                    info_msg = await message.channel.send(embed=embed)
                    await asyncio.sleep(3)
                    await info_msg.delete()
            except ValueError:
                await message.reply(embed=fehler_embed("Nutze: `!clear [anzahl 1-100]`"))
            except discord.Forbidden:
                await message.reply(embed=fehler_embed("Mir fehlt die Berechtigung **Nachrichten verwalten**!"))

    # ─── !kick Befehl ────────────────────────────────────────
    elif inhalt.startswith("!kick"):
        if not message.author.guild_permissions.kick_members:
            await message.reply(embed=fehler_embed("Du brauchst die Berechtigung **Mitglieder kicken**!"))
        elif not message.mentions:
            await message.reply(embed=fehler_embed("Nutze: `!kick @user [grund]`"))
        else:
            ziel = message.mentions[0]
            grund = inhalt.split(" ", 2)[2] if len(inhalt.split(" ", 2)) > 2 else "Kein Grund angegeben"
            if ziel.guild_permissions.administrator:
                await message.reply(embed=fehler_embed("Du kannst keinen Administrator kicken!"))
            else:
                try:
                    await ziel.kick(reason=f"{grund} (von {user_name})")
                    embed = discord.Embed(title="👋 Mitglied gekickt", color=FARBE_ERFOLG)
                    embed.add_field(name="User", value=ziel.mention, inline=True)
                    embed.add_field(name="Von", value=message.author.mention, inline=True)
                    embed.add_field(name="Grund", value=grund, inline=False)
                    await message.reply(embed=embed)
                except discord.Forbidden:
                    await message.reply(embed=fehler_embed("Ich habe keine Berechtigung diesen User zu kicken! (Rolle zu hoch?)"))

    # ─── !ban Befehl ─────────────────────────────────────────
    elif inhalt.startswith("!ban"):
        if not message.author.guild_permissions.ban_members:
            await message.reply(embed=fehler_embed("Du brauchst die Berechtigung **Mitglieder bannen**!"))
        elif not message.mentions:
            await message.reply(embed=fehler_embed("Nutze: `!ban @user [grund]`"))
        else:
            ziel = message.mentions[0]
            grund = inhalt.split(" ", 2)[2] if len(inhalt.split(" ", 2)) > 2 else "Kein Grund angegeben"
            if ziel.guild_permissions.administrator:
                await message.reply(embed=fehler_embed("Du kannst keinen Administrator bannen!"))
            else:
                try:
                    await ziel.ban(reason=f"{grund} (von {user_name})")
                    embed = discord.Embed(title="🔨 Mitglied gebannt", color=FARBE_FEHLER)
                    embed.add_field(name="User", value=f"{ziel.mention} ({ziel})", inline=True)
                    embed.add_field(name="Von", value=message.author.mention, inline=True)
                    embed.add_field(name="Grund", value=grund, inline=False)
                    await message.reply(embed=embed)
                except discord.Forbidden:
                    await message.reply(embed=fehler_embed("Ich habe keine Berechtigung diesen User zu bannen! (Rolle zu hoch?)"))

    # ─── !unban Befehl ───────────────────────────────────────
    elif inhalt.startswith("!unban "):
        if not message.author.guild_permissions.ban_members:
            await message.reply(embed=fehler_embed("Du brauchst die Berechtigung **Mitglieder bannen**!"))
        else:
            name_eingabe = inhalt[7:].strip()
            try:
                banne = [entry async for entry in message.guild.bans()]
                gefunden = None
                for ban_entry in banne:
                    if name_eingabe.lower() in str(ban_entry.user).lower() or name_eingabe == str(ban_entry.user.id):
                        gefunden = ban_entry.user
                        break
                if gefunden:
                    await message.guild.unban(gefunden)
                    await message.reply(embed=discord.Embed(description=f"✅ **{gefunden}** wurde entbannt!", color=FARBE_ERFOLG))
                else:
                    await message.reply(embed=fehler_embed(f"Kein gebannter User mit '{name_eingabe}' gefunden!"))
            except discord.Forbidden:
                await message.reply(embed=fehler_embed("Mir fehlt die Berechtigung **Mitglieder bannen**!"))

    # ─── !mute Befehl (Timeout) ──────────────────────────────
    elif inhalt.startswith("!mute"):
        if not message.author.guild_permissions.moderate_members:
            await message.reply(embed=fehler_embed("Du brauchst die Berechtigung **Mitglieder timeout** (moderate_members)!"))
        elif not message.mentions:
            await message.reply(embed=fehler_embed("Nutze: `!mute @user [zeit] [grund]` (z.B. `!mute @Leon 10m Spam`)"))
        else:
            ziel = message.mentions[0]
            teile = inhalt.split(" ", 3)
            zeit_str = teile[2] if len(teile) > 2 else "10m"
            grund = teile[3] if len(teile) > 3 else "Kein Grund angegeben"
            sekunden = parse_zeit(zeit_str)
            if sekunden is None:
                await message.reply(embed=fehler_embed("Ungültige Zeit! Nutze z.B. `10m`, `1h`, `30s`"))
            elif sekunden > 2419200:  # max 28 Tage
                await message.reply(embed=fehler_embed("Maximal 28 Tage Timeout möglich!"))
            elif ziel.guild_permissions.administrator:
                await message.reply(embed=fehler_embed("Du kannst keinen Administrator muten!"))
            else:
                try:
                    from datetime import timedelta
                    await ziel.timeout(timedelta(seconds=sekunden), reason=f"{grund} (von {user_name})")
                    embed = discord.Embed(title="🔇 Mitglied gemutet", color=FARBE_SPIEL)
                    embed.add_field(name="User", value=ziel.mention, inline=True)
                    embed.add_field(name="Dauer", value=zeit_str, inline=True)
                    embed.add_field(name="Grund", value=grund, inline=False)
                    await message.reply(embed=embed)
                except discord.Forbidden:
                    await message.reply(embed=fehler_embed("Ich habe keine Berechtigung diesen User zu muten! (Rolle zu hoch?)"))

    # ─── !unmute Befehl ──────────────────────────────────────
    elif inhalt.startswith("!unmute"):
        if not message.author.guild_permissions.moderate_members:
            await message.reply(embed=fehler_embed("Du brauchst die Berechtigung **Mitglieder timeout**!"))
        elif not message.mentions:
            await message.reply(embed=fehler_embed("Nutze: `!unmute @user`"))
        else:
            ziel = message.mentions[0]
            try:
                await ziel.timeout(None)
                await message.reply(embed=discord.Embed(description=f"🔊 {ziel.mention} wurde entmutet!", color=FARBE_ERFOLG))
            except discord.Forbidden:
                await message.reply(embed=fehler_embed("Ich habe keine Berechtigung!"))

    # ─── !warn Befehl ─────────────────────────────────────────
    elif inhalt.startswith("!warn"):
        if not message.author.guild_permissions.kick_members:
            await message.reply(embed=fehler_embed("Du brauchst die Berechtigung **Mitglieder kicken** um zu verwarnen!"))
        elif not message.mentions:
            await message.reply(embed=fehler_embed("Nutze: `!warn @user [grund]`"))
        else:
            ziel = message.mentions[0]
            ziel_id = str(ziel.id)
            grund = inhalt.split(" ", 2)[2] if len(inhalt.split(" ", 2)) > 2 else "Kein Grund angegeben"
            if ziel_id not in warnungen:
                warnungen[ziel_id] = []
            warnungen[ziel_id].append({"grund": grund, "von": user_name})
            anzahl = len(warnungen[ziel_id])
            embed = discord.Embed(title="⚠️ Verwarnung erteilt", color=FARBE_SPIEL)
            embed.add_field(name="User", value=ziel.mention, inline=True)
            embed.add_field(name="Anzahl Verwarnungen", value=f"**{anzahl}**", inline=True)
            embed.add_field(name="Grund", value=grund, inline=False)
            if anzahl >= 3:
                embed.add_field(name="⚠️ Achtung", value="Dieser User hat **3 oder mehr** Verwarnungen!", inline=False)
            await message.reply(embed=embed)

    # ─── !warnungen Befehl ────────────────────────────────────
    elif inhalt.startswith("!warnungen"):
        ziel = message.mentions[0] if message.mentions else message.author
        ziel_id = str(ziel.id)
        if ziel_id not in warnungen or not warnungen[ziel_id]:
            await message.reply(embed=discord.Embed(description=f"✅ {ziel.mention} hat keine Verwarnungen!", color=FARBE_ERFOLG))
        else:
            text = "\n".join(f"**{i+1}.** {w['grund']} *(von {w['von']})*" for i, w in enumerate(warnungen[ziel_id]))
            embed = discord.Embed(title=f"⚠️ Verwarnungen von {ziel.display_name}", description=text, color=FARBE_SPIEL)
            embed.set_thumbnail(url=ziel.display_avatar.url)
            await message.reply(embed=embed)

    # ─── !entwarnen Befehl ─────────────────────────────────────
    elif inhalt.startswith("!entwarnen"):
        if not message.author.guild_permissions.kick_members:
            await message.reply(embed=fehler_embed("Du brauchst die Berechtigung **Mitglieder kicken**!"))
        elif not message.mentions:
            await message.reply(embed=fehler_embed("Nutze: `!entwarnen @user`"))
        else:
            ziel = message.mentions[0]
            ziel_id = str(ziel.id)
            warnungen[ziel_id] = []
            await message.reply(embed=discord.Embed(description=f"✅ Alle Verwarnungen von {ziel.mention} gelöscht!", color=FARBE_ERFOLG))

    # ─── !lock Befehl ────────────────────────────────────────
    elif inhalt == "!lock":
        if not message.author.guild_permissions.manage_channels:
            await message.reply(embed=fehler_embed("Du brauchst die Berechtigung **Kanäle verwalten**!"))
        else:
            try:
                overwrite = message.channel.overwrites_for(message.guild.default_role)
                overwrite.send_messages = False
                await message.channel.set_permissions(message.guild.default_role, overwrite=overwrite)
                await message.reply(embed=discord.Embed(description="🔒 Kanal gesperrt! Niemand kann mehr schreiben.", color=FARBE_FEHLER))
            except discord.Forbidden:
                await message.reply(embed=fehler_embed("Mir fehlt die Berechtigung **Kanäle verwalten**!"))

    # ─── !unlock Befehl ──────────────────────────────────────
    elif inhalt == "!unlock":
        if not message.author.guild_permissions.manage_channels:
            await message.reply(embed=fehler_embed("Du brauchst die Berechtigung **Kanäle verwalten**!"))
        else:
            try:
                overwrite = message.channel.overwrites_for(message.guild.default_role)
                overwrite.send_messages = None
                await message.channel.set_permissions(message.guild.default_role, overwrite=overwrite)
                await message.reply(embed=discord.Embed(description="🔓 Kanal entsperrt! Alle können wieder schreiben.", color=FARBE_ERFOLG))
            except discord.Forbidden:
                await message.reply(embed=fehler_embed("Mir fehlt die Berechtigung **Kanäle verwalten**!"))

    # ─── !slowmode Befehl ────────────────────────────────────
    elif inhalt.startswith("!slowmode"):
        if not message.author.guild_permissions.manage_channels:
            await message.reply(embed=fehler_embed("Du brauchst die Berechtigung **Kanäle verwalten**!"))
        else:
            teile = inhalt.split(" ")
            try:
                sekunden = int(teile[1]) if len(teile) > 1 else 0
                if sekunden < 0 or sekunden > 21600:
                    await message.reply(embed=fehler_embed("Zwischen 0 (aus) und 21600 Sekunden (6h)!"))
                else:
                    await message.channel.edit(slowmode_delay=sekunden)
                    if sekunden == 0:
                        await message.reply(embed=discord.Embed(description="⏱️ Slowmode deaktiviert!", color=FARBE_ERFOLG))
                    else:
                        await message.reply(embed=discord.Embed(description=f"⏱️ Slowmode auf **{sekunden} Sekunden** gesetzt!", color=FARBE_TOOL))
            except ValueError:
                await message.reply(embed=fehler_embed("Nutze: `!slowmode [sekunden]`"))
            except discord.Forbidden:
                await message.reply(embed=fehler_embed("Mir fehlt die Berechtigung **Kanäle verwalten**!"))

    # ─── !ankündigung Befehl ──────────────────────────────────
    elif inhalt.startswith("!ankündigung "):
        if not message.author.guild_permissions.manage_messages:
            await message.reply(embed=fehler_embed("Du brauchst die Berechtigung **Nachrichten verwalten**!"))
        else:
            text = inhalt[13:]
            embed = discord.Embed(title="📢 Ankündigung", description=text, color=0xE74C3C)
            embed.set_footer(text=f"Von {user_name}", icon_url=avatar_url)
            embed.timestamp = datetime.utcnow()
            await message.delete()
            await message.channel.send(content="@everyone", embed=embed)

    # ─── !userinfo Befehl ────────────────────────────────────
    elif inhalt.startswith("!userinfo"):
        ziel = message.mentions[0] if message.mentions else message.author
        embed = discord.Embed(title=f"👤 {ziel.display_name}", color=ziel.color if ziel.color.value != 0 else FARBE_INFO)
        embed.set_thumbnail(url=ziel.display_avatar.url)
        embed.add_field(name="Name", value=str(ziel), inline=True)
        embed.add_field(name="ID", value=ziel.id, inline=True)
        embed.add_field(name="Konto erstellt", value=ziel.created_at.strftime("%d.%m.%Y"), inline=True)
        if hasattr(ziel, 'joined_at') and ziel.joined_at:
            embed.add_field(name="Server beigetreten", value=ziel.joined_at.strftime("%d.%m.%Y"), inline=True)
        if hasattr(ziel, 'roles'):
            rollen = ", ".join(r.mention for r in ziel.roles if r.name != "@everyone")
            embed.add_field(name="Rollen", value=rollen if rollen else "Keine", inline=False)
        await message.reply(embed=embed)

    # ─── !serverinfo Befehl ──────────────────────────────────
    elif inhalt == "!serverinfo":
        guild = message.guild
        embed = discord.Embed(title=f"🏠 {guild.name}", color=FARBE_INFO)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Mitglieder", value=guild.member_count, inline=True)
        embed.add_field(name="Erstellt am", value=guild.created_at.strftime("%d.%m.%Y"), inline=True)
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unbekannt", inline=True)
        embed.add_field(name="Kanäle", value=len(guild.channels), inline=True)
        embed.add_field(name="Rollen", value=len(guild.roles), inline=True)
        embed.add_field(name="Server ID", value=guild.id, inline=True)
        await message.reply(embed=embed)

    # ════════════════════════════════════════════════════════
    # ENDE MODERATION
    # ════════════════════════════════════════════════════════

    # ════════════════════════════════════════════════════════
    # 🎮 NEUE SPIELE (keine KI nötig!)
    # ════════════════════════════════════════════════════════

    # ─── !ttt Befehl (Tic-Tac-Toe starten) ──────────────────
    elif inhalt == "!ttt":
        ttt_spiele[channel_id] = {"board": [" "]*9, "spieler": user_id}
        brett_text = ttt_anzeigen(ttt_spiele[channel_id]["board"])
        embed = discord.Embed(title="❌⭕ Tic-Tac-Toe gestartet!", description=f"{brett_text}\n\nDu bist ❌, ich bin ⭕.\nSchreib eine Zahl (1-9) um zu spielen!", color=FARBE_SPIEL)
        embed.set_footer(text=f"Gestartet von {user_name}")
        await message.reply(embed=embed)

    # ─── !hangman Befehl (Galgenmännchen starten) ───────────
    elif inhalt == "!hangman":
        wort = random.choice(HANGMAN_WOERTER)
        hangman_spiele[channel_id] = {"wort": wort, "geraten": set(), "leben": 6}
        anzeige = " ".join("_" for _ in wort)
        embed = discord.Embed(title="🪦 Galgenmännchen gestartet!", description=f"**{anzeige}**\n\nLeben: ❤️❤️❤️❤️❤️❤️\n\nRate Buchstaben, indem du sie einfach in den Chat schreibst!", color=FARBE_SPIEL)
        await message.reply(embed=embed)

    # ─── !quiz Befehl ────────────────────────────────────────
    elif inhalt == "!quiz":
        frage = random.choice(QUIZ_FRAGEN)
        quiz_aktiv[channel_id] = frage
        embed = discord.Embed(title="❓ Quiz-Zeit!", description=f"**{frage['frage']}**\n\nSchreib deine Antwort in den Chat!", color=FARBE_SPIEL)
        embed.set_footer(text="+15 XP für die richtige Antwort")
        await message.reply(embed=embed)

    # ════════════════════════════════════════════════════════
    # 🛠️ SERVER-TOOLS (keine KI nötig!)
    # ════════════════════════════════════════════════════════

    # ─── !setwelcome Befehl ──────────────────────────────────
    elif inhalt.startswith("!setwelcome"):
        if not message.author.guild_permissions.manage_guild:
            await message.reply(embed=fehler_embed("Du brauchst die Berechtigung **Server verwalten**!"))
        elif not message.channel_mentions:
            await message.reply(embed=fehler_embed("Nutze: `!setwelcome #kanal [optional: Nachricht mit {user} und {server}]`"))
        else:
            guild_id = str(message.guild.id)
            if guild_id not in server_config:
                server_config[guild_id] = {}
            server_config[guild_id]["welcome_channel"] = message.channel_mentions[0].id

            # Nachricht extrahieren (alles nach dem Kanal-Mention)
            rest = inhalt.split(">", 1)
            if len(rest) > 1 and rest[1].strip():
                server_config[guild_id]["welcome_msg"] = rest[1].strip()

            embed = discord.Embed(title="✅ Willkommens-Nachricht eingerichtet!", color=FARBE_ERFOLG)
            embed.add_field(name="Kanal", value=message.channel_mentions[0].mention, inline=True)
            embed.add_field(name="Nachricht", value=server_config[guild_id].get("welcome_msg", "Willkommen {user} auf **{server}**! 🎉"), inline=False)
            embed.set_footer(text="Platzhalter: {user} = Mitglied, {server} = Servername")
            await message.reply(embed=embed)

    # ─── !removewelcome Befehl ────────────────────────────────
    elif inhalt == "!removewelcome":
        if not message.author.guild_permissions.manage_guild:
            await message.reply(embed=fehler_embed("Du brauchst die Berechtigung **Server verwalten**!"))
        else:
            guild_id = str(message.guild.id)
            if guild_id in server_config:
                server_config[guild_id].pop("welcome_channel", None)
                server_config[guild_id].pop("welcome_msg", None)
            await message.reply(embed=discord.Embed(description="✅ Willkommens-Nachricht deaktiviert!", color=FARBE_ERFOLG))

    # ─── !autorole Befehl ──────────────────────────────────────
    elif inhalt.startswith("!autorole"):
        if not message.author.guild_permissions.manage_roles:
            await message.reply(embed=fehler_embed("Du brauchst die Berechtigung **Rollen verwalten**!"))
        elif not message.role_mentions:
            await message.reply(embed=fehler_embed("Nutze: `!autorole @rolle`"))
        else:
            guild_id = str(message.guild.id)
            if guild_id not in server_config:
                server_config[guild_id] = {}
            rolle = message.role_mentions[0]
            server_config[guild_id]["autorole"] = rolle.id
            embed = discord.Embed(description=f"✅ Neue Mitglieder bekommen automatisch die Rolle {rolle.mention}!", color=FARBE_ERFOLG)
            await message.reply(embed=embed)

    # ─── !removeautorole Befehl ────────────────────────────────
    elif inhalt == "!removeautorole":
        if not message.author.guild_permissions.manage_roles:
            await message.reply(embed=fehler_embed("Du brauchst die Berechtigung **Rollen verwalten**!"))
        else:
            guild_id = str(message.guild.id)
            if guild_id in server_config:
                server_config[guild_id].pop("autorole", None)
            await message.reply(embed=discord.Embed(description="✅ Auto-Rolle deaktiviert!", color=FARBE_ERFOLG))

    # ════════════════════════════════════════════════════════
    # ℹ️ INFO-BEFEHLE (keine KI nötig!)
    # ════════════════════════════════════════════════════════

    # ─── !ping Befehl ────────────────────────────────────────
    elif inhalt == "!ping":
        latenz = round(bot.latency * 1000)
        embed = discord.Embed(title="🏓 Pong!", description=f"Latenz: **{latenz}ms**", color=FARBE_ERFOLG if latenz < 200 else FARBE_SPIEL)
        await message.reply(embed=embed)

    # ─── !uptime Befehl ──────────────────────────────────────
    elif inhalt == "!uptime":
        delta = datetime.utcnow() - BOT_START
        tage, rest = divmod(int(delta.total_seconds()), 86400)
        stunden, rest = divmod(rest, 3600)
        minuten, sekunden = divmod(rest, 60)
        text = f"{tage}d {stunden}h {minuten}m {sekunden}s"
        embed = discord.Embed(title="⏱️ Bot Uptime", description=f"Online seit: **{text}**", color=FARBE_INFO)
        await message.reply(embed=embed)

    # ─── !avatar Befehl ───────────────────────────────────────
    elif inhalt.startswith("!avatar"):
        ziel = message.mentions[0] if message.mentions else message.author
        embed = discord.Embed(title=f"🖼️ Avatar von {ziel.display_name}", color=FARBE_INFO)
        embed.set_image(url=ziel.display_avatar.url)
        await message.reply(embed=embed)

    # ════════════════════════════════════════════════════════
    # ENDE NEUE FUNKTIONEN
    # ════════════════════════════════════════════════════════

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
            "`!ssp [schere/stein/papier]` · `!rechne [rechnung]`\n"
            "`!ttt` — Tic-Tac-Toe · `!hangman` — Galgenmännchen\n"
            "`!quiz` — Allgemeinwissen-Quiz"
        ), inline=False)
        embed.add_field(name="🛠️ Tools", value=(
            "`!umfrage [frage]` · `!erinnere [zeit] [text]`\n"
            "`!todo add/liste/done/clear`"
        ), inline=False)
        embed.add_field(name="⭐ Level", value=(
            "`!level` · `!rangliste`"
        ), inline=False)
        embed.add_field(name="🛡️ Moderation (braucht Rechte)", value=(
            "`!clear [n]` · `!kick @user [grund]` · `!ban @user [grund]`\n"
            "`!unban [name/id]` · `!mute @user [zeit]` · `!unmute @user`\n"
            "`!warn @user [grund]` · `!warnungen [@user]` · `!entwarnen @user`\n"
            "`!lock` · `!unlock` · `!slowmode [sek]` · `!ankündigung [text]`"
        ), inline=False)
        embed.add_field(name="ℹ️ Info", value=(
            "`!userinfo [@user]` · `!serverinfo` · `!ping`\n"
            "`!uptime` · `!avatar [@user]`"
        ), inline=False)
        embed.add_field(name="⚙️ Server-Einstellungen (braucht Rechte)", value=(
            "`!setwelcome #kanal [text]` · `!removewelcome`\n"
            "`!autorole @rolle` · `!removeautorole`"
        ), inline=False)
        embed.set_footer(text=f"Angefordert von {user_name}", icon_url=avatar_url)
        await message.reply(embed=embed)


# ════════════════════════════════════════════════════════════
# ⚡ SLASH-BEFEHLE (/...)
# Funktionieren genauso wie die !-Befehle, aber mit Discords
# eingebautem Auswahlmenü und Beschreibungen!
# ════════════════════════════════════════════════════════════

# ─── /hilfe ──────────────────────────────────────────────────
@tree.command(name="hilfe", description="Zeigt alle Befehle des Bots übersichtlich an")
async def slash_hilfe(interaction: discord.Interaction):
    embed = bau_hilfe_embed(interaction.user)
    await interaction.response.send_message(embed=embed)

# ─── /ki ─────────────────────────────────────────────────────
@tree.command(name="ki", description="Stelle der KI eine Frage")
@app_commands.describe(frage="Was möchtest du die KI fragen?")
async def slash_ki(interaction: discord.Interaction, frage: str):
    await interaction.response.defer()
    user_id = str(interaction.user.id)
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
            system_text += f" Wichtige Infos über den User: {'; '.join(merkliste[user_id])}."

        messages = [{"role": "system", "content": system_text}] + chat_verlaeufe[user_id]
        antwort_text = await groq_anfrage(messages)
        chat_verlaeufe[user_id].append({"role": "assistant", "content": antwort_text})
        if len(antwort_text) > 4000:
            antwort_text = antwort_text[:3997] + "..."

        aufgestiegen = xp_geben(user_id, 5)
        embed = discord.Embed(description=antwort_text, color=p_info["farbe"])
        embed.set_author(name=f"{p_info['emoji']} {p_info['name']}", icon_url=bot.user.display_avatar.url)
        embed.set_footer(text=f"Gefragt von {interaction.user.display_name} · +5 XP" + (" · 🎉 LEVEL UP!" if aufgestiegen else ""), icon_url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(embed=fehler_embed(f"Fehler: {repr(e)}"))

# ─── /persönlichkeit ─────────────────────────────────────────
@tree.command(name="persönlichkeit", description="Wechsle den Charakter der KI")
@app_commands.describe(charakter="Welcher Charakter soll die KI haben?")
@app_commands.choices(charakter=[
    app_commands.Choice(name="🧑‍⚖️ Anwalt", value="anwalt"),
    app_commands.Choice(name="👧 Mädel", value="mädel"),
    app_commands.Choice(name="👨‍🏫 Lehrer", value="lehrer"),
    app_commands.Choice(name="🏴‍☠️ Pirat", value="pirat"),
    app_commands.Choice(name="🤖 Standard", value="standard"),
])
async def slash_persona(interaction: discord.Interaction, charakter: app_commands.Choice[str]):
    user_id = str(interaction.user.id)
    wahl = charakter.value
    persoenlichkeit[user_id] = wahl
    p_info = PERSONA_INFO[wahl]
    begruessungen = {
        "anwalt": "Wie kann ich Ihnen behilflich sein?",
        "mädel": "Heyyy, na was geht ab? 😊✨",
        "lehrer": "Guten Tag! Womit kann ich dir heute helfen?",
        "pirat": "Arrr! Bereit für ein Abenteuer, Landratte?",
        "standard": "Zurück zum Standard-Modus!"
    }
    embed = discord.Embed(title=f"{p_info['emoji']} Persönlichkeit gewechselt", description=f"**{p_info['name']}**\n\n*{begruessungen[wahl]}*", color=p_info['farbe'])
    await interaction.response.send_message(embed=embed)

# ─── /würfel ─────────────────────────────────────────────────
@tree.command(name="würfel", description="Wirf einen Würfel")
@app_commands.describe(seiten="Wie viele Seiten soll der Würfel haben? (Standard: 6)")
async def slash_wuerfel(interaction: discord.Interaction, seiten: int = 6):
    if seiten < 2 or seiten > 1000:
        await interaction.response.send_message(embed=fehler_embed("Bitte 2-1000 Seiten!"))
        return
    ergebnis = random.randint(1, seiten)
    embed = discord.Embed(title="🎲 Würfelwurf", description=f"# {ergebnis}\n(1-{seiten})", color=FARBE_SPIEL)
    await interaction.response.send_message(embed=embed)

# ─── /münze ──────────────────────────────────────────────────
@tree.command(name="münze", description="Wirf eine Münze (Kopf oder Zahl)")
async def slash_muenze(interaction: discord.Interaction):
    ergebnis = random.choice(["Kopf", "Zahl"])
    emoji = "👑" if ergebnis == "Kopf" else "🔢"
    embed = discord.Embed(title="🪙 Münzwurf", description=f"## {emoji} {ergebnis}", color=FARBE_SPIEL)
    await interaction.response.send_message(embed=embed)

# ─── /rechne ─────────────────────────────────────────────────
@tree.command(name="rechne", description="Taschenrechner - berechnet einen mathematischen Ausdruck")
@app_commands.describe(rechnung="z.B. 5*3+2")
async def slash_rechne(interaction: discord.Interaction, rechnung: str):
    try:
        erlaubt = set("0123456789+-*/(). ")
        if all(c in erlaubt for c in rechnung):
            ergebnis = eval(rechnung)
            embed = discord.Embed(title="🧮 Taschenrechner", color=FARBE_TOOL)
            embed.add_field(name="Rechnung", value=f"`{rechnung}`", inline=True)
            embed.add_field(name="Ergebnis", value=f"**{ergebnis}**", inline=True)
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(embed=fehler_embed("Nur Zahlen und + - * / ( ) erlaubt!"))
    except Exception:
        await interaction.response.send_message(embed=fehler_embed("Das konnte ich nicht berechnen!"))

# ─── /witz, /zitat, /fakt, /kompliment (KI-Befehle ohne Argument) ──
@tree.command(name="witz", description="Erzählt einen lustigen Witz")
async def slash_witz(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        messages = [{"role": "system", "content": "Erzähle einen kurzen, lustigen Witz auf Deutsch. Nur den Witz, keine Einleitung."}, {"role": "user", "content": "Erzähl mir einen Witz"}]
        text = await groq_anfrage(messages, modell="llama-3.1-8b-instant", max_tokens=200)
        await interaction.followup.send(embed=discord.Embed(title="😂 Witz des Tages", description=text, color=FARBE_SPIEL))
    except Exception as e:
        await interaction.followup.send(embed=fehler_embed(f"Fehler: {repr(e)}"))

@tree.command(name="zitat", description="Gibt ein motivierendes Zitat aus")
async def slash_zitat(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        messages = [{"role": "system", "content": "Gib ein kurzes, motivierendes Zitat auf Deutsch aus. Nenne auch einen Autor. Format: 'Zitat' - Autor"}, {"role": "user", "content": "Gib mir ein Zitat"}]
        text = await groq_anfrage(messages, modell="llama-3.1-8b-instant", max_tokens=150)
        await interaction.followup.send(embed=discord.Embed(title="💬 Zitat des Tages", description=f"*{text}*", color=0xF39C12))
    except Exception as e:
        await interaction.followup.send(embed=fehler_embed(f"Fehler: {repr(e)}"))

@tree.command(name="fakt", description="Gibt einen interessanten Fakt aus")
async def slash_fakt(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        messages = [{"role": "system", "content": "Gib einen kurzen, interessanten und überraschenden Fakt auf Deutsch aus. Nur den Fakt."}, {"role": "user", "content": "Gib mir einen Fakt"}]
        text = await groq_anfrage(messages, modell="llama-3.1-8b-instant", max_tokens=150)
        await interaction.followup.send(embed=discord.Embed(title="💡 Wusstest du schon?", description=text, color=0x1ABC9C))
    except Exception as e:
        await interaction.followup.send(embed=fehler_embed(f"Fehler: {repr(e)}"))

@tree.command(name="kompliment", description="Der Bot macht dir ein Kompliment")
async def slash_kompliment(interaction: discord.Interaction):
    await interaction.response.defer()
    try:
        messages = [{"role": "system", "content": f"Gib ein kurzes, herzliches und kreatives Kompliment auf Deutsch an {interaction.user.display_name}. Nur das Kompliment."}, {"role": "user", "content": "Gib mir ein Kompliment"}]
        text = await groq_anfrage(messages, modell="llama-3.1-8b-instant", max_tokens=100)
        embed = discord.Embed(description=f"💖 {text}", color=0xFF6B9D)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(embed=fehler_embed(f"Fehler: {repr(e)}"))

# ─── /übersetzen, /zusammenfassen, /geschichte, /reim ─────────
@tree.command(name="übersetzen", description="Übersetzt einen Text ins Englische")
@app_commands.describe(text="Der zu übersetzende Text")
async def slash_uebersetzen(interaction: discord.Interaction, text: str):
    await interaction.response.defer()
    try:
        messages = [{"role": "system", "content": "Du bist ein Übersetzer. Antworte NUR mit der Übersetzung auf Englisch."}, {"role": "user", "content": text}]
        antwort = await groq_anfrage(messages, modell="llama-3.1-8b-instant", max_tokens=500)
        embed = discord.Embed(title="🌍 Übersetzung", color=FARBE_TOOL)
        embed.add_field(name="Original (DE)", value=text, inline=False)
        embed.add_field(name="Englisch", value=antwort, inline=False)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(embed=fehler_embed(f"Fehler: {repr(e)}"))

@tree.command(name="zusammenfassen", description="Fasst einen Text kurz zusammen")
@app_commands.describe(text="Der zusammenzufassende Text")
async def slash_zusammenfassen(interaction: discord.Interaction, text: str):
    await interaction.response.defer()
    try:
        messages = [{"role": "system", "content": "Du fasst Texte kurz und präzise zusammen."}, {"role": "user", "content": text}]
        antwort = await groq_anfrage(messages, modell="llama-3.1-8b-instant", max_tokens=500)
        await interaction.followup.send(embed=discord.Embed(title="📝 Zusammenfassung", description=antwort, color=FARBE_TOOL))
    except Exception as e:
        await interaction.followup.send(embed=fehler_embed(f"Fehler: {repr(e)}"))

@tree.command(name="geschichte", description="Schreibt eine kurze Geschichte zu einem Thema")
@app_commands.describe(thema="Worüber soll die Geschichte handeln?")
async def slash_geschichte(interaction: discord.Interaction, thema: str):
    await interaction.response.defer()
    try:
        messages = [{"role": "system", "content": "Schreibe eine kurze, kreative Geschichte (max 150 Wörter) auf Deutsch zum gegebenen Thema."}, {"role": "user", "content": thema}]
        antwort = await groq_anfrage(messages, modell="llama-3.3-70b-versatile", max_tokens=400)
        embed = discord.Embed(title=f"📖 {thema}", description=antwort, color=0x8E44AD)
        embed.set_footer(text="✨ KI-generierte Geschichte")
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(embed=fehler_embed(f"Fehler: {repr(e)}"))

@tree.command(name="reim", description="Schreibt einen kurzen Reim zu einem Thema")
@app_commands.describe(thema="Worüber soll der Reim handeln?")
async def slash_reim(interaction: discord.Interaction, thema: str):
    await interaction.response.defer()
    try:
        messages = [{"role": "system", "content": "Schreibe ein kurzes, lustiges 4-zeiliges Gedicht/Reim auf Deutsch zum gegebenen Thema."}, {"role": "user", "content": thema}]
        antwort = await groq_anfrage(messages, modell="llama-3.1-8b-instant", max_tokens=200)
        await interaction.followup.send(embed=discord.Embed(title=f"🎤 Reim: {thema}", description=antwort, color=0x8E44AD))
    except Exception as e:
        await interaction.followup.send(embed=fehler_embed(f"Fehler: {repr(e)}"))

# ─── /level, /rangliste ────────────────────────────────────────
@tree.command(name="level", description="Zeigt dein aktuelles Level und XP")
async def slash_level(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    daten = levels.get(user_id, {"xp": 0, "level": 1})
    benoetigt = daten["level"] * 100
    balken_voll = int((daten["xp"] / benoetigt) * 10)
    balken = "🟩" * balken_voll + "⬜" * (10 - balken_voll)
    embed = discord.Embed(title=f"⭐ Level von {interaction.user.display_name}", color=0xF1C40F)
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(name="Level", value=f"**{daten['level']}**", inline=True)
    embed.add_field(name="XP", value=f"{daten['xp']}/{benoetigt}", inline=True)
    embed.add_field(name="Fortschritt", value=balken, inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="rangliste", description="Zeigt die Top 10 Level-Rangliste")
async def slash_rangliste(interaction: discord.Interaction):
    if not levels:
        await interaction.response.send_message(embed=discord.Embed(description="📊 Noch keine Daten vorhanden!", color=FARBE_INFO))
        return
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
    await interaction.response.send_message(embed=discord.Embed(title="🏆 Rangliste", description=text, color=0xF1C40F))

# ─── /ping, /uptime, /avatar ─────────────────────────────────
@tree.command(name="ping", description="Zeigt die Bot-Latenz an")
async def slash_ping(interaction: discord.Interaction):
    latenz = round(bot.latency * 1000)
    embed = discord.Embed(title="🏓 Pong!", description=f"Latenz: **{latenz}ms**", color=FARBE_ERFOLG if latenz < 200 else FARBE_SPIEL)
    await interaction.response.send_message(embed=embed)

@tree.command(name="uptime", description="Zeigt wie lange der Bot schon läuft")
async def slash_uptime(interaction: discord.Interaction):
    delta = datetime.utcnow() - BOT_START
    tage, rest = divmod(int(delta.total_seconds()), 86400)
    stunden, rest = divmod(rest, 3600)
    minuten, sekunden = divmod(rest, 60)
    text = f"{tage}d {stunden}h {minuten}m {sekunden}s"
    await interaction.response.send_message(embed=discord.Embed(title="⏱️ Bot Uptime", description=f"Online seit: **{text}**", color=FARBE_INFO))

@tree.command(name="avatar", description="Zeigt das Profilbild groß an")
@app_commands.describe(user="Von wem soll das Profilbild gezeigt werden? (leer = du selbst)")
async def slash_avatar(interaction: discord.Interaction, user: discord.Member = None):
    ziel = user or interaction.user
    embed = discord.Embed(title=f"🖼️ Avatar von {ziel.display_name}", color=FARBE_INFO)
    embed.set_image(url=ziel.display_avatar.url)
    await interaction.response.send_message(embed=embed)

# ─── /userinfo, /serverinfo ───────────────────────────────────
@tree.command(name="userinfo", description="Zeigt Informationen über ein Mitglied")
@app_commands.describe(user="Über wen sollen Infos gezeigt werden? (leer = du selbst)")
async def slash_userinfo(interaction: discord.Interaction, user: discord.Member = None):
    ziel = user or interaction.user
    embed = discord.Embed(title=f"👤 {ziel.display_name}", color=ziel.color if ziel.color.value != 0 else FARBE_INFO)
    embed.set_thumbnail(url=ziel.display_avatar.url)
    embed.add_field(name="Name", value=str(ziel), inline=True)
    embed.add_field(name="ID", value=ziel.id, inline=True)
    embed.add_field(name="Konto erstellt", value=ziel.created_at.strftime("%d.%m.%Y"), inline=True)
    if ziel.joined_at:
        embed.add_field(name="Server beigetreten", value=ziel.joined_at.strftime("%d.%m.%Y"), inline=True)
    rollen = ", ".join(r.mention for r in ziel.roles if r.name != "@everyone")
    embed.add_field(name="Rollen", value=rollen if rollen else "Keine", inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="serverinfo", description="Zeigt Informationen über diesen Server")
async def slash_serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"🏠 {guild.name}", color=FARBE_INFO)
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="Mitglieder", value=guild.member_count, inline=True)
    embed.add_field(name="Erstellt am", value=guild.created_at.strftime("%d.%m.%Y"), inline=True)
    embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unbekannt", inline=True)
    embed.add_field(name="Kanäle", value=len(guild.channels), inline=True)
    embed.add_field(name="Rollen", value=len(guild.roles), inline=True)
    embed.add_field(name="Server ID", value=guild.id, inline=True)
    await interaction.response.send_message(embed=embed)

# ════════════════════════════════════════════════════════════
# 🛡️ SLASH MODERATIONS-BEFEHLE
# ════════════════════════════════════════════════════════════

@tree.command(name="kick", description="Kickt ein Mitglied vom Server")
@app_commands.describe(user="Wer soll gekickt werden?", grund="Warum wird gekickt?")
async def slash_kick(interaction: discord.Interaction, user: discord.Member, grund: str = "Kein Grund angegeben"):
    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message(embed=fehler_embed("Du brauchst die Berechtigung **Mitglieder kicken**!"), ephemeral=True)
        return
    if user.guild_permissions.administrator:
        await interaction.response.send_message(embed=fehler_embed("Du kannst keinen Administrator kicken!"), ephemeral=True)
        return
    try:
        await user.kick(reason=f"{grund} (von {interaction.user.display_name})")
        embed = discord.Embed(title="👋 Mitglied gekickt", color=FARBE_ERFOLG)
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Von", value=interaction.user.mention, inline=True)
        embed.add_field(name="Grund", value=grund, inline=False)
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message(embed=fehler_embed("Ich habe keine Berechtigung! (Rolle zu hoch?)"), ephemeral=True)

@tree.command(name="ban", description="Bannt ein Mitglied vom Server")
@app_commands.describe(user="Wer soll gebannt werden?", grund="Warum wird gebannt?")
async def slash_ban(interaction: discord.Interaction, user: discord.Member, grund: str = "Kein Grund angegeben"):
    if not interaction.user.guild_permissions.ban_members:
        await interaction.response.send_message(embed=fehler_embed("Du brauchst die Berechtigung **Mitglieder bannen**!"), ephemeral=True)
        return
    if user.guild_permissions.administrator:
        await interaction.response.send_message(embed=fehler_embed("Du kannst keinen Administrator bannen!"), ephemeral=True)
        return
    try:
        await user.ban(reason=f"{grund} (von {interaction.user.display_name})")
        embed = discord.Embed(title="🔨 Mitglied gebannt", color=FARBE_FEHLER)
        embed.add_field(name="User", value=f"{user.mention} ({user})", inline=True)
        embed.add_field(name="Von", value=interaction.user.mention, inline=True)
        embed.add_field(name="Grund", value=grund, inline=False)
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message(embed=fehler_embed("Ich habe keine Berechtigung! (Rolle zu hoch?)"), ephemeral=True)

@tree.command(name="mute", description="Mutet ein Mitglied für eine bestimmte Zeit (Timeout)")
@app_commands.describe(user="Wer soll gemutet werden?", zeit="z.B. 10m, 1h, 30s", grund="Warum wird gemutet?")
async def slash_mute(interaction: discord.Interaction, user: discord.Member, zeit: str = "10m", grund: str = "Kein Grund angegeben"):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message(embed=fehler_embed("Du brauchst die Berechtigung **Mitglieder timeout**!"), ephemeral=True)
        return
    sekunden = parse_zeit(zeit)
    if sekunden is None:
        await interaction.response.send_message(embed=fehler_embed("Ungültige Zeit! Nutze z.B. `10m`, `1h`, `30s`"), ephemeral=True)
        return
    if sekunden > 2419200:
        await interaction.response.send_message(embed=fehler_embed("Maximal 28 Tage Timeout möglich!"), ephemeral=True)
        return
    if user.guild_permissions.administrator:
        await interaction.response.send_message(embed=fehler_embed("Du kannst keinen Administrator muten!"), ephemeral=True)
        return
    try:
        await user.timeout(timedelta(seconds=sekunden), reason=f"{grund} (von {interaction.user.display_name})")
        embed = discord.Embed(title="🔇 Mitglied gemutet", color=FARBE_SPIEL)
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Dauer", value=zeit, inline=True)
        embed.add_field(name="Grund", value=grund, inline=False)
        await interaction.response.send_message(embed=embed)
    except discord.Forbidden:
        await interaction.response.send_message(embed=fehler_embed("Ich habe keine Berechtigung! (Rolle zu hoch?)"), ephemeral=True)

@tree.command(name="unmute", description="Hebt den Timeout eines Mitglieds auf")
@app_commands.describe(user="Wer soll entmutet werden?")
async def slash_unmute(interaction: discord.Interaction, user: discord.Member):
    if not interaction.user.guild_permissions.moderate_members:
        await interaction.response.send_message(embed=fehler_embed("Du brauchst die Berechtigung **Mitglieder timeout**!"), ephemeral=True)
        return
    try:
        await user.timeout(None)
        await interaction.response.send_message(embed=discord.Embed(description=f"🔊 {user.mention} wurde entmutet!", color=FARBE_ERFOLG))
    except discord.Forbidden:
        await interaction.response.send_message(embed=fehler_embed("Ich habe keine Berechtigung!"), ephemeral=True)

@tree.command(name="warn", description="Verwarnt ein Mitglied")
@app_commands.describe(user="Wer soll verwarnt werden?", grund="Warum wird verwarnt?")
async def slash_warn(interaction: discord.Interaction, user: discord.Member, grund: str = "Kein Grund angegeben"):
    if not interaction.user.guild_permissions.kick_members:
        await interaction.response.send_message(embed=fehler_embed("Du brauchst die Berechtigung **Mitglieder kicken** um zu verwarnen!"), ephemeral=True)
        return
    ziel_id = str(user.id)
    if ziel_id not in warnungen:
        warnungen[ziel_id] = []
    warnungen[ziel_id].append({"grund": grund, "von": interaction.user.display_name})
    anzahl = len(warnungen[ziel_id])
    embed = discord.Embed(title="⚠️ Verwarnung erteilt", color=FARBE_SPIEL)
    embed.add_field(name="User", value=user.mention, inline=True)
    embed.add_field(name="Anzahl Verwarnungen", value=f"**{anzahl}**", inline=True)
    embed.add_field(name="Grund", value=grund, inline=False)
    if anzahl >= 3:
        embed.add_field(name="⚠️ Achtung", value="Dieser User hat **3 oder mehr** Verwarnungen!", inline=False)
    await interaction.response.send_message(embed=embed)

@tree.command(name="clear", description="Löscht eine Anzahl Nachrichten in diesem Kanal")
@app_commands.describe(anzahl="Wie viele Nachrichten sollen gelöscht werden? (1-100)")
async def slash_clear(interaction: discord.Interaction, anzahl: int):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message(embed=fehler_embed("Du brauchst die Berechtigung **Nachrichten verwalten**!"), ephemeral=True)
        return
    if anzahl < 1 or anzahl > 100:
        await interaction.response.send_message(embed=fehler_embed("Bitte eine Zahl zwischen 1 und 100!"), ephemeral=True)
        return
    try:
        deleted = await interaction.channel.purge(limit=anzahl)
        await interaction.response.send_message(embed=discord.Embed(description=f"🧹 **{len(deleted)}** Nachrichten gelöscht!", color=FARBE_ERFOLG), ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message(embed=fehler_embed("Mir fehlt die Berechtigung **Nachrichten verwalten**!"), ephemeral=True)

import discord
import aiohttp
import os
import random
import asyncio
import string
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
BOT_START = datetime.now(timezone.utc)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = discord.Client(intents=intents)

# ─── Daten ─────────────────────────────────────────────────
chat_verlaeufe = {}
persoenlichkeit = {}
merkliste = {}
levels = {}
rate_spiel = {}
todo_listen = {}
warnungen = {}
hangman_spiele = {}
quiz_spiele = {}
tictactoe_spiele = {}
willkommen_kanal = {}

# ─── Design ────────────────────────────────────────────────
FARBE_KI      = 0x5865F2
FARBE_ERFOLG  = 0x57F287
FARBE_FEHLER  = 0xED4245
FARBE_SPIEL   = 0xFEE75C
FARBE_TOOL    = 0xEB459E
FARBE_INFO    = 0x5DADE2

# ─── Persönlichkeiten ──────────────────────────────────────
PERSONAS = {
    "anwalt":   "Du bist ein seriöser Anwalt. Formell, präzise, du sprichst den User mit 'Sie' an.",
    "mädel":    "Du bist eine freche, lustige Freundin. Locker, mit Emojis 😊✨. Du sagst 'du'.",
    "lehrer":   "Du bist ein geduldiger Lehrer. Schritt für Schritt, ermutigend.",
    "pirat":    "Du bist ein wilder Pirat! Arrr, Landratte! Dramatisch und abenteuerlustig.",
    "standard": "Du bist ein hilfreicher Assistent."
}
PERSONA_INFO = {
    "anwalt":   {"emoji": "🧑‍⚖️", "farbe": 0x2C3E50, "name": "Anwalt"},
    "mädel":    {"emoji": "👧",    "farbe": 0xFF6B9D, "name": "Mädel"},
    "lehrer":   {"emoji": "👨‍🏫", "farbe": 0x27AE60, "name": "Lehrer"},
    "pirat":    {"emoji": "🏴‍☠️", "farbe": 0x8B4513, "name": "Pirat"},
    "standard": {"emoji": "🤖",    "farbe": FARBE_KI, "name": "Standard"},
}

# ─── Hangman ───────────────────────────────────────────────
HANGMAN_WOERTER = ["python","discord","programmieren","computer","internet",
                   "datenbank","algorithmus","software","netzwerk","server"]
HANGMAN_BILDER = [
    "```\n  +---+\n  |   |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n  |   |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|   |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n /    |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n=========```",
]

# ─── Quiz ──────────────────────────────────────────────────
QUIZ_FRAGEN = [
    {"frage":"Was ist die Hauptstadt von Deutschland?","antworten":["A) München","B) Berlin","C) Hamburg","D) Frankfurt"],"richtig":"B"},
    {"frage":"Wie viele Planeten hat unser Sonnensystem?","antworten":["A) 7","B) 9","C) 8","D) 10"],"richtig":"C"},
    {"frage":"Was ist H2O?","antworten":["A) Salz","B) Sauerstoff","C) Wasser","D) Wasserstoff"],"richtig":"C"},
    {"frage":"Wer entwickelte die Relativitätstheorie?","antworten":["A) Newton","B) Einstein","C) Hawking","D) Tesla"],"richtig":"B"},
    {"frage":"Wie viele Sekunden hat eine Stunde?","antworten":["A) 3000","B) 3200","C) 3600","D) 4000"],"richtig":"C"},
    {"frage":"Wie viele Bits hat ein Byte?","antworten":["A) 4","B) 16","C) 8","D) 32"],"richtig":"C"},
    {"frage":"Welches Tier ist das größte der Welt?","antworten":["A) Elefant","B) Blauwal","C) Hai","D) Giraffe"],"richtig":"B"},
    {"frage":"Wie viele Kontinente hat die Erde?","antworten":["A) 5","B) 6","C) 7","D) 8"],"richtig":"C"},
]

# ─── Hilfsfunktionen ───────────────────────────────────────
def fehler_embed(text):
    return discord.Embed(description=f"❌ {text}", color=FARBE_FEHLER)

def parse_zeit(text):
    try:
        einheit = text[-1].lower()
        zahl = int(text[:-1])
        return {"s": zahl, "m": zahl*60, "h": zahl*3600}.get(einheit)
    except Exception:
        return None

def xp_geben(user_id, menge=5):
    if user_id not in levels:
        levels[user_id] = {"xp": 0, "level": 1}
    levels[user_id]["xp"] += menge
    benoetigt = levels[user_id]["level"] * 100
    if levels[user_id]["xp"] >= benoetigt:
        levels[user_id]["xp"] -= benoetigt
        levels[user_id]["level"] += 1
        return True
    return False

async def groq_anfrage(messages, modell="llama-3.3-70b-versatile", max_tokens=1000):
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": modell, "messages": messages, "max_tokens": max_tokens}
    async with aiohttp.ClientSession() as session:
        async with session.post(GROQ_URL, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            data = await resp.json()
            if resp.status != 200:
                raise Exception(f"Groq Fehler: {data}")
            return data["choices"][0]["message"]["content"]

# ─── Events ────────────────────────────────────────────────
@bot.event
async def on_member_join(member):
    guild_id = str(member.guild.id)
    if guild_id in willkommen_kanal:
        kanal = bot.get_channel(willkommen_kanal[guild_id])
        if kanal:
            embed = discord.Embed(
                title=f"👋 Willkommen, {member.display_name}!",
                description=f"Schön dass du auf **{member.guild.name}** bist!\nDu bist Mitglied **#{member.guild.member_count}**.",
                color=FARBE_ERFOLG
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            await kanal.send(content=member.mention, embed=embed)

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

    # ── Hangman: Buchstabe raten ──────────────────────────
    if user_id in hangman_spiele and len(inhalt) == 1 and inhalt.isalpha():
        spiel = hangman_spiele[user_id]
        b = inhalt.lower()
        if b in spiel["geraten"]:
            await message.reply(embed=discord.Embed(description=f"❗ **{b}** hast du schon versucht!", color=FARBE_SPIEL))
            return
        spiel["geraten"].append(b)
        if b not in spiel["wort"]:
            spiel["falsch"] += 1
        angezeigt = " ".join(c if c in spiel["geraten"] else "_" for c in spiel["wort"])
        falsch = [c for c in spiel["geraten"] if c not in spiel["wort"]]
        if "_" not in angezeigt:
            del hangman_spiele[user_id]
            xp_geben(user_id, 30)
            await message.reply(embed=discord.Embed(title="🎉 Gewonnen!", description=f"Das Wort war: **{spiel['wort']}**\n+30 XP!", color=FARBE_ERFOLG))
        elif spiel["falsch"] >= 6:
            del hangman_spiele[user_id]
            await message.reply(embed=discord.Embed(title="💀 Verloren!", description=f"{HANGMAN_BILDER[6]}\nDas Wort war: **{spiel['wort']}**", color=FARBE_FEHLER))
        else:
            embed = discord.Embed(title="🎯 Hangman", description=f"{HANGMAN_BILDER[spiel['falsch']]}\n`{angezeigt}`", color=FARBE_SPIEL)
            embed.add_field(name="Falsch", value=" ".join(falsch) or "—", inline=True)
            embed.add_field(name="Übrig", value=str(6-spiel["falsch"]), inline=True)
            await message.reply(embed=embed)
        return

    # ── Quiz: Antwort ─────────────────────────────────────
    if user_id in quiz_spiele and inhalt.upper() in ["A","B","C","D"]:
        spiel = quiz_spiele.pop(user_id)
        if inhalt.upper() == spiel["richtig"]:
            xp_geben(user_id, 15)
            await message.reply(embed=discord.Embed(description="✅ **Richtig!** +15 XP ⭐", color=FARBE_ERFOLG))
        else:
            await message.reply(embed=discord.Embed(description=f"❌ **Falsch!** Richtige Antwort: **{spiel['richtig']}**", color=FARBE_FEHLER))
        return

    # ── Zahlenraten: Tipp ────────────────────────────────
    if user_id in rate_spiel and inhalt.strip().lstrip("-").isdigit():
        tipp = int(inhalt.strip())
        ziel = rate_spiel[user_id]["zahl"]
        rate_spiel[user_id]["versuche"] += 1
        if tipp == ziel:
            v = rate_spiel[user_id]["versuche"]
            del rate_spiel[user_id]
            xp_geben(user_id, 20)
            await message.reply(embed=discord.Embed(title="🎉 Richtig!", description=f"Die Zahl war **{ziel}**!\n{v} Versuche · +20 XP", color=FARBE_ERFOLG))
        elif tipp < ziel:
            await message.add_reaction("📈")
        else:
            await message.add_reaction("📉")
        return

    # ── TicTacToe: Zug ───────────────────────────────────
    if inhalt.strip().isdigit() and 1 <= int(inhalt.strip()) <= 9:
        for sid, s in list(tictactoe_spiele.items()):
            if s["spieler"][s["aktuell"]].id == message.author.id:
                pos = int(inhalt.strip()) - 1
                if s["brett"][pos] != " ":
                    await message.reply(embed=fehler_embed("Dieses Feld ist schon belegt!"))
                    return
                s["brett"][pos] = s["zeichen"][s["aktuell"]]
                brett = s["brett"]
                gewinn = [(0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6)]
                gewinner = None
                for a,b,c in gewinn:
                    if brett[a] == brett[b] == brett[c] != " ":
                        gewinner = s["spieler"][s["aktuell"]]
                brett_text = (f"`{brett[0]}|{brett[1]}|{brett[2]}`\n"
                              f"`{brett[3]}|{brett[4]}|{brett[5]}`\n"
                              f"`{brett[6]}|{brett[7]}|{brett[8]}`").replace(" ","⬜")
                if gewinner:
                    del tictactoe_spiele[sid]
                    xp_geben(str(gewinner.id), 25)
                    await message.channel.send(embed=discord.Embed(title=f"🎉 {gewinner.display_name} gewinnt!", description=brett_text, color=FARBE_ERFOLG))
                elif " " not in brett:
                    del tictactoe_spiele[sid]
                    await message.channel.send(embed=discord.Embed(title="🤝 Unentschieden!", description=brett_text, color=FARBE_INFO))
                else:
                    s["aktuell"] = 1 - s["aktuell"]
                    naechster = s["spieler"][s["aktuell"]]
                    embed = discord.Embed(title="❌⭕ TicTacToe", description=brett_text, color=FARBE_SPIEL)
                    embed.add_field(name="Am Zug", value=f"{s['zeichen'][s['aktuell']]} {naechster.mention}")
                    await message.channel.send(embed=embed)
                return

    # ════════════════ BEFEHLE ════════════════════════════

    # ── !ki ──────────────────────────────────────────────
    if inhalt.startswith("!ki "):
        frage = inhalt[4:]
        async with message.channel.typing():
            try:
                if user_id not in chat_verlaeufe:
                    chat_verlaeufe[user_id] = []
                chat_verlaeufe[user_id].append({"role":"user","content":frage})
                if len(chat_verlaeufe[user_id]) > 20:
                    chat_verlaeufe[user_id] = chat_verlaeufe[user_id][-20:]
                p = persoenlichkeit.get(user_id, "standard")
                sys = PERSONAS[p]
                if user_id in merkliste and merkliste[user_id]:
                    sys += f" Infos über den User: {'; '.join(merkliste[user_id])}."
                msgs = [{"role":"system","content":sys}] + chat_verlaeufe[user_id]
                antwort = await groq_anfrage(msgs)
                chat_verlaeufe[user_id].append({"role":"assistant","content":antwort})
                if len(antwort) > 4000:
                    antwort = antwort[:3997] + "..."
                aufgestiegen = xp_geben(user_id, 5)
                pi = PERSONA_INFO[p]
                embed = discord.Embed(description=antwort, color=pi["farbe"])
                embed.set_author(name=f"{pi['emoji']} {pi['name']}", icon_url=bot.user.display_avatar.url)
                embed.set_footer(text=f"Gefragt von {user_name} · +5 XP" + (" · 🎉 LEVEL UP!" if aufgestiegen else ""), icon_url=avatar_url)
                await message.reply(embed=embed)
            except Exception as e:
                await message.reply(embed=fehler_embed(repr(e)))

    # ── !persönlichkeit ───────────────────────────────────
    elif inhalt.startswith("!persönlichkeit"):
        t = inhalt.split(" ")
        if len(t) < 2:
            embed = discord.Embed(title="🎭 Persönlichkeiten", color=FARBE_INFO)
            for k,v in PERSONA_INFO.items():
                embed.add_field(name=f"{v['emoji']} {v['name']}", value=f"`!persönlichkeit {k}`", inline=True)
            await message.reply(embed=embed)
        elif t[1].lower() in PERSONAS:
            w = t[1].lower()
            persoenlichkeit[user_id] = w
            pi = PERSONA_INFO[w]
            begruess = {"anwalt":"Wie kann ich Ihnen helfen?","mädel":"Heyyy! 😊✨","lehrer":"Guten Tag!","pirat":"Arrr! Landratte!","standard":"Bereit!"}
            await message.reply(embed=discord.Embed(title=f"{pi['emoji']} {pi['name']}", description=begruess[w], color=pi["farbe"]))
        else:
            await message.reply(embed=fehler_embed("Unbekannt! Nutze `!persönlichkeit` für die Liste."))

    # ── !merke ────────────────────────────────────────────
    elif inhalt.startswith("!merke "):
        info = inhalt[7:]
        if user_id not in merkliste: merkliste[user_id] = []
        merkliste[user_id].append(info)
        await message.reply(embed=discord.Embed(description=f"🧠 Gemerkt: *{info}*", color=FARBE_ERFOLG))

    elif inhalt == "!merkliste":
        if user_id in merkliste and merkliste[user_id]:
            embed = discord.Embed(title="🧠 Meine Notizen über dich", description="\n".join(f"• {x}" for x in merkliste[user_id]), color=FARBE_INFO)
            embed.set_thumbnail(url=avatar_url)
            await message.reply(embed=embed)
        else:
            await message.reply(embed=discord.Embed(description="🧠 Noch nichts gemerkt! Nutze `!merke [info]`", color=FARBE_INFO))

    elif inhalt == "!vergiss":
        merkliste[user_id] = []
        await message.reply(embed=discord.Embed(description="🗑️ Alles vergessen!", color=FARBE_ERFOLG))

    # ── !übersetzen ───────────────────────────────────────
    elif inhalt.startswith("!übersetzen "):
        text = inhalt[12:]
        async with message.channel.typing():
            try:
                antwort = await groq_anfrage([{"role":"system","content":"Übersetze NUR auf Englisch, keine Erklärung."},{"role":"user","content":text}], modell="llama-3.1-8b-instant", max_tokens=500)
                embed = discord.Embed(title="🌍 Übersetzung", color=FARBE_TOOL)
                embed.add_field(name="Original", value=text, inline=False)
                embed.add_field(name="Englisch", value=antwort, inline=False)
                await message.reply(embed=embed)
            except Exception as e:
                await message.reply(embed=fehler_embed(repr(e)))

    # ── !zusammenfassen ───────────────────────────────────
    elif inhalt.startswith("!zusammenfassen "):
        text = inhalt[16:]
        async with message.channel.typing():
            try:
                antwort = await groq_anfrage([{"role":"system","content":"Fasse kurz zusammen."},{"role":"user","content":text}], modell="llama-3.1-8b-instant", max_tokens=500)
                await message.reply(embed=discord.Embed(title="📝 Zusammenfassung", description=antwort, color=FARBE_TOOL))
            except Exception as e:
                await message.reply(embed=fehler_embed(repr(e)))

    # ── !geschichte ───────────────────────────────────────
    elif inhalt.startswith("!geschichte "):
        thema = inhalt[12:]
        async with message.channel.typing():
            try:
                antwort = await groq_anfrage([{"role":"system","content":"Schreibe eine kurze kreative Geschichte (max 150 Wörter) auf Deutsch."},{"role":"user","content":thema}], max_tokens=400)
                await message.reply(embed=discord.Embed(title=f"📖 {thema}", description=antwort, color=0x8E44AD))
            except Exception as e:
                await message.reply(embed=fehler_embed(repr(e)))

    # ── !reim ─────────────────────────────────────────────
    elif inhalt.startswith("!reim "):
        thema = inhalt[6:]
        async with message.channel.typing():
            try:
                antwort = await groq_anfrage([{"role":"system","content":"Schreibe ein lustiges 4-zeiliges Gedicht auf Deutsch."},{"role":"user","content":thema}], modell="llama-3.1-8b-instant", max_tokens=200)
                await message.reply(embed=discord.Embed(title=f"🎤 Reim: {thema}", description=antwort, color=0x8E44AD))
            except Exception as e:
                await message.reply(embed=fehler_embed(repr(e)))

    # ── !witz ─────────────────────────────────────────────
    elif inhalt == "!witz":
        async with message.channel.typing():
            try:
                antwort = await groq_anfrage([{"role":"system","content":"Erzähle einen kurzen Witz auf Deutsch. Nur den Witz."},{"role":"user","content":"Witz"}], modell="llama-3.1-8b-instant", max_tokens=200)
                await message.reply(embed=discord.Embed(title="😂 Witz", description=antwort, color=FARBE_SPIEL))
            except Exception as e:
                await message.reply(embed=fehler_embed(repr(e)))

    # ── !zitat ────────────────────────────────────────────
    elif inhalt == "!zitat":
        async with message.channel.typing():
            try:
                antwort = await groq_anfrage([{"role":"system","content":"Gib ein motivierendes Zitat auf Deutsch. Format: 'Zitat' - Autor"},{"role":"user","content":"Zitat"}], modell="llama-3.1-8b-instant", max_tokens=150)
                await message.reply(embed=discord.Embed(title="💬 Zitat", description=f"*{antwort}*", color=0xF39C12))
            except Exception as e:
                await message.reply(embed=fehler_embed(repr(e)))

    # ── !fakt ─────────────────────────────────────────────
    elif inhalt == "!fakt":
        async with message.channel.typing():
            try:
                antwort = await groq_anfrage([{"role":"system","content":"Gib einen überraschenden Fakt auf Deutsch. Nur den Fakt."},{"role":"user","content":"Fakt"}], modell="llama-3.1-8b-instant", max_tokens=150)
                await message.reply(embed=discord.Embed(title="💡 Wusstest du schon?", description=antwort, color=0x1ABC9C))
            except Exception as e:
                await message.reply(embed=fehler_embed(repr(e)))

    # ── !kompliment ───────────────────────────────────────
    elif inhalt == "!kompliment":
        async with message.channel.typing():
            try:
                antwort = await groq_anfrage([{"role":"system","content":f"Gib ein herzliches Kompliment auf Deutsch an {user_name}. Nur das Kompliment."},{"role":"user","content":"Kompliment"}], modell="llama-3.1-8b-instant", max_tokens=100)
                embed = discord.Embed(description=f"💖 {antwort}", color=0xFF6B9D)
                embed.set_thumbnail(url=avatar_url)
                await message.reply(embed=embed)
            except Exception as e:
                await message.reply(embed=fehler_embed(repr(e)))

    # ── !rechne ───────────────────────────────────────────
    elif inhalt.startswith("!rechne "):
        text = inhalt[8:]
        try:
            if all(c in "0123456789+-*/(). " for c in text):
                ergebnis = eval(text)
                embed = discord.Embed(title="🧮 Rechner", color=FARBE_TOOL)
                embed.add_field(name="Rechnung", value=f"`{text}`", inline=True)
                embed.add_field(name="Ergebnis", value=f"**{ergebnis}**", inline=True)
                await message.reply(embed=embed)
            else:
                await message.reply(embed=fehler_embed("Nur Zahlen und + - * / ( ) erlaubt!"))
        except Exception:
            await message.reply(embed=fehler_embed("Ungültige Rechnung!"))

    # ── !würfel ───────────────────────────────────────────
    elif inhalt.startswith("!würfel"):
        t = inhalt.split(" ")
        seiten = int(t[1]) if len(t) > 1 and t[1].isdigit() else 6
        await message.reply(embed=discord.Embed(title="🎲 Würfelwurf", description=f"# {random.randint(1,seiten)}\n(1-{seiten})", color=FARBE_SPIEL))

    # ── !münze ────────────────────────────────────────────
    elif inhalt == "!münze":
        e, r = random.choice([("👑","Kopf"),("🔢","Zahl")])
        await message.reply(embed=discord.Embed(title="🪙 Münzwurf", description=f"## {e} {r}", color=FARBE_SPIEL))

    # ── !rate ─────────────────────────────────────────────
    elif inhalt.startswith("!rate"):
        t = inhalt.split(" ")
        maxz = int(t[1]) if len(t) > 1 and t[1].isdigit() else 100
        rate_spiel[user_id] = {"zahl": random.randint(1,maxz), "versuche": 0}
        await message.reply(embed=discord.Embed(title="🔢 Zahlenraten", description=f"Ich denke an eine Zahl zwischen **1 und {maxz}**!\nSchreib eine Zahl um zu raten!", color=FARBE_SPIEL))

    # ── !ssp ──────────────────────────────────────────────
    elif inhalt.startswith("!ssp "):
        w = inhalt[5:].strip().lower()
        opt = {"schere":"✂️","stein":"🪨","papier":"📄"}
        if w not in opt:
            await message.reply(embed=fehler_embed("Nutze: `!ssp schere/stein/papier`"))
        else:
            wb = random.choice(list(opt.keys()))
            if w == wb:
                r, f = "🤝 Unentschieden!", FARBE_INFO
            elif (w=="schere" and wb=="papier") or (w=="stein" and wb=="schere") or (w=="papier" and wb=="stein"):
                r, f = "🎉 Du gewinnst! +10 XP", FARBE_ERFOLG
                xp_geben(user_id, 10)
            else:
                r, f = "😢 Du verlierst!", FARBE_FEHLER
            embed = discord.Embed(title="✂️ Schere Stein Papier", color=f)
            embed.add_field(name="Du", value=f"{opt[w]} {w}", inline=True)
            embed.add_field(name="Bot", value=f"{opt[wb]} {wb}", inline=True)
            embed.add_field(name="Ergebnis", value=r, inline=False)
            await message.reply(embed=embed)

    # ── !hangman ──────────────────────────────────────────
    elif inhalt == "!hangman":
        wort = random.choice(HANGMAN_WOERTER)
        hangman_spiele[user_id] = {"wort": wort, "geraten": [], "falsch": 0}
        angezeigt = " ".join("_" for _ in wort)
        embed = discord.Embed(title="🎯 Hangman", description=f"{HANGMAN_BILDER[0]}\n`{angezeigt}`\n\nSchreibe einen Buchstaben!", color=FARBE_SPIEL)
        await message.reply(embed=embed)

    # ── !quiz ─────────────────────────────────────────────
    elif inhalt == "!quiz":
        frage = random.choice(QUIZ_FRAGEN)
        quiz_spiele[user_id] = {"richtig": frage["richtig"]}
        embed = discord.Embed(title="🧠 Quiz", description=f"**{frage['frage']}**\n\n" + "\n".join(frage["antworten"]), color=FARBE_INFO)
        embed.set_footer(text="Antworte mit A, B, C oder D!")
        await message.reply(embed=embed)

    # ── !ttt ──────────────────────────────────────────────
    elif inhalt.startswith("!ttt "):
        if not message.mentions:
            await message.reply(embed=fehler_embed("Nutze: `!ttt @user`"))
        else:
            gegner = message.mentions[0]
            if gegner == message.author or gegner.bot:
                await message.reply(embed=fehler_embed("Ungültiger Gegner!"))
            else:
                sid = f"{user_id}-{gegner.id}"
                tictactoe_spiele[sid] = {"brett":[" "]*9,"spieler":[message.author,gegner],"aktuell":0,"zeichen":["❌","⭕"]}
                embed = discord.Embed(title="❌⭕ TicTacToe", description="`1|2|3`\n`4|5|6`\n`7|8|9`", color=FARBE_SPIEL)
                embed.add_field(name="Spieler", value=f"❌ {message.author.mention}\n⭕ {gegner.mention}")
                embed.add_field(name="Am Zug", value=f"❌ {message.author.mention}")
                embed.set_footer(text="Schreibe 1-9 um zu spielen!")
                await message.channel.send(embed=embed)

    # ── !ship ─────────────────────────────────────────────
    elif inhalt.startswith("!ship"):
        if len(message.mentions) >= 2:
            u1, u2 = message.mentions[0], message.mentions[1]
        elif len(message.mentions) == 1:
            u1, u2 = message.author, message.mentions[0]
        else:
            await message.reply(embed=fehler_embed("Nutze: `!ship @user1 @user2`"))
            return
        random.seed((u1.id + u2.id) % 101)
        p = random.randint(0, 100)
        random.seed()
        emoji = "💕" if p >= 80 else "💖" if p >= 60 else "💛" if p >= 40 else "💔" if p >= 20 else "😬"
        text = "Perfektes Match!" if p >= 80 else "Sehr gute Chancen!" if p >= 60 else "Naja..." if p >= 40 else "Eher nicht..." if p >= 20 else "Keine Chance!"
        balken = "❤️"*(p//10) + "🖤"*(10-p//10)
        await message.reply(embed=discord.Embed(title="💘 Ship-O-Meter", description=f"**{u1.display_name}** & **{u2.display_name}**\n\n{balken}\n**{p}%** {emoji}\n*{text}*", color=0xFF6B9D))

    # ── !avatar ───────────────────────────────────────────
    elif inhalt.startswith("!avatar"):
        ziel = message.mentions[0] if message.mentions else message.author
        embed = discord.Embed(title=f"🖼️ {ziel.display_name}", color=FARBE_INFO)
        embed.set_image(url=ziel.display_avatar.url)
        await message.reply(embed=embed)

    # ── !passwort ─────────────────────────────────────────
    elif inhalt.startswith("!passwort"):
        t = inhalt.split(" ")
        l = min(max(int(t[1]),8),64) if len(t)>1 and t[1].isdigit() else 16
        pw = "".join(random.choice(string.ascii_letters+string.digits+"!@#$%^&*") for _ in range(l))
        embed = discord.Embed(title="🔐 Sicheres Passwort", color=FARBE_TOOL)
        embed.add_field(name="Passwort", value=f"||`{pw}`||", inline=False)
        embed.add_field(name="Länge", value=str(l), inline=True)
        embed.set_footer(text="⚠️ Nur du siehst den Spoiler! Speichere es sicher.")
        await message.reply(embed=embed)

    # ── !umrechnen ────────────────────────────────────────
    elif inhalt.startswith("!umrechnen "):
        t = inhalt.split(" ")
        if len(t) < 4:
            await message.reply(embed=discord.Embed(title="🔄 Umrechner", description="Nutze: `!umrechnen [zahl] [von] [zu]`\nz.B. `!umrechnen 100 km miles`\n\n**Unterstützt:** km↔miles, kg↔lbs, celsius↔fahrenheit, liter↔gallonen, euro↔dollar", color=FARBE_TOOL))
        else:
            try:
                zahl = float(t[1])
                von, zu = t[2].lower(), t[3].lower()
                umr = {("km","miles"):lambda x:x*0.621371,("miles","km"):lambda x:x*1.60934,
                       ("kg","lbs"):lambda x:x*2.20462,("lbs","kg"):lambda x:x/2.20462,
                       ("celsius","fahrenheit"):lambda x:x*9/5+32,("fahrenheit","celsius"):lambda x:(x-32)*5/9,
                       ("liter","gallonen"):lambda x:x*0.264172,("gallonen","liter"):lambda x:x*3.78541,
                       ("euro","dollar"):lambda x:x*1.08,("dollar","euro"):lambda x:x/1.08}
                if (von,zu) in umr:
                    ergebnis = round(umr[(von,zu)](zahl), 4)
                    embed = discord.Embed(title="🔄 Umrechnung", color=FARBE_TOOL)
                    embed.add_field(name="Eingabe", value=f"`{zahl} {von}`", inline=True)
                    embed.add_field(name="Ergebnis", value=f"**{ergebnis} {zu}**", inline=True)
                    await message.reply(embed=embed)
                else:
                    await message.reply(embed=fehler_embed(f"Kann `{von}` nicht in `{zu}` umrechnen!"))
            except Exception:
                await message.reply(embed=fehler_embed("Ungültige Eingabe!"))

    # ── !umfrage ──────────────────────────────────────────
    elif inhalt.startswith("!umfrage "):
        frage = inhalt[9:]
        embed = discord.Embed(title="📊 Umfrage", description=f"## {frage}", color=FARBE_TOOL)
        embed.set_footer(text=f"Erstellt von {user_name}", icon_url=avatar_url)
        msg = await message.channel.send(embed=embed)
        for r in ["👍","👎","🤷"]: await msg.add_reaction(r)

    # ── !erinnere ─────────────────────────────────────────
    elif inhalt.startswith("!erinnere "):
        t = inhalt[10:].split(" ", 1)
        if len(t) < 2:
            await message.reply(embed=fehler_embed("Nutze: `!erinnere 10m Text`"))
        else:
            sek = parse_zeit(t[0])
            if sek is None or sek > 86400:
                await message.reply(embed=fehler_embed("Ungültige Zeit (max 24h)!"))
            else:
                await message.reply(embed=discord.Embed(title="⏰ Erinnerung gesetzt", description=f"In **{t[0]}**: *{t[1]}*", color=FARBE_TOOL))
                await asyncio.sleep(sek)
                await message.channel.send(content=message.author.mention, embed=discord.Embed(title="🔔 Erinnerung!", description=t[1], color=0xF39C12))

    # ── !todo ─────────────────────────────────────────────
    elif inhalt.startswith("!todo"):
        t = inhalt.split(" ", 2)
        if user_id not in todo_listen: todo_listen[user_id] = []
        aktion = t[1] if len(t) > 1 else "liste"
        if aktion == "liste" or len(t) == 1:
            if not todo_listen[user_id]:
                await message.reply(embed=discord.Embed(description="📋 Liste leer! `!todo add [aufgabe]`", color=FARBE_TOOL))
            else:
                liste = "\n".join(f"**{i+1}.** {x}" for i,x in enumerate(todo_listen[user_id]))
                await message.reply(embed=discord.Embed(title="📋 To-Do Liste", description=liste, color=FARBE_TOOL))
        elif aktion == "add" and len(t) > 2:
            todo_listen[user_id].append(t[2])
            await message.reply(embed=discord.Embed(description=f"✅ Hinzugefügt: *{t[2]}*", color=FARBE_ERFOLG))
        elif aktion == "done" and len(t) > 2 and t[2].isdigit():
            idx = int(t[2])-1
            if 0 <= idx < len(todo_listen[user_id]):
                e = todo_listen[user_id].pop(idx)
                await message.reply(embed=discord.Embed(description=f"🎉 Erledigt: *{e}*", color=FARBE_ERFOLG))
        elif aktion == "clear":
            todo_listen[user_id] = []
            await message.reply(embed=discord.Embed(description="🗑️ Liste geleert!", color=FARBE_ERFOLG))

    # ── !willkommen ───────────────────────────────────────
    elif inhalt.startswith("!willkommen"):
        if not message.author.guild_permissions.manage_guild:
            await message.reply(embed=fehler_embed("Du brauchst **Server verwalten**!"))
        elif "aus" in inhalt:
            willkommen_kanal.pop(str(message.guild.id), None)
            await message.reply(embed=discord.Embed(description="✅ Willkommen deaktiviert!", color=FARBE_ERFOLG))
        else:
            willkommen_kanal[str(message.guild.id)] = message.channel.id
            await message.reply(embed=discord.Embed(description=f"✅ Willkommen in {message.channel.mention} aktiviert!", color=FARBE_ERFOLG))

    # ── !giveaway ─────────────────────────────────────────
    elif inhalt.startswith("!giveaway "):
        if not message.author.guild_permissions.manage_guild:
            await message.reply(embed=fehler_embed("Du brauchst **Server verwalten**!"))
        else:
            t = inhalt.split(" ", 2)
            if len(t) < 3:
                await message.reply(embed=fehler_embed("Nutze: `!giveaway [zeit] [preis]`\nz.B. `!giveaway 10m Discord Nitro`"))
            else:
                sek = parse_zeit(t[1])
                if not sek:
                    await message.reply(embed=fehler_embed("Ungültige Zeitangabe! Nutze z.B. 30s, 10m, 2h"))
                else:
                    preis = t[2]
                    embed = discord.Embed(title="🎉 GIVEAWAY 🎉", description=f"Gewinne: **{preis}**\nReagiere mit 🎉 um teilzunehmen!\nZeit: {t[1]}", color=FARBE_SPIEL)
                    g_msg = await message.channel.send(embed=embed)
                    await g_msg.add_reaction("🎉")
                    
                    await asyncio.sleep(sek)
                    
                    # Nachricht neu laden, um die Reaktionen abzufragen
                    g_msg = await message.channel.fetch_message(g_msg.id)
                    users = []
                    for reaction in g_msg.reactions:
                        if str(reaction.emoji) == "🎉":
                            async for u in reaction.users():
                                if not u.bot:
                                    users.append(u)
                    
                    if users:
                        gewinner = random.choice(users)
                        await message.channel.send(f"🎉 Herzlichen Glückwunsch {gewinner.mention}! Du hast **{preis}** gewonnen!")
                    else:
                        await message.channel.send("😢 Das Giveaway ist vorbei, aber niemand hat teilgenommen.")

    # ── !hilfe ────────────────────────────────────────────
    elif inhalt == "!hilfe":
        embed = discord.Embed(title="📜 Bot Befehlsliste", description="Hier sind alle verfügbaren Befehle:", color=FARBE_INFO)
        embed.add_field(name="🤖 KI & Tools", value="`!ki [Frage]` · `!persönlichkeit` · `!übersetzen [Text]` · `!zusammenfassen [Text]` · `!rechne [Formel]` · `!umrechnen [Werte]`", inline=False)
        embed.add_field(name="🎮 Spiele & Spaß", value="`!hangman` · `!quiz` · `!rate` · `!ssp [Wahl]` · `!ttt @user` · `!ship @user` · `!würfel` · `!münze` · `!geschichte [Thema]` · `!reim [Thema]` · `!witz` · `!fakt` · `!kompliment`", inline=False)
        embed.add_field(name="⚙️ Utilities", value="`!merke [Text]` · `!merkliste` · `!vergiss` · `!avatar [@user]` · `!passwort [Länge]` · `!umfrage [Frage]` · `!erinnere [Zeit] [Text]` · `!todo [add/done/clear]`", inline=False)
        embed.add_field(name="🛠️ Moderation", value="`!willkommen [aus]` · `!giveaway [Zeit] [Preis]`", inline=False)
        await message.reply(embed=embed)

bot.run(DISCORD_TOKEN)

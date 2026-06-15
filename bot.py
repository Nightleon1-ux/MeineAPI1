import discord
from discord import app_commands
import aiohttp
import os
import random
import asyncio
import string
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# ─── CONFIGURATION: STATICS ────────────────────────────────
LEVEL_ROLLEN_BELOHNUNGEN = {
    5: "Bronze-Mitglied",
    10: "Silber-Mitglied",
    20: "Gold-Mitglied",
    50: "Server-Legende"
}

SHOP_ITEMS = {
    "kekse": {"name": "🍪 Kekse", "preis": 25, "beschreibung": "Leckeres Futter für dein Haustier (-30 Hunger)"},
    "steak": {"name": "🥩 Premium Steak", "preis": 60, "beschreibung": "Perfekt für Drachen und Hunde (-80 Hunger)"},
    "booster": {"name": "⚡ XP-Booster", "preis": 150, "beschreibung": "Gibt dir sofort 200 zusätzliche User-XP"},
    "gluecksbringer": {"name": "🍀 Glücksbringer", "preis": 300, "beschreibung": "Erhöht deine Gewinnchancen bei Minigames passiv"}
}

PERSONAS = {
    "anwalt": "Du bist ein seriöser Anwalt. Formell, präzise, du sprichst den User mit 'Sie' an.",
    "mädel": "Du bist eine freche, lustige Freundin. Locker, mit Emojis 😊✨. Du sagst 'du'.",
    "lehrer": "Du bist ein geduldiger Lehrer. Schritt für Schritt, ermutigend.",
    "pirat": "Du bist ein wilder Pirat! Arrr, Landratte! Dramatisch und abenteuerlustig.",
    "standard": "Du bist ein hilfreicher Assistent."
}

# Farb-Palette für konsistentes UI-Design
class BotFarben:
    KI = 0x5865F2
    ERFOLG = 0x57F287
    FEHLER = 0xED4245
    SPIEL = 0xFEE75C
    TOOL = 0xEB459E
    INFO = 0x5DADE2
    WIRTSCHAFT = 0xE67E22

# ─── DATA MODELS (PROFESSIONELLE DATENHALTUNG) ─────────────
@dataclass
class UserProfile:
    xp: int = 0
    level: int = 1
    gesamt_xp: int = 0
    muenzen: int = 100  # Startguthaben
    inventar: Dict[str, int] = field(default_factory=dict)
    todo: List[str] = field(default_factory=list)
    ki_persona: str = "standard"
    partner_id: Optional[str] = None
    letztes_daily: Optional[str] = None  # ISO-String für Zeitzonen-Sicherheit

@dataclass
class PetProfile:
    name: str
    typ: str
    level: int = 1
    hunger: int = 20
    letztes_streicheln: Optional[str] = None

# Globaler State-Manager
class BotState:
    def __init__(self, datei_pfad: str = "bot_daten.json"):
        self.datei_pfad = datei_pfad
        self.user_daten: Dict[str, UserProfile] = {}
        self.pet_daten: Dict[str, PetProfile] = {}
        self.chat_verlaeufe: Dict[str, List[dict]] = {}
        self.laden()

    def get_user(self, user_id: str) -> UserProfile:
        if user_id not in self.user_daten:
            self.user_daten[user_id] = UserProfile()
        return self.user_daten[user_id]

    def speichern(self):
        daten = {
            "users": {uid: asdict(prof) for uid, prof in self.user_daten.items()},
            "pets": {uid: asdict(prof) for uid, prof in self.pet_daten.items()}
        }
        with open(self.datei_pfad, "w", encoding="utf-8") as f:
            json.dump(daten, f, ensure_ascii=False, indent=4)

    def laden(self):
        if os.path.exists(self.datei_pfad):
            try:
                with open(self.datei_pfad, "r", encoding="utf-8") as f:
                    daten = json.load(f)
                    self.user_daten = {uid: UserProfile(**v) for uid, v in daten.get("users", {}).items()}
                    self.pet_daten = {uid: PetProfile(**v) for uid, v in daten.get("pets", {}).items()}
            except Exception as e:
                print(f"⚠️ Fehler beim Laden der Datenbank: {e}. Erstelle neue Daten.")

state = BotState()

# ─── BOT INITIALISIERUNG & KERN-LOGIK ──────────────────────
class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        # Automatischer Speicher-Task im Hintergrund (alle 5 Minuten)
        self.loop.create_task(self.automatischer_speicher_task())

    async def automatischer_speicher_task(self):
        while not self.is_closed():
            await asyncio.sleep(300)
            state.speichern()
            print("💾 Datenbank-Auto-Save erfolgreich ausgeführt.")

bot = MyBot()

# ─── INTERNE HELPER RE-DESIGNED ────────────────────────────
def erstelle_embed(titel: str, beschreibung: str, farbe: int) -> discord.Embed:
    return discord.Embed(title=titel, description=beschreibung, color=farbe, timestamp=datetime.now(timezone.utc))

def fehler_embed(text: str) -> discord.Embed:
    return erstelle_embed("❌ System-Fehler", text, BotFarben.FEHLER)

async def pruefe_und_gebe_level_rolle(member: discord.Member, neues_level: int) -> Optional[str]:
    if neues_level in LEVEL_ROLLEN_BELOHNUNGEN:
        rollen_name = LEVEL_ROLLEN_BELOHNUNGEN[neues_level]
        rolle = discord.utils.get(member.guild.roles, name=rollen_name)
        if rolle:
            try:
                await member.add_roles(rolle)
                return rollen_name
            except discord.Forbidden:
                return None
    return None

def xp_geben(user_id: str, menge: int = 5) -> bool:
    u = state.get_user(user_id)
    u.xp += menge
    u.gesamt_xp += menge
    benoetigt = u.level * 100
    level_up = False
    while u.xp >= benoetigt:
        u.xp -= benoetigt
        u.level += 1
        benoetigt = u.level * 100
        level_up = True
    return level_up

async def groq_anfrage(messages: list, modell: str = "llama-3.3-70b-versatile") -> str:
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": modell, "messages": messages, "max_tokens": 800}
    async with aiohttp.ClientSession() as session:
        async with session.post(GROQ_URL, headers=headers, json=payload, timeout=25) as resp:
            if resp.status != 200:
                raise Exception(f"Groq-Schnittstelle verweigert Dienst (Status: {resp.status})")
            data = await resp.json()
            return data["choices"][0]["message"]["content"]

# ─── EVENTS ────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"🤖 Maximale System-Architektur aktiv. Eingeloggt als: {bot.user}")
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="/hilfe"))

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: 
        return
        
    user_id = str(message.author.id)
    u = state.get_user(user_id)
    
    # Text-Validierung & Passives Wirtschaftssystem
    if len(message.content) > 3 and not message.content.startswith("/"):
        # Haustier-Hunger dynamisch erhöhen
        if user_id in state.pet_daten and random.random() < 0.15:
            p = state.pet_daten[user_id]
            p.hunger = min(100, p.hunger + random.randint(2, 6))

        # XP-Generierung
        if xp_geben(user_id, random.randint(2, 5)):
            msg_text = f"🎉 **GG** {message.author.mention}, du hast **Level {u.level}** erreicht!"
            erhaltene_rolle = await pruefe_und_gebe_level_rolle(message.author, u.level)
            if erhaltene_rolle:
                msg_text += f"\n🏅 Rolle freigeschaltet: **{erhaltene_rolle}**"
            await message.channel.send(embed=erstelle_embed("Level Aufstieg!", msg_text, BotFarben.ERFOLG))
        
        # Passive Münzen
        if random.random() < 0.25:
            u.muenzen += random.randint(2, 7)
            # ─── SLASHE-COMMANDS: HILFE & PROFIL ───────────────────────
@bot.tree.command(name="hilfe", description="Zeigt das hochentwickelte Navigationsmenü für alle Module.")
async def hilfe(interaction: discord.Interaction):
    embed = discord.Embed(title="⚙️ Zentrales Befehls-Terminal", color=BotFarben.INFO)
    embed.add_field(name="💰 Wirtschaft & Progression", value="`/rank` · `/leaderboard` · `/daily` · `/money` · `/coinflip` · `/shop` · `/buy` · `/inventory`", inline=False)
    embed.add_field(name="💞 Soziales & Interaktion", value="`/ship` · `/marry` · `/divorce` · `/marry-status`", inline=False)
    embed.add_field(name="🐾 Bio-Gefährten (Pets)", value="`/pet-adopt` · `/pet-status` · `/pet-feed` · `/pet-love`", inline=False)
    embed.add_field(name="🤖 KI & Werkzeuge", value="`/ki` · `/persönlichkeit` · `/todo` · `/passwort` · `/wurf`", inline=False)
    embed.set_footer(text="Profisystem v2.4 · Entwickelt mit discord.py")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="rank", description="Zeigt statistische Werte deines Serverprofils.")
async def rank(interaction: discord.Interaction, user: discord.Member = None):
    ziel = user if user else interaction.user
    u = state.get_user(str(ziel.id))
    benoetigt = u.level * 100
    
    beschreibung = f"Fortschritt: **{u.xp} / {benoetigt} XP**\nGesamt-Erfahrung: `{u.gesamt_xp} XP`"
    embed = erstelle_embed(f"⭐ Profil von {ziel.display_name}", beschreibung, BotFarben.INFO)
    embed.add_field(name="Aktuelles Level", value=f"**`Level {u.level}`**", inline=True)
    embed.add_field(name="Finanzen", value=f"**`🪙 {u.muenzen} Münzen`**", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="leaderboard", description="Listet die aktivsten User des Servers.")
async def leaderboard(interaction: discord.Interaction):
    sortiert = sorted(state.user_daten.items(), key=lambda x: x[1].gesamt_xp, reverse=True)[:5]
    if not sortiert:
        return await interaction.response.send_message(embed=fehler_embed("Noch keine Daten auf diesem Server vorhanden."))
        
    t = "\n".join(f"**#{i+1}** · <@{uid}> · Level `{d.level}` *({d.gesamt_xp} Gesamt-XP)*" for i, (uid, d) in enumerate(sortiert))
    await interaction.response.send_message(embed=erstelle_embed("🏆 Top 5 globale Server-Rangliste", t, BotFarben.SPIEL))

# ─── MARKTPLATZ-LOGIK ──────────────────────────────────────
@bot.tree.command(name="shop", description="Zeigt verfügbare Gegenstände im Server-Shop.")
async def shop(interaction: discord.Interaction):
    embed = erstelle_embed("🛒 Globaler Server-Marktplatz", "Nutze den Befehl `/buy`, um Gegenstände zu erwerben.", BotFarben.WIRTSCHAFT)
    for item_id, info in SHOP_ITEMS.items():
        embed.add_field(
            name=f"{info['name']} *(ID: `{item_id}`)*", 
            value=f"Preis: **{info['preis']} Münzen**\n*{info['beschreibung']}*", 
            inline=False
        )
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="buy", description="Kaufe ein Item aus dem Laden.")
@app_commands.choices(item_id=[
    app_commands.Choice(name="🍪 Kekse (25 Münzen)", value="kekse"),
    app_commands.Choice(name="🥩 Premium Steak (60 Münzen)", value="steak"),
    app_commands.Choice(name="⚡ XP-Booster (150 Münzen)", value="booster"),
    app_commands.Choice(name="🍀 Glücksbringer (300 Münzen)", value="gluecksbringer")
])
async def buy(interaction: discord.Interaction, item_id: app_commands.Choice[str]):
    u_id = str(interaction.user.id)
    u = state.get_user(u_id)
    item_daten = SHOP_ITEMS[item_id.value]
    
    if u.muenzen < item_daten["preis"]:
        return await interaction.response.send_message(embed=fehler_embed(f"Finanzierung abgelehnt. Du benötigst **{item_daten['preis']} Münzen** (Aktuell: {u.muenzen})."), ephemeral=True)
        
    u.muenzen -= item_daten["preis"]
    u.inventar[item_id.value] = u.inventar.get(item_id.value, 0) + 1
    
    # Sonderlogik für Direktverzehr (z.B. XP Booster)
    if item_id.value == "booster":
        u.inventar["booster"] -= 1
        xp_geben(u_id, 200)
        state.speichern()
        return await interaction.response.send_message(embed=erstelle_embed("⚡ Spezial-Item aktiviert", f"Du hast **{item_daten['name']}** gekauft. Die 200 XP wurden direkt auf dein Konto gutgeschrieben!", BotFarben.ERFOLG))

    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🛍️ Transaktion erfolgreich", f"Du hast **{item_daten['name']}** für **{item_daten['preis']} Münzen** erworben.\nDas Item befindet sich in deinem `/inventory`.", BotFarben.ERFOLG))

@bot.tree.command(name="inventory", description="Zeigt deine gesammelten Gegenstände.")
async def inventory(interaction: discord.Interaction):
    u = state.get_user(str(interaction.user.id))
    aktiv = [f"{SHOP_ITEMS[iid]['name']}: **{anzahl}x**" for iid, anzahl in u.inventar.items() if anzahl > 0]
    
    beschreibung = "\n".join(aktiv) if aktiv else "*Dein Rucksack ist komplett leer.*"
    await interaction.response.send_message(embed=erstelle_embed("🎒 Dein persönliches Inventar", beschreibung, BotFarben.TOOL))

# ─── HAUSTIER (PET) MANAGMENT ──────────────────────────────
@bot.tree.command(name="pet-adopt", description="Adoptiert einen biologischen Gefährten.")
@app_commands.choices(typ=[app_commands.Choice(name="🐱 Katze", value="Katze"), app_commands.Choice(name="🐶 Hund", value="Hund"), app_commands.Choice(name="🐉 Drache", value="Drache")])
async def pet_adopt(interaction: discord.Interaction, typ: app_commands.Choice[str], name: str):
    u_id = str(interaction.user.id)
    if u_id in state.pet_daten:
        return await interaction.response.send_message(embed=fehler_embed("Du besitzt bereits ein Haustier. Du kannst kein weiteres adoptieren."), ephemeral=True)
        
    if len(name) > 16:
        return await interaction.response.send_message(embed=fehler_embed("Der Tiername darf maximal 16 Zeichen lang sein."), ephemeral=True)

    state.pet_daten[u_id] = PetProfile(name=name, typ=typ.value)
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🐾 Adoption abgeschlossen", f"Herzlichen Glückwunsch! Du hast deinen Gefährten **{name}** ({typ.value}) erfolgreich registriert!", BotFarben.ERFOLG))

@bot.tree.command(name="pet-status", description="Prüft die Vitalwerte deines Haustiers.")
async def pet_status(interaction: discord.Interaction):
    u_id = str(interaction.user.id)
    if u_id not in state.pet_daten:
        return await interaction.response.send_message(embed=fehler_embed("Es konnte kein registriertes Haustier für dich gefunden werden."), ephemeral=True)
        
    p = state.pet_daten[u_id]
    status_balken = "🟢 Gesund" if p.hunger < 50 else ("🟡 Hungrig" if p.hunger < 85 else "🔴 Kritisch / Verweigert Arbeit")
    
    embed = erstelle_embed(f"🐾 Gefährten-Status: {p.name}", f"Spezies: **{p.typ}**\nStatus: **{status_balken}**", BotFarben.INFO)
    embed.add_field(name="Tier-Level", value=f"`Lvl {p.level}`", inline=True)
    embed.add_field(name="Hunger-Index", value=f"`{p.hunger} / 100`", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="pet-feed", description="Füttere dein Haustier mit Items aus deinem Inventar.")
@app_commands.choices(futter_typ=[app_commands.Choice(name="🍪 Kekse benutzen", value="kekse"), app_commands.Choice(name="🥩 Premium Steak benutzen", value="steak")])
async def pet_feed(interaction: discord.Interaction, futter_typ: app_commands.Choice[str]):
    u_id = str(interaction.user.id)
    if u_id not in state.pet_daten:
        return await interaction.response.send_message(embed=fehler_embed("Du musst erst ein Tier adoptieren."), ephemeral=True)
        
    u = state.get_user(u_id)
    if u.inventar.get(futter_typ.value, 0) <= 0:
        return await interaction.response.send_message(embed=fehler_embed(f"Du besitzt kein(e) {futter_typ.name} im Inventar. Besuche den `/shop`."), ephemeral=True)

    u.inventar[futter_typ.value] -= 1
    p = state.pet_daten[u_id]
    
    wert = 30 if futter_typ.value == "kekse" else 80
    p.hunger = max(0, p.hunger - wert)
    p.level += 1
    state.speichern()
    
    await interaction.response.send_message(embed=erstelle_embed("🍖 Fütterung durchgeführt", f"Du hast **{p.name}** gefüttert.\nHunger fällt auf **{p.hunger}/100**. Das Tier steigt auf **Level {p.level}**!", BotFarben.ERFOLG))

@bot.tree.command(name="pet-love", description="Kuschel mit deinem Tier für Zuneigungs-XP.")
async def pet_love(interaction: discord.Interaction):
    u_id = str(interaction.user.id)
    if u_id not in state.pet_daten:
        return await interaction.response.send_message(embed=fehler_embed("Du besitzt kein Haustier."), ephemeral=True)
        
    p = state.pet_daten[u_id]
    if p.hunger >= 90:
        return await interaction.response.send_message(embed=fehler_embed(f"**{p.name}** ist zu hungrig ({p.hunger}/100) und lässt dich nicht an sich heran. Füttere es!"), ephemeral=True)
        
    jetzt = datetime.now(timezone.utc)
    if p.letztes_streicheln:
        last_time = datetime.fromisoformat(p.letztes_streicheln)
        if jetzt < last_time + timedelta(hours=1):
            restzeit = (last_time + timedelta(hours=1)) - jetzt
            return await interaction.response.send_message(embed=fehler_embed(f"Dein Tier schläft noch. Bitte warte noch `{int(restzeit.seconds // 60)} Minuten`."), ephemeral=True)
            
    p.letztes_streicheln = jetzt.isoformat()
    xp_geben(u_id, 35)
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("❤️ Zuneigung erwidert", f"Du hast **{p.name}** intensiv gekuschelt. Das stärkt eure Bindung! *(+35 User-XP)*", BotFarben.ERFOLG))
    # ─── WIRTSCHAFTS-MINIGAMES ─────────────────────────────────
@bot.tree.command(name="money", description="Gibt Auskunft über dein Erspartes.")
async def money(interaction: discord.Interaction, user: discord.Member = None):
    ziel = user if user else interaction.user
    u = state.get_user(str(ziel.id))
    await interaction.response.send_message(embed=erstelle_embed("🪙 Kontostand", f"Der User **{ziel.display_name}** besitzt aktuell **{u.muenzen} Münzen**.", BotFarben.WIRTSCHAFT))

@bot.tree.command(name="daily", description="Sichert dir tägliche Ressourcen.")
async def daily(interaction: discord.Interaction):
    u_id = str(interaction.user.id)
    u = state.get_user(u_id)
    jetzt = datetime.now(timezone.utc)
    
    if u.letztes_daily:
        last_daily = datetime.fromisoformat(u.letztes_daily)
        if jetzt < last_daily + timedelta(days=1):
            verbleibend = (last_daily + timedelta(days=1)) - jetzt
            stunden = int(verbleibend.seconds // 3600)
            minuten = int((verbleibend.seconds % 3600) // 60)
            return await interaction.response.send_message(embed=fehler_embed(f"Du hast deine Belohnung bereits beansprucht. Warte noch `{stunden} Std. {minuten} Min.`"), ephemeral=True)
            
    u.letztes_daily = jetzt.isoformat()
    xp_geben(u_id, 150)
    u.muenzen += 50
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🎁 Tagesbonus abgeholt", "Du hast deine tägliche Versorgung erhalten:\n**+150 XP**\n**+50 Münzen**", BotFarben.ERFOLG))

@bot.tree.command(name="coinflip", description="Riskiere Münzen beim Münzwurf.")
@app_commands.choices(seite=[app_commands.Choice(name="Kopf", value="Kopf"), app_commands.Choice(name="Zahl", value="Zahl")])
async def coinflip(interaction: discord.Interaction, einsatz: int, seite: app_commands.Choice[str]):
    u_id = str(interaction.user.id)
    u = state.get_user(u_id)
    
    if einsatz <= 0:
        return await interaction.response.send_message(embed=fehler_embed("Der Einsatz muss mindestens 1 Münze betragen."), ephemeral=True)
    if u.muenzen < einsatz:
        return await interaction.response.send_message(embed=fehler_embed("Unzureichende Liquidität auf deinem Konto für diesen Einsatz."), ephemeral=True)
        
    # Passiver Bonus durch Glücksbringer-Item aus dem Shop
    chance_gewinn = 0.50
    if u.inventar.get("gluecksbringer", 0) > 0:
        chance_gewinn = 0.55  # 5% höhere Gewinnchance

    ergebnis = seite.value if random.random() < chance_gewinn else ("Zahl" if seite.value == "Kopf" else "Kopf")
    
    if ergebnis == seite.value:
        u.muenzen += einsatz
        state.speichern()
        await interaction.response.send_message(embed=erstelle_embed("🎉 Gewinn!", f"Die Münze zeigt **{ergebnis}**. Du gewinnst **{einsatz} Münzen**!", BotFarben.ERFOLG))
    else:
        u.muenzen -= einsatz
        state.speichern()
        await interaction.response.send_message(embed=erstelle_embed("😢 Verlust!", f"Die Münze fiel auf **{ergebnis}**. Du verlierst **{einsatz} Münzen**.", BotFarben.FEHLER))

# ─── NEURONALE KI SCHNITTTSTELLE (GROQ) ─────────────────────
@bot.tree.command(name="ki", description="Sendet eine Anfrage an das neuronale KI-Netz.")
async def ki(interaction: discord.Interaction, frage: str):
    await interaction.response.defer()
    u_id = str(interaction.user.id)
    u = state.get_user(u_id)
    
    try:
        if u_id not in state.chat_verlaeufe:
            state.chat_verlaeufe[u_id] = []
            
        state.chat_verlaeufe[u_id].append({"role": "user", "content": frage})
        
        # System-Instruktionen zusammenbauen
        sys_prompt = PERSONAS.get(u.ki_persona, "standard")
        if u.todo:
            sys_prompt += f" Merkliste/ToDos des Users: {'; '.join(u.todo)}."
            
        # Begrenzung auf die letzten 8 Nachrichten für Kontext-Erhalt
        kontext = [{"role": "system", "content": sys_prompt}] + state.chat_verlaeufe[u_id][-8:]
        
        antwort = await groq_anfrage(kontext)
        state.chat_verlaeufe[u_id].append({"role": "assistant", "content": antwort})
        
        await interaction.followup.send(embed=erstelle_embed("🤖 KI-Rückmeldung", antwort[:2000], BotFarben.KI))
    except Exception as e:
        await interaction.followup.send(embed=fehler_embed(f"Fehler bei der KI-Verarbeitung: {str(e)}"))

@bot.tree.command(name="persönlichkeit", description="Ändert das Profilverhalten der KI.")
@app_commands.choices(wahl=[
    app_commands.Choice(name="Standard", value="standard"), 
    app_commands.Choice(name="Pirat 🏴‍☠️", value="pirat"), 
    app_commands.Choice(name="Anwalt ⚖️", value="anwalt"),
    app_commands.Choice(name="Lehrer 🎓", value="lehrer")
])
async def persoenlichkeit_cmd(interaction: discord.Interaction, wahl: app_commands.Choice[str]):
    u = state.get_user(str(interaction.user.id))
    u.ki_persona = wahl.value
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🎭 Persona konfiguriert", f"Das KI-Verhaltensprofil wurde auf **{wahl.name}** umgestellt.", BotFarben.TOOL))

# ─── INTERAKTION & SOCIALS ─────────────────────────────────
@bot.tree.command(name="ship", description="Berechnet die Kompatibilität basierend auf Serverrollen.")
async def ship(interaction: discord.Interaction, user1: discord.Member, user2: discord.Member = None):
    u1, u2 = user1, (user2 if user2 else interaction.user)
    
    if u1 == u2:
        return await interaction.response.send_message(embed=fehler_embed("Selbst-Shippen ist mathematisch ineffizient."), ephemeral=True)

    # Rollenbasierte Validierung
    u1_rollen = [r.name for r in u1.roles]
    u2_rollen = [r.name for r in u2.roles]
    
    g1 = "divers" if "Divers" in u1_rollen else ("männlich" if "Männlich" in u1_rollen else ("weiblich" if "Weiblich" in u1_rollen else None))
    g2 = "divers" if "Divers" in u2_rollen else ("männlich" if "Männlich" in u2_rollen else ("weiblich" if "Weiblich" in u2_rollen else None))

    if not g1 or not g2:
        return await interaction.response.send_message(embed=fehler_embed("Rollen-Validierung fehlgeschlagen. Einer der User hat keine Geschlechtsrolle ('Männlich', 'Weiblich', 'Divers')."), ephemeral=True)

    if not (g1 == "divers" or g2 == "divers" or g1 != g2):
        return await interaction.response.send_message(embed=fehler_embed("Kombinationsregel-Konflikt: Paarung blockiert nach Server-Vorgabe."), ephemeral=True)

    random.seed((u1.id + u2.id))
    p = random.randint(0, 100)
    random.seed()
    
    balken = "❤️" * (p // 10) + "🖤" * (10 - (p // 10))
    await interaction.response.send_message(embed=erstelle_embed("💘 Partnerprüfung abgeschlossen", f"**{u1.display_name}** ({g1}) & **{u2.display_name}** ({g2})\n\n{balken}\n\nKompatibilität: **{p}%**", BotFarben.TOOL))

@bot.tree.command(name="marry", description="Sendet einen formellen Hochzeitsantrag.")
async def marry(interaction: discord.Interaction, partner: discord.Member):
    u_id, p_id = str(interaction.user.id), str(partner.id)
    u = state.get_user(u_id)
    
    if u.partner_id or partner.bot or partner == interaction.user:
        return await interaction.response.send_message(embed=fehler_embed("Heiratsantrag ungültig (Du bist bereits verheiratet, der User ist ein Bot oder du selbst)."), ephemeral=True)

    await interaction.response.send_message(f"💍 {partner.mention}, nimm den Antrag von {interaction.user.mention} an, indem du exakt innerhalb 60 Sekunden **'ja ich will'** in den Chat schreibst!")
    
    try:
        def check(m): return m.author.id == partner.id and m.content.lower() == "ja ich will" and m.channel.id == interaction.channel_id
        await bot.wait_for("message", check=check, timeout=60.0)
        
        u.partner_id = p_id
        state.get_user(p_id).partner_id = u_id
        state.speichern()
        await interaction.channel.send(embed=erstelle_embed("🎉 Bund der Ehe geschlossen!", f"{interaction.user.mention} und {partner.mention} sind nun offiziell verheiratet!", BotFarben.ERFOLG))
    except asyncio.TimeoutError:
        await interaction.channel.send(embed=erstelle_embed("💔 Antrag abgelaufen", "Die Frist verstrich ohne rechtsgültige Zustimmung.", BotFarben.FEHLER))

@bot.tree.command(name="divorce", description="Löst eine bestehende Ehe auf.")
async def divorce(interaction: discord.Interaction):
    u_id = str(interaction.user.id)
    u = state.get_user(u_id)
    if not u.partner_id:
        return await interaction.response.send_message(embed=fehler_embed("Du bist aktuell mit niemandem verheiratet."), ephemeral=True)
        
    p_id = u.partner_id
    u.partner_id = None
    state.get_user(p_id).partner_id = None
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("💔 Scheidung vollzogen", f"Die Bindung zu <@{p_id}> wurde mit sofortiger Wirkung aufgehoben.", BotFarben.FEHLER))

@bot.tree.command(name="marry-status", description="Überprüft Beziehungsstrukturen.")
async def marry_status(interaction: discord.Interaction, user: discord.Member = None):
    z = user if user else interaction.user
    u = state.get_user(str(z.id))
    text = f"💍 Verheiratet mit: <@{u.partner_id}>" if u.partner_id else "🕊️ Beziehungsstatus: Single"
    await interaction.response.send_message(embed=erstelle_embed(f"Herz-Status: {z.display_name}", text, BotFarben.INFO))

# ─── UTILITIES & ALLGEMEINES ───────────────────────────────
@bot.tree.command(name="todo", description="Einträge der Organisationsliste anpassen.")
@app_commands.choices(mode=[app_commands.Choice(name="Anzeigen/Hinzufügen", value="show"), app_commands.Choice(name="Leeren", value="clear")])
async def todo(interaction: discord.Interaction, mode: app_commands.Choice[str], text: str = None):
    u = state.get_user(str(interaction.user.id))
    if mode.value == "show":
        if text:
            if len(text) > 60: return await interaction.response.send_message(embed=fehler_embed("Text zu lang (Max. 60 Zeichen)."), ephemeral=True)
            u.todo.append(text)
            state.speichern()
            await interaction.response.send_message(embed=erstelle_embed("📝 Notiz erfasst", f"Hinzugefügt: `{text}`", BotFarben.ERFOLG))
        else:
            liste = "\n".join(f"• {x}" for x in u.todo) if u.todo else "*Keine aktiven Einträge.*"
            await interaction.response.send_message(embed=erstelle_embed("📋 Deine To-Do Liste", liste, BotFarben.INFO))
    else:
        u.todo = []
        state.speichern()
        await interaction.response.send_message(embed=erstelle_embed("🗑️ Bereinigt", "Deine Liste wurde vollständig geleert.", BotFarben.FEHLER))

@bot.tree.command(name="passwort", description="Gibt ein zufällig generiertes, sicheres Passwort aus.")
async def passwort(interaction: discord.Interaction, laenge: int = 16):
    laenge = min(max(laenge, 10), 32)
    zeichen = string.ascii_letters + string.digits + "!@#$%^&*"
    pw = "".join(random.choice(zeichen) for _ in range(laenge))
    await interaction.response.send_message(f"🔐 **Dein generiertes Passwort:**\n||`{pw}`||\n*Nur für dich sichtbar. Gib dieses Passwort niemals weiter.*", ephemeral=True)

@bot.tree.command(name="wurf", description="Simuliert ein mathematisches Würfelexperiment.")
async def wurf(interaction: discord.Interaction, seiten: int = 6):
    if seiten < 2: return await interaction.response.send_message(embed=fehler_embed("Ein Würfel benötigt mindestens 2 Seiten."), ephemeral=True)
    await interaction.response.send_message(embed=erstelle_embed("🎲 Würfel gefallen", f"Ergebnis auf einem {seiten}-seitigen Würfel: **{random.randint(1, seiten)}**", BotFarben.SPIEL))

@bot.tree.command(name="avatar", description="Ruft die hochauflösende Grafikdatei eines Profils ab.")
async def avatar(interaction: discord.Interaction, user: discord.Member = None):
    z = user if user else interaction.user
    embed = discord.Embed(title=f"🖼️ Avatar von {z.display_name}", color=BotFarben.INFO)
    embed.set_image(url=z.display_avatar.url)
    await interaction.response.send_message(embed=embed)

# ─── ADMINISTRATIVER BEREICH ───────────────────────────────
@bot.tree.command(name="xp-geben", description="Fügt administrative XP hinzu.")
@app_commands.checks.has_permissions(administrator=True)
async def admin_xp(interaction: discord.Interaction, user: discord.Member, menge: int):
    if menge <= 0: return await interaction.response.send_message(embed=fehler_embed("Menge muss positiv sein."), ephemeral=True)
    xp_geben(str(user.id), menge)
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("⚙️ System-Eingriff", f"{user.mention} wurden erfolgreich **{menge} XP** gutgeschrieben.", BotFarben.ERFOLG))

@admin_xp.error
async def admin_xp_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(embed=fehler_embed("Du besitzt nicht die erforderlichen Rechte (`Administrator`), um diesen Befehl zu nutzen."), ephemeral=True)

# ─── BOT START ─────────────────────────────────────────────
bot.run(DISCORD_TOKEN)

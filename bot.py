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

# ─── CONFIGURATION ─────────────────────────────────────────
LEVEL_ROLLEN_BELOHNUNGEN = {
    5: "Bronze-Mitglied",
    10: "Silber-Mitglied",
    20: "Gold-Mitglied"
}

SHOP_ITEMS = {
    "kekse": {"name": "🍪 Kekse", "preis": 25, "beschreibung": "Futter für dein Haustier (-30 Hunger)"},
    "steak": {"name": "🥩 Premium Steak", "preis": 60, "beschreibung": "Perfekt für Haustiere (-80 Hunger)"},
    "milch": {"name": "🍼 Milchflasche", "preis": 40, "beschreibung": "Nahrung für dein Kind (-35 Hunger)"}
}

ERZ_PREISE = {
    "kohle": {"name": "⚫ Kohle", "wert": 15},
    "eisen": {"name": "🪙 Eisenerz", "wert": 35},
    "gold": {"name": "🟡 Golderz", "wert": 75},
    "diamant": {"name": "💎 Diamant", "wert": 200}
}

PERSONAS = {
    "standard": "Du bist ein hilfreicher Assistent."
}

class BotFarben:
    KI = 0x5865F2
    ERFOLG = 0x57F287
    FEHLER = 0xED4245
    SPIEL = 0xFEE75C
    TOOL = 0xEB459E
    INFO = 0x5DADE2
    WIRTSCHAFT = 0xE67E22

# ─── DATA MODELS ───────────────────────────────────────────
@dataclass
class ChildProfile:
    name: str
    hunger: int = 30
    level: int = 1
    letztes_spielen: Optional[str] = None

@dataclass
class UserProfile:
    xp: int = 0
    level: int = 1
    gesamt_xp: int = 0
    muenzen: int = 100
    inventar: Dict[str, int] = field(default_factory=dict)
    todo: List[str] = field(default_factory=list)
    ki_persona: str = "standard"
    partner_id: Optional[str] = None
    hochzeits_datum: Optional[str] = None  # Speichert das Hochzeitsdatum als ISO-String
    kinder: Dict[str, dict] = field(default_factory=dict)
    letztes_daily: Optional[str] = None
    letzte_arbeit: Optional[str] = None
    letzte_mine: Optional[str] = None

@dataclass
class PetProfile:
    name: str
    typ: str
    level: int = 1
    hunger: int = 20
    letztes_streicheln: Optional[str] = None

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
                print(f"⚠️ Fehler beim Laden: {e}")

state = BotState()

class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

bot = MyBot()

def erstelle_embed(titel: str, beschreibung: str, farbe: int) -> discord.Embed:
    return discord.Embed(title=titel, description=beschreibung, color=farbe, timestamp=datetime.now(timezone.utc))

def fehler_embed(text: str) -> discord.Embed:
    return erstelle_embed("❌ Fehler", text, BotFarben.FEHLER)

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

@bot.event
async def on_ready():
    print(f"🤖 Eingeloggt als: {bot.user}")
    @bot.tree.command(name="hilfe", description="Zeigt alle Befehle.")
async def hilfe(interaction: discord.Interaction):
    embed = discord.Embed(title="⚙️ Befehlsübersicht", color=BotFarben.INFO)
    embed.add_field(name="💰 Wirtschaft", value="`/money` · `/daily` · `/work` · `/mine` · `/sell` · `/shop` · `/buy` · `/inventory`", inline=False)
    embed.add_field(name="💞 Familie", value="`/ship` · `/marry` · `/divorce` · `/marry-status` · `/love` · `/family` · `/baby-feed` · `/baby-play`", inline=False)
    embed.add_field(name="🎮 Fun-Games", value="`/coinflip` · `/schere-stein` · `/zahlen-raten`", inline=False)
    await interaction.response.send_message(embed=embed)

# ─── WIRTSCHAFTS-BEFEHLE ───────────────────────────────────
@bot.tree.command(name="money", description="Prüfe deinen Kontostand.")
async def money(interaction: discord.Interaction):
    u = state.get_user(str(interaction.user.id))
    await interaction.response.send_message(embed=erstelle_embed("🪙 Kontostand", f"Du besitzt **{u.muenzen} Münzen**.", BotFarben.WIRTSCHAFT))

@bot.tree.command(name="daily", description="Sammle tägliche Münzen.")
async def daily(interaction: discord.Interaction):
    u_id = str(interaction.user.id); u = state.get_user(u_id); jetzt = datetime.now(timezone.utc)
    if u.letztes_daily and jetzt < datetime.fromisoformat(u.letztes_daily) + timedelta(days=1):
        return await interaction.response.send_message(embed=fehler_embed("Morgen wieder verfügbar."), ephemeral=True)
    u.letztes_daily = jetzt.isoformat(); u.muenzen += 50; state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🎁 Daily", "+50 Münzen erhalten!", BotFarben.ERFOLG))

@bot.tree.command(name="work", description="Gehe arbeiten.")
@app_commands.choices(beruf=[app_commands.Choice(name="👷 Bauarbeiter", value="bau"), app_commands.Choice(name="💻 Entwickler", value="dev")])
async def work(interaction: discord.Interaction, beruf: app_commands.Choice[str]):
    u_id = str(interaction.user.id); u = state.get_user(u_id); jetzt = datetime.now(timezone.utc)
    if u.letzte_arbeit and jetzt < datetime.fromisoformat(u.letzte_arbeit) + timedelta(hours=1):
        return await interaction.response.send_message(embed=fehler_embed("Warte 1 Stunde."), ephemeral=True)
    lohn = random.randint(40, 60) if beruf.value == "bau" else random.randint(20, 120)
    u.muenzen += lohn; u.letzte_arbeit = jetzt.isoformat(); state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("💼 Arbeit", f"Verdiener Lohn: **{lohn} Münzen**.", BotFarben.WIRTSCHAFT))

@bot.tree.command(name="mine", description="Gehe in die Mine.")
async def mine(interaction: discord.Interaction):
    u_id = str(interaction.user.id); u = state.get_user(u_id); jetzt = datetime.now(timezone.utc)
    if u.letzte_mine and jetzt < datetime.fromisoformat(u.letzte_mine) + timedelta(minutes=45):
        return await interaction.response.send_message(embed=fehler_embed("Warte 45 Minuten."), ephemeral=True)
    erz = "kohle" if random.random() < 0.60 else "eisen"
    u.inventar[erz] = u.inventar.get(erz, 0) + 1; u.letzte_mine = jetzt.isoformat(); state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("⛏️ Mine", f"Gefunden: {ERZ_PREISE[erz]['name']}", BotFarben.SPIEL))

@bot.tree.command(name="sell", description="Verkaufe Rohstoffe.")
async def sell(interaction: discord.Interaction, erz: str, anzahl: int = 1):
    u = state.get_user(str(interaction.user.id))
    if erz not in ERZ_PREISE or u.inventar.get(erz, 0) < anzahl: return await interaction.response.send_message(embed=fehler_embed("Nicht genug Rohstoffe."), ephemeral=True)
    erloes = ERZ_PREISE[erz]["wert"] * anzahl; u.inventar[erz] -= anzahl; u.muenzen += erloes; state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("⚖️ Verkauf", f"Erhaltener Wert: **{erloes} Münzen**.", BotFarben.WIRTSCHAFT))

@bot.tree.command(name="shop", description="Shop anzeigen.")
async def shop(interaction: discord.Interaction):
    embed = erstelle_embed("🛒 Shop", "Kauf via `/buy`", BotFarben.WIRTSCHAFT)
    for k, i in SHOP_ITEMS.items(): embed.add_field(name=i["name"], value=f"{i['preis']} Münzen", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="buy", description="Item kaufen.")
async def buy(interaction: discord.Interaction, item: str):
    u = state.get_user(str(interaction.user.id))
    if item not in SHOP_ITEMS or u.muenzen < SHOP_ITEMS[item]["preis"]: return await interaction.response.send_message(embed=fehler_embed("Kauf fehlgeschlagen."), ephemeral=True)
    u.muenzen -= SHOP_ITEMS[item]["preis"]; u.inventar[item] = u.inventar.get(item, 0) + 1; state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🛒 Gekauft", "Item erfolgreich erworben.", BotFarben.ERFOLG))

@bot.tree.command(name="inventory", description="Zeige dein Inventar.")
async def inventory(interaction: discord.Interaction):
    u = state.get_user(str(interaction.user.id))
    inv = [f"{k}: {v}x" for k, v in u.inventar.items() if v > 0]
    await interaction.response.send_message(embed=erstelle_embed("🎒 Inventar", "\n".join(inv) if inv else "Leer", BotFarben.TOOL))
    # ─── NEURONALE KI SCHNITTTSTELLE (GROQ) ─────────────────────
@bot.tree.command(name="ki", description="Stelle der künstlichen Intelligenz eine Frage.")
async def ki(interaction: discord.Interaction, frage: str):
    await interaction.response.defer()
    u_id = str(interaction.user.id)
    u = state.get_user(u_id)
    
    try:
        if u_id not in state.chat_verlaeufe:
            state.chat_verlaeufe[u_id] = []
            
        state.chat_verlaeufe[u_id].append({"role": "user", "content": frage})
        
        # System-Persona laden
        sys_prompt = PERSONAS.get(u.ki_persona, "standard")
        if u.todo:
            sys_prompt += f" Die aktuellen To-Dos des Users lauten: {'; '.join(u.todo)}."
            
        # Maximal die letzten 6 Nachrichten für den Kontext nutzen
        kontext = [{"role": "system", "content": sys_prompt}] + state.chat_verlaeufe[u_id][-6:]
        
        antwort = await groq_anfrage(kontext)
        state.chat_verlaeufe[u_id].append({"role": "assistant", "content": antwort})
        
        await interaction.followup.send(embed=erstelle_embed("🤖 KI-Assistent", antwort[:2000], BotFarben.KI))
    except Exception as e:
        await interaction.followup.send(embed=fehler_embed(f"Fehler bei der KI-Anfrage: {str(e)}"))

@bot.tree.command(name="persönlichkeit", description="Ändere das Verhalten und die Tonalität der KI.")
@app_commands.choices(wahl=[
    app_commands.Choice(name="Standard (Freundlich/Neutral)", value="standard")
])
async def persoenlichkeit_cmd(interaction: discord.Interaction, wahl: app_commands.Choice[str]):
    state.get_user(str(interaction.user.id)).ki_persona = wahl.value
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🎭 KI-Modus aktualisiert", f"Die KI antwortet dir ab jetzt im Modus: **{wahl.name}**.", BotFarben.TOOL))

# ─── USER-PROFILE & RANGLISTEN ─────────────────────────────
@bot.tree.command(name="rank", description="Zeige dein aktuelles Level und deine gesammelten Münzen.")
async def rank(interaction: discord.Interaction, user: discord.Member = None):
    ziel = user if user else interaction.user
    u = state.get_user(str(ziel.id))
    
    beschreibung = (
        f"⭐ **Level:** {u.level}\n"
        f"✨ **Erfahrung:** `{u.xp} / {u.level * 100} XP`\n"
        f"🪙 **Vermögen:** `{u.muenzen} Münzen`"
    )
    await interaction.response.send_message(embed=erstelle_embed(f"Statistiken von {ziel.display_name}", beschreibung, BotFarben.INFO))

@bot.tree.command(name="leaderboard", description="Zeigt die Top 5 Mitglieder mit dem höchsten Level.")
async def leaderboard(interaction: discord.Interaction):
    if not state.user_daten:
        return await interaction.response.send_message(embed=erstelle_embed("🏆 Server-Rangliste", "Noch keine Daten vorhanden.", BotFarben.SPIEL))
        
    sortiert = sorted(state.user_daten.items(), key=lambda x: x[1].gesamt_xp, reverse=True)[:5]
    
    rangliste = []
    for i, (uid, daten) in enumerate(sortiert):
        rangliste.append(f"**#{i+1}** · <@{uid}> · Level **{daten.level}** ({daten.gesamt_xp} Gesamt-XP)")
        
    await interaction.response.send_message(embed=erstelle_embed("🏆 Top 5 Server-Rangliste", "\n".join(rangliste), BotFarben.SPIEL))

# ─── ORGANISATION & UTILITIES ──────────────────────────────
@bot.tree.command(name="todo", description="Verwalte deine persönliche Aufgabenliste.")
@app_commands.choices(modus=[
    app_commands.Choice(name="Anzeigen & Hinzufügen", value="add"),
    app_commands.Choice(name="Liste komplett leeren", value="clear")
])
async def todo(interaction: discord.Interaction, modus: app_commands.Choice[str], aufgabe: str = None):
    u = state.get_user(str(interaction.user.id))
    
    if modus.value == "add":
        if aufgabe:
            u.todo.append(aufgabe)
            state.speichern()
            
        liste = "\n".join(f"• {x}" for x in u.todo) if u.todo else "*Deine Liste ist aktuell leer.*"
        await interaction.response.send_message(embed=erstelle_embed("📋 Deine To-Do-Liste", list, BotFarben.INFO))
    else:
        u.todo.clear()
        state.speichern()
        await interaction.response.send_message(embed=erstelle_embed("🗑️ To-Do gelöscht", "Deine Aufgabenliste wurde vollständig geleert.", BotFarben.FEHLER))

@bot.tree.command(name="passwort", description="Generiert ein sicheres Zufallspasswort für dich.")
async def passwort(interaction: discord.Interaction, laenge: int = 16):
    # Begrenzung der Länge auf sichere Werte zwischen 10 und 32 Zeichen
    sichere_laenge = min(max(laenge, 10), 32)
    zeichen = string.ascii_letters + string.digits + "!@%&*"
    pw = "".join(random.choice(zeichen) for _ in range(sichere_laenge))
    
    await interaction.response.send_message(f"🔐 **Dein generiertes Passwort:** ||`{pw}`||\n*(Nur du kannst diesen Text sehen, klicke darauf um ihn aufzudecken)*", ephemeral=True)

@bot.tree.command(name="wurf", description="Wirf einen Würfel mit einer beliebigen Anzahl an Seiten.")
async def wurf(interaction: discord.Interaction, seiten: int = 6):
    sicher_seiten = max(2, seiten)
    ergebnis = random.randint(1, sicher_seiten)
    await interaction.response.send_message(embed=erstelle_embed("🎲 Würfelbecher", f"Du hast einen `{sicher_seiten}-seitigen` Würfel geworfen.\n\nErgebnis: **{ergebnis}**", BotFarben.SPIEL))

@bot.tree.command(name="avatar", description="Ruft das Profilbild eines Nutzers in hoher Auflösung ab.")
async def avatar(interaction: discord.Interaction, user: discord.Member = None):
    ziel = user if user else interaction.user
    embed = discord.Embed(title=f"🖼️ Avatar von {ziel.display_name}", color=BotFarben.INFO)
    embed.set_image(url=ziel.display_avatar.url)
    await interaction.response.send_message(embed=embed)

# ─── ADMINISTRATOR COMMANDS ────────────────────────────────
@bot.tree.command(name="xp-geben", description="Vergibt administrative Erfahrungspunkte an einen User.")
@app_commands.checks.has_permissions(administrator=True)
async def admin_xp(interaction: discord.Interaction, user: discord.Member, menge: int):
    if menge <= 0:
        return await interaction.response.send_message(embed=fehler_embed("Die Anzahl der XP muss positiv sein."), ephemeral=True)
        
    xp_geben(str(user.id), menge)
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("⚙️ Admin-Eingriff", f"{user.mention} wurden erfolgreich **{menge} XP** gutgeschrieben.", BotFarben.ERFOLG))
    # ─── SOZIALES, EHE & UPDATED FAMILIENSYSTEM ────────────────
@bot.tree.command(name="ship", description="Testet eure Liebe.")
async def ship(interaction: discord.Interaction, user: discord.Member):
    p = random.randint(0, 100)
    await interaction.response.send_message(embed=erstelle_embed("💘 Ship-O-Meter", f"{interaction.user.mention} + {user.mention} = **{p}%**", BotFarben.TOOL))

@bot.tree.command(name="marry", description="Heirate ein anderes Mitglied.")
async def marry(interaction: discord.Interaction, partner: discord.Member):
    u_id, p_id = str(interaction.user.id), str(partner.id); u = state.get_user(u_id)
    if u.partner_id or partner.bot or partner == interaction.user: return await interaction.response.send_message(embed=fehler_embed("Nicht möglich."), ephemeral=True)
    
    await interaction.response.send_message(f"💍 {partner.mention}, nimmst du den Antrag an? Schreibe **'ja ich will'**!")
    try:
        def check(m): return m.author.id == partner.id and m.content.lower() == "ja ich will" and m.channel.id == interaction.channel_id
        await bot.wait_for("message", check=check, timeout=60.0)
        jetzt = datetime.now(timezone.utc).isoformat()
        u.partner_id = p_id; u.hochzeits_datum = jetzt
        state.get_user(p_id).partner_id = u_id; state.get_user(p_id).hochzeits_datum = jetzt
        state.speichern()
        await interaction.channel.send(embed=erstelle_embed("🎉 Ehe geschlossen!", f"Ihr seid nun offiziell verheiratet!", BotFarben.ERFOLG))
    except asyncio.TimeoutError:
        await interaction.channel.send("💔 Keine Antwort erhalten.")

@bot.tree.command(name="divorce", description="Löse die Ehe.")
async def divorce(interaction: discord.Interaction):
    u_id = str(interaction.user.id); u = state.get_user(u_id)
    if not u.partner_id: return await interaction.response.send_message(embed=fehler_embed("Du bist Single."), ephemeral=True)
    p_id = u.partner_id; u.partner_id = None; u.hochzeits_datum = None; u.kinder.clear()
    state.get_user(p_id).partner_id = None; state.get_user(p_id).hochzeits_datum = None; state.get_user(p_id).kinder.clear()
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("💔 Scheidung", "Ehe gelöst und Familie zurückgesetzt.", BotFarben.FEHLER))

@bot.tree.command(name="marry-status", description="Zeigt deinen Ehe-Status.")
async def marry_status(interaction: discord.Interaction):
    u = state.get_user(str(interaction.user.id))
    txt = f"💍 Verheiratet mit <@{u.partner_id}>" if u.partner_id else "🕊️ Single"
    await interaction.response.send_message(embed=erstelle_embed("Beziehungsstatus", txt, BotFarben.INFO))

@bot.tree.command(name="love", description="Schenke deinem Partner Zuneigung (60 % Chance auf Familienzuwachs).")
async def love(interaction: discord.Interaction, kind_name: str):
    u_id = str(interaction.user.id); u = state.get_user(u_id)
    if not u.partner_id: return await interaction.response.send_message(embed=fehler_embed("Du musst verheiratet sein!"), ephemeral=True)
    
    # Zeitprüfung: Mindestens 2 Tage zusammen
    h_datum = datetime.fromisoformat(u.hochzeits_datum)
    if datetime.now(timezone.utc) < h_datum + timedelta(days=2):
        verbleibend = (h_datum + timedelta(days=2)) - datetime.now(timezone.utc)
        stunden = int(verbleibend.total_seconds() // 3600)
        return await interaction.response.send_message(embed=fehler_embed(f"Ihr müsst mindestens 2 Tage verheiratet sein! Wartet noch `{stunden} Stunden`."), ephemeral=True)
        
    if len(u.kinder) >= 3: return await interaction.response.send_message(embed=fehler_embed("Ihr habt bereits das Maximum von 3 Kindern erreicht!"), ephemeral=True)
    if kind_name in u.kinder: return await interaction.response.send_message(embed=fehler_embed("Dieser Name existiert bereits."), ephemeral=True)

    await interaction.response.defer()
    await asyncio.sleep(2) # Spannungsbogen
    
    # 60% Chance auf ein Kind
    if random.random() < 0.60:
        neues_kind = asdict(ChildProfile(name=kind_name))
        u.kinder[kind_name] = neues_kind
        state.get_user(u.partner_id).kinder[kind_name] = neues_kind
        state.speichern()
        await interaction.followup.send(embed=erstelle_embed("👶 Ein Wunder!", f"Aus eurer Liebe ist ein Kind entstanden! Herzlich willkommen, **{kind_name}**!", BotFarben.ERFOLG))
    else:
        await interaction.followup.send(embed=erstelle_embed("❤️ Romantik", "Ihr hattet ein wunderschönes, romantisches Date, aber es ist diesmal kein Kind entstanden.", BotFarben.INFO))

@bot.tree.command(name="family", description="Zeige deine Familie.")
async def family(interaction: discord.Interaction):
    u = state.get_user(str(interaction.user.id))
    if not u.kinder: return await interaction.response.send_message(embed=erstelle_embed("🏠 Familie", "Keine Kinder vorhanden.", BotFarben.INFO))
    embed = erstelle_embed("🏠 Deine Familie", "Status deiner Kinder:", BotFarben.INFO)
    for k, v in u.kinder.items(): embed.add_field(name=f"👶 {k}", value=f"Level: {v['level']} | Hunger: {v['hunger']}/100")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="baby-feed", description="Füttere dein Kind.")
async def baby_feed(interaction: discord.Interaction, name: str):
    u_id = str(interaction.user.id); u = state.get_user(u_id)
    if name not in u.kinder: return await interaction.response.send_message(embed=fehler_embed("Kind nicht gefunden."), ephemeral=True)
    if u.inventar.get("milch", 0) <= 0: return await interaction.response.send_message(embed=fehler_embed("Du brauchst `milch` aus dem Shop."), ephemeral=True)
    
    u.inventar["milch"] -= 1; k = u.kinder[name]; k["hunger"] = max(0, k["hunger"] - 35); k["level"] += 1
    if u.partner_id: state.get_user(u.partner_id).kinder[name] = k
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🍼 Milchflasche", f"**{name}** ist satt und steigt auf Level {k['level']}!", BotFarben.ERFOLG))

@bot.tree.command(name="baby-play", description="Spiele mit deinem Kind.")
async def baby_play(interaction: discord.Interaction, name: str):
    u_id = str(interaction.user.id); u = state.get_user(u_id)
    if name not in u.kinder: return await interaction.response.send_message(embed=fehler_embed("Kind nicht gefunden."), ephemeral=True)
    xp_geben(u_id, 40); await interaction.response.send_message(embed=erstelle_embed("🧸 Spielzeit", f"Du spielst mit **{name}**. (+40 User-XP)", BotFarben.ERFOLG))

# ─── NEUE FUN-SPIELE ───────────────────────────────────────
@bot.tree.command(name="coinflip", description="Münzwurf.")
@app_commands.choices(tipp=[app_commands.Choice(name="Kopf", value="kopf"), app_commands.Choice(name="Zahl", value="zahl")])
async def coinflip(interaction: discord.Interaction, tipp: app_commands.Choice[str], einsatz: int):
    u = state.get_user(str(interaction.user.id))
    if u.muenzen < einsatz or einsatz <= 0: return await interaction.response.send_message(embed=fehler_embed("Ungültiger Einsatz."), ephemeral=True)
    
    ergebnis = "kopf" if random.random() < 0.50 else "zahl"
    if tipp.value == ergebnis:
        u.muenzen += einsatz
        await interaction.response.send_message(embed=erstelle_embed("🎉 Sieg!", f"Die Münze zeigt {ergebnis}. Du gewinnst **{einsatz} Münzen**!", BotFarben.ERFOLG))
    else:
        u.muenzen -= einsatz
        await interaction.response.send_message(embed=erstelle_embed("📉 Verloren", f"Die Münze zeigt {ergebnis}. Du verlierst **{einsatz} Münzen**.", BotFarben.FEHLER))
    state.speichern()

@bot.tree.command(name="schere-stein", description="Spiele Schere, Stein, Papier gegen den Bot.")
@app_commands.choices(wahl=[app_commands.Choice(name="Schere", value="schere"), app_commands.Choice(name="Stein", value="stein"), app_commands.Choice(name="Papier", value="papier")])
async def ssp(interaction: discord.Interaction, wahl: app_commands.Choice[str]):
    bot_wahl = random.choice(["schere", "stein", "papier"])
    if wahl.value == bot_wahl:
        msg = f"Unentschieden! Wir beide haben **{wahl.name}** gewählt."
    elif (wahl.value == "schere" and bot_wahl == "papier") or (wahl.value == "stein" and bot_wahl == "schere") or (wahl.value == "papier" and bot_wahl == "stein"):
        msg = f"Du gewinnst! **{wahl.name}** schlägt **{bot_wahl}**."
    else:
        msg = f"Verloren! **{bot_wahl}** schlägt **{wahl.name}**."
    await interaction.response.send_message(embed=erstelle_embed("🎮 Schere, Stein, Papier", msg, BotFarben.SPIEL))

@bot.tree.command(name="zahlen-raten", description="Errate eine Zahl zwischen 1 und 10.")
async def raten(interaction: discord.Interaction, zahl: int):
    geheim = random.randint(1, 10)
    if zahl == geheim:
        await interaction.response.send_message(embed=erstelle_embed("🎉 Volltreffer!", f"Richtig! Die Zahl war **{geheim}**.", BotFarben.ERFOLG))
    else:
        await interaction.response.send_message(embed=erstelle_embed("❌ Daneben", f"Falsch. Die gesuchte Zahl war **{geheim}**.", BotFarben.FEHLER))

# ─── BOT RUN ───────────────────────────────────────────────
bot.run(DISCORD_TOKEN)

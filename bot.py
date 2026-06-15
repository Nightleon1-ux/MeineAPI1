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

# ─── STATISCHE CONFIGURATIONEN ─────────────────────────────
LEVEL_ROLLEN_BELOHNUNGEN = {
    5: "Bronze-Mitglied",
    10: "Silber-Mitglied",
    20: "Gold-Mitglied",
    50: "Server-Legende"
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
    "standard": "Du bist ein hilfreicher Assistent.",
    "pirat": "Du bist ein wilder Pirat! Arrr!",
    "lehrer": "Du bist ein geduldiger Lehrer. Erkläre Schritte einfach."
}

QUIZ_FRAGEN = [
    {"frage": "Wie viele Planeten hat unser Sonnensystem?", "antwort": "8"},
    {"frage": "Was ist das chemische Zeichen für Wasser?", "antwort": "H2O"},
    {"frage": "Welches ist das größte Säugetier der Erde?", "antwort": "Blauwal"},
    {"frage": "In welchem Jahr sank die Titanic?", "antwort": "1912"},
    {"frage": "Wie viele Bundesländer hat Deutschland?", "antwort": "16"},
    {"frage": "Wer malte die Mona Lisa?", "antwort": "Leonardo da Vinci"},
    {"frage": "Was ist die Hauptstadt von Australien?", "antwort": "Canberra"}
]

class BotFarben:
    KI = 0x5865F2
    ERFOLG = 0x57F287
    FEHLER = 0xED4245
    SPIEL = 0xFEE75C
    TOOL = 0xEB459E
    INFO = 0x5DADE2
    WIRTSCHAFT = 0xE67E22

# ─── DATA MODELS FOR DATABASES ─────────────────────────────
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
    hochzeits_datum: Optional[str] = None
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
    print(f"🤖 Bot erfolgreich gestartet als: {bot.user}")
@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    user_id = str(message.author.id)
    u = state.get_user(user_id)
    
    if len(message.content) > 3 and not message.content.startswith("/"):
        if xp_geben(user_id, random.randint(2, 5)):
            await message.channel.send(embed=erstelle_embed("🎉 Level Up!", f"{message.author.mention} ist nun **Level {u.level}**!", BotFarben.ERFOLG))
        if random.random() < 0.20:
            u.muenzen += random.randint(1, 5)

@bot.tree.command(name="hilfe", description="Zeigt die Befehlsübersicht.")
async def hilfe(interaction: discord.Interaction):
    embed = discord.Embed(title="⚙️ Kontrollzentrum", color=BotFarben.INFO)
    embed.add_field(name="🪙 Wirtschaft & Berufe", value="`/money` · `/daily` · `/work` · `/mine` · `/sell` · `/shop` · `/buy` · `/inventory`", inline=False)
    embed.add_field(name="💞 Ehe & Familie", value="`/ship` · `/marry` · `/divorce` · `/marry-status` · `/love` · `/family` · `/baby-feed` · `/baby-play`", inline=False)
    embed.add_field(name="🎮 Fun & Quiz", value="`/quiz` · `/coinflip` · `/schere-stein` · `/zahlen-raten` · `/wurf`", inline=False)
    embed.add_field(name="🐾 Haustiere & KI", value="`/pet-adopt` · `/pet-status` · `/pet-feed` · `/ki` · `/persönlichkeit` · `/rank` · `/leaderboard`", inline=False)
    await interaction.response.send_message(embed=embed)

# ─── WIRTSCHAFTS-LOGIK ──────────────────────────────────────
@bot.tree.command(name="money", description="Zeigt deinen aktuellen Kontostand.")
async def money(interaction: discord.Interaction):
    u = state.get_user(str(interaction.user.id))
    await interaction.response.send_message(embed=erstelle_embed("🪙 Kontostand", f"Du besitzt aktuell **{u.muenzen} Münzen**.", BotFarben.WIRTSCHAFT))

@bot.tree.command(name="daily", description="Hol dir deine tägliche Belohnung ab.")
async def daily(interaction: discord.Interaction):
    u_id = str(interaction.user.id); u = state.get_user(u_id); jetzt = datetime.now(timezone.utc)
    if u.letztes_daily and jetzt < datetime.fromisoformat(u.letztes_daily) + timedelta(days=1):
        return await interaction.response.send_message(embed=fehler_embed("Dein Daily steht erst morgen wieder bereit."), ephemeral=True)
    u.letztes_daily = jetzt.isoformat(); u.muenzen += 75; state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🎁 Tägliche Belohnung", "Du hast **75 Münzen** erhalten!", BotFarben.ERFOLG))

@bot.tree.command(name="work", description="Gehe arbeiten, um Geld zu verdienen.")
@app_commands.choices(beruf=[
    app_commands.Choice(name="👷 Bauarbeiter (Sicher)", value="bau"),
    app_commands.Choice(name="💻 Programmierer (Risiko)", value="dev")
])
async def work(interaction: discord.Interaction, beruf: app_commands.Choice[str]):
    u_id = str(interaction.user.id); u = state.get_user(u_id); jetzt = datetime.now(timezone.utc)
    if u.letzte_arbeit and jetzt < datetime.fromisoformat(u.letzte_arbeit) + timedelta(hours=1):
        return await interaction.response.send_message(embed=fehler_embed("Du bist zu müde. Warte 1 Stunde."), ephemeral=True)
    
    lohn = random.randint(45, 65) if beruf.value == "bau" else random.randint(20, 130)
    u.muenzen += lohn; u.letzte_arbeit = jetzt.isoformat(); state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("💼 Arbeit beendet", f"Du hast fleißig gearbeitet und **{lohn} Münzen** verdient.", BotFarben.WIRTSCHAFT))

@bot.tree.command(name="mine", description="Arbeite in den Minen und sammle Erze.")
async def mine(interaction: discord.Interaction):
    u_id = str(interaction.user.id); u = state.get_user(u_id); jetzt = datetime.now(timezone.utc)
    if u.letzte_mine and jetzt < datetime.fromisoformat(u.letzte_mine) + timedelta(minutes=45):
        return await interaction.response.send_message(embed=fehler_embed("Die Mine ist vorübergehend gesperrt. Warte 45 Minuten."), ephemeral=True)
    
    rand = random.random()
    erz = "kohle" if rand < 0.55 else ("eisen" if rand < 0.85 else ("gold" if rand < 0.96 else "diamant"))
    u.inventar[erz] = u.inventar.get(erz, 0) + 1; u.letzte_mine = jetzt.isoformat(); state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("⛏️ Bergbau-Erfolg", f"Du hast tief gegraben und **{ERZ_PREISE[erz]['name']}** gefunden!", BotFarben.SPIEL))

@bot.tree.command(name="sell", description="Verkaufe deine Erze aus dem Inventar.")
@app_commands.choices(erz_id=[app_commands.Choice(name="⚫ Kohle", value="kohle"), app_commands.Choice(name="🪙 Eisen", value="eisen"), app_commands.Choice(name="🟡 Gold", value="gold"), app_commands.Choice(name="💎 Diamant", value="diamant")])
async def sell(interaction: discord.Interaction, erz_id: app_commands.Choice[str], anzahl: int = 1):
    u = state.get_user(str(interaction.user.id))
    if u.inventar.get(erz_id.value, 0) < anzahl or anzahl <= 0: return await interaction.response.send_message(embed=fehler_embed("Du hast nicht genügend Erze im Inventar."), ephemeral=True)
    erloes = ERZ_PREISE[erz_id.value]["wert"] * anzahl; u.inventar[erz_id.value] -= anzahl; u.muenzen += erloes; state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("⚖️ Rohstoff-Markt", f"Du hast {anzahl}x {erz_id.name} für **{erloes} Münzen** verkauft.", BotFarben.WIRTSCHAFT))
  @bot.tree.command(name="shop", description="Öffnet den Marktplatz.")
async def shop(interaction: discord.Interaction):
    embed = erstelle_embed("🛒 Server-Marktplatz", "Nutze `/buy <item>` zum Einkaufen.", BotFarben.WIRTSCHAFT)
    for k, i in SHOP_ITEMS.items():
        embed.add_field(name=i["name"], value=f"Code: `{k}` · Preis: **{i['preis']} Münzen**\n*{i['beschreibung']}*", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="buy", description="Kaufe ein Item aus dem Laden.")
@app_commands.choices(item_id=[app_commands.Choice(name="🍪 Kekse", value="kekse"), app_commands.Choice(name="🥩 Steak", value="steak"), app_commands.Choice(name="🍼 Milchflasche", value="milch")])
async def buy(interaction: discord.Interaction, item_id: app_commands.Choice[str]):
    u = state.get_user(str(interaction.user.id)); item = SHOP_ITEMS[item_id.value]
    if u.muenzen < item["preis"]: return await interaction.response.send_message(embed=fehler_embed("Dein Geld reicht dafür nicht aus."), ephemeral=True)
    u.muenzen -= item["preis"]; u.inventar[item_id.value] = u.inventar.get(item_id.value, 0) + 1; state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🛒 Kauf erfolgreich", f"Du hast {item['name']} für dein Inventar erworben.", BotFarben.ERFOLG))

@bot.tree.command(name="inventory", description="Zeigt deine gesammelten Schätze.")
async def inventory(interaction: discord.Interaction):
    u = state.get_user(str(interaction.user.id))
    inhalt = []
    for k, v in u.inventar.items():
        if v > 0:
            name = SHOP_ITEMS[k]["name"] if k in SHOP_ITEMS else ERZ_PREISE[k]["name"]
            inhalt.append(f"{name}: **{v}x**")
    await interaction.response.send_message(embed=erstelle_embed("🎒 Dein Inventar", "\n".join(inhalt) if inhalt else "*Dein Rucksack ist komplett leer.*", BotFarben.TOOL))

# ─── HAUSTIER STEUERUNG ─────────────────────────────────────
@bot.tree.command(name="pet-adopt", description="Adoptiere einen treuen Begleiter.")
@app_commands.choices(typ=[app_commands.Choice(name="🐱 Katze", value="Katze"), app_commands.Choice(name="🐶 Hund", value="Hund")])
async def pet_adopt(interaction: discord.Interaction, typ: app_commands.Choice[str], name: str):
    u_id = str(interaction.user.id)
    if u_id in state.pet_daten: return await interaction.response.send_message(embed=fehler_embed("Du besitzt bereits ein Haustier."), ephemeral=True)
    state.pet_daten[u_id] = PetProfile(name=name, typ=typ.value); state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🐾 Zuwachs", f"Du hast erfolgreich die/den {typ.name} **{name}** adoptiert!", BotFarben.ERFOLG))

@bot.tree.command(name="pet-status", description="Prüfe das Wohlbefinden deines Haustiers.")
async def pet_status(interaction: discord.Interaction):
    p = state.pet_daten.get(str(interaction.user.id))
    if not p: return await interaction.response.send_message(embed=fehler_embed("Du hast kein Haustier."), ephemeral=True)
    await interaction.response.send_message(embed=erstelle_embed(f"🐾 Begleiter {p.name}", f"Spezies: **{p.typ}**\nLevel: **{p.level}**\nHungerstatus: `{p.hunger}/100`", BotFarben.INFO))

@bot.tree.command(name="pet-feed", description="Füttere dein Haustier mit Vorräten.")
@app_commands.choices(futter=[app_commands.Choice(name="🍪 Keks", value="kekse"), app_commands.Choice(name="🥩 Steak", value="steak")])
async def pet_feed(interaction: discord.Interaction, futter: app_commands.Choice[str]):
    u_id = str(interaction.user.id); u = state.get_user(u_id); p = state.pet_daten.get(u_id)
    if not p: return await interaction.response.send_message(embed=fehler_embed("Du hast kein Haustier zum Füttern."), ephemeral=True)
    if u.inventar.get(futter.value, 0) <= 0: return await interaction.response.send_message(embed=fehler_embed("Dieses Futter musst du erst im Shop erwerben."), ephemeral=True)
    
    u.inventar[futter.value] -= 1
    p.hunger = max(0, p.hunger - (30 if futter.value == "kekse" else 80))
    p.level += 1; state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🍖 Mampf!", f"Du fütterst {p.name}. Das Haustier steigt auf **Level {p.level}**!", BotFarben.ERFOLG))  
@bot.tree.command(name="ship", description="Misst die Liebe zwischen zwei Usern.")
async def ship(interaction: discord.Interaction, user: discord.Member):
    prozent = random.randint(0, 100)
    await interaction.response.send_message(embed=erstelle_embed("💘 Liebes-Barometer", f"{interaction.user.mention} & {user.mention} passen zu **{prozent}%** zusammen!", BotFarben.TOOL))

@bot.tree.command(name="marry", description="Mache jemandem einen Heiratsantrag.")
async def marry(interaction: discord.Interaction, partner: discord.Member):
    u_id, p_id = str(interaction.user.id), str(partner.id); u = state.get_user(u_id)
    if u.partner_id or partner.bot or partner == interaction.user: return await interaction.response.send_message(embed=fehler_embed("Diese Hochzeit ist nicht möglich."), ephemeral=True)
    
    await interaction.response.send_message(f"💍 {partner.mention}, nimmst du den Antrag von {interaction.user.mention} an? Antworte mit **'ja ich will'**!")
    try:
        def check(m): return m.author.id == partner.id and m.content.lower() == "ja ich will" and m.channel.id == interaction.channel_id
        await bot.wait_for("message", check=check, timeout=60.0)
        jetzt = datetime.now(timezone.utc).isoformat()
        u.partner_id = p_id; u.hochzeits_datum = jetzt
        state.get_user(p_id).partner_id = u_id; state.get_user(p_id).hochzeits_datum = jetzt
        state.speichern()
        await interaction.channel.send(embed=erstelle_embed("🎉 Bund fürs Leben", f"{interaction.user.mention} und {partner.mention} sind jetzt verheiratet!", BotFarben.ERFOLG))
    except asyncio.TimeoutError:
        await interaction.channel.send("💔 Der Antrag ist unbeantwortet abgelaufen.")

@bot.tree.command(name="divorce", description="Reiche die Scheidung ein.")
async def divorce(interaction: discord.Interaction):
    u_id = str(interaction.user.id); u = state.get_user(u_id)
    if not u.partner_id: return await interaction.response.send_message(embed=fehler_embed("Du bist nicht verheiratet."), ephemeral=True)
    p_id = u.partner_id; u.partner_id = None; u.hochzeits_datum = None; u.kinder.clear()
    state.get_user(p_id).partner_id = None; state.get_user(p_id).hochzeits_datum = None; state.get_user(p_id).kinder.clear()
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("💔 Getrennte Wege", "Die Ehe wurde geschieden, die Familie aufgelöst.", BotFarben.FEHLER))

@bot.tree.command(name="marry-status", description="Zeigt deinen Beziehungsstatus.")
async def marry_status(interaction: discord.Interaction):
    u = state.get_user(str(interaction.user.id))
    text = f"💍 Verheiratet mit <@{u.partner_id}>" if u.partner_id else "🕊️ Single"
    await interaction.response.send_message(embed=erstelle_embed("Ehe-Status", text, BotFarben.INFO))

@bot.tree.command(name="love", description="Verbringt romantische Zeit. Nach 2 Tagen Ehe besteht eine 60% Chance auf ein Kind.")
async def love(interaction: discord.Interaction, kind_name: str):
    u_id = str(interaction.user.id); u = state.get_user(u_id)
    if not u.partner_id: return await interaction.response.send_message(embed=fehler_embed("Dafür müsst ihr verheiratet sein!"), ephemeral=True)
    
    h_datum = datetime.fromisoformat(u.hochzeits_datum)
    if datetime.now(timezone.utc) < h_datum + timedelta(days=2):
        verbleibend = (h_datum + timedelta(days=2)) - datetime.now(timezone.utc)
        stunden = int(verbleibend.total_seconds() // 3600)
        return await interaction.response.send_message(embed=fehler_embed(f"Ihr seid noch frisch verheiratet. Kuscheln erlaubt, aber ein Kind geht erst in `{stunden} Std.`!"), ephemeral=True)
        
    if len(u.kinder) >= 3: return await interaction.response.send_message(embed=fehler_embed("Eure Familie hat das Limit von 3 Kindern erreicht."), ephemeral=True)
    if kind_name in u.kinder: return await interaction.response.send_message(embed=fehler_embed("Der Name ist in eurer Familie schon vergeben."), ephemeral=True)

    await interaction.response.defer()
    await asyncio.sleep(2)
    
    if random.random() < 0.60:
        n_kind = asdict(ChildProfile(name=kind_name))
        u.kinder[kind_name] = n_kind
        state.get_user(u.partner_id).kinder[kind_name] = n_kind; state.speichern()
        await interaction.followup.send(embed=erstelle_embed("👶 Nachwuchs!", f"Herzlichen Glückwunsch! Eure Liebe hat Früchte getragen: **{kind_name}** wurde geboren!", BotFarben.ERFOLG))
    else:
        await interaction.followup.send(embed=erstelle_embed("❤️ Romantischer Abend", "Ihr hattet ein wunderschönes Date, aber es ist kein Kind entstanden.", BotFarben.INFO))

@bot.tree.command(name="family", description="Zeigt deine Kinder.")
async def family(interaction: discord.Interaction):
    u = state.get_user(str(interaction.user.id))
    if not u.kinder: return await interaction.response.send_message(embed=erstelle_embed("🏠 Stammbaum", "Ihr habt noch keine Kinder.", BotFarben.INFO))
    embed = erstelle_embed("🏠 Familienspiegel", "Status eurer Kinder:", BotFarben.INFO)
    for k, v in u.kinder.items(): embed.add_field(name=f"👶 {k}", value=f"Stufe: Level {v['level']} | Hunger: {v['hunger']}/100", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="baby-feed", description="Füttere dein Kind mit Milch.")
async def baby_feed(interaction: discord.Interaction, name: str):
    u_id = str(interaction.user.id); u = state.get_user(u_id)
    if name not in u.kinder: return await interaction.response.send_message(embed=fehler_embed("Dieses Kind gehört nicht zu deiner Familie."), ephemeral=True)
    if u.inventar.get("milch", 0) <= 0: return await interaction.response.send_message(embed=fehler_embed("Du besitzt keine `milch` im Rucksack."), ephemeral=True)
    
    u.inventar["milch"] -= 1; k = u.kinder[name]; k["hunger"] = max(0, k["hunger"] - 35); k["level"] += 1
    if u.partner_id: state.get_user(u.partner_id).kinder[name] = k
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🍼 Milchflasche", f"Du hast **{name}** gefüttert. Es ist glücklich auf **Level {k['level']}**!", BotFarben.ERFOLG))

@bot.tree.command(name="baby-play", description="Spiele mit deinem Kind.")
async def baby_play(interaction: discord.Interaction, name: str):
    u = state.get_user(str(interaction.user.id))
    if name not in u.kinder: return await interaction.response.send_message(embed=fehler_embed("Kind nicht gefunden."), ephemeral=True)
    xp_geben(str(interaction.user.id), 40)
    await interaction.response.send_message(embed=erstelle_embed("🧸 Spielstunde", f"Du baust Bauklötze mit **{name}**. (+40 User-XP)", BotFarben.ERFOLG))
    # ─── NEUES GROSSES QUIZ SYSTEM ─────────────────────────────
@bot.tree.command(name="quiz", description="Starte ein Server-Quiz und gewinne Münzen!")
async def quiz(interaction: discord.Interaction):
    eintrag = random.choice(QUIZ_FRAGEN)
    await interaction.response.send_message(embed=erstelle_embed("🧠 Quiz-Zentrale", f"Hier ist deine Preisfrage:\n\n**{eintrag['frage']}**\n\n*Schreibe die richtige Antwort innerhalb von 25 Sekunden in den Chat!*", BotFarben.SPIEL))
    
    try:
        def check(m): return m.channel.id == interaction.channel_id and not m.author.bot
        msg = await bot.wait_for("message", check=check, timeout=25.0)
        
        if msg.content.lower().strip() == eintrag["antwort"].lower().strip():
            u = state.get_user(str(msg.author.id)); u.muenzen += 35; state.speichern()
            await interaction.channel.send(embed=erstelle_embed("🎉 Richtige Antwort!", f"{msg.author.mention} hat die Frage blitzschnell gelöst!\nBelohnung: **+35 Münzen** 🪙", BotFarben.ERFOLG))
        else:
            await interaction.channel.send(embed=erstelle_embed("❌ Falsche Antwort", f"Schade, das war leider nicht korrekt. Die richtige Antwort war: **{eintrag['antwort']}**.", BotFarben.FEHLER))
    except asyncio.TimeoutError:
        await interaction.channel.send(embed=erstelle_embed("⏰ Zeit abgelaufen", f"Niemand hat rechtzeitig geantwortet. Die Lösung war: **{eintrag['antwort']}**", BotFarben.INFO))

# ─── WEITERE MINISPIELE & FUN FUNCTIONS ───────────────────
@bot.tree.command(name="coinflip", description="Setze Münzen auf Kopf oder Zahl.")
@app_commands.choices(tipp=[app_commands.Choice(name="Kopf", value="kopf"), app_commands.Choice(name="Zahl", value="zahl")])
async def coinflip(interaction: discord.Interaction, tipp: app_commands.Choice[str], einsatz: int):
    u = state.get_user(str(interaction.user.id))
    if u.muenzen < einsatz or einsatz <= 0: return await interaction.response.send_message(embed=fehler_embed("Ungültiger oder zu hoher Einsatz."), ephemeral=True)
    
    seite = "kopf" if random.random() < 0.50 else "zahl"
    if tipp.value == seite:
        u.muenzen += einsatz
        await interaction.response.send_message(embed=erstelle_embed("🎉 Gewonnen!", f"Die Münze zeigt {seite}! Du gewinnst **{einsatz} Münzen**.", BotFarben.ERFOLG))
    else:
        u.muenzen -= einsatz
        await interaction.response.send_message(embed=erstelle_embed("📉 Verloren!", f"Die Münze landete auf {seite}. Du verlierst **{einsatz} Münzen**.", BotFarben.FEHLER))
    state.speichern()

@bot.tree.command(name="schere-stein", description="Fordere den Bot heraus.")
@app_commands.choices(wahl=[app_commands.Choice(name="Schere", value="schere"), app_commands.Choice(name="Stein", value="stein"), app_commands.Choice(name="Papier", value="papier")])
async def ssp(interaction: discord.Interaction, wahl: app_commands.Choice[str]):
    gegner = random.choice(["schere", "stein", "papier"])
    if wahl.value == gegner: msg = f"Gleichstand! Beide wählten **{wahl.name}**."
    elif (wahl.value == "schere" and gegner == "papier") or (wahl.value == "stein" and gegner == "schere") or (wahl.value == "papier" and gegner == "stein"):
        msg = f"Sieg! Deine Auswahl **{wahl.name}** schlägt **{gegner}**."
    else: msg = f"Niederlage! Der Bot kontert mit **{gegner}**."
    await interaction.response.send_message(embed=erstelle_embed("🎮 Schere-Stein-Papier", msg, BotFarben.SPIEL))

@bot.tree.command(name="zahlen-raten", description="Errate die Geheimzahl von 1 bis 10.")
async def raten(interaction: discord.Interaction, zahl: int):
    ziel = random.randint(1, 10)
    if zahl == ziel: await interaction.response.send_message(embed=erstelle_embed("🎯 Volltreffer", "Genau getroffen!", BotFarben.ERFOLG))
    else: await interaction.response.send_message(embed=erstelle_embed("❌ Daneben", f"Die gesuchte Zahl war **{ziel}**.", BotFarben.FEHLER))

@bot.tree.command(name="wurf", description="Wirft einen Würfel.")
async def wurf(interaction: discord.Interaction, seiten: int = 6):
    await interaction.response.send_message(embed=erstelle_embed("🎲 Würfel", f"Ergebnis: **{random.randint(1, max(2, seiten))}**", BotFarben.SPIEL))

# ─── NEURONALE KI SCHNITTTSTELLE & PROFIL ───────────────────
@bot.tree.command(name="ki", description="Frage die KI.")
async def ki(interaction: discord.Interaction, frage: str):
    await interaction.response.defer(); u_id = str(interaction.user.id); u = state.get_user(u_id)
    try:
        if u_id not in state.chat_verlaeufe: state.chat_verlaeufe[u_id] = []
        state.chat_verlaeufe[u_id].append({"role": "user", "content": frage})
        sys = PERSONAS.get(u.ki_persona, "standard")
        antwort = await groq_anfrage([{"role": "system", "content": sys}] + state.chat_verlaeufe[u_id][-6:])
        state.chat_verlaeufe[u_id].append({"role": "assistant", "content": antwort})
        await interaction.followup.send(embed=erstelle_embed("🤖 KI", antwort[:2000], BotFarben.KI))
    except Exception as e: await interaction.followup.send(embed=fehler_embed(str(e)))

@bot.tree.command(name="persönlichkeit", description="Ändere die Persona der KI.")
@app_commands.choices(wahl=[app_commands.Choice(name="Standard", value="standard"), app_commands.Choice(name="Pirat", value="pirat")])
async def persoenlichkeit_cmd(interaction: discord.Interaction, wahl: app_commands.Choice[str]):
    state.get_user(str(interaction.user.id)).ki_persona = wahl.value; state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🎭 Persona", f"Modus **{wahl.name}** ist bereit.", BotFarben.TOOL))

@bot.tree.command(name="rank", description="Zeigt deine Statistiken.")
async def rank(interaction: discord.Interaction):
    u = state.get_user(str(interaction.user.id))
    await interaction.response.send_message(embed=erstelle_embed("⭐ Dein Profil", f"Level: **{u.level}**\nErfahrung: `{u.xp}/{u.level*100} XP`\nMünzen: `🪙 {u.muenzen}`", BotFarben.INFO))

@bot.tree.command(name="leaderboard", description="Zeigt die Server-Besten.")
async def leaderboard(interaction: discord.Interaction):
    sortiert = sorted(state.user_daten.items(), key=lambda x: x[1].gesamt_xp, reverse=True)[:5]
    t = "\n".join(f"#{i+1} · <@{uid}> · Level {d.level}" for i, (uid, d) in enumerate(sortiert))
    await interaction.response.send_message(embed=erstelle_embed("🏆 Top 5 Rangliste", t if t else "Keine Daten.", BotFarben.SPIEL))

# ─── BOT START ─────────────────────────────────────────────
bot.run(DISCORD_TOKEN)

import discord
from discord import app_commands
import aiohttp
import os
import random
import asyncio
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# ─── OWNER KONFIGURATION ───────────────────────────────────
OWNER_ID = 1405193599984861255  # Deine Discord ID als Nightleon1

# ─── STATISCHE KONFIGURATIONEN ─────────────────────────────
LEVEL_ROLLEN_BELOHNUNGEN = {
    5: "Bronze-Mitglied",
    10: "Silber-Mitglied",
    15: "Gold-Mitglied",
    20: "Platin-Mitglied",
    30: "Diamant-Mitglied"
}

SHOP_ITEMS = {
    "kekse": {"name": "🍪 Kekse", "preis": 25, "beschreibung": "Futter für dein Haustier (-30 Hunger)", "typ": "item"},
    "steak": {"name": "🥩 Premium Steak", "preis": 60, "beschreibung": "Perfekt für Haustiere (-80 Hunger)", "typ": "item"},
    "milch": {"name": "🍼 Milchflasche", "preis": 40, "beschreibung": "Nahrung für dein Kind (-35 Hunger)", "typ": "item"},
    
    "hacke_holz": {"name": "🪵 Holz-Spitzhacke", "preis": 50, "beschreibung": "Haltbarkeit: 5 Einsätze.", "typ": "tool", "max_uses": 5, "luck": 1.0},
    "hacke_stein": {"name": "🪨 Stein-Spitzhacke", "preis": 120, "beschreibung": "Haltbarkeit: 12 Einsätze.", "typ": "tool", "max_uses": 12, "luck": 1.1},
    "hacke_kupfer": {"name": "🟫 Kupfer-Spitzhacke", "preis": 250, "beschreibung": "Haltbarkeit: 20 Einsätze.", "typ": "tool", "max_uses": 20, "luck": 1.2},
    "hacke_eisen": {"name": "🪙 Eisen-Spitzhacke", "preis": 450, "beschreibung": "Haltbarkeit: 35 Einsätze.", "typ": "tool", "max_uses": 35, "luck": 1.4},
    "hacke_stahl": {"name": "⚔️ Stahl-Spitzhacke", "preis": 700, "beschreibung": "Haltbarkeit: 50 Einsätze.", "typ": "tool", "max_uses": 50, "luck": 1.6},
    "hacke_gold": {"name": "🟡 Gold-Spitzhacke", "preis": 1000, "beschreibung": "Magisch! Haltbarkeit: 15 Einsätze.", "typ": "tool", "max_uses": 15, "luck": 2.5},
    "hacke_diamant": {"name": "💎 Diamant-Spitzhacke", "preis": 1800, "beschreibung": "Haltbarkeit: 80 Einsätze.", "typ": "tool", "max_uses": 80, "luck": 2.0},
    "hacke_obsidian": {"name": "🔮 Obsidian-Spitzhacke", "preis": 2500, "beschreibung": "Haltbarkeit: 120 Einsätze.", "typ": "tool", "max_uses": 120, "luck": 2.2},
    "hacke_titan": {"name": "🛡️ Titan-Spitzhacke", "preis": 4000, "beschreibung": "Haltbarkeit: 200 Einsätze.", "typ": "tool", "max_uses": 200, "luck": 2.6},
    "hacke_mythril": {"name": "✨ Mythril-Spitzhacke", "preis": 7500, "beschreibung": "Haltbarkeit: 300 Einsätze.", "typ": "tool", "max_uses": 300, "luck": 3.5}
}

ERZ_PREISE = {
    "kohle": {"name": "⚫ Kohle", "wert": 15},
    "eisen": {"name": "🪙 Eisenerz", "wert": 35},
    "gold": {"name": "🟡 Golderz", "wert": 75},
    "diamant": {"name": "💎 Diamant", "wert": 200},
    "schrott": {"name": "⚙️ Elektronik-Schrott", "wert": 110},
    "astral": {"name": "🌌 Astralsplitter", "wert": 320},
    "fragment": {"name": "🔮 Zeit-Fragment", "wert": 500}
}

PET_TYPEN = {
    "Katze": {"emoji": "🐱", "preis": 0, "min_level": 1, "atki_bonus": 5, "premium": False},
    "Hund": {"emoji": "🐶", "preis": 0, "min_level": 1, "atki_bonus": 6, "premium": False},
    "Hase": {"emoji": "🐰", "preis": 150, "min_level": 3, "atki_bonus": 4, "premium": False},
    "Fuchs": {"emoji": "🦊", "preis": 400, "min_level": 5, "atki_bonus": 8, "premium": False},
    "Bär": {"emoji": "🐻", "preis": 800, "min_level": 8, "atki_bonus": 12, "premium": False},
    "Panda": {"emoji": "🐼", "preis": 1200, "min_level": 10, "atki_bonus": 10, "premium": False},
    "Löwe": {"emoji": "🦁", "preis": 2000, "min_level": 12, "atki_bonus": 16, "premium": False},
    "Affenkoenig": {"emoji": "🐵", "preis": 3500, "min_level": 15, "atki_bonus": 14, "premium": False},
    "Drache": {"emoji": "🐉", "preis": 6000, "min_level": 18, "atki_bonus": 22, "premium": False},
    "Phönix": {"emoji": "✨", "preis": 9999, "min_level": 20, "atki_bonus": 25, "premium": False},
    # Premium Tiere
    "Pegasus": {"emoji": "🦄", "preis": 2500, "min_level": 5, "atki_bonus": 15, "premium": True},
    "Schattenwolf": {"emoji": "🐺", "preis": 5000, "min_level": 12, "atki_bonus": 24, "premium": True},
    "Mecha-Greif": {"emoji": "🦅", "preis": 8500, "min_level": 18, "atki_bonus": 30, "premium": True},
    "Leviathan": {"emoji": "🐉", "preis": 12000, "min_level": 22, "atki_bonus": 40, "premium": True},
    "Kosmische_Katze": {"emoji": "🌌", "preis": 20000, "min_level": 25, "atki_bonus": 50, "premium": True}
}

ABENTEUER_GEBIETE = {
    "wald": {"name": "🌲 Grüner Wald (Sicher)", "hunger_kosten": 15, "min_level": 1, "schaden_max": 10, "looten": ["kohle", "eisen", "kekse"], "legendaer_chance": 0.01, "premium": False},
    "hoehle": {"name": "🦇 Düstere Höhle (Mittel)", "hunger_kosten": 30, "min_level": 5, "schaden_max": 35, "looten": ["eisen", "gold", "steak"], "legendaer_chance": 0.08, "premium": False},
    "vulkan": {"name": "🌋 Vulkanland (Hochriskant)", "hunger_kosten": 50, "min_level": 10, "schaden_max": 75, "looten": ["gold", "diamant", "steak"], "legendaer_chance": 0.20, "premium": False},
    "oedland": {"name": "⚡ Tesla-Ödland (Gefährlich)", "hunger_kosten": 65, "min_level": 12, "schaden_max": 90, "looten": ["eisen", "schrott", "diamant"], "legendaer_chance": 0.25, "premium": False},
    "astral": {"name": "🌌 Astralebene (Magisch)", "hunger_kosten": 0, "min_level": 16, "schaden_max": 110, "looten": ["diamant", "astral", "astral"], "legendaer_chance": 0.35, "premium": False},
    # Premium Welten
    "schloss": {"name": "🏰 Schwebendes Schloss (Sicher & Edel)", "hunger_kosten": 20, "min_level": 5, "schaden_max": 0, "looten": ["gold", "diamant", "steak"], "legendaer_chance": 0.15, "premium": True},
    "krater": {"name": "🌋 Urzeit-Krater (Extrem Lukrativ)", "hunger_kosten": 45, "min_level": 15, "schaden_max": 60, "looten": ["diamant", "astral", "gold"], "legendaer_chance": 0.45, "premium": True},
    "chronos": {"name": "🪐 Chronos-Riss (Zeitlos)", "hunger_kosten": 0, "min_level": 22, "schaden_max": 80, "looten": ["astral", "fragment", "fragment"], "legendaer_chance": 0.50, "premium": True}
}

BOSS_GEGNER = [
    {"name": "🦧 Der Riesenaffe", "hp": 120, "atk": 12, "min_level": 1, "belohnung_muenzen": 200, "xp": 100, "premium": False},
    {"name": "🦂 Der Gift-Skorpion", "hp": 250, "atk": 22, "min_level": 8, "belohnung_muenzen": 600, "xp": 250, "premium": False},
    {"name": "🤖 Der Mech-Skorpion", "hp": 400, "atk": 35, "min_level": 10, "belohnung_muenzen": 1000, "xp": 450, "premium": False},
    {"name": "👹 Der Höhlen-Golem", "hp": 600, "atk": 45, "min_level": 15, "belohnung_muenzen": 1800, "xp": 700, "premium": False},
    {"name": "🔮 Der Cyber-Dschinn", "hp": 950, "atk": 65, "min_level": 18, "belohnung_muenzen": 3500, "xp": 1200, "premium": False},
    # Premium Bosse
    {"name": "👑 König der Verdammten", "hp": 1500, "atk": 85, "min_level": 20, "belohnung_muenzen": 5000, "xp": 2000, "premium": True},
    {"name": "💥 Obsidian-Titan", "hp": 2200, "atk": 110, "min_level": 25, "belohnung_muenzen": 8000, "xp": 3500, "premium": True},
    {"name": "🌌 Dimensions-Schlucker", "hp": 3500, "atk": 150, "min_level": 30, "belohnung_muenzen": 15000, "xp": 6000, "premium": True}
]

PERSONAS = {
    "standard": "Du bist ein hilfreicher Assistent.",
    "pirat": "Du bist ein wilder Pirat! Arrr!",
    "lehrer": "Du bist ein geduldiger Lehrer."
}

QUIZ_FRAGEN = [
    {"frage": "Wie viele Planeten hat unser Sonnensystem?", "antwort": "8"},
    {"frage": "Was ist das chemische Zeichen für Wasser?", "antwort": "H2O"},
    {"frage": "Welches ist das größte Säugetier der Erde?", "antwort": "Blauwal"}
]

class BotFarben:
    KI = 0x5865F2
    ERFOLG = 0x57F287
    FEHLER = 0xED4245
    SPIEL = 0xFEE75C
    TOOL = 0xEB459E
    INFO = 0x5DADE2
    WIRTSCHAFT = 0xE67E22
    FAMILIE = 0xE91E63
    PREMIUM = 0xD4AF37 # Goldfarben für Premium

# ─── DATEN-MODELLE ─────────────────────────────────────────
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
    ehe_konto: int = 0
    letztes_daily: Optional[str] = None
    letzte_arbeit: Optional[str] = None
    letzte_mine: Optional[str] = None
    arbeits_erfahrung: int = 0
    berufs_stufe: int = 1
    minen_counter: int = 0
    aktive_hacke: Optional[str] = None
    hacke_haltbarkeit: int = 0
    # Premium Felder
    premium_bis: Optional[str] = None  # ISO-Timestamp oder "permanent"
    premium_titel: Optional[str] = None
    premium_aura: Optional[str] = None
    premium_residenz_name: Optional[str] = None

@dataclass
class PetProfile:
    name: str
    typ: str
    level: int = 1
    hunger: int = 20
    zufriedenheit: int = 50
    max_hp: int = 100
    aktuelle_hp: int = 100
    atk: int = 10
    abenteuer_counter: int = 0
    letztes_training: Optional[str] = None
    letztes_streicheln: Optional[str] = None
    letztes_abenteuer: Optional[str] = None
    premium_verkleidung: Optional[str] = None

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

    def ist_premium(self, user_id: str) -> bool:
        u = self.get_user(user_id)
        if not u.premium_bis: return False
        if u.premium_bis == "permanent": return True
        try:
            bis_zeit = datetime.fromisoformat(u.premium_bis)
            if datetime.now(timezone.utc) < bis_zeit:
                return True
            else:
                u.premium_bis = None # Abgelaufen
                self.speichern()
                return False
        except:
            return False

    def speichern(self):
        try:
            daten = {
                "users": {uid: asdict(prof) for uid, prof in self.user_daten.items()},
                "pets": {uid: asdict(prof) for uid, prof in self.pet_daten.items()}
            }
            with open(self.datei_pfad, "w", encoding="utf-8") as f:
                json.dump(daten, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"⚠️ Fehler beim Speichern: {e}")

    def laden(self):
        if os.path.exists(self.datei_pfad):
            try:
                with open(self.datei_pfad, "r", encoding="utf-8") as f:
                    daten = json.load(f)
                    self.user_daten = {uid: UserProfile(**{k: v for k, v in val.items() if k in UserProfile.__dataclass_fields__}) for uid, val in daten.get("users", {}).items()}
                    self.pet_daten = {uid: PetProfile(**{k: v for k, v in val.items() if k in PetProfile.__dataclass_fields__}) for uid, val in daten.get("pets", {}).items()}
            except Exception as e:
                print(f"⚠️ Fehler beim Laden: {e}")

state = BotState()

# ─── HELFER-FUNKTIONEN ─────────────────────────────────────
def erstelle_embed(titel: str, beschreibung: str, farbe: int) -> discord.Embed:
    return discord.Embed(title=titel, description=beschreibung, color=farbe, timestamp=datetime.now(timezone.utc))

def fehler_embed(text: str) -> discord.Embed:
    return erstelle_embed("❌ Fehler", text, BotFarben.FEHLER)

def xp_geben(user_id: str, menge: int = 5) -> bool:
    u = state.get_user(user_id)
    if state.ist_premium(user_id):
        menge = int(menge * 1.25) # +25% XP Bonus
    u.xp += menge
    u.gesamt_xp += menge
    benoetigt = u.level * 100
    level_up = False
    while u.xp >= benoetigt:
        u.xp -= benoetigt
        u.level += 1
        bonus = u.level * 50
        if state.ist_premium(user_id): bonus = int(bonus * 1.25)
        u.muenzen += bonus
        benoetigt = u.level * 100
        level_up = True
    return level_up

def generiere_fortschrittsbalken(aktuell: int, max_wert: int, balken_laenge: int = 10) -> str:
    if max_wert <= 0: return "⬜" * balken_laenge + " 0%"
    prozent = min(1.0, max(0.0, aktuell / max_wert))
    gefuellt = int(prozent * balken_laenge)
    leer = balken_laenge - gefuellt
    return f"{'🟩' * gefuellt}{'⬜' * leer} {int(prozent * 100)}%"

async def check_und_vergebe_rollen(member: discord.Member, level: int, channel: discord.TextChannel):
    if level in LEVEL_ROLLEN_BELOHNUNGEN:
        rollen_name = LEVEL_ROLLEN_BELOHNUNGEN[level]
        rolle = discord.utils.get(member.guild.roles, name=rollen_name)
        if rolle:
            try:
                await member.add_roles(rolle)
                await channel.send(embed=erstelle_embed("🎖️ Neue Level-Rolle!", f"Herzlichen Glückwunsch {member.mention}!\nDu hast Level **{level}** erreicht und erhältst die Rolle **{rolle.name}**!", BotFarben.ERFOLG))
            except discord.Forbidden:
                pass

async def groq_anfrage(messages: list) -> str:
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "llama-3.3-70b-versatile", "messages": messages, "max_tokens": 800}
    async with aiohttp.ClientSession() as session:
        async with session.post(GROQ_URL, headers=headers, json=payload, timeout=25) as resp:
            if resp.status != 200: raise Exception(f"API-Fehler")
            data = await resp.json()
            return data["choices"][0]["message"]["content"]

# ─── UI INTERAKTIONS-KOMPONENTEN ───────────────────────────
class ShopView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    async def handle_buy(self, interaction: discord.Interaction, item_id: str):
        u = state.get_user(str(interaction.user.id)); item = SHOP_ITEMS[item_id]
        if u.muenzen < item["preis"]: return await interaction.response.send_message(embed=fehler_embed("Dein Geld reicht dafür nicht."), ephemeral=True)
        u.muenzen -= item["preis"]; u.inventar[item_id] = u.inventar.get(item_id, 0) + 1; state.speichern()
        await interaction.response.send_message(embed=erstelle_embed("🛒 Gekauft", f"Du hast {item['name']} für **{item['preis']} Münzen** gekauft!", BotFarben.ERFOLG), ephemeral=True)

    @discord.ui.button(label="🍪 Kekse", style=discord.ButtonStyle.secondary, custom_id="persistent:kekse")
    async def buy_kekse(self, interaction: discord.Interaction, button: discord.ui.Button): await self.handle_buy(interaction, "kekse")
    @discord.ui.button(label="🥩 Premium Steak", style=discord.ButtonStyle.secondary, custom_id="persistent:steak")
    async def buy_steak(self, interaction: discord.Interaction, button: discord.ui.Button): await self.handle_buy(interaction, "steak")
    @discord.ui.button(label="🍼 Milchflasche", style=discord.ButtonStyle.secondary, custom_id="persistent:milch")
    async def buy_milch(self, interaction: discord.Interaction, button: discord.ui.Button): await self.handle_buy(interaction, "milch")

class ToolSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=i["name"], description=f"{i['preis']} Münzen", value=k) for k, i in SHOP_ITEMS.items() if i.get("typ") == "tool"]
        super().__init__(placeholder="Wähle eine Spitzhacke zum Kaufen...", min_values=1, max_values=1, options=options)
    async def callback(self, interaction: discord.Interaction):
        u = state.get_user(str(interaction.user.id)); item = SHOP_ITEMS[self.values[0]]
        if u.muenzen < item["preis"]: return await interaction.response.send_message(embed=fehler_embed(f"Du brauchst **{item['preis']} Münzen**!"), ephemeral=True)
        u.muenzen -= item["preis"]; u.aktive_hacke = self.values[0]; u.hacke_haltbarkeit = item["max_uses"]; state.speichern()
        await interaction.response.send_message(embed=erstelle_embed("🛒 Werkzeug gekauft!", f"Du hast die **{item['name']}** gekauft und ausgerüstet!", BotFarben.ERFOLG), ephemeral=True)

class PersonaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        options = [
            discord.SelectOption(label="Standard", emoji="🤖", value="standard"),
            discord.SelectOption(label="Pirat", emoji="🏴‍☠️", value="pirat"),
            discord.SelectOption(label="Lehrer", emoji="👨‍🏫", value="lehrer")
        ]
        self.add_item(discord.ui.Select(placeholder="Wähle eine KI-Persönlichkeit...", options=options))

# ─── BOT KLASSE & INITIALISIERUNG ─────────────────────────
class MyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default(); intents.message_content = True; intents.members = True
        super().__init__(intents=intents); self.tree = app_commands.CommandTree(self)
    async def setup_hook(self): self.add_view(ShopView()); await self.tree.sync()

bot = MyBot()

@bot.event
async def on_ready(): print(f"🤖 Bot läuft! Eingeloggt als Owner-ID-System.")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: return
    user_id = str(message.author.id); u = state.get_user(user_id)
    if len(message.content) > 3 and not message.content.startswith("/"):
        if xp_geben(user_id, random.randint(2, 5)):
            bonus_coins = u.level * 50
            if state.ist_premium(user_id): bonus_coins = int(bonus_coins * 1.25)
            await message.channel.send(embed=erstelle_embed("🎉 Level Up!", f"{message.author.mention} ist nun **Level {u.level}**!", BotFarben.ERFOLG))
        # Passiver Münz-Zufallsgewinn (+25% falls Premium)
        if random.random() < 0.20:
            c = random.randint(1, 5)
            if state.ist_premium(user_id): c = int(c * 1.25)
            u.muenzen += c

# ─── HILFE COMMANDS ────────────────────────────────────────
@bot.tree.command(name="hilfe", description="Zeigt alle normalen Befehle.")
async def hilfe(interaction: discord.Interaction):
    embed = discord.Embed(title="⚙️ Hilfecenter", color=BotFarben.INFO)
    embed.add_field(name="🪙 Wirtschaft & Bank", value="`/money` · `/daily` · `/work` · `/mine` · `/sell` · `/shop` · `/inventory` · `/pay` · `/family-bank`", inline=False)
    embed.add_field(name="🐾 Haustiere", value="`/pet-adopt` · `/pet-status` · `/pet-feed` · `/pet-train` · `/pet-pet` · `/pet-explore` · `/pet-bossfight` · `/pet-duel` · `/pet-leaderboard`", inline=False)
    embed.add_field(name="💞 Familie & Interaktion", value="`/ship` · `/marry` · `/divorce` · `/marry-status` · `/love` · `/family` · `/baby-feed` · `/baby-play` · `/cuddle` · `/kiss`", inline=False)
    embed.add_field(name="🎮 Unterhaltung & KI", value="`/quiz` · `/coinflip` · `/schere-stein` · `/zahlen-raten` · `/ki` · `/persönlichkeit` · `/rank` · `/leaderboard` · `/todo`", inline=False)
    embed.set_footer(text="💎 Premium-Mitglieder nutzen /hilfe-premium für exklusive Befehle!")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="hilfe-premium", description="Zeigt exklusive Premium-Befehle (Nur für VIPs).")
async def hilfe_premium(interaction: discord.Interaction):
    if not state.ist_premium(str(interaction.user.id)) and interaction.user.id != OWNER_ID:
        return await interaction.response.send_message(embed=fehler_embed("Dieses Hilfemenü ist exklusiv für Premium-Mitglieder!"), ephemeral=True)
    
    embed = discord.Embed(title="💎 VIP Gold-Hilfecenter", description="Willkommen im Premium-Bereich! Hier sind deine Privilegien:", color=BotFarben.PREMIUM)
    embed.add_field(name="📈 Passive Boni", value="• **+25% mehr Münzen** bei `/work`, `/mine` & `/daily`.\n• **+25% schnelleres Leveln** bei allen Aktivitäten.", inline=False)
    embed.add_field(name="🗺️ Abenteuer & Bosse (Premium)", value="• Welten im Krater, Schloss oder Chronos-Riss über `/pet-explore`.\n• Epische Endgame-Bosse über `/pet-bossfight`.", inline=False)
    embed.add_field(name="🐾 VIP Zucht", value="Exklusive Tiere adoptieren: *Pegasus, Schattenwolf, Mecha-Greif, Leviathan, Kosmische Katze*.", inline=False)
    embed.add_field(name="🎭 10 Premium-Roleplay Befehle", value=(
        "`/premium-residenz` · `/premium-gift` · `/premium-flex` · `/premium-tea`\n"
        "`/premium-oracle` · `/premium-title` · `/premium-aura` · `/premium-clandance`\n"
        "`/premium-disguise` · `/premium-dice`"
    ), inline=False)
    await interaction.response.send_message(embed=embed)

# ─── ADMIN- & OWNER-SYSTEM (NIGHTLEON1) ───────────────────
@bot.tree.command(name="premium-give", description="Vergibt Premium-Status an einen User (Nur Owner Nightleon1).")
@app_commands.choices(paket=[
    app_commands.Choice(name="1 Monat", value="1m"),
    app_commands.Choice(name="3 Monate", value="3m"),
    app_commands.Choice(name="6 Monate", value="6m"),
    app_commands.Choice(name="Permanent", value="perm")
])
async def premium_give(interaction: discord.Interaction, user: discord.User, paket: app_commands.Choice[str]):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message(embed=fehler_embed("Du bist nicht der Owner (Nightleon1)! Befehl verweigert."), ephemeral=True)
    
    u = state.get_user(str(user.id))
    jetzt = datetime.now(timezone.utc)
    
    if paket.value == "1m":
        bis = jetzt + timedelta(days=30); u.premium_bis = bis.isoformat()
    elif paket.value == "3m":
        bis = jetzt + timedelta(days=90); u.premium_bis = bis.isoformat()
    elif paket.value == "6m":
        bis = jetzt + timedelta(days=180); u.premium_bis = bis.isoformat()
    else:
        u.premium_bis = "permanent"
        
    state.speichern()
    dur = paket.name
    embed = erstelle_embed("💎 Premium aktiviert!", f"Der Owner hat {user.mention} den Premium-Status freigeschaltet!\n⏱️ Paket: **{dur}**", BotFarben.PREMIUM)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="premium-remove", description="Entzieht Premium-Status (Nur Owner Nightleon1).")
async def premium_remove(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message(embed=fehler_embed("Du bist nicht der Owner!"), ephemeral=True)
    
    u = state.get_user(str(user.id))
    u.premium_bis = None
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🗑️ Premium entzogen", f"{user.mention} hat keine VIP-Rechte mehr.", BotFarben.FEHLER))

@bot.tree.command(name="premium-status", description="Zeigt die aktuelle Premium-Laufzeit an.")
async def premium_status(interaction: discord.Interaction):
    u_id = str(interaction.user.id)
    u = state.get_user(u_id)
    if not state.ist_premium(u_id):
        return await interaction.response.send_message(embed=erstelle_embed("🕊️ Premium-Status", "Du hast aktuell kein aktives Premium-Paket.", BotFarben.INFO), ephemeral=True)
    
    if u.premium_bis == "permanent":
        zeit_text = "∞ Lebenslang (Permanent)"
    else:
        bis_dt = datetime.fromisoformat(u.premium_bis)
        rest = bis_dt - datetime.now(timezone.utc)
        zeit_text = f"{bis_dt.strftime('%d.%m.%Y')} ({rest.days} Tage verbleibend)"
        
    await interaction.response.send_message(embed=erstelle_embed("💎 Dein Premium-Status ist AKTIV", f"Auslaufdatum: **{zeit_text}**\nNutze `/hilfe-premium` für deine Vorteile!", BotFarben.PREMIUM))

# ─── ANPASSUNGEN STANDARD-BEFEHLE (BONUS WIRTSCHAFT) ──────
@bot.tree.command(name="daily", description="Tägliche Belohnung.")
async def daily(interaction: discord.Interaction):
    u_id = str(interaction.user.id); u = state.get_user(u_id); jetzt = datetime.now(timezone.utc)
    if u.letztes_daily:
        if (jetzt - datetime.fromisoformat(u.letztes_daily)) < timedelta(days=1):
            return await interaction.response.send_message(embed=fehler_embed("Schon abgeholt!"), ephemeral=True)
            
    geld = 75
    text_add = ""
    if state.ist_premium(u_id):
        geld = int(geld * 1.25)
        text_add = " *(inkl. +25% VIP-Bonus)*"
        
    u.letztes_daily = jetzt.isoformat(); u.muenzen += geld; state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🎁 Daily", f"Du hast **{geld} Münzen** erhalten!{text_add}", BotFarben.ERFOLG))

@bot.tree.command(name="work", description="Arbeiten gehen.")
@app_commands.choices(beruf=[app_commands.Choice(name="👷 Bauarbeiter", value="bau"), app_commands.Choice(name="💻 Programmierer", value="dev")])
async def work(interaction: discord.Interaction, beruf: app_commands.Choice[str]):
    u_id = str(interaction.user.id); u = state.get_user(u_id); jetzt = datetime.now(timezone.utc)
    if u.letzte_arbeit:
        if (jetzt - datetime.fromisoformat(u.letzte_arbeit)) < timedelta(hours=1): 
            return await interaction.response.send_message(embed=fehler_embed("Ruh dich aus!"), ephemeral=True)
            
    u.arbeits_erfahrung += 1
    if u.arbeits_erfahrung >= u.berufs_stufe * 5: u.berufs_stufe += 1
    mult = 1.0 + (u.berufs_stufe - 1) * 0.20
    
    if beruf.value == "bau":
        lohn = int(random.randint(45, 65) * mult)
        text = f"Schicht geschafft: **{lohn} Münzen**."
    else:
        if random.random() < 0.25: lohn = 0; text = "Absturz! **0 Münzen**."
        else: lohn = int(random.randint(70, 140) * mult); text = f"Viral gegangen! **{lohn} Münzen**."
            
    if state.ist_premium(u_id) and lohn > 0:
        lohn = int(lohn * 1.25)
        text += " *(+25% VIP-Bonus)*"
        
    u.muenzen += lohn; u.letzte_arbeit = jetzt.isoformat(); state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("💼 Job", text, BotFarben.WIRTSCHAFT))

# ─── HAUSTIER ADOPT, EXPLORE, BOSS (UPGRADED) ──────────────
@bot.tree.command(name="pet-adopt", description="Adoptiere ein Haustier.")
async def pet_adopt(interaction: discord.Interaction, typ: str, name: str):
    u_id = str(interaction.user.id); u = state.get_user(u_id)
    if u_id in state.pet_daten: return await interaction.response.send_message(embed=fehler_embed("Du hast bereits ein Tier!"), ephemeral=True)
    if typ not in PET_TYPEN: return await interaction.response.send_message(embed=fehler_embed("Tierart existiert nicht."), ephemeral=True)
    
    t_info = PET_TYPEN[typ]
    if t_info["premium"] and not state.ist_premium(u_id):
        return await interaction.response.send_message(embed=fehler_embed("Dieses Tier ist exklusiv für Premium-Mitglieder!"), ephemeral=True)
        
    if u.level < t_info["min_level"] or u.muenzen < t_info["preis"]:
        return await interaction.response.send_message(embed=fehler_embed("Voraussetzungen (Level/Geld) nicht erfüllt."), ephemeral=True)
        
    u.muenzen -= t_info["preis"]
    start_atk = 10 + t_info["atki_bonus"]
    state.pet_daten[u_id] = PetProfile(name=name, typ=typ, atk=start_atk)
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🐾 Tier adoptiert!", f"Herzlichen Glückwunsch zu deinem **{name}** ({typ})!", BotFarben.ERFOLG))

@bot.tree.command(name="pet-explore", description="Schicke dein Tier auf Erkundung.")
async def pet_explore(interaction: discord.Interaction, gebiet: str):
    u_id = str(interaction.user.id); u = state.get_user(u_id); p = state.pet_daten.get(u_id)
    if not p: return await interaction.response.send_message(embed=fehler_embed("Kein Tier."), ephemeral=True)
    if gebiet not in ABENTEUER_GEBIETE: return await interaction.response.send_message(embed=fehler_embed("Gebiet existiert nicht."), ephemeral=True)
    
    g = ABENTEUER_GEBIETE[gebiet]
    if g["premium"] and not state.ist_premium(u_id):
        return await interaction.response.send_message(embed=fehler_embed("Diese Welt erfordert den Premium-Status!"), ephemeral=True)
        
    if p.level < g["min_level"]: return await interaction.response.send_message(embed=fehler_embed("Tier-Level zu niedrig."), ephemeral=True)
    
    # Ausführung des Abenteuers
    schaden = max(0, random.randint(0, g["schaden_max"]) - p.level)
    p.aktuelle_hp = max(1, p.aktuelle_hp - schaden)
    loot = random.choice(g["looten"])
    u.inventar[loot] = u.inventar.get(loot, 0) + 1
    
    if gebiet != "astral" and gebiet != "chronos": # In Astral & Chronos kein Hunger-Abzug
        p.hunger = min(100, p.hunger + g["hunger_kosten"])
        
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed(f"🗺️ Erkundung: {g['name']}", f"Dein Tier brachte 1x **{loot}** zurück!\n💥 Erlitten: -{schaden} HP.", BotFarben.SPIEL))

@bot.tree.command(name="pet-bossfight", description="Kämpfe gegen Bosse.")
async def pet_bossfight(interaction: discord.Interaction, boss_index: int):
    u_id = str(interaction.user.id); u = state.get_user(u_id); p = state.pet_daten.get(u_id)
    if not p: return await interaction.response.send_message(embed=fehler_embed("Kein Tier."), ephemeral=True)
    if boss_index < 0 or boss_index >= len(BOSS_GEGNER): return await interaction.response.send_message(embed=fehler_embed("Boss existiert nicht."), ephemeral=True)
    
    b = BOSS_GEGNER[boss_index]
    if b["premium"] and not state.ist_premium(u_id):
        return await interaction.response.send_message(embed=fehler_embed("Dieser Boss ist exklusiv für Premium-Mitglieder!"), ephemeral=True)
        
    if p.level < b["min_level"]: return await interaction.response.send_message(embed=fehler_embed("Tierstufe zu gering."), ephemeral=True)
    
    # Stark vereinfachte Kampf-Logik
    if p.atk * 10 > b["hp"]:
        m_bel = b["belohnung_muenzen"]
        if state.ist_premium(u_id): m_bel = int(m_bel * 1.25)
        u.muenzen += m_bel
        xp_geben(u_id, b["xp"])
        state.speichern()
        await interaction.response.send_message(embed=erstelle_embed("🏆 Boss besiegt!", f"Sieg über {b['name']}! Belohnung: **+{m_bel} Münzen**.", BotFarben.ERFOLG))
    else:
        await interaction.response.send_message(embed=fehler_embed(f"Niederlage gegen {b['name']}! Trainiere weiter."))

# ─── 10 NEUE EXKLUSIVE PREMIUM-ROLEPLAY BEFEHLE ─────────────
@bot.tree.command(name="premium-residenz", description="Benenne dein eigenes virtuelles Luxus-Zuhause.")
async def premium_residenz(interaction: discord.Interaction, name: str):
    u_id = str(interaction.user.id)
    if not state.ist_premium(u_id): return await interaction.response.send_message(embed=fehler_embed("Nur für VIPs!"), ephemeral=True)
    u = state.get_user(u_id)
    u.premium_residenz_name = name; state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🏰 Luxus-Residenz", f"{interaction.user.mention} hat seine Residenz feierlich auf den Namen **„{name}“** getauft!", BotFarben.PREMIUM))

@bot.tree.command(name="premium-gift", description="Verpacke ein Item edel und verschenke es.")
async def premium_gift(interaction: discord.Interaction, empfaenger: discord.Member, item: str):
    u_id = str(interaction.user.id)
    if not state.ist_premium(u_id): return await interaction.response.send_message(embed=fehler_embed("Nur für VIPs!"), ephemeral=True)
    u = state.get_user(u_id); empf = state.get_user(str(empfaenger.id))
    if u.inventar.get(item, 0) <= 0: return await interaction.response.send_message(embed=fehler_embed("Du hast dieses Item nicht."), ephemeral=True)
    
    u.inventar[item] -= 1; empf.inventar[item] = empf.inventar.get(item, 0) + 1; state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🎁 VIP-Geschenk", f"✨ {interaction.user.mention} überreicht {empfaenger.mention} eine edel funkelnde Premium-Geschenkbox mit **1x {item}**! 🎉", BotFarben.PREMIUM))

@bot.tree.command(name="premium-flex", description="Protze im Chat mit deinem Reichtum.")
async def premium_flex(interaction: discord.Interaction):
    if not state.ist_premium(str(interaction.user.id)): return await interaction.response.send_message(embed=fehler_embed("Nur für VIPs!"), ephemeral=True)
    u = state.get_user(str(interaction.user.id))
    sprueche = [
        f"lässt seine **{u.muenzen} Münzen** so laut klimpern, dass der gesamte Server wegschaut! 🪙😎",
        f"winkt lässig mit Geldscheinen und bestellt Champagner für das gesamte Haustiergehege! 🥂",
        f"zeigt stolz sein High-End Equipment. Eure Armut widert ihn dezent an! 💎🛡️"
    ]
    await interaction.response.send_message(f"👑 **[VIP Flex]** {interaction.user.mention} {random.choice(sprueche)}")

@bot.tree.command(name="premium-tea", description="Lade jemanden in die VIP-Lounge ein (+Bonus XP).")
async def premium_tea(interaction: discord.Interaction, gast: discord.Member):
    if not state.ist_premium(str(interaction.user.id)): return await interaction.response.send_message(embed=fehler_embed("Nur für VIPs!"), ephemeral=True)
    xp_geben(str(interaction.user.id), 25); xp_geben(str(gast.id), 25)
    await interaction.response.send_message(embed=erstelle_embed("☕ VIP-Lounge", f"🫖 {interaction.user.mention} hat {gast.mention} zu einer exquisiten Tasse Tee in den VIP-Salon eingeladen. Beide erhalten **+25 XP** für die feine Konversation!", BotFarben.PREMIUM))

@bot.tree.command(name="premium-oracle", description="Befrage das Premium-Orakel nach deiner Zukunft.")
async def premium_oracle(interaction: discord.Interaction):
    if not state.ist_premium(str(interaction.user.id)): return await interaction.response.send_message(embed=fehler_embed("Nur für VIPs!"), ephemeral=True)
    await interaction.response.defer()
    weisheiten = [
        "Die Sterne stehen günstig. Dein Haustier wird bald legendäre Reichtümer finden!",
        "Ein dunkler Schatten nähert sich der Mine... Nimm beim nächsten Mal eine stärkere Hacke mit!",
        "Die kosmischen Ströme besagen: Deine nächste Ehe-Überweisung wird vom Glück gesegnet sein."
    ]
    await interaction.followup.send(embed=erstelle_embed("🔮 Das Premium-Orakel spricht", random.choice(weisheiten), BotFarben.PREMIUM))

@bot.tree.command(name="premium-title", description="Lege einen Suffix-Prestige-Titel fest.")
async def premium_title(interaction: discord.Interaction, titel: str):
    u_id = str(interaction.user.id)
    if not state.ist_premium(u_id): return await interaction.response.send_message(embed=fehler_embed("Nur für VIPs!"), ephemeral=True)
    u = state.get_user(u_id); u.premium_titel = titel; state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🎖️ Titel vergeben", f"Dein Profil trägt nun den Prestige-Titel: `[{titel}]`", BotFarben.PREMIUM))

@bot.tree.command(name="premium-aura", description="Aktiviere eine leuchtende magische Aura.")
@app_commands.choices(aura=[app_commands.Choice(name="🔥 Feuer", value="Feuer"), app_commands.Choice(name="⚡ Neon", value="Neon"), app_commands.Choice(name="🌌 Astral", value="Astral")])
async def premium_aura(interaction: discord.Interaction, aura: app_commands.Choice[str]):
    u_id = str(interaction.user.id)
    if not state.ist_premium(u_id): return await interaction.response.send_message(embed=fehler_embed("Nur für VIPs!"), ephemeral=True)
    u = state.get_user(u_id); u.premium_aura = aura.value; state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("✨ Aura entfesselt", f"Dich umgibt nun die mystische **{aura.value}-Aura**!", BotFarben.PREMIUM))

@bot.tree.command(name="premium-clandance", description="Starte einen VIP-Siegestanz mit einem Freund.")
async def premium_clandance(interaction: discord.Interaction, partner: discord.Member):
    if not state.ist_premium(str(interaction.user.id)): return await interaction.response.send_message(embed=fehler_embed("Nur für VIPs!"), ephemeral=True)
    await interaction.response.send_message(f"💃🕺 **[VIP-Tanz]** {interaction.user.mention} und {partner.mention} vollführen einen perfekt synchronisierten, golden funkelnden Ritualtanz im Chat! Die Menge tobt! 💫")

@bot.tree.command(name="premium-disguise", description="Verkleide dein Tier kosmetisch.")
async def premium_disguise(interaction: discord.Interaction, verkleidung: str):
    u_id = str(interaction.user.id); p = state.pet_daten.get(u_id)
    if not state.ist_premium(u_id): return await interaction.response.send_message(embed=fehler_embed("Nur für VIPs!"), ephemeral=True)
    if not p: return await interaction.response.send_message(embed=fehler_embed("Kein Tier vorhanden."), ephemeral=True)
    
    p.premium_verkleidung = verkleidung; state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🎭 Haustier-Kostüm", f"**{p.name}** trägt nun das exklusive Kostüm: **{verkleidung}**!", BotFarben.PREMIUM))

@bot.tree.command(name="premium-dice", description="High-Stakes VIP Würfelspiel.")
async def premium_dice(interaction: discord.Interaction):
    if not state.ist_premium(str(interaction.user.id)): return await interaction.response.send_message(embed=fehler_embed("Nur für VIPs!"), ephemeral=True)
    w1, w2 = random.randint(1, 6), random.randint(1, 6)
    ges = w1 + w2
    await interaction.response.send_message(embed=erstelle_embed("🎲 VIP-Würfel", f"Du hast gewürfelt: ⚀ **{w1}** und ⚁ **{w2}**.\nGesamtergebnis: **{ges}**!", BotFarben.PREMIUM))

# ─── PROFILKARTE ERWEITERUNG ──────────────────────────────
@bot.tree.command(name="rank", description="Zeigt deine Profil-Karte.")
async def rank(interaction: discord.Interaction):
    u_id = str(interaction.user.id)
    u = state.get_user(u_id)
    
    titel_str = f" `{u.premium_titel}`" if u.premium_titel else ""
    aura_str = f"\n• Aktive Aura: **{u.premium_aura}**" if u.premium_aura else ""
    res_str = f"\n• Residenz: **{u.premium_residenz_name}**" if u.premium_residenz_name else ""
    vip_tag = " [💎 VIP-Mitglied]" if state.ist_premium(u_id) else ""
    
    benoetigt_xp = u.level * 100
    balken = generiere_fortschrittsbalken(u.xp, benoetigt_xp)
    
    profil_text = (
        f"• Name/Titel: {interaction.user.mention}{titel_str}{vip_tag}\n"
        f"• Level: **{u.level}**\n"
        f"• XP-Fortschritt: `{u.xp} / {benoetigt_xp} XP`\n"
        f"📊 {balken}\n\n"
        f"• Münzen: `🪙 {u.muenzen}`"
        f"{aura_str}{res_str}"
    )
    
    farbe = BotFarben.PREMIUM if state.ist_premium(u_id) else BotFarben.INFO
    await interaction.response.send_message(embed=erstelle_embed("⭐ Charakter-Profil", profil_text, farbe))

# ─── WEITERE UNTERHALTUNGSBEFEHLE & FALLBACKS ─────────────
@bot.tree.command(name="money", description="Kontostand.")
async def money(interaction: discord.Interaction):
    u = state.get_user(str(interaction.user.id))
    await interaction.response.send_message(embed=erstelle_embed("🪙 Kontostand", f"Du besitzt **{u.muenzen} Münzen**.", BotFarben.WIRTSCHAFT))

bot.run(DISCORD_TOKEN)

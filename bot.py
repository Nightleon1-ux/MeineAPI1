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

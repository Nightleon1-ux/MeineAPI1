import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import random
import asyncio
import aiofiles
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from typing import Dict, Any, Optional

# --- BRANDING & DESIGN (FARBEN) ---
class Colors:
    DEFAULT = 0x3498db      # Blau (Standard)
    SUCCESS = 0x2ecc71      # Grün (Erfolg)
    ERROR = 0xe74c3c        # Rot (Fehler)
    WARNING = 0xf1c40f      # Gelb (Warnung)
    INFO = 0x9b59b6         # Lila (Information)
    ECONOMY = 0xe67e22      # Orange (Wirtschaft)
    PET = 0x1abc9c          # Türkis (Haustiere)
    PREMIUM = 0x9b59b6      # VIP-Lila

# --- GLOBAL DATABASES & CONFIG ---
# Alle Gegenstände, die man besitzen oder nutzen kann
ALL_ITEMS = {
    "apple": {"name": "🍎 Apfel", "hunger": -3},
    "banana": {"name": "🍌 Banane", "hunger": -4},
    "pet_food": {"name": "🍖 Standard-Tierfutter", "hunger": -8},
    "health_potion": {"name": "🧪 Heiltrank (50 HP)", "heal": 50},
    "elixir": {"name": "🧪 Elixier der Götter (200 HP)", "heal": 200},
    "golden_apple": {"name": "🍏 Goldenes Futter", "hunger": -20}
}

# Vollständiger Haustier-Katalog (Normal & Premium)
PET_TYPES = {
    "cat": {"name": "🐱 Katze", "base_hp": 80, "base_atk": 8, "premium": False, "rarity": "common"},
    "dog": {"name": "🐶 Hund", "base_hp": 90, "base_atk": 10, "premium": False, "rarity": "common"},
    "rabbit": {"name": "🐰 Hase", "base_hp": 70, "base_atk": 6, "premium": False, "rarity": "common"},
    "bird": {"name": "🐦 Vogel", "base_hp": 65, "base_atk": 9, "premium": False, "rarity": "common"},
    "hamster": {"name": "🐹 Hamster", "base_hp": 60, "base_atk": 5, "premium": False, "rarity": "common"},
    "slime_king": {"name": "👑 Schleim-König", "base_hp": 200, "base_atk": 12, "premium": False, "rarity": "uncommon"},
    "astral_lynx": {"name": "🐱 Astral-Luchs", "base_hp": 140, "base_atk": 22, "premium": False, "rarity": "rare"},
    # Premium-Kreaturen
    "pegasus": {"name": "🦄 Pegasus", "base_hp": 165, "base_atk": 16, "premium": True, "rarity": "rare"},
    "void_demon": {"name": "👿 Void-Dämon", "base_hp": 180, "base_atk": 32, "premium": True, "rarity": "epic"},
    "kraken": {"name": "🦑 Tiefsee-Kraken", "base_hp": 230, "base_atk": 28, "premium": True, "rarity": "legendary"},
    "kirin": {"name": "⚡ Mythisches Kirin", "base_hp": 270, "base_atk": 32, "premium": True, "rarity": "legendary"},
    "phoenix": {"name": "🔥 Unsterblicher Phönix", "base_hp": 250, "base_atk": 35, "premium": True, "rarity": "mythic"},
    "cyber_dragon": {"name": "⚡ Cyber-Drache", "base_hp": 300, "base_atk": 40, "premium": True, "rarity": "mythic"},
    "grim_reaper": {"name": "💀 Seelenschnitter", "base_hp": 220, "base_atk": 45, "premium": True, "rarity": "mythic"}
}

# --- DATA STRUCTURES (DATEN-MODELLE) ---
class PetProfile:
    def __init__(self, name: str, type: str, max_hp: int, current_hp: int, atk: int, 
                 level: int = 1, xp: int = 0, hunger: int = 0, happiness: int = 100, 
                 last_adventure: Optional[str] = None, last_premium_train: Optional[str] = None,
                 last_premium_bless: Optional[str] = None, evolved: bool = False):
        self.name = name
        self.type = type
        self.max_hp = max_hp
        self.current_hp = current_hp
        self.atk = atk
        self.level = level
        self.xp = xp
        self.hunger = hunger
        self.happiness = happiness
        self.last_adventure = last_adventure
        self.last_premium_train = last_premium_train
        self.last_premium_bless = last_premium_bless
        self.evolved = evolved

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)

class UserProfile:
    def __init__(self, server_id: int, coins: int = 100, family_coins: int = 0, 
                 xp: int = 0, level: int = 1, job: Optional[str] = None, 
                 job_level: int = 1, last_work: Optional[str] = None, 
                 last_daily: Optional[str] = None, last_interest_claim: Optional[str] = None,
                 last_premium_claim: Optional[str] = None, wins: int = 0, losses: int = 0,
                 inventory: Optional[Dict[str, int]] = None):
        self.server_id = server_id
        self.coins = coins
        self.family_coins = family_coins  # Wird hier als Bankguthaben genutzt
        self.xp = xp
        self.level = level
        self.job = job
        self.job_level = job_level
        self.last_work = last_work
        self.last_daily = last_daily
        self.last_interest_claim = last_interest_claim
        self.last_premium_claim = last_premium_claim
        self.wins = wins
        self.losses = losses
        self.inventory = inventory if inventory is not None else {}

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)

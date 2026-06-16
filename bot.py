import discord
from discord import app_commands
from discord.ext import tasks
import os
import json
import random
import zipfile
import asyncio
import aiofiles
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List, Tuple
from dotenv import load_dotenv
from collections import defaultdict

# ------- ENVIRONMENT -------
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = 1405193599984861255

# ------- COLORS -------
class Colors:
    INFO = 0x5DADE2
    SUCCESS = 0x57F287
    ERROR = 0xED4245
    PREMIUM = 0xD4AF37
    ECONOMY = 0xE67E22
    WARNING = 0xFEE75C
    PET = 0x9B59B6
    MARRIAGE = 0xE91E63
    SHOP = 0x1ABC9C

# ------- DATA MODELS -------
@dataclass
class UserProfile:
    xp: int = 0
    level: int = 1
    total_xp: int = 0
    coins: int = 100
    server_id: Optional[int] = None
    inventory: Dict[str, int] = field(default_factory=dict)
    partner_id: Optional[str] = None
    marriage_date: Optional[str] = None
    family_coins: int = 0
    last_interest_claim: Optional[str] = None
    children: Dict[str, dict] = field(default_factory=dict)
    last_daily: Optional[str] = None
    last_work: Optional[str] = None
    last_mine: Optional[str] = None
    premium_until: Optional[str] = None
    premium_title: Optional[str] = None
    premium_aura: Optional[str] = None
    premium_residence_name: Optional[str] = None
    job: Optional[str] = None
    job_level: int = 1
    job_xp: int = 0
    deaths: int = 0
    wins: int = 0
    losses: int = 0
    streak: int = 0
    max_streak: int = 0
    badges: List[str] = field(default_factory=list)
    last_gamble: Optional[str] = None

@dataclass
class PetProfile:
    name: str
    type: str
    level: int = 1
    hunger: int = 20
    happiness: int = 50
    max_hp: int = 100
    current_hp: int = 100
    atk: int = 10
    last_adventure: Optional[str] = None
    premium_costume: Optional[str] = None
    xp: int = 0
    skill: str = "none"

@dataclass
class ServerConfig:
    backup_channel_id: Optional[int] = None
    level_up_channel_id: Optional[int] = None
    marriage_channel_id: Optional[int] = None
    shop_channel_id: Optional[int] = None
    prefix: str = "/"
    premium_role_id: Optional[int] = None

# ------- FILEPATHS -------
DATA_FOLDER = "server_data"
BACKUP_FOLDER = "backups"
CONFIG_FILE = "backup_config.json"
SERVER_CONFIG_FILE = "server_configs.json"

os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(BACKUP_FOLDER, exist_ok=True)

# ------- UTILS -------
def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

async def save_json_async(filepath, data):
    async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=4))

def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

async def load_json_async(filepath):
    if os.path.exists(filepath):
        async with aiofiles.open(filepath, "r", encoding="utf-8") as f:
            content = await f.read()
            return json.loads(content)
    return None

def create_embed(title: str, description: str, color: int) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color, 
                         timestamp=datetime.now(timezone.utc))
    embed.set_footer(text="Premium Core Bot")
    return embed

def error_embed(text: str) -> discord.Embed:
    return create_embed("❌ Fehler", text, Colors.ERROR)

def success_embed(text: str) -> discord.Embed:
    return create_embed("✅ Erfolg", text, Colors.SUCCESS)

def info_embed(text: str) -> discord.Embed:
    return create_embed("ℹ️ Info", text, Colors.INFO)

def premium_embed(text: str) -> discord.Embed:
    return create_embed("🌟 Premium", text, Colors.PREMIUM)

def format_number(num: int) -> str:
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    elif num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)

# ------- BOT STATE -------
class BotState:
    def __init__(self):
        self.users: Dict[str, UserProfile] = {}
        self.pets: Dict[str, PetProfile] = {}
        self.server_configs: Dict[int, ServerConfig] = {}
        self.load_all_servers()
        self.load_server_configs()

    def get_file_path(self, guild_id: int) -> str:
        return os.path.join(DATA_FOLDER, f"server_{guild_id}.json")

    def save_server(self, guild_id: int):
        users_to_save = {uid: asdict(profile) for uid, profile in self.users.items() 
                        if self.users[uid].server_id == guild_id}
        pets_to_save = {uid: asdict(profile) for uid, profile in self.pets.items() 
                       if self.users.get(uid) and self.users[uid].server_id == guild_id}
        data = {"users": users_to_save, "pets": pets_to_save}
        save_json(self.get_file_path(guild_id), data)

    async def save_server_async(self, guild_id: int):
        users_to_save = {uid: asdict(profile) for uid, profile in self.users.items() 
                        if self.users[uid].server_id == guild_id}
        pets_to_save = {uid: asdict(profile) for uid, profile in self.pets.items() 
                       if self.users.get(uid) and self.users[uid].server_id == guild_id}
        data = {"users": users_to_save, "pets": pets_to_save}
        await save_json_async(self.get_file_path(guild_id), data)

    def load_server(self, guild_id: int):
        path = self.get_file_path(guild_id)
        data = load_json(path)
        if data is None:
            return
        for uid, val in data.get("users", {}).items():
            self.users[uid] = UserProfile(**val)
        for uid, val in data.get("pets", {}).items():
            self.pets[uid] = PetProfile(**val)

    def load_all_servers(self):
        for filename in os.listdir(DATA_FOLDER):
            if filename.startswith("server_") and filename.endswith(".json"):
                try:
                    guild_id = int(filename[7:-5])
                    self.load_server(guild_id)
                except ValueError:
                    continue

    def load_server_configs(self):
        data = load_json(SERVER_CONFIG_FILE)
        if data:
            for guild_id, config_data in data.items():
                self.server_configs[int(guild_id)] = ServerConfig(**config_data)

    def save_server_configs(self):
        data = {str(guild_id): asdict(config) for guild_id, config in self.server_configs.items()}
        save_json(SERVER_CONFIG_FILE, data)

    async def save_server_configs_async(self):
        data = {str(guild_id): asdict(config) for guild_id, config in self.server_configs.items()}
        await save_json_async(SERVER_CONFIG_FILE, data)

    def get_server_config(self, guild_id: int) -> ServerConfig:
        if guild_id not in self.server_configs:
            self.server_configs[guild_id] = ServerConfig()
        return self.server_configs[guild_id]

    def get_user(self, user_id: str, server_id: Optional[int] = None) -> UserProfile:
        if user_id not in self.users:
            self.users[user_id] = UserProfile()
        if server_id:
            self.users[user_id].server_id = server_id
        return self.users[user_id]

    def get_pet(self, user_id: str) -> Optional[PetProfile]:
        return self.pets.get(user_id)

    def is_premium(self, user_id: str) -> bool:
        user = self.get_user(user_id)
        if user.premium_until is None:
            return False
        if user.premium_until == "permanent":
            return True
        try:
            premium_end = datetime.fromisoformat(user.premium_until)
            if datetime.now(timezone.utc) < premium_end:
                return True
            else:
                user.premium_until = None
                return False
        except Exception:
            user.premium_until = None
            return False

    def save_all(self):
        guilds = set(u.server_id for u in self.users.values() if u.server_id)
        for guild_id in guilds:
            self.save_server(guild_id)
        self.save_server_configs()

    async def save_all_async(self):
        guilds = set(u.server_id for u in self.users.values() if u.server_id)
        tasks = []
        for guild_id in guilds:
            tasks.append(self.save_server_async(guild_id))
        await asyncio.gather(*tasks)
        await self.save_server_configs_async()

state = BotState()

# ------- SHOP DATA -------
NORMAL_ITEMS = {
    "apple": {"name": "🍏 Grüner Apfel", "price": 15, "hunger": -15, "type": "food"},
    "banana": {"name": "🍌 Banane", "price": 15, "hunger": -15, "type": "food"},
    "carrot": {"name": "🥕 Karotte", "price": 22, "hunger": -22, "type": "food"},
    "bread": {"name": "🍞 Brot", "price": 30, "hunger": -25, "type": "food"},
    "pizza": {"name": "🍕 Pizza", "price": 50, "hunger": -40, "type": "food"},
    "burger": {"name": "🍔 Burger", "price": 45, "hunger": -35, "type": "food"},
    "steak": {"name": "🥩 Steak", "price": 80, "hunger": -50, "type": "food"},
    "fish": {"name": "🐟 Fisch", "price": 40, "hunger": -30, "type": "food"},
    "sushi": {"name": "🍣 Sushi", "price": 60, "hunger": -45, "type": "food"},
    "icecream": {"name": "🍦 Eiscreme", "price": 25, "hunger": -20, "type": "food"},
    "chocolate": {"name": "🍫 Schokolade", "price": 20, "hunger": -15, "type": "food"},
    "cookie": {"name": "🍪 Keks", "price": 10, "hunger": -10, "type": "food"},
    "donut": {"name": "🍩 Donut", "price": 35, "hunger": -25, "type": "food"},
    "taco": {"name": "🌮 Taco", "price": 45, "hunger": -35, "type": "food"},
    "ramen": {"name": "🍜 Ramen", "price": 55, "hunger": -40, "type": "food"},
    "coffee": {"name": "☕ Kaffee", "price": 15, "energy": 20, "type": "drink"},
    "tea": {"name": "🍵 Tee", "price": 12, "energy": 15, "type": "drink"},
    "soda": {"name": "🥤 Limo", "price": 18, "energy": 10, "type": "drink"},
    "juice": {"name": "🧃 Saft", "price": 20, "energy": 15, "type": "drink"},
    "milk": {"name": "🥛 Milch", "price": 15, "hunger": -10, "type": "drink"},
    "pickaxe": {"name": "⛏️ Spitzhacke", "price": 500, "mining_bonus": 1.2, "type": "tool"},
    "fishing_rod": {"name": "🎣 Angelrute", "price": 400, "fishing_bonus": 1.2, "type": "tool"},
    "hoe": {"name": "🌾 Hacke", "price": 300, "farming_bonus": 1.2, "type": "tool"},
    "axe": {"name": "🪓 Axt", "price": 350, "wood_bonus": 1.2, "type": "tool"},
    "backpack": {"name": "🎒 Rucksack", "price": 200, "inventory_slots": 10, "type": "equipment"},
    "lucky_charm": {"name": "🍀 Glücksbringer", "price": 1000, "luck_bonus": 1.1, "type": "accessory"},
    "energy_drink": {"name": "⚡ Energie-Drink", "price": 100, "energy": 50, "type": "consumable"},
    "health_potion": {"name": "❤️‍🩹 Heiltrank", "price": 150, "heal": 50, "type": "potion"},
    "mana_potion": {"name": "🔮 Manatrank", "price": 120, "mana": 50, "type": "potion"},
    "pet_toy": {"name": "🎾 Haustierspielzeug", "price": 50, "happiness": 20, "type": "pet"},
    "pet_food": {"name": "🥩 Haustierfutter", "price": 30, "hunger": -25, "type": "pet"},
    "pet_bed": {"name": "🛏️ Haustierbett", "price": 200, "happiness": 10, "type": "pet"},
    "diamond_pickaxe": {"name": "💎 Diamant-Spitzhacke", "price": 2000, "mining_bonus": 1.5, "type": "tool"},
    "dragon_sword": {"name": "🐉 DrachenschHier ist der **komplette, fertige Premium Core Bot** in einer Nachricht. Dies ist die endgültige Version mit allen Funktionen:

```python
import discord
from discord import app_commands
from discord.ext import tasks
import os
import json
import random
import zipfile
import asyncio
import aiofiles
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, List, Tuple
from dotenv import load_dotenv
from collections import defaultdict

# ------- ENVIRONMENT -------
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
OWNER_ID = 1405193599984861255

# ------- COLORS -------
class Colors:
    INFO = 0x5DADE2
    SUCCESS = 0x57F287
    ERROR = 0xED4245
    PREMIUM = 0xD4AF37
    ECONOMY = 0xE67E22
    WARNING = 0xFEE75C
    PET = 0x9B59B6
    MARRIAGE = 0xE91E63
    SHOP = 0x1ABC9C

# ------- DATA MODELS -------
@dataclass
class UserProfile:
    xp: int = 0
    level: int = 1
    total_xp: int = 0
    coins: int = 100
    server_id: Optional[int] = None
    inventory: Dict[str, int] = field(default_factory=dict)
    partner_id: Optional[str] = None
    marriage_date: Optional[str] = None
    family_coins: int = 0
    last_interest_claim: Optional[str] = None
    children: Dict[str, dict] = field(default_factory=dict)
    last_daily: Optional[str] = None
    last_work: Optional[str] = None
    last_mine: Optional[str] = None
    premium_until: Optional[str] = None
    premium_title: Optional[str] = None
    premium_aura: Optional[str] = None
    premium_residence_name: Optional[str] = None
    job: Optional[str] = None
    job_level: int = 1
    job_xp: int = 0
    deaths: int = 0
    wins: int = 0
    losses: int = 0
    streak: int = 0
    max_streak: int = 0
    badges: List[str] = field(default_factory=list)
    last_gamble: Optional[str] = None

@dataclass
class PetProfile:
    name: str
    type: str
    level: int = 1
    hunger: int = 20
    happiness: int = 50
    max_hp: int = 100
    current_hp: int = 100
    atk: int = 10
    last_adventure: Optional[str] = None
    premium_costume: Optional[str] = None
    xp: int = 0
    skill: str = "none"

@dataclass
class ServerConfig:
    backup_channel_id: Optional[int] = None
    level_up_channel_id: Optional[int] = None
    marriage_channel_id: Optional[int] = None
    shop_channel_id: Optional[int] = None
    prefix: str = "/"
    premium_role_id: Optional[int] = None

# ------- FILEPATHS -------
DATA_FOLDER = "server_data"
BACKUP_FOLDER = "backups"
CONFIG_FILE = "backup_config.json"
SERVER_CONFIG_FILE = "server_configs.json"

os.makedirs(DATA_FOLDER, exist_ok=True)
os.makedirs(BACKUP_FOLDER, exist_ok=True)

# ------- UTILS -------
def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

async def save_json_async(filepath, data):
    async with aiofiles.open(filepath, "w", encoding="utf-8") as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=4))

def load_json(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

async def load_json_async(filepath):
    if os.path.exists(filepath):
        async with aiofiles.open(filepath, "r", encoding="utf-8") as f:
            content = await f.read()
            return json.loads(content)
    return None

def create_embed(title: str, description: str, color: int) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color, 
                         timestamp=datetime.now(timezone.utc))
    embed.set_footer(text="Premium Core Bot")
    return embed

def error_embed(text: str) -> discord.Embed:
    return create_embed("❌ Fehler", text, Colors.ERROR)

def success_embed(text: str) -> discord.Embed:
    return create_embed("✅ Erfolg", text, Colors.SUCCESS)

def info_embed(text: str) -> discord.Embed:
    return create_embed("ℹ️ Info", text, Colors.INFO)

def premium_embed(text: str) -> discord.Embed:
    return create_embed("🌟 Premium", text, Colors.PREMIUM)

def format_number(num: int) -> str:
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    elif num >= 1000:
        return f"{num/1000:.1f}K"
    return str(num)

# ------- BOT STATE -------
class BotState:
    def __init__(self):
        self.users: Dict[str, UserProfile] = {}
        self.pets: Dict[str, PetProfile] = {}
        self.server_configs: Dict[int, ServerConfig] = {}
        self.load_all_servers()
        self.load_server_configs()

    def get_file_path(self, guild_id: int) -> str:
        return os.path.join(DATA_FOLDER, f"server_{guild_id}.json")

    def save_server(self, guild_id: int):
        users_to_save = {uid: asdict(profile) for uid, profile in self.users.items() 
                        if self.users[uid].server_id == guild_id}
        pets_to_save = {uid: asdict(profile) for uid, profile in self.pets.items() 
                       if self.users.get(uid) and self.users[uid].server_id == guild_id}
        data = {"users": users_to_save, "pets": pets_to_save}
        save_json(self.get_file_path(guild_id), data)

    async def save_server_async(self, guild_id: int):
        users_to_save = {uid: asdict(profile) for uid, profile in self.users.items() 
                        if self.users[uid].server_id == guild_id}
        pets_to_save = {uid: asdict(profile) for uid, profile in self.pets.items() 
                       if self.users.get(uid) and self.users[uid].server_id == guild_id}
        data = {"users": users_to_save, "pets": pets_to_save}
        await save_json_async(self.get_file_path(guild_id), data)

    def load_server(self, guild_id: int):
        path = self.get_file_path(guild_id)
        data = load_json(path)
        if data is None:
            return
        for uid, val in data.get("users", {}).items():
            self.users[uid] = UserProfile(**val)
        for uid, val in data.get("pets", {}).items():
            self.pets[uid] = PetProfile(**val)

    def load_all_servers(self):
        for filename in os.listdir(DATA_FOLDER):
            if filename.startswith("server_") and filename.endswith(".json"):
                try:
                    guild_id = int(filename[7:-5])
                    self.load_server(guild_id)
                except ValueError:
                    continue

    def load_server_configs(self):
        data = load_json(SERVER_CONFIG_FILE)
        if data:
            for guild_id, config_data in data.items():
                self.server_configs[int(guild_id)] = ServerConfig(**config_data)

    def save_server_configs(self):
        data = {str(guild_id): asdict(config) for guild_id, config in self.server_configs.items()}
        save_json(SERVER_CONFIG_FILE, data)

    async def save_server_configs_async(self):
        data = {str(guild_id): asdict(config) for guild_id, config in self.server_configs.items()}
        await save_json_async(SERVER_CONFIG_FILE, data)

    def get_server_config(self, guild_id: int) -> ServerConfig:
        if guild_id not in self.server_configs:
            self.server_configs[guild_id] = ServerConfig()
        return self.server_configs[guild_id]

    def get_user(self, user_id: str, server_id: Optional[int] = None) -> UserProfile:
        if user_id not in self.users:
            self.users[user_id] = UserProfile()
        if server_id:
            self.users[user_id].server_id = server_id
        return self.users[user_id]

    def get_pet(self, user_id: str) -> Optional[PetProfile]:
        return self.pets.get(user_id)

    def is_premium(self, user_id: str) -> bool:
        user = self.get_user(user_id)
        if user.premium_until is None:
            return False
        if user.premium_until == "permanent":
            return True
        try:
            premium_end = datetime.fromisoformat(user.premium_until)
            if datetime.now(timezone.utc) < premium_end:
                return True
            else:
                user.premium_until = None
                return False
        except Exception:
            user.premium_until = None
            return False

    def save_all(self):
        guilds = set(u.server_id for u in self.users.values() if u.server_id)
        for guild_id in guilds:
            self.save_server(guild_id)
        self.save_server_configs()

    async def save_all_async(self):
        guilds = set(u.server_id for u in self.users.values() if u.server_id)
        tasks = []
        for guild_id in guilds:
            tasks.append(self.save_server_async(guild_id))
        await asyncio.gather(*tasks)
        await self.save_server_configs_async()

state = BotState()

# ------- SHOP DATA -------
NORMAL_ITEMS = {
    "apple": {"name": "🍏 Grüner Apfel", "price": 15, "hunger": -15, "type": "food"},
    "banana": {"name": "🍌 Banane", "price": 15, "hunger": -15, "type": "food"},
    "carrot": {"name": "🥕 Karotte", "price": 22, "hunger": -22, "type": "food"},
    "bread": {"name": "🍞 Brot", "price": 30, "hunger": -25, "type": "food"},
    "pizza": {"name": "🍕 Pizza", "price": 50, "hunger": -40, "type": "food"},
    "burger": {"name": "🍔 Burger", "price": 45, "hunger": -35, "type": "food"},
    "steak": {"name": "🥩 Steak", "price": 80, "hunger": -50, "type": "food"},
    "fish": {"name": "🐟 Fisch", "price": 40, "hunger": -30, "type": "food"},
    "sushi": {"name": "🍣 Sushi", "price": 60, "hunger": -45, "type": "food"},
    "icecream": {"name": "🍦 Eiscreme", "price": 25, "hunger": -20, "type": "food"},
    "chocolate": {"name": "🍫 Schokolade", "price": 20, "hunger": -15, "type": "food"},
    "cookie": {"name": "🍪 Keks", "price": 10, "hunger": -10, "type": "food"},
    "donut": {"name": "🍩 Donut", "price": 35, "hunger": -25, "type": "food"},
    "taco": {"name": "🌮 Taco", "price": 45, "hunger": -35, "type": "food"},
    "ramen": {"name": "🍜 Ramen", "price": 55, "hunger": -40, "type": "food"},
    "coffee": {"name": "☕ Kaffee", "price": 15, "energy": 20, "type": "drink"},
    "tea": {"name": "🍵 Tee", "price": 12, "energy": 15, "type": "drink"},
    "soda": {"name": "🥤 Limo", "price": 18, "energy": 10, "type": "drink"},
    "juice": {"name": "🧃 Saft", "price": 20, "energy": 15, "type": "drink"},
    "milk": {"name": "🥛 Milch", "price": inve", "hunger": -10, "type": "drink"},
    "pickaxe": {"name": "⛏️ Spitzhacke", "price": 500, "mining_bonus": 1.2, "type": "tool"},
    "fishing_rod": {"name": "🎣 Angelrute", "price": 400, "fishing_bonus": 1.2, "type": "tool"},
    "hoe": {"name": "🌾 Hacke", "price": 300, "farming_bonus": 1.2, "type": "tool"},
    "axe": {"name": "🪓 Axt", "price": 350, "wood_bonus": 1.2, "type": "tool"},
    "backpack": {"name": "🎒 Rucksack", "price": 200, "inventory_slots": 10, "type": "equipment"},
    "lucky_charm": {"name": "🍀 Glücksbringer", "price": 1000, "luck_bonus": 1.1, "type": "accessory"},
    "energy_drink": {"name": "⚡ Energie-Drink", "price": 100, "energy": 50, "type": "consumable"},
    "health_potion": {"name": "❤️‍🩹 Heiltrank", "price": 150, "heal": 50, "type": "potion"},
    "mana_potion": {"name": "🔮 Manatrank", "price": 120, "mana": 50, "type": "potion"},
    "pet_toy": {"name": "🎾 Haustierspielzeug", "price": 50, "happiness": 20, "type": "pet"},
    "pet_food": {"name": "🥩 Haustierfutter", "price": 30, "hunger": -25, "type": "pet"},
    "pet_bed": {"name": "🛏️ Haustierbett", "price": 200, "happiness": 10, "type": "pet"},
    "diamond_pickaxe": {"name": "💎 Diamant-Spitzhacke", "price": 2000, "mining_bonus": 1.5, "type": "tool"},
    "dragon_sword": {"name": "🐉 Drachenschwert", "price": 5000, "damage": 50, "type": "weapon"},
    "magic_wand": {"name": "🪄 Zauberstab", "price": 3000, "magic_power": 30, "type": "weapon"},
    "gold_ring": {"name": "💍 Goldring", "price": 1000, "charm_bonus": 1.2, "type": "accessory"},
    "silver_necklace": {"name": "📿 Silberkette", "price": 800, "charm_bonus": 1.1, "type": "accessory"},
    "crystal_ball": {"name": "🔮 Kristallkugel", "price": 1500, "prediction_bonus": 1.3, "type": "magic"},
    "ancient_scroll": {"name": "📜 Antike Schriftrolle", "price": 2500, "wisdom_bonus": 1.4, "type": "magic"},
    "phoenix_feather": {"name": "🪶 Phönixfeder", "price": 3000, "rebirth_chance": 0.1, "type": "legendary"},
    "dragon_scale": {"name": "🐲 Drachenschuppe", "price": 3500, "defense": 40, "type": "armor"},
    "unicorn_horn": {"name": "🦄 Einhornhorn", "price": 4000, "purity_bonus": 1.5, "type": "legendary"},
    "mermaid_scale": {"name": "🧜‍♀️ Meerjungfrauschuppe", "price": 2800, "water_bonus": 1.4, "type": "armor"},
    "fairy_dust": {"name": "✨ Feenstaub", "price": 1200, "magic_bonus": 1.2, "type": "magic"},
    "troll_blood": {"name": "🧌 Trollblut", "price": 900, "strength_bonus": 1.3, "type": "potion"},
    "witch_hat": {"name": "🧙‍♀️ Hexenhut", "price": 1500, "magic_power": 20, "type": "equipment"},
    "wizard_robe": {"name": "🧙‍♂️ Zaubererrobe", "price": 1800, "magic_defense": 25, "type": "armor"},
    "knight_armor": {"name": "🛡️ Ritterrüstung", "price": 2200, "defense": 35, "type": "armor"},
    "assassin_cloak": {"name": "🥷 Assassinenumhang", "price": 1900, "stealth_bonus": 1.4, "type": "equipment"},
    "pirate_hat": {"name": "🏴‍☠️ Piratenhut", "price": 700, "luck_bonus": 1.1, "type": "accessory"},
    "samurai_sword": {"name": "🗡️ Samuraischwert", "price": 4500, "damage": 45, "type": "weapon"},
    "ninja_star": {"name": "🥷 Ninjasterne", "price": 600, "throw_damage": 15, "type": "weapon"},
    "viking_helmet": {"name": "⚔️ Wikingerhelm", "price": 1300, "defense": 20, "type": "armor"},
    "robot_parts": {"name": "🤖 Roboterteile", "price": 3200, "tech_bonus": 1.5, "type": "tech"},
    "alien_artifact": {"name": "👽 Alien-Artefakt", "price": 5000, "mystery_bonus": 1.6, "type": "tech"}
}

PREMIUM_ITEMS = {
    "excalibur": {"name": "⚔️ Excalibur", "price": 150000, "damage": 100, "premium": True, "type": "legendary_weapon"},
    "astral_diamond": {"name": "💎 Astral-Diamant", "price": 300000, "magic_power": 100, "premium": True, "type": "legendary_gem"},
    "crown": {"name": "👑 Kaiserkrone", "price": 1000000, "authority_bonus": 2.0, "premium": True, "type": "royal"},
    "eternity_stone": {"name": "💎 Ewigkeitsstein", "price": 500000, "immortality_chance": 0.01, "premium": True, "type": "legendary"},
    "dragon_egg": {"name": "🥚 Drachenei", "price": 250000, "pet_type": "dragon", "premium": True, "type": "pet"},
    "phoenix_feather_premium": {"name": "🔥 Phönixfeder (Premium)", "price": 350000, "rebirth_chance": 0.5, "premium": True, "type": "legendary"},
    "unicorn_soul": {"name": "🦄 Einhornseele", "price": 400000, "purity_bonus": 2.5, "premium": True, "type": "legendary"},
    "godly_armor": {"name": "✨ Göttliche Rüstung", "price": 600000, "defense": 150, "premium": True, "type": "legendary_armor"},
    "infinity_gauntlet": {"name": "🪅 Unendlichkeitshandschuh", "price": 1000000, "power_bonus": 3.0, "premium": True, "type": "artifact"},
    "time_machine": {"name": "⏰ Zeitmaschine", "price": 800000, "time_warp": True, "premium": True, "type": "artifact"},
    "eternal_flame": {"name": "🔥 Ewige Flamme", "price": 450000, "energy_infinite": True, "premium": True, "type": "artifact"},
    "mystic_orb": {"name": "🔮 Mystischer Orb", "price": 280000, "divination_power": 80, "premium": True, "type": "magic"},
    "celestial_wings": {"name": "👼🏻 Himmlische Flügel", "price": 320000, "flight_enabled": True, "premium": True, "type": "accessory"},
    "abyssal_trident": {"name": "🔱 Abgrund-Dreizack", "price": 380000, "water_damage": 120, "premium": True, "type": "weapon"},
    "sunstone": {"name": "☀️ Sonnenstein", "price": 220000, "light_power": 90, "premium": True, "type": "gem"},
    "moonstone": {"name": "🌙 Mondstein", "price": 220000, "dark_power": 90, "premium": True, "type": "gem"},
    "stardust": {"name": "✨ Sternenstaub", "price": 180000, "wish_power": 1.8, "premium": True, "type": "magic"}
}

ALL_ITEMS = {**NORMAL_ITEMS, **PREMIUM_ITEMS}

# ------- PET TYPES -------
PET_TYPES = {
    "cat": {"name": "🐱 Katze", "base_hp": 100, "base_atk": 10, "premium": False, "rarity": "common"},
    "dog": {"name": "🐶 Hund", "base_hp": 120, "base_atk": 12, "premium": False, "rarity": "common"},
    "rabbit": {"name": "🐰 Hase", "base_hp": 80, "base_atk": 8, "premium": False, "rarity": "common"},
    "bird": {"name": "🐦 Vogel", "base_hp": 70, "base_atk": 15, "premium": False, "rarity": "common"},
    "hamster": {"name": "🐹 Hamster", "base_hp": 60, "base_atk": 6, "premium": False, "rarity": "common"},
    "turtle": {"name": "🐢 Schildkröte", "base_hp": 150, "base_atk": 5, "premium": False, "rarity": "uncommon"},
    "fish": {"name": "🐠 Fisch", "base_hp": 50, "base_atk": 9, "premium": False, "rarity": "common"},
    "dragon": {"name": "🐉 Drache", "base_hp": 200, "base_atk": 25, "premium": True, "rarity": "legendary"},
    "unicorn": {"name": "🦄 Einhorn", "base_hp": 180, "base_atk": 20, "premium": True, "rarity": "epic"},
    "phoenix": {"name": "🔥 Phönix", "base_hp": 190, "base_atk": 22, "premium": True, "rarity": "legendary"},
    "griffin": {"name": "🦅 Greif", "base_hp": 170, "base_atk": 18, "premium": True, "rarity": "epic"},
    "werewolf": {"name": "🐺 Werwolf", "base_hp": 160, "base_atk": 19, "premium": True, "rarity": "rare"},
    "kitsune": {"name": "🦊 Kitsune", "base_hp": 140, "base_atk": 17, "premium": True, "rarity": "rare"},
    "basilisk": {"name": "🐍 Basilisk", "base_hp": 175, "base_atk": 23, "premium": True, "rarity": "epic"},
    "pegasus": {"name": "🐎 Pegasus", "base_hp": 165, "base_atk": 16, "premium": True, "rarity": "rare"},
    "chimera": {"name": "🦁 Chimäre", "base_hp": 195, "base_atk": 24, "premium": True, "rarity": "legendary"},
    "hydra": {"name": "🐉 Hydra", "base_hp": 210, "base_atk": 26, "premium": True, "rarity": "legendary"},
    "cerberus": {"name": "🐕‍🔥 Zerberus", "base_hp": 185, "base_atk": 21, "premium": True, "rarity": "epic"},
    "sphinx": {"name": "🦁 Sphinx", "base_hp": 155, "base_atk": 14, "premium": True, "rarity": "rare"},
    "leviathan": {"name": "🐋 Leviathan", "base_hp": 220, "base_atk": 27, "premium": True, "rarity": "legendary"},
    "fairy": {"name": "🧚‍♀️ Fee", "base_hp": 90, "base_atk": 13, "premium": True, "rarity": "uncommon"},
    "imp": {"name": "👿 Imp", "base_hp": 95, "base_atk": 14, "premium": True, "rarity": "uncommon"},
    "golem": {"name": "🗿 Golem", "base_hp": 250, "base_atk": 15, "premium": True, "rarity": "epic"},
    "elemental": {"name": "🌊 Elementar", "base_hp": 130, "base_atk": 18, "premium": True, "rarity": "rare"}
}

# ------- JOBS -------
JOBS = {
    "miner": {"name": "⛏️ Bergarbeiter", "base_income": 50, "xp_per_work": 10, "premium_boost": 1.3},
    "fisher": {"name": "🎣 Fischer", "base_income": 45, "xp_per_work": 8, "premium_boost": 1.3},
    "farmer": {"name": "🌾 Farmer", "base_income": 40, "xp_per_work": 7, "premium_boost": 1.3},
    "blacksmith": {"name": "🔨 Schmied", "base_income": 70, "xp_per_work": 15, "premium_boost": 1.4},
    "merchant": {"name": "💰 Händler", "base_income": 60, "xp_per_work": 12, "premium_boost": 1.4},
    "hunter": {"name": "🏹 Jäger", "base_income": 65, "xp_per_work": 14, "premium_boost": 1.4},
    "alchemist": {"name": "🧪 Alchemist", "base_income": 80, "xp_per_work": 18, "premium_boost": 1.5},
    "wizard": {"name": "🧙‍♂️ Zauberer", "base_income": 90, "xp_per_work": 20, "premium_boost": 1.5},
    "knight": {"name": "⚔️ Ritter", "base_income": 75, "xp_per_work": 16, "premium_boost": 1.5},
    "assassin": {"name": "🗡️ Assassine", "base_income": 85, "xp_per_work": 19, "premium_boost": 1.6},
    "pirate": {"name": "🏴‍☠️ Pirat", "base_income": 95, "xp_per_work": 22, "premium_boost": 1.6},
    "samurai": {"name": "🗾 Samurai", "base_income": 100, "xp_per_work": 25, "premium_boost": 1.7}
}

# ------- XP SYSTEM -------
def add_xp(user_id: str, amount: int):
    user = state.get_user(user_id)
    if state.is_premium(user_id):
        amount = int(amount * 1.25)
    user.xp += amount
    user.total_xp += amount
    
    if user.job:
        user.job_xp += amount // 2
        if user.job_xp >= user.job_level * 100:
            user.job_xp -= user.job_level * 100
            user.job_level += 1
    
    needed = user.level * 100
    leveled_up = False
    while user.xp >= needed:
        user.xp -= needed
        user.level += 1
        bonus = user.level * 50
        if state.is_premium(user_id):
            bonus = int(bonus * 1.25)
        user.coins += bonus
        needed = user.level * 100
        leveled_up = True
    
    return leveled_up

# ------- BACKUP CONFIG -------
backup_config = load_json(CONFIG_FILE) or {}

def save_backup_config():
    save_json(CONFIG_FILE, backup_config)

# ------- BOT CLASS -------
class PremiumCoreBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.auto_save.start()
        self.daily_reset.start()
        self.interest_reset.start()

    @tasks.loop(minutes=5)
    async def auto_save(self):
        print(f"[AutoSave {datetime.now().strftime('%H:%M:%S')}] Speichere Serverdaten...")
        await state.save_all_async()
        print(f"[AutoSave {datetime.now().strftime('%H:%M:%S')}] Fertig.")

    @tasks.loop(hours=24)
    async def daily_reset(self):
        print(f"[Daily Reset {datetime.now().strftime('%Y-%m-%d')}] Täglicher Reset durchgeführt.")

    @tasks.loop(hours=6)
    async def interest_reset(self):
        print(f"[Interest Reset {datetime.now().strftime('%H:%M:%S')}] Zinsesperioden aktualisiert.")

    async def setup_hook(self):
        await self.tree.sync()
        print("Commands wurden gesynced.")

bot = PremiumCoreBot()

# ------- EVENTS -------
@bot.event
async def on_ready():
    print(f"Bot gestartet als {bot.user} (ID: {bot.user.id})")
    print(f"Owner ID: {OWNER_ID}")
    print(f"Eingeladen zu {len(bot.guilds)} Servern")
    print(f"------ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ------")

@bot.event
async def on_guild_join(guild):
    print(f"Neuer Server: {guild.name} (ID: {guild.id})")
    state.save_server(guild.id)

@bot.event
async def on_guild_remove(guild):
    print(f"Verlassen: {guild.name} (ID: {guild.id})")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return
    
    user_id = str(message.author.id)
    user = state.get_user(user_id, server_id=message.guild.id)
    
    if len(message.content) > 3 and not message.content.startswith(("/", bot.user.mention)):
        leveled_up = add_xp(user_id, random.randint(1, 3))
        if leveled_up:
            await state.save_server_async(message.guild.id)
            config = state.get_server_config(message.guild.id)
            channel_id = config.level_up_channel_id or message.channel.id
            channel = message.guild.get_channel(channel_id)
            if channel:
                await channel.send(f"🎉 **Level Up!** {message.author.mention} hat Level **{user.level}** erreicht und **{user.level * 50}** Coins erhalten!")
    
    if state.is_premium(user_id):
        config = state.get_server_config(message.guild.id)
        if config.premium_role_id:
            role = message.guild.get_role(config.premium_role_id)
            if role and role not in message.author.roles:
                try:
                    await message.author.add_roles(role)
                except discord.Forbidden:
                    pass

# ------- OWNER BACKUP COMMANDS -------
@bot.tree.command(name="backup-setchannel", description="Setzt den Backup-Channel (Owner only).")
@app_commands.describe(channel="Channel für Backups")
async def backup_setchannel(interaction: discord.Interaction, channel: discord.TextChannel):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("Nur der Bot-Owner kann dies nutzen.", ephemeral=True)
    
    backup_config["backup_channel_id"] = channel.id
    save_backup_config()
    await interaction.response.send_message(f"Backup-Channel auf {channel.mention} gesetzt.", ephemeral=True)

@bot.tree.command(name="backup-create-global", description="Erstellt globales Backup aller Server (Owner only).")
async def backup_create_global(interaction: discord.Interaction):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message("Nur der Bot-Owner kann dies nutzen.", ephemeral=True)
    
    backup_channel_id = backup_config.get("backup_channel_id")
    if not backup_channel_id:
        return await interaction.response.send_message(
            "Backup-Channel nicht gesetzt. Bitte zuerst /backup-setchannel nutzen.", 
            ephemeral=True
        )
    
    await interaction.response.send_message("Backup wird erstellt... Dies kann einen Moment dauern.", ephemeral=True)
    
    await state.save_all_async()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    zip_path = os.path.join(BACKUP_FOLDER, f"global_backup_{timestamp}.zip")
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(DATA_FOLDER):
            for file in files:
                if file.endswith(".json"):
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, DATA_FOLDER)
                    zipf.write(file_path, arcname=arcname)
        
        if os.path.exists(CONFIG_FILE):
            zipf.write(CONFIG_FILE, "backup_config.json")
        if os.path.exists(SERVER_CONFIG_FILE):
            zipf.write(SERVER_CONFIG_FILE, "server_configs.json")
    
    channel = bot.get_channel(backup_channel_id)
    if not channel:
        return await interaction.followup.send("Backup-Channel nicht gefunden.", ephemeral=True)
    
    try:
        embed = discord.Embed(
            title="🗄️ Globales Backup",
            description=f"Backup erstellt am {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
            color=Colors.SUCCESS
        )
        embed.add_field(name="Server", value=f"{len(bot.guilds)} Server")
        embed.add_field(name="Benutzer", value=f"{len(state.users)} gespeicherte Benutzer")
        embed.add_field(name="Dateigröße", value=f"{os.path.getsize(zip_path) / 1024:.1f} KB")
        embed.set_footer(text=f"Backup-ID: {timestamp}")
        
        await channel.send(embed=embed, file=discord.File(zip_path))
        await interaction.followup.send(f"✅ Backup erfolgreich im {channel.mention} gespeichert.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Fehler beim Senden: {e}", ephemeral=True)
    finally:
        if os.path.exists(zip_path):
            os.remove(zip_path)

@bot.tree.command(name="backup-load", description="Lädt ein Backup für diesen Server (Admin only).")
@app_commands.describe(file="Backup-Datei (.json oder .zip)")
async def backup_load(interaction: discord.Interaction, file: discord.Attachment):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "Du benötigst Administrator-Rechte für diesen Befehl.", 
            ephemeral=True
        )
    
    if not file.filename.endswith(('.json', '.zip')):
        return await interaction.response.send_message(
            "Nur .json oder .zip Dateien sind erlaubt.", 
            ephemeral=True
        )
    
    await interaction.response.send_message("Backup wird geladen...", ephemeral=True)
    
    try:
        temp_path = f"temp_backup_{interaction.guild.id}_{datetime.now().timestamp()}"
        await file.save(temp_path)
        
        if file.filename.endswith('.zip'):
            with zipfile.ZipFile(temp_path, 'r') as zip_ref:
                zip_ref.extractall(f"temp_extract_{interaction.guild.id}")
            
            server_file = f"server_{interaction.guild.id}.json"
            extract_path = f"temp_extract_{interaction.guild.id}/{server_file}"
            
            if os.path.exists(extract_path):
                old_path = state.get_file_path(interaction.guild.id)
                if os.path.exists(old_path):
                    backup_path = f"{old_path}.backup_{datetime.now().timestamp()}"
                    os.rename(old_path, backup_path)
                
                os.rename(extract_path, old_path)
                state.load_server(interaction.guild.id)
                
                await interaction.followup.send(
                    "✅ Backup erfolgreich geladen. Alte Daten wurden gesichert.", 
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "❌ Keine Server-spezifischen Daten im Backup gefunden.", 
                    ephemeral=True
                )
            
            import shutil
            shutil.rmtree(f"temp_extract_{interaction.guild.id}")
        
        elif file.filename.endswith('.json'):
            with open(temp_path, 'r') as f:
                data = json.load(f)
            
            if 'users' not in data:
                await interaction.followup.send("❌ Ungültiges Backup-Format.", ephemeral=True)
                return
            
            old_path = state.get_file_path(interaction.guild.id)
            if os.path.exists(old_path):
                backup_path = f"{old_path}.backup_{datetime.now().timestamp()}"
                os.rename(old_path, backup_path)
            
            save_json(old_path, data)
            state.load_server(interaction.guild.id)
            
            await interaction.followup.send(
                f"✅ Backup erfolgreich geladen. **{len(data.get('users', {}))}** Benutzer importiert.", 
                ephemeral=True
            )
    
    except Exception as e:
        await interaction.followup.send(f"❌ Fehler beim Laden: {e}", ephemeral=True)
    
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

# ------- SERVER CONFIG COMMANDS -------
@bot.tree.command(name="config-setup", description="Server-Konfiguration einrichten (Admin only).")
@app_commands.describe(
    level_channel="Channel für Level-Ups",
    marriage_channel="Channel für Hochzeiten",
    shop_channel="Channel für Shop-Nachrichten",
    premium_role="Premium-Rolle"
)
async def config_setup(
    interaction: discord.Interaction,
    level_channel: Optional[discord.TextChannel] = None,
    marriage_channel: Optional[discord.TextChannel] = None,
    shop_channel: Optional[discord.TextChannel] = None,
    premium_role: Optional[discord.Role] = None
):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            "Du benötigst Administrator-Rechte für diesen Befehl.", 
            ephemeral=True
        )
    
    config = state.get_server_config(interaction.guild.id)
    
    if level_channel:
        config.level_up_channel_id = level_channel.id
    if marriage_channel:
        config.marriage_channel_id = marriage_channel.id
    if shop_channel:
        config.shop_channel_id = shop_channel.id
    if premium_role:
        config.premium_role_id = premium_role.id
    
    state.save_server_configs()
    
    embed = discord.Embed(
        title="⚙️ Server-Konfiguration",
        description="Konfiguration wurde erfolgreich aktualisiert.",
        color=Colors.SUCCESS
    )
    
    if level_channel:
        embed.add_field(name="Level-Up Channel", value=level_channel.mention, inline=True)
    if marriage_channel:
        embed.add_field(name="Hochzeits-Channel", value=marriage_channel.mention, inline=True)
    if shop_channel:
        embed.add_field(name="Shop-Channel", value=shop_channel.mention, inline=True)
    if premium_role:
        embed.add_field(name="Premium-Rolle", value=premium_role.mention, inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="config-view", description="Aktuelle Server-Konfiguration anzeigen.")
async def config_view(interaction: discord.Interaction):
    config = state.get_server_config(interaction.guild.id)
    
    embed = discord.Embed(
        title="⚙️ Server-Konfiguration",
        color=Colors.INFO
    )
    
    level_channel = interaction.guild.get_channel(config.level_up_channel_id) if config.level_up_channel_id else None
    marriage_channel = interaction.guild.get_channel(config.marriage_channel_id) if config.marriage_channel_id else None
    shop_channel = interaction.guild.get_channel(config.shop_channel_id) if config.shop_channel_id else None
    premium_role = interaction.guild.get_role(config.premium_role_id) if config.premium_role_id else None
    
    embed.add_field(name="Level-Up Channel", 
                   value=level_channel.mention if level_channel else "Nicht gesetzt", 
                   inline=True)
    embed.add_field(name="Hochzeits-Channel", 
                   value=marriage_channel.mention if marriage_channel else "Nicht gesetzt", 
                   inline=True)
    embed.add_field(name="Shop-Channel", 
                   value=shop_channel.mention if shop_channel else "Nicht gesetzt", 
                   inline=True)
    embed.add_field(name="Premium-Rolle", 
                   value=premium_role.mention if premium_role else "Nicht gesetzt", 
                   inline=True)
    embed.add_field(name="Prefix", 
                   value=f"`{config.prefix}`", 
                   inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ------- PROFILE COMMANDS -------
@bot.tree.command(name="profile", description="Dein Profil anzeigen.")
@app_commands.describe(user="Optional: Ein anderer Benutzer")
async def profile_cmd(interaction: discord.Interaction, user: Optional[discord.User] = None):
    target = user or interaction.user
    user_id = str(target.id)
    
    user_profile = state.get_user(user_id, interaction.guild.id)
    pet_profile = state.get_pet(user_id)
    
    embed = discord.Embed(
        title=f"👤 Profil von {target.display_name}",
        color=Colors.PREMIUM if state.is_premium(user_id) else Colors.INFO
    )
    
    if state.is_premium(user_id):
        embed.title += " 🌟"
    
    embed.set_thumbnail(url=target.display_avatar.url)
    
    xp_needed = user_profile.level * 100
    xp_percent = min(100, int((user_profile.xp / xp_needed) * 100))
    
    embed.add_field(name="🏆 Level", value=f"**{user_profile.level}**", inline=True)
    embed.add_field(name="📊 XP", value=f"{user_profile.xp}/{xp_needed}", inline=True)
    embed.add_field(name="💰 Coins", value=f"**{format_number(user_profile.coins)}**", inline=True)
    
    bar_length = 10
    filled = int(xp_percent / 100 * bar_length)
    bar = "█" * filled + "░" * (bar_length - filled)
    embed.add_field(name="XP Fortschritt", value=f"`{bar}` {xp_percent}%", inline=False)
    
    embed.add_field(name="🌟 Total XP", value=f"**{format_number(user_profile.total_xp)}**", inline=True)
    
    if user_profile.job:
        job_info = JOBS.get(user_profile.job, {})
        embed.add_field(name="💼 Job", 
                       value=f"{job_info.get('name', 'Unbekannt')} (Level {user_profile.job_level})", 
                       inline=True)
    else:
        embed.add_field(name="💼 Job", value="Kein Job", inline=True)
    
    if user_profile.partner_id:
        try:
            partner = await bot.fetch_user(int(user_profile.partner_id))
            embed.add_field(name="💖 Partner/in", value=partner.mention, inline=True)
        except:
            embed.add_field(name="💖 Partner/in", value="Unbekannt", inline=True)
    
    if pet_profile:
        pet_type_info = PET_TYPES.get(pet_profile.type, {})
        embed.add_field(name="🐾 Haustier", 
                       value=f"{pet_profile.name} ({pet_type_info.get('name', 'Unbekannt')})", 
                       inline=True)
    
    embed.add_field(name="⚔️ Siege/Niederlagen", 
                   value=f"{user_profile.wins}🏆/{user_profile.losses}💀", 
                   inline=True)
    embed.add_field(name="🔥 Aktuelle Serie", 
                   value=f"{user_profile.streak} Siege", 
                   inline=True)
    
    if user_profile.premium_until:
        if user_profile.premium_until == "permanent":
            premium_status = "Permanent 🌟"
        else:
            try:
                end_date = datetime.fromisoformat(user_profile.premium_until)
                days_left = (end_date - datetime.now(timezone.utc)).days
                premium_status = f"{days_left} Tage übrig"
            except:
                premium_status = "Aktiv"
        embed.add_field(name="🌟 Premium Status", value=premium_status, inline=True)
    
    if user_profile.badges:
        badges_display = " ".join(user_profile.badges)
        embed.add_field(name="🏅 Badges", value=badges_display, inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="inventory", description="Dein Inventar anzeigen.")
async def inventory_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user = state.get_user(user_id, interaction.guild.id)
    
    if not user.inventory:
        return await interaction.response.send_message(
            embed=error_embed("Dein Inventar ist leer. Kaufe Items im Shop mit `/shop`!"),
            ephemeral=True
        )
    
    embed = discord.Embed(
        title=f"🎒 Inventar von {interaction.user.display_name}",
        color=Colors.ECONOMY
    )
    
    items_by_type = defaultdict(list)
    for item_id, quantity in user.inventory.items():
        item_info = ALL_ITEMS.get(item_id, {"name": item_id, "type": "unknown"})
        items_by_type[item_info.get("type", "unknown")].append((item_info.get("name", item_id), quantity))
    
    for item_type, items in items_by_type.items():
        itemjoin([f"• {name} **{quantity}x**" for name, quantity in items])
        embed.add_field(
            name=f"📦 {item_type.capitalize()} ({len(items)})",
            value=item_text,
            inline=False
        )
    
    total_value = sum(quantity * ALL_ITEMS.get(item_id, {}).get('price', 0) for item_id, quantity in user.inventory.items())
    embed.add_field(name="💰 Gesamtwert", value=f"**{format_number(total_value)}** Coins", inline=False)
    
    await interaction.response.send_message(embed=embed)

# ------- ECONOMY COMMANDS -------
@bot.tree.command(name="daily", description="Hole deine tägliche Belohnung.")
async def daily_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user = state.get_user(user_id, interaction.guild.id)
    
    now = datetime.now(timezone.utc)
    today = now.date().isoformat()
    
    if user.last_daily == today:
        next_daily = now + timedelta(days=1)
        next_daily = next_daily.replace(hour=0, minute=0, second=0, microsecond=0)
        time_left = next_daily - now
        
        hours = time_left.seconds // 3600
        minutes = (time_left.seconds % 3600) // 60
        
        return await interaction.response.send_message(
            embed=error_embed(f"Du hast deine tägliche Belohnung bereits abgeholt. Nächste Belohnung in **{hours}h {minutes}m**."),
            ephemeral=True
        )
    
    base_reward = 100
    streak_bonus = min(user.streak * 10, 100)
    premium_bonus = 1.5 if state.is_premium(user_id) else 1.0
    
    total_reward = int((base_reward + streak_bonus) * premium_bonus)
    
    user.streak += 1
    if user.streak > user.max_streak:
        user.max_streak = user.streak
    
    user.coins += total_reward
    user.last_daily = today
    
    random_item = None
    if random.random() < 0.05:
        normal_items = [item_id for item_id in NORMAL_ITEMS.keys() if NORMAL_ITEMS[item_id].get('price', 0) < 100]
        if normal_items:
            random_item = random.choice(normal_items)
            user.inventory[random_item] = user.inventory.get(random_item, 0) + 1
    
    add_xp(user_id, 25)
    
    await state.save_server_async(interaction.guild.id)
    
    embed = discord.Embed(
        title="💰 Tägliche Belohnung",
        description=f"Du hast **{total_reward}** Coins erhalten!",
        color=Colors.SUCCESS
    )
    
    embed.add_field(name="💎 Aktuelle Serie", value=f"{user.streak} Tage", inline=True)
    embed.add_field(name="🏆 Beste Serie", value=f"{user.max_streak} Tage", inline=True)
    
    details = []
    details.append(f"Basis: {base_reward} Coins")
    details.append(f"Serien-Bonus: +{streak_bonus} Coins")
    if state.is_premium(user_id):
        details.append(f"Premium-Bonus: +{int(total_reward * (premium_bonus - 1))} Coins")
    
    embed.add_field(name="📊 Details", value="etails), inline=False)
    
    if random_item:
        item_info = NORMAL_ITEMS.get(random_item, {"name": random_item})
        embed.add_field(name="🎁 Zufälliger Bonus", 
                       value=f"Du hast **{item_info['name']}** erhalten!", 
                       inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="work", description="Gehe arbeiten, um Coins zu verdienen.")
async def work_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user = state.get_user(user_id, interaction.guild.id)
    
    now = datetime.now(timezone.utc)
    
    if user.last_work:
        try:
            last_work_time = datetime.fromisoformat(user.last_work)
            time_since = now - last_work_time
            if time_since.total_seconds() < 1800:
                time_left = 1800 - int(time_since.total_seconds())
                minutes = time_left // 60
                seconds = time_left % 60
                
                return await interaction.response.send_message(
                    embed=error_embed(f"Du musst dich erst ausruhen! Warte **{minutes}m {seconds}s**."),
                    ephemeral=True
                )
        except ValueError:
            pass
    
    if not user.job:
        base_income = 50
        job_name = "Gelegenheitsjob"
    else:
        job_info = JOBS.get(user.job, {})
        base_income = job_info.get('base_income', 50)
        job_name = job_info.get('name', user.job)
        
        user.job_xp += 10
        if user.job_xp >= user.job_level * 100:
            user.job_xp -= user.job_level * 100
            user.job_level += 1
            job_level_up = True
        else:
            job_level_up = False
    
    premium_multiplier = 1.5 if state.is_premium(user_id) else 1.0
    level_bonus = 1 + (user.level * 0.01)
    job_level_bonus = 1 + (user.job_level * 0.05)
    random_factor = random.uniform(0.8, 1.2)
    
    total_income = int(base_income * premium_multiplier * level_bonus * job_level_bonus * random_factor)
    
    user.coins += total_income
    user.last_work = now.isoformat()
    
    xp_earned = random.randint(10, 20)
    add_xp(user_id, xp_earned)
    
    await state.save_server_async(interaction.guild.id)
    
    embed = discord.Embed(
        title="💼 Arbeit",
        description=f"Du hast **{total_income}** Coins verdient!",
        color=Colors.SUCCESS
    )
    
    embed.add_field(name="🏢 Job", value=job_name, inline=True)
    embed.add_field(name="📈 Job Level", value=f"{user.job_level}", inline=True)
    embed.add_field(name="➕ XP verdient", value=f"{xp_earned} XP", inline=True)
    
    details = []
    details.append(f"Basis: {base_income} Coins")
    if state.is_premium(user_id):
        details.append(f"Premium: +{int(total_income * (premium_multiplier - 1))} Coins")
    details.append(f"Level Bonus: +{int(total_income * (level_bonus - 1))} Coins")
    details.append(f"Job Level Bonus: +{int(total_income * (job_level_bonus - 1))} Coins")
    details.append(f"Glück: {random_factor:.2f}x")
    
    embed.add_field(name="n".join(details), inline=False)
    
    if 'job_level_up' in locals() and job_level_up:
        embed.add_field(name="🎉 Job-Level-Up!", value=f"Dein Job-Level ist auf **{user.job_level}** gestiegen!", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="beg", description="Bette um Coins (Cooldown: 5 Minuten).")
async def beg_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user = state.get_user(user_id, interaction.guild.id)
    
    now = datetime.now(timezone.utc)
    
    if hasattr(user, 'last_beg'):
        try:
            last_beg_time = datetime.fromisoformat(user.last_beg)
            time_since = now - last_beg_time
            if time_since.total_seconds() < 300:
                time_left = 300 - int(time_since.total_seconds())
                minutes = time_left // 60
                seconds = time_left % 60
                
                return await interaction.response.send_message(
                    embed=error_embed(f"Die Leute haben genug von dir! Warte **{minutes}m {seconds}s**."),
                    ephemeral=True
                )
        except (ValueError, AttributeError):
            pass
    
    success_rate = 0.7
    if random.random() > success_rate:
        responses = ["Niemand gibt dir etwas!", "Geh arbeiten statt zu betteln!", "Versuche es später noch einmal.", "Die Leute ignorieren dich."]
        return await interaction.response.send_message(embed=error_embed(random.choice(responses)), ephemeral=True)
    
    base_amount = random.randint(5, 30)
    premium_bonus = 1.5 if state.is_premium(user_id) else 1.0
    charisma_bonus = 1 + (user.level * 0.01)
    
    amount = int(base_amount * premium_bonus * charisma_bonus)
    
    user.coins += amount
    user.last_beg = now.isoformat()
    
    add_xp(user_id, 5)
    
    responses = [
        f"Ein freundlicher Fremder gibt dir **{amount}** Coins!",
        f"Jemand hat Mitleid mit dir und gibt dir **{amount}** Coins.",
        f"Du erhältst **{amount}** Coins für deine Bettelkunst.",
        f"Ein Reicher wirft dir **{amount}** Coins zu."
    ]
    
    embed = success_embed(random.choice(responses))
    embed.set_footer(text="Cooldown: 5 Minuten")
    
    await interaction.response.send_message(embed=embed)

# ------- SHOP SYSTEM -------
@bot.tree.command(name="shop", description="Shop mit allen verfügbaren Items anzeigen.")
@app_commands.describe(page="Seitenzahl (1-5)")
async def shop_cmd(interaction: discord.Interaction, page: int = 1):
    items_per_page = 10
    all_items = list(ALL_ITEMS.items())
    
    user_id = str(interaction.user.id)
    if not state.is_premium(user_id):
        all_items = [(k, v) for k, v in all_items if not v.get('premium', False)]
    
    total_pages = (len(all_items) + items_per_page - 1) // items_per_page
    page = max(1, min(page, total_pages))
    
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    
    embed = discord.Embed(
        title="🛒 Premium Core Shop",
        description=f"Seite {page}/{total_pages} • {len(all_items)} Items verfügbar",
        color=Colors.SHOP
    )
    
    for item_id, item_info in all_items[start_idx:end_idx]:
        price = item_info.get('price', 0)
        item_type = item_info.get('type', 'unknown')
        premium_tag = " 🌟" if item_info.get('premium', False) else ""
        
        description = f"Preis: **{price}** Coins"
        if 'hunger' in item_info:
            description += f" | Hunger: {item_info['hunger']}"
        if 'damage' in item_info:
            description += f" | Schaden: {item_info['damage']}"
        if 'defense' in item_info:
            description += f" | Verteidigung: {item_info['defense']}"
        
        embed.add_field(
            name=f"{item_info['name']}{premium_tag}",
nBefehl: `/buy {item_id}`",
            inline=False
        )
    
    embed.set_footer(text="Nutze /shop [Seite] um weitere Seiten zu sehen")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="buy", description="Kaufe ein Item aus dem Shop.")
@app_commands.describe(item_id="ID des Items", quantity="Anzahl (default: 1)")
async def buy_cmd(interaction: discord.Interaction, item_id: str, quantity: int = 1):
    if quantity <= 0 or quantity > 100:
        return await interaction.response.send_message(
            embed=error_embed("Die Menge muss zwischen 1 und 100 liegen."),
            ephemeral=True
        )
    
    if item_id not in ALL_ITEMS:
        return await interaction.response.send_message(
            embed=error_embed("Dieses Item existiert nicht im Shop."),
            ephemeral=True
        )
    
    item_info = ALL_ITEMS[item_id]
    user_id = str(interaction.user.id)
    user = state.get_user(user_id, interaction.guild.id)
    
    if item_info.get('premium', False) and not state.is_premium(user_id):
        return await interaction.response.send_message(
            embed=error_embed("Dies ist ein Premium-Item! Du benötigst einen Premium-Account, um es zu kaufen."),
            ephemeral=True
        )
    
    total_price = item_info['price'] * quantity
    
    if user.coins < total_price:
        needed = total_price - user.coins
        return await interaction.response.send_message(
            embed=error_embed(f"Du hast nicht genug Coins! Du benötigst noch **{needed}** Coins"),
            ephemeral=True
        )
    
    user.coins -= total_price
    user.inventory[item_id] = user.inventory.get(item_id, 0) + quantity
    
    xp_earned = max(1, total_price // 100)
    add_xp(user_id, xp_earned)
    
    await state.save_server_async(interaction.guild.id)
    
    embed = success_embed(f"✅ Du hast **{quantity}x {item_info['name']}** für **{total_price}** Coins gekauft!")
    
    if item_id == "pet_food" and state.get_pet(user_id):
        embed.add_field(name="🐾 Haustier-Tipp", value="Nutze `/pet feed` um dein Haustier zu füttern!", inline=False)
    elif item_id == "health_potion":
        embed.add_field(name="❤️‍🩹 Heilung", value="Nutze `/use health_potion` um dich zu heilen!", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="sell", description="Verkaufe Items aus deinem Inventar.")
@app_commands.describe(item_id="ID des Items", quantity="Anzahl (default: 1)")
async def sell_cmd(interaction: discord.Interaction, item_id: str, quantity: int = 1):
    user_id = str(interaction.user.id)
    user = state.get_user(user_id, interaction.guild.id)
    
    if quantity <= 0:
        return await interaction.response.send_message(
            embed=error_embed("Die Menge muss mindestens 1 sein."),
            ephemeral=True
        )
    
    if item_id not in user.inventory or user.inventory[item_id] < quantity:
        available = user.inventory.get(item_id, 0)
        return await interaction.response.send_message(
            embed=error_embed(f"Du hast nicht genug von diesem Item! Verfügbar: {available}x"),
            ephemeral=True
        )
    
    item_info = ALL_ITEMS.get(item_id, {"price": 10})
    sell_price = int(item_info['price'] * 0.7 * quantity)
    
    user.inventory[item_id] -= quantity
    if user.inventory[item_id] == 0:
        del user.inventory[item_id]
    
    user.coins += sell_price
    
    await state.save_server_async(interaction.guild.id)
    
    item_name = item_info.get('name', item_id)
    embed = success_embed(f"✅ Du hast **{quantity}x {item_name}** für **{sell_price}** Coins verkauft!")
    
    await interaction.response.send_message(embed=embed)

# ------- PET SYSTEM -------
@bot.tree.command(name="pet-create", description="Erstelle ein neues Haustier.")
@app_commands.describe(
    name="Name deines Haustiers",
    pet_type="Art des Haustiers"
)
@app_commands.choices(pet_type=[
    app_commands.Choice(name="🐱 Katze", value="cat"),
    app_commands.Choice(name="🐶 Hund", value="dog"),
    app_commands.Choice(name="🐰 Hase", value="rabbit"),
    app_commands.Choice(name="🐦 Vogel", value="bird"),
    app_commands.Choice(name="🐢 Schildkröte", value="turtle"),
    app_commands.Choice(name="🐉 Drache (Premium)", value="dragon"),
    app_commands.Choice(name="🦄 Einhorn (Premium)", value="unicorn"),
    app_commands.Choice(name="🔥 Phönix (Premium)", value="phoenix"),
])
async def pet_create_cmd(interaction: discord.Interaction, name: str, pet_type: str):
    user_id = str(interaction.user.id)
    
    if state.get_pet(user_id):
        return await interaction.response.send_message(
            embed=error_embed("Du hast bereits ein Haustier! Nutze `/pet` um es anzuzeigen."),
            ephemeral=True
        )
    
    pet_info = PET_TYPES.get(pet_type, {})
    if pet_info.get('premium', False) and not state.is_premium(user_id):
        return await interaction.response.send_message(
            embed=error_embed("Dies ist ein Premium-Haustier! Du benötigst einen Premium-Account, um es zu erstellen."),
            ephemeral=True
        )
    
    base_cost = 1000
    if pet_info.get('premium', False):
        base_cost = 5000
    
    user = state.get_user(user_id, interaction.guild.id)
    
    if user.coins < base_cost:
        return await interaction.response.send_message(
            embed=error_embed(f"Du benötigst **{base_cost}** Coins! Dein Kontostand: **{user.coins}** Coins"),
            ephemeral=True
        )
    
    user.coins -= base_cost
    pet = PetProfile(
        name=name[:20],
        type=pet_type,
        level=1,
        hunger=20,
        happiness=50,
        max_hp=pet_info.get('base_hp', 100),
        current_hp=pet_info.get('base_hp', 100),
        atk=pet_info.get('base_atk', 10)
    )
    
    state.pets[user_id] = pet
    add_xp(user_id, 50)
    
    await state.save_server_async(interaction.guild.id)
    
    pet_type_name = pet_info.get('name', pet_type)
    
    embed = discord.Embed(
        title=f"🎉 Neues Haustier erschaffen!",
        description=f"Willkommen, **{name}**!",
        color=Colors.PET
    )
    
    embed.add_field(name="🧬 Art", value=pet_type_name, inline=True)
    embed.add_field(name="❤️ Gesundheit", value=f"{pet.current_hp}/{pet.max_hp} HP", inline=True)
    embed.add_field(name="⚔️ Angriff", value=f"{pet.atk} ATK", inline=True)
    embed.add_field(name="🍖 Hunger", value=f"{pet.hunger}/100", inline=True)
    embed.add_field(name="😊 Zufriedenheit", value=f"{pet.happiness}/100", inline=True)
    embed.add_field(name="🏆 Level", value=f"{pet.level}", inline=True)
    
    embed.set_footer(text="Nutze /pet um dein Haustier zu sehen und /pet-help für alle Befehle")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="pet", description="Zeige dein aktuelles Haustier an.")
async def pet_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    pet = state.get_pet(user_id)
    
    if not pet:
        return await interaction.response.send_message(
            embed=error_embed("Du hast kein Haustier! Erstelle eins mit `/pet-create`."),
            ephemeral=True
        )
    
    pet_info = PET_TYPES.get(pet.type, {})
    
    embed = discord.Embed(
        title=f"🐾 {pet.name}",
        description=f"Ein **{pet_info.get('name', pet.type)}** der Stufe {pet.level}",
        color=Colors.PET
    )
    
    hunger_bar = "█" * (pet.hunger // 10) + "░" * (10 - pet.hunger // 10)
    happiness_bar = "█" * (pet.happiness // 10) + "░" * (10 - pet.happiness // 10)
    health_bar = "█" * (pet.current_hp // (pet.max_hp // 10)) + "░" * (10 - pet.current_hp // (pet.max_hp // 10))
    
    embed.add_field(name="❤️ Gesundheit", 
                   value=f"`{health_bar}` {pet.current_hp}/{pet.max_hp} HP", 
                   inline=False)
    embed.add_field(name="🍖 Hunger", 
                   value=f"`{hunger_bar}` {pet.hunger}/100", 
                   inline=True)
    embed.add_field(name="😊 Zufriedenheit", 
                   value=f"`{happiness_bar}` {pet.happiness}/100", 
                   inline=True)
    
    embed.add_field(name="⚔️ Angriff", value=f"**{pet.atk}** ATK", inline=True)
    embed.add_field(name="📊 XP", value=f"**{pet.xp}**/100", inline=True)
    embed.add_field(name="⭐ Seltenheit", 
                   value=pet_info.get('rarity', 'common').capitalize(), 
                   inline=True)
    
    status_messages = []
    if pet.hunger > 70:
        status_messages.append("⚠️ Dein Haustier ist hungrig!")
    elif pet.hunger < 20:
        status_messages.append("✅ Dein Haustier ist gut gefüttert.")
    
    if pet.happiness < 30:
        status_messages.append("😞 Dein Haustier ist traurig.")
    elif pet.happiness > 80:
        status_messages.append("😊 Dein Haustier ist sehr glücklich!")
    
    if pet.current_hp < pet.max_hp * 0.5:
        status_messages.append("🏥 Dein Haustier benötigt Heilung!")
    
    if status_messages:
        embed.add_field(name="n".join(status_messages), inline=False)
    
    if pet.premium_costume:
        embed.add_field(name="👗 Premium-Kostüm", value=pet.premium_costume, inline=False)
    
    commands_tips = []
    if pet.hunger > 50:
        commands_tips.append("• `/pet feed` - Haustier füttern")
    if pet.happiness < 50:
        commands_tips.append("• `/pet play` - Mit Haustier spielen")
    if pet.current_hp < pet.max_hp:
        commands_tips.append("• `/pet heal` - Haustier heilen")
    if pet.level < 10:
        commands_tips.append("• `/pet train` - Haustier trainieren")
    
    if commands_tips:
        embed.add_field(name="🔧 Befehle",(commands_tips), inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="pet-feed", description="Füttere dein Haustier.")
async def pet_feed_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    pet = state.get_pet(user_id)
    
    if not pet:
        return await interaction.response.send_message(
            embed=error_embed("Du hast kein Haustier! Erstelle eins mit `/pet-create`."),
            ephemeral=True
        )
    
    user = state.get_user(user_id, interaction.guild.id)
    
    if "pet_food" not in user.inventory or user.inventory["pet_food"] < 1:
        return await interaction.response.send_message(
            embed=error_embed("Du benötigst **Haustierfutter**! Kaufe es im Shop mit `/shop`."),
            ephemeral=True
        )
    
    user.inventory["pet_food"] -= 1
    if user.inventory["pet_food"] == 0:
        del user.inventory["pet_food"]
    
    hunger_reduction = 25
    old_hunger = pet.hunger
    pet.hunger = max(0, pet.hunger - hunger_reduction)
    
    pet.xp += 5
    if pet.xp >= 100:
        pet.xp -= 100
        pet.level += 1
        pet.max_hp += 10
        pet.atk += 2
        pet.current_hp = pet.max_hp
        leveled_up = True
    else:
        leveled_up = False
    
    add_xp(user_id, 10)
    
    await state.save_server_async(interaction.guild.id)
    
    embed = discord.Embed(
        title=f"🍖 {pet.name} wurde gefüttert!",
        description=f"Hunger reduziert von **{old_hunger}** auf **{pet.hunger}**",
        color=Colors.SUCCESS
    )
    
    embed.add_field(name="🍽️ Verbraucht", value="1x Haustierfutter", inline=True)
    embed.add_field(name="📈 XP", value=f"+5 Haustier-XP", inline=True)
    embed.add_field(name="😊 Zufriedenheit", value=f"+10", inline=True)
    
    if leveled_up:
        embed.add_field(name="🎉 Level Up!", value=f"{pet.name} ist jetzt Level **{pet.level}**!", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="pet-play", description="Spiele mit deinem Haustier.")
async def pet_play_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    pet = state.get_pet(user_id)
    
    if not pet:
        return await interaction.response.send_message(
            embed=error_embed("Du hast kein Haustier! Erstelle eins mit `/pet-create`."),
            ephemeral=True
        )
    
    now = datetime.now(timezone.utc)
    if pet.last_adventure:
        try:
            last_play = datetime.fromisoformat(pet.last_adventure)
            time_since = now - last_play
            if time_since.total_seconds() < 1800:
                time_left = 1800 - int(time_since.total_seconds())
                minutes = time_left // 60
                seconds = time_left % 60
                return await interaction.response.send_message(
                    embed=error_embed(f"Dein Haustier ist noch müde! Warte **{minutes}m {seconds}s**."),
                    ephemeral=True
                )
        except ValueError:
            pass
    
    pet.happiness = min(100, pet.happiness + 15)
    pet.hunger = min(100, pet.hunger + 10)
    
    pet.xp += 10
    if pet.xp >= 100:
        pet.xp -= 100
        pet.level += 1
        pet.max_hp += 10
        pet.atk += 2
        leveled_up = True
    else:
        leveled_up = False
    
    add_xp(user_id, 15)
    pet.last_adventure = now.isoformat()
    
    await state.save_server_async(interaction.guild.id)
    
    activities = [
        f"{pet.name} jagt einem Ball hinterher!",
        f"Du wirfst einen Stock und {pet.name} holt ihn zurück!",
        f"{pet.name} spielt fröhlich mit einem Spielzeug!",
        f"Du und {pet.name} haben eine tolle Zeit zusammen!",
        f"{pet.name} zeigt dir einen neuen Trick!"
    ]
    
    embed = discord.Embed(
        title=f"🎾 Spielzeit mit {pet.name}!",
        description=random.choice(activities),
        color=Colors.PET
    )
    
    embed.add_field(name="😊 Zufriedenheit", value=f"+15 (Jetzt: {pet.happiness}/100)", inline=True)
    embed.add_field(name="🍖 Hunger", value=f"+10 (Jetzt: {pet.hunger}/100)", inline=True)
    embed.add_field(name="📈 XP", value=f"+10 Haustier-XP", inline=True)
    
    if leveled_up:
        embed.add_field(name="🎉 Level Up!", value=f"{pet.name} ist jetzt Level **{pet.level}**!", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="pet-heal", description="Heile dein Haustier.")
async def pet_heal_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    pet = state.get_pet(user_id)
    
    if not pet:
        return await interaction.response.send_message(
            embed=error_embed("Du hast kein Haustier! Erstelle eins mit `/pet-create`."),
            ephemeral=True
        )
    
    if pet.current_hp >= pet.max_hp:
        return await interaction.response.send_message(
            embed=error_embed(f"{pet.name} ist bereits vollständig geheilt!"),
            ephemeral=True
        )
    
    user = state.get_user(user_id, interaction.guild.id)
    
    if "health_potion" not in user.inventory or user.inventory["health_potion"] < 1:
        return await interaction.response.send_message(
            embed=error_embed("Du benötigst **Heiltränke**! Kaufe sie im Shop mit `/shop`."),
            ephemeral=True
        )
    
    user.inventory["health_potion"] -= 1
    if user.inventory["health_potion"] == 0:
        del user.inventory["health_potion"]
    
    heal_amount = 50
    old_hp = pet.current_hp
    pet.current_hp = min(pet.max_hp, pet.current_hp + heal_amount)
    
    pet.xp += 3
    add_xp(user_id, 5)
    
    await state.save_server_async(interaction.guild.id)
    
    embed = discord.Embed(
        title=f"❤️‍🩹 {pet.name} wurde geheilt!",
        description=f"Gesundheit erhöht von **{old_hp}** auf **{pet.current_hp}** HP",
        color=Colors.SUCCESS
    )
    
    embed.add_field(name="💊 Verbraucht", value="1x Heiltrank", inline=True)
    embed.add_field(name="❤️ Heilung", value=f"+{heal_amount} HP", inline=True)
    embed.add_field(name="📈 XP", value=f"+3 Haustier-XP", inline=True)
    
    await interaction.response.send_message(embed=embed)

# ------- MARRIAGE SYSTEM -------
@bot.tree.command(name="marry", description="Heirate einen anderen Benutzer.")
@app_commands.describe(user="Der Benutzer, den du heiraten möchtest")
async def marry_cmd(interaction: discord.Interaction, user: discord.User):
    if user == interaction.user:
        return await interaction.response.send_message(embed=error_embed("Du kannst dich nicht selbst heiraten!"), ephemeral=True)
    
    if user.bot:
        return await interaction.response.send_message(embed=error_embed("Du kannst keinen Bot heiraten!"), ephemeral=True)
    
    user_id = str(interaction.user.id)
    target_id = str(user.id)
    
    proposer = state.get_user(user_id, interaction.guild.id)
    target = state.get_user(target_id, interaction.guild.id)
    
    if proposer.partner_id:
        return await interaction.response.send_message(embed=error_embed("Du bist bereits verheiratet!"), ephemeral=True)
    
    if target.partner_id:
        return await interaction.response.send_message(embed=error_embed(f"{user.display_name} ist bereits verheiratet!"), ephemeral=True)
    
    marriage_cost = 1000
    if proposer.coins < marriage_cost:
        return await interaction.response.send_message(
            embed=error_embed(f"Die Hochzeit kostet **{marriage_cost}** Coins! Dein Kontostand: **{proposer.coins}** Coins"),
            ephemeral=True
        )
    
    if state.is_premium(user_id):
        marriage_cost = 500
    
    embed = discord.Embed(
        title="💍 Heiratsantrag!",
        description=f"{interaction.user.mention} möchte {user.mention} heiraten! 💖",
        color=Colors.MARRIAGE
    )
    
    embed.add_field(name="💰 Kosten", value=f"{marriage_cost} Coins", inline=True)
    embed.add_field(name="🌟 Premium-Vorteil", value="Gemeinsame Familienkasse und tägliche Boni", inline=True)
    embed.set_footer(text="Der Antrag läuft in 60 Sekunden ab")
    
    view = discord.ui.View(timeout=60)
    
    async def accept_callback(button_interaction: discord.Interaction):
        if button_interaction.user.id != user.id:
            await button_interaction.response.send_message("Nur die angefragte Person kann den Antrag annehmen!", ephemeral=True)
            return
        
        proposer = state.get_user(user_id, interaction.guild.id)
        target = state.get_user(target_id, interaction.guild.id)
        
        if proposer.partner_id or target.partner_id:
            await button_interaction.response.send_message(embed=error_embed("Einer von euch ist bereits verheiratet!"), ephemeral=True)
            return
        
        if proposer.coins < marriage_cost:
            await button_interaction.response.send_message(embed=error_embed("Der Antragsteller hat nicht mehr genug Coins!"), ephemeral=True)
            return
        
        proposer.coins -= marriage_cost
        proposer.partner_id = target_id
        target.partner_id = user_id
        now = datetime.now(timezone.utc)
        proposer.marriage_date = now.isoformat()
        target.marriage_date = now.isoformat()
        
        proposer.family_coins = 0
        target.family_coins = 0
        
        add_xp(user_id, 100)
        add_xp(target_id, 100)
        
        await state.save_server_async(interaction.guild.id)
        
        config = state.get_server_config(interaction.guild.id)
        wedding_channel = None
        if config.marriage_channel_id:
            wedding_channel = interaction.guild.get_channel(config.marriage_channel_id)
        
        if wedding_channel:
            wedding_embed = discord.Embed(
                title="🎉 Hochzeit!",
                description=f"{interaction.user.mention} 💖 {user.mention} sind jetzt verheiratet!",
                color=Colors.MARRIAGE,
                timestamp=now
            )
            wedding_embed.add_field(name="💰 Kosten", value=f"{marriage_cost} Coins", inline=True)
            wedding_embed.add_field(name="📅 Datum", value=now.strftime("%d.%m.%Y"), inline=True)
            wedding_embed.add_field(name="👨‍👩‍👧‍👦 Familienkasse", value="0 Coins", inline=True)
            wedding_embed.set_footer(text="Nutze /family um eure Familie zu sehen")
            
            await wedding_channel.send(embed=wedding_embed)
        
        success_embed = discord.Embed(
            title="✅ Heiratsantrag angenommen!",
            description=f"Herzlichen Glückwunsch! {interaction.user.mention} und {user.mention} sind jetzt verheiratet!",
            color=Colors.SUCCESS
        )
        
        await button_interaction.response.send_message(embed=success_embed)
    
    async def decline_callback(button_interaction: discord.Interaction):
        if button_interaction.user.id != user.id:
            await button_interaction.response.send_message("Nur die angefragte Person kann den Antrag ablehnen!", ephemeral=True)
            return
        
        await button_interaction.response.send_message(embed=error_embed(f"{user.display_name} hat den Heiratsantrag abgelehnt."), ephemeral=True)
    
    accept_button = discord.ui.Button(label="✅ Annehmen", style=discord.ButtonStyle.success)
    accept_button.callback = accept_callback
    
    decline_button = discord.ui.Button(label="❌ Ablehnen", style=discord.ButtonStyle.danger)
    decline_button.callback = decline_callback
    
    view.add_item(accept_button)
    view.add_item(decline_button)
    
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="divorce", description="Lasse dich scheiden.")
async def divorce_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user = state.get_user(user_id, interaction.guild.id)
    
    if not user.partner_id:
        return await interaction.response.send_message(embed=error_embed("Du bist nicht verheiratet!"), ephemeral=True)
    
    divorce_cost = 500
    if user.coins < divorce_cost:
        return await interaction.response.send_message(
            embed=error_embed(f"Die Scheidung kostet **{divorce_cost}** Coins! Dein Kontostand: **{user.coins}** Coins"),
            ephemeral=True
        )
    
    try:
        partner = await bot.fetch_user(int(user.partner_id))
        partner_user = state.get_user(user.partner_id, interaction.guild.id)
        
        family_coins = user.family_coins
        if family_coins > 0:
            user.coins += family_coins // 2
            partner_user.coins += family_coins // 2
        
        user.coins -= divorce_cost
        partner_user.partner_id = None
        user.partner_id = None
        user.marriage_date = None
        partner_user.marriage_date = None
        user.family_coins = 0
        partner_user.family_coins = 0
        
        await state.save_server_async(interaction.guild.id)
        
        embed = discord.Embed(
            title="💔 Geschieden",
            description=f"{interaction.user.mention} und {partner.mention} sind jetzt geschieden.",
            color=Colors.ERROR
        )
        
        embed.add_field(name="💰 Kosten", value=f"{divorce_cost} Coins", inline=True)
        if family_coins > 0:
            embed.add_field(name="🏦 Aufgeteilt", value=f"{family_coins // 2} Coins an jeden", inline=True)
        
        await interaction.response.send_message(embed=embed)
        
    except Exception as e:
        await interaction.response.send_message(embed=error_embed(f"Fehler bei der Scheidung: {e}"), ephemeral=True)

@bot.tree.command(name="family", description="Zeige deine Familieninformationen an.")
async def family_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    user = state.get_user(user_id, interaction.guild.id)
    
    if not user.partner_id:
        return await interaction.response.send_message(embed=error_embed("Du bist nicht verheiratet und hast keine Familie!"), ephemeral=True)
    
    try:
        partner = await bot.fetch_user(int(user.partner_id))
        partner_user = state.get_user(user.partner_id, interaction.guild.id)
        
        marriage_date = None
        if user.marriage_date:
            try:
                date_obj = datetime.fromisoformat(user.marriage_date)
                marriage_date = date_obj.strftime("%d.%m.%Y")
                days_married = (datetime.now(timezone.utc) - date_obj).days
            except ValueError:
                marriage_date = "Unbekannt"
                days_married = 0
        
        embed = discord.Embed(
            title="👨‍👩‍👧‍👦 Familie",
            description=f"{interaction.user.mention} 💖 {partner.mention}",
            color=Colors.MARRIAGE
        )
        
        embed.add_field(name="💍 Verheiratet seit", value=f"{marriage_date} ({days_married} Tage)", inline=True)
        embed.add_field(name="🏦 Familienkasse", value=f"**{user.family_coins}** Coins", inline=True)
        
        if user.children:
            children_list = []
            for child_name, child_info in user.children.items():
                age = child_info.get('age', 0)
                children_list.append(f"👶 {child_name} (Alter: {age} Tage)")
            
            embed.add_field(name="👶 Kinderjoin(children_list[:5]), inline=False)
            
            if len(user.children) > 5:
                embed.add_field(name="", value=f"... und {len(user.children) - 5} weitere Kinder", inline=False)
        else:
            embed.add_field(name="👶 Kinder", value="Keine Kinder", inline=False)
        
        embed.add_field(name="💑 Gemeinsame Statistiken", 
                       value=f"• Level: {user.level} & {                             f"• Coins: {user.coins} & {partner_user.co"• Premium: {'✅' if state.is_premium(user_id) else '❌'} & {'✅' if state.is_premium(user.partner_id) else '❌'}",
                       inline=False)
        
        await interaction.response.send_message(embed=embed)
        
    except Exception:
        await interaction.response.send_message(embed=error_embed("Dein Partner konnte nicht gefunden werden."), ephemeral=True)

@bot.tree.command(name="family-deposit", description="Geld auf die Familienkasse einzahlen.")
@app_commands.describe(amount="Einzahlungsbetrag")
async def family_deposit_cmd(interaction: discord.Interaction, amount: int):
    if amount <= 0:
        return await interaction.response.send_message(embed=error_embed("Der Betrag muss größer als 0 sein!"), ephemeral=True)
    
    user_id = str(interaction.user.id)
    user = state.get_user(user_id, interaction.guild.id)
    
    if not user.partner_id:
        return await interaction.response.send_message(embed=error_embed("Du bist nicht verheiratet!"), ephemeral=True)
    
    if user.coins < amount:
        return await interaction.response.send_message(
            embed=error_embed(f"Du hast nur **{user.coins}** Coins! Du möchtest **{amount}** Coins einzahlen."),
            ephemeral=True
        )
    
    user.coins -= amount
    user.family_coins += amount
    
    partner_user = state.get_user(user.partner_id, interaction.guild.id)
    partner_user.family_coins = user.family_coins
    
    await state.save_server_async(interaction.guild.id)
    
    embed = success_embed(f"✅ **{amount}** Coins wurden auf die Familienkasse einguer Familienkontostand: **{user.family_coins}** Coins")
    
    await interaction.response.send_message(embed=embed)

# ------- PREMIUM SYSTEM -------
@bot.tree.command(name="premium-info", description="Informationen über Premium-Mitgliedschaft.")
async def premium_info_cmd(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    is_premium = state.is_premium(user_id)
    
    embed = discord.Embed(
        title="🌟 Premium-Mitgliedschaft",
        description="Erhalte exklusive Vorteile mit einer Premium-Mitgliedschaft!",
        color=Colors.PREMIUM
    )
    
    embed.add_field(
        name="✨ Vorteile",
        value="• +• +50% mehr Coins bei täglichen• Zugang zu Premium-H• Exklusive Befitäts-Support",
        inline=False
    )
    
    embed.add_field(
        name="💰 Preise",
        value="• 1 Monat: **50.000** Coate: **135.000** Coins (101 Jahr: **450.000** Coins (25 Permanent: **2.000.000** Coins",
        inline=False
    )
    
    if is_premium:
        user = state.get_user(user_id, interaction.guild.id)
        if user.premium_until == "permanent":
            status = "**Permanente** Premium-Mitgliedschaft"
        else:
            try:
                end_date = datetime.fromisoformat(user.premium_until)
                days_left = (end_date - datetime.now(timezone.utc)).days
                status = f"Premium läuft ab in **{days_left}** Tagen"
            except:
                status = "Premium-Mitglied"
        
        embed.add_field(
            name="✅ Dein StatusnPremium Titel: {user.premium_title ornPremium Aura: {user.premium_aura or 'Keine'}",
            inline=False
        )
    
    embed.set_footer(text="Nutze /premium-buy [dauer] um Premium zu kaufen")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="premium-buy", description="Kaufe eine Premium-Mitgliedschaft.")
@app_commands.describe(duration="Dauer der Mitgliedschaft")
@app_commands.choices(duration=[
    app_commands.Choice(name="1 Monat - 50.000 Coins", value="30"),
    app_commands.Choice(name="3 Monate - 135.000 Coins", value="90"),
    app_commands.Choice(name="1 Jahr - 450.000 Coins", value="365"),
    app_commands.Choice(name="Permanent - 2.000.000 Coins", value="permanent"),
])
async def premium_buy_cmd(interaction: discord.Interaction, duration: str):
    user_id = str(interaction.user.id)
    user = state.get_user(user_id, interaction.guild.id)
    
    costs = {
        "30": 50000,
        "90": 135000,
        "365": 450000,
        "permanent": 2000000
    }
    
    cost = costs[duration]
    
    if user.coins < cost:
        needed = cost - user.coins
        return await interaction.response.send_message(
            embed=error_embed(f"Du benötigst **{needed}** mehr Coins für diesen Kaufostand: **{user.coins}** Coins"),
            ephemeral=True
        )
    
    if state.is_premium(user_id) and user.premium_until != "permanent":
        if duration == "permanent":
            user.coins -= cost
            user.premium_until = "permanent"
            
            await state.save_server_async(interaction.guild.id)
            
            return await interaction.response.send_message(
                embed=success_embed("✅ Du hast ein **permanentes** Premium-Upgradeine Premium-Mitgliedschaft läuft jetzt für immer!")
            )
        else:
            try:
                days = int(duration)
                end_date = datetime.now(timezone.utc) + timedelta(days=days)
                
                if user.premium_until and user.premium_until != "permanent":
                    current_end = datetime.fromisoformat(user.premium_until)
                    if current_end > datetime.now(timezone.utc):
                        new_end = current_end + timedelta(days=days)
                        user.premium_until = new_end.isoformat()
                    else:
                        user.premium_until = end_date.isoformat()
                else:
                    user.premium_until = end_date.isoformat()
                
                user.coins -= cost
                
                await state.save_server_async(interaction.guild.id)
                
                return await interaction.response.send_message(
                    embed=success_embed(f"✅ Deine Premium-Mitgliedschaft wurde um **{days}** Tage verläng Ablaufdatum: {end_date.strftime('%d.%m.%Y')}")
                )
            except Exception as e:
                return await interaction.response.send_message(embed=error_embed(f"Fehler bei der Verlängerung: {e}"), ephemeral=True)
    else:
        user.coins -= cost
        
        if duration == "permanent":
            user.premium_until = "permanent"
        else:
            days = int(duration)
            end_date = datetime.now(timezone.utc) + timedelta(days=days)
            user.premium_until = end_date.isoformat()
        
        if not user.premium_title:
            user.premium_title = "🌟 Premium Nutzer"
        if not user.premium_aura:
            user.premium_aura = "golden"
        
        await state.save_server_async(interaction.guild.id)
        
        duration_text = {
            "30": "1 Monat",
            "90": "3 Monate",
            "365": "1 Jahr",
            "permanent": "permanent"
        }[duration]
        
        embed = success_embed(
            f"✅ Du hast eine **{duration_text}** Premium-Mitglied            f"**Vorteile aktiviert:**"• +25% mehr mehr Coins bei tägang zu Premium-Haustieren-Titel: {user.premium_title}"
        )
        
        if duration != "permanent":
            end_date = datetime.now(timezone.utc) + timedelta(days=int(duration))
            embed.add_field(name="📅 Ablaufdatum", value=end_date.strftime("%d.%m.%Y %H:%M"), inline=False)
        
        await interaction.response.send_message(embed=embed)

# ------- LEADERBOARD SYSTEM -------
@bot.tree.command(name="leaderboard", description="Zeige die Bestenliste an.")
@app_commands.describe(type="Art der Bestenliste")
@app_commands.choices(type=[
    app_commands.Choice(name="🏆 Level", value="level"),
    app_commands.Choice(name="💰 Coins", value="coins"),
    app_commands.Choice(name="💎 Premium", value="premium"),
    app_commands.Choice(name="👑 Reichste", value="rich"),
    app_commands.Choice(name="⚔️ Kämpfe", value="wins"),
    app_commands.Choice(name="💼 Jobs", value="jobs"),
    app_commands.Choice(name="🐾 Haustiere", value="pets"),
])
async def leaderboard_cmd(interaction: discord.Interaction, type: str = "level"):
    server_users = []
    for user_id, user in state.users.items():
        if user.server_id == interaction.guild.id:
            try:
                discord_user = await bot.fetch_user(int(user_id))
                server_users.append((user_id, user, discord_user))
            except:
                continue
    
    if not server_users:
        return await interaction.response.send_message(
            embed=error_embed("Keine Benutzerdaten für diesen Server gefunden."),
            ephemeral=True
        )
    
    if type == "level":
        server_users.sort(key=lambda x: (x[1].level, x[1].xp), reverse=True)
        title = "🏆 Level Leaderboard"
        value_func = lambda u: f"Level {u.level} | {u.xp}/{u.level * 100} XP"
    elif type == "coins":
        server_users.sort(key=lambda x: x[1].coins, reverse=True)
        title = "💰 Coins Leaderboard"
        value_func = lambda u: f"{format_number(u.coins)} Coins"
    elif type == "premium":
        premium_users = [(uid, u, du) for uid, u, du in server_users if state.is_premium(uid)]
        premium_users.sort(key=lambda x: (x[1].premium_until == "permanent", x[1].level), reverse=True)
        title = "💎 Premium Leaderboard"
        value_func = lambda u: "🌟 Permanent" if u.premium_until == "permanent" else "Premium"
    elif type == "rich":
        server_users.sort(key=lambda x: (x[1].coins + x[1].family_coins), reverse=True)
        title = "👑 Reichsten Spieler"
        value_func = lambda u: f"{format_number(u.coins + u.family_coins)} Gesamtvermögen"
    elif type == "wins":
        server_users.sort(key=lambda x: (x[1].wins, x[1].max_streak), reverse=True)
        title = "⚔️ Kampf Leaderboard"
        value_func = lambda u: f"{u.wins} Siege | {u.max_streak} Beste Serie"
    elif type == "jobs":
        job_users = [(uid, u, du) for uid, u, du in server_users if u.job]
        job_users.sort(key=lambda x: (x[1].job_level, x[1].job_xp), reverse=True)
        title = "💼 Job Leaderboard"
        value_func = lambda u: f"{JOBS.get(u.job, {}).get('name', u.job)} Level {u.job_level}"
    elif type == "pets":
        pet_users = [(uid, u, du) for uid, u, du in server_users if state.get_pet(uid)]
        pet_users.sort(key=lambda x: state.get_pet(x[0]).level if state.get_pet(x[0]) else 0, reverse=True)
        title = "🐾 Haustier Leaderboard"
        value_func = lambda u: f"Level {state.get_pet(u.id).level}" if state.get_pet(u.id) else "Kein Haustier"
    
    top_users = server_users[:10]
    
    embed = discord.Embed(
        title=title,
        description=f"Top 10 Spieler auf {interaction.guild.name}",
        color=Colors.INFO
    )
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, (user_id, user_data, discord_user) in enumerate(top_users):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        value = value_func(user_data)
        
        embed.add_field(
            name=f"{medal} {discord_user.display_name}",
            value=value,
            inline=False
        )
    
    current_user_id = str(interaction.user.id)
    for rank, (user_id, user_data, discord_user) in enumerate(server_users):
        if user_id == current_user_id:
            embed.set_footer(text=f"Dein Rang: #{rank + 1}")
            break
    
    await interaction.response.send_message(embed=embed)

# ------- ADMIN COMMANDS -------
@bot.tree.command(name="admin-give-coins", description="Vergebe Coins an einen Benutzer (Admin only).")
@app_commands.describe(user="Benutzer", amount="Anzahl der Coins")
async def admin_give_coins(interaction: discord.Interaction, user: discord.User, amount: int):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            embed=error_embed("Du benötigst Administrator-Rechte für diesen Befehl."),
            ephemeral=True
        )
    
    if amount <= 0:
        return await interaction.response.send_message(
            embed=error_embed("Der Betrag muss größer als 0 sein."),
            ephemeral=True
        )
    
    user_id = str(user.id)
    target_user = state.get_user(user_id, interaction.guild.id)
    
    target_user.coins += amount
    
    await state.save_server_async(interaction.guild.id)
    
    embed = success_embed(f"✅ **{amount}** Coins wurden an {user.mention Kontostand: **{target_user.coins}** Coins")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="admin-set-level", description="Setze das Level eines Benutzers (Admin only).")
@app_commands.describe(user="Benutzer", level="Neues Level")
async def admin_set_level(interaction: discord.Interaction, user: discord.User, level: int):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            embed=error_embed("Du benötigst Administrator-Rechte für diesen Befehl."),
            ephemeral=True
        )
    
    if level < 1 or level > 1000:
        return await interaction.response.send_message(
            embed=error_embed("Das Level muss zwischen 1 und 1000 liegen."),
            ephemeral=True
        )
    
    user_id = str(user.id)
    target_user = state.get_user(user_id, interaction.guild.id)
    
    old_level = target_user.level
    target_user.level = level
    target_user.xp = 0
    
    await state.save_server_async(interaction.guild.id)
    
    embed = success_embed(f"✅ Level von {user.mention} von **{old_level}** auf **{level}** gesetzt.")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="admin-reset-user", description="Setze einen Benutzer zurück (Admin only).")
@app_commands.describe(user="Benutzer")
async def admin_reset_user(interaction: discord.Interaction, user: discord.User):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            embed=error_embed("Du benötigst Administrator-Rechte für diesen Befehl."),
            ephemeral=True
        )
    
    user_id = str(user.id)
    
    state.users[user_id] = UserProfile()
    state.users[user_id].server_id = interaction.guild.id
    
    if user_id in state.pets:
        del state.pets[user_id]
    
    await state.save_server_async(interaction.guild.id)
    
    embed = success_embed(f"✅ {user.mention} wurde erfolgreich zurückgesetzt.")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="admin-server-stats", description="Server-Statistiken anzeigen (Admin only).")
async def admin_server_stats(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator:
        return await interaction.response.send_message(
            embed=error_embed("Du benötigst Administrator-Rechte für diesen Befehl."),
            ephemeral=True
        )
    
    server_users = [u for u in state.users.values() if u.server_id == interaction.guild.id]
    
    if not server_users:
        return await interaction.response.send_message(
            embed=error_embed("Keine Benutzerdaten für diesen Server gefunden."),
            ephemeral=True
        )
    
    total_coins = sum(u.coins for u in server_users)
    total_family_coins = sum(u.family_coins for u in server_users)
    total_level = sum(u.level for u in server_users)
    premium_users = sum(1 for u in server_users if state.is_premium(str(list(state.users.keys())[list(state.users.values()).index(u)])))
    pet_users = sum(1 for u in server_users if str(list(state.users.keys())[list(state.users.values()).index(u)]) in state.pets)
    married_users = sum(1 for u in server_users if u.partner_id)
    
    embed = discord.Embed(
        title=f"📊 Server-Statistiken - {interaction.guild.name}",
        color=Colors.INFO,
        timestamp=datetime.now(timezone.utc)
    )
    
    embed.add_field(name="👥 Gesamte Benutzer", value=str(len(server_users)), inline=True)
    embed.add_field(name="💰 Gesamt-Coins", value=format_number(total_coins), inline=True)
    embed.add_field(name="💒 Familienkassen", value=format_number(total_family_coins), inline=True)
    
    embed.add_field(name="🏆 Durchschnittliches Level", value=f"{total_level/len(server_users):.1f}", inline=True)
    embed.add_field(name="🌟 Premium Nutzer", value=str(premium_users), inline=True)
    embed.add_field(name="🐾 Haustier-Besitzer", value=str(pet_users), inline=True)
    
    embed.add_field(name="💍 Verheiratete Paare", value=str(married_users//2), inline=True)
    embed.add_field(name="💼 Aktive Jobs", value=str(sum(1 for u in server_users if u.job)), inline=True)
    embed.add_field(name="📊 Dateigröße", 
                   value=f"{os.path.getsize(state.get_file_path(interaction.guild.id))/1024:.1f} KB" 
                         if os.path.exists(state.get_file_path(interaction.guild.id)) else "0 KB", 
                   inline=True)
    
    top_users = sorted(server_users, key=lambda u: u.coins, reverse=True)[:3]
    top_list = []
    for i, user_data in enumerate(top_users):
        user_id = str(list(state.users.keys())[list(state.users.values()).index(user_data)])
        try:
            discord_user = await bot.fetch_user(int(user_id))
            top_list.append(f"{i+1}. {discord_user.display_name}: {format_number(user_data.coins)} Coins")
        except:
            top_list.append(f"{i+1}. Unbekannt: {format_number(user_data.coins)} Coins")
    
    if top_list:
        embed.add_field(name="👑 Top 3 Reich".join(top_list), inline=False)
    
    await interaction.response.send_message(embed=embed)

# ------- HELP COMMANDS -------
@bot.tree.command(name="help", description="Zeige alle verfügbaren Befehle an.")
@app_commands.describe(category="Kategorie der Befehle")
@app_commands.choices(category=[
    app_commands.Choice(name="📊 Allgemein", value="general"),
    app_commands.Choice(name="💰 Wirtschaft", value="economy"),
    app_commands.Choice(name="🛒 Shop", value="shop"),
    app_commands.Choice(name="🐾 Haustiere", value="pets"),
    app_commands.Choice(name="💍 Familie", value="family"),
    app_commands.Choice(name="🌟 Premium", value="premium"),
    app_commands.Choice(name="🏆 Ranglisten", value="leaderboards"),
    app_commands.Choice(name="⚙️ Admin", value="admin"),
    app_commands.Choice(name="🗄️ Backup", value="backup"),
])
async def help_cmd(interaction: discord.Interaction, category: str = "general"):
    help_data = {
        "general": {
            "title": "📊 Allgemeine Befehle",
            "commands": [
                ("/profile [user]", "Zeige dein Profil oder das eines anderen an"),
                ("/inventory", "Zeige dein Inventar an"),
                ("/help [category]", "Zeige diese Hilfeseite an"),
                ("/config-view", "Zeige Server-Konfiguration"),
            ]
        },
        "economy": {
            "title": "💰 Wirtschafts-Befehle",
            "commands": [
                ("/daily", "Hole deine tägliche Belohnung"),
                ("/work", "Gehe arbeiten, um Coins zu verdienen"),
                ("/beg", "Bette um Coins (5 Min Cooldown)"),
                ("/buy [item] [amount]", "Kaufe Items aus dem Shop"),
                ("/sell [item] [amount]", "Verkaufe Items aus deinem Inventar"),
            ]
        },
        "shop": {
            "title": "🛒 Shop-Befehle",
            "commands": [
                ("/shop [page]", "Zeige alle verfügbaren Items an"),
                ("/buy [item_id] [quantity]", "Kaufe ein Item aus dem Shop"),
                ("/sell [item_id] [quantity]", "Verkaufe Items aus deinem Inventar"),
            ]
        },
        "pets": {
            "title": "🐾 Haustier-Befehle",
            "commands": [
                ("/pet-create [name] [type]", "Erstelle ein neues Haustier"),
                ("/pet", "Zeige dein aktuelles Haustier an"),
                ("/pet-feed", "Füttere dein Haustier"),
                ("/pet-play", "Spiele mit deinem Haustier"),
                ("/pet-heal", "Heile dein Haustier"),
            ]
        },
        "family": {
            "title": "💍 Familien-Befehle",
            "commands": [
                ("/marry [user]", "Heirate einen anderen Benutzer"),
                ("/divorce", "Lasse dich scheiden"),
                ("/family", "Zeige deine Familieninformationen an"),
                ("/family-deposit [amount]", "Geld auf die Familienkasse einzahlen"),
            ]
        },
        "premium": {
            "title": "🌟 Premium-Befehle",
            "commands": [
                ("/premium-info", "Informationen über Premium-Mitgliedschaft"),
                ("/premium-buy [duration]", "Kaufe eine Premium-Mitgliedschaft"),
            ]
        },
        "leaderboards": {
            "title": "🏆 Ranglisten-Befehle",
            "commands": [
                ("/leaderboard [type]", "Zeige die Bestenliste an"),
            ]
        },
        "admin": {
            "title": "⚙️ Admin-Befehle",
            "commands": [
                ("/config-setup", "Server-Konfiguration einrichten"),
                ("/admin-give-coins [user] [amount]", "Vergebe Coins an einen Benutzer"),
                ("/admin-set-level [user] [level]", "Setze das Level eines Benutzers"),
                ("/admin-reset-user [user]", "Setze einen Benutzer zurück"),
                ("/admin-server-stats", "Server-Statistiken anzeigen"),
            ],
            "note": "⚠️ Erfordert Administrator-Rechte"
        },
        "backup": {
            "title": "🗄️ Backup-Befehle",
            "commands": [
                ("/backup-setchannel [channel]", "Setzt den Backup-Channel (Owner only)"),
                ("/backup-create-global", "Erstellt globales Backup aller Server (Owner only)"),
                ("/backup-load [file]", "Lädt ein Backup für diesen Server (Admin only)"),
            ]
        }
    }
    
    if category not in help_data:
        embed = discord.Embed(
            title="📚 Premium Core Bot - Hilfe",
            description="Verwende `/help [kategorie]` für spezifische Befehle.",
            color=Colors.INFO
        )
        
        for cat_name, cat_data in help_data.items():
            embed.add_field(
                name=cat_data["title"],
                value=f"`/help {cat_name}`",
                inline=True
            )
        
        embed.set_footer(text=f"Bot Version 2.0 • {len(help_data)} Kategorien verfügbar")
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    data = help_data[category]
    embed = discord.Embed(
        title=data["title"],
        description="Hier sind alle verfügbaren Befehle:",
        color=Colors.INFO
    )
    
    for command, description in data["commands"]:
        embed.add_field(name=command, value=description, inline=False)
    
    if "note" in data:
        embed.add_field(name="Hinweis", value=data["note"], inline=False)
    
    embed.set_footer(text=f"Kategorie: {category} • Nutze /help für alle Kategorien")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ------- ERROR HANDLING -------
@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandNotFound):
        await interaction.response.send_message(embed=error_embed("Dieser Befehl existiert nicht."), ephemeral=True)
    elif isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(embed=error_embed("Du hast nicht die erforderlichen Berechtigungen."), ephemeral=True)
    elif isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            embed=error_embed(f"Dieser Befehl hat einen Cooldown! Versuche es in {error.retry_after:.1f} Sekunden erneut."),
            ephemeral=True
        )
    else:
        print(f"[ERROR] {type(error).__name__}: {error}")
        try:
            await interaction.response.send_message(
                embed=error_embed(f"Ein unerwarteter Fehler ist aufgetreten: {errorde dies dem Bot-Owner."),
                ephemeral=True
            )
        except discord.InteractionResponded:
            await interaction.followup.send(embed=error_embed(f"Fehler: {error}"), ephemeral=True)

# ------- START BOT -------
if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN nicht gefunden! Bitte setze ihn in der .env Datei.")
        print("Beispiel: DISCORD_TOKEN=dein_token_hier")
        exit(1)
    
    try:
        bot.run(DISCORD_TOKEN)
    except discord.LoginFailure:
        print("❌ Fehler beim Einloggen: Ungültiger Token!")
    except KeyboardInterrupt:
        print("🤖 Bot wird heruntergefahren...")
        state.save_all()
        print("✅ Alle Daten gespeichert.")
    except Exception as e:
        print(f"❌ Kritischer Fehler: {e}")
        state.save_all() 

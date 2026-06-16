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

# --- GLOBAL BOT STATE MANAGEMENT ---
class BotStateManager:
    def __init__(self, data_directory: str = "bot_data"):
        self.data_dir = data_directory
        self.users: Dict[str, UserProfile] = {}
        self.pets: Dict[str, PetProfile] = {}
        self.premium_users: set = set() # Enthält IDs von Premium-Usern
        
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def get_user(self, user_id: str, server_id: int) -> UserProfile:
        if user_id not in self.users:
            self.users[user_id] = UserProfile(server_id=server_id)
        return self.users[user_id]

    def get_pet(self, user_id: str) -> Optional[PetProfile]:
        return self.pets.get(user_id)

    def is_premium(self, user_id: str) -> bool:
        return user_id in self.premium_users

    # Asynchrones Laden der Serverdaten
    async def load_server_async(self, server_id: int):
        file_path = os.path.join(self.data_dir, f"server_{server_id}.json")
        if not os.path.exists(file_path):
            return

        try:
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                content = await f.read()
                if not content.strip():
                    return
                data = json.loads(content)
                
                # Benutzer wiederherstellen
                for uid, udata in data.get("users", {}).items():
                    self.users[uid] = UserProfile.from_dict(udata)
                    
                # Haustiere wiederherstellen
                for uid, pdata in data.get("pets", {}).items():
                    self.pets[uid] = PetProfile.from_dict(pdata)
                    
                # Premium-Status wiederherstellen
                for uid in data.get("premium", []):
                    self.premium_users.add(uid)
        except Exception as e:
            print(f"Fehler beim Laden von Server {server_id}: {e}")

    # Asynchrones Speichern der Serverdaten
    async def save_server_async(self, server_id: int):
        file_path = os.path.join(self.data_dir, f"server_{server_id}.json")
        
        # Daten filtern, die zu diesem spezifischen Server gehören
        server_users = {uid: u.to_dict() for uid, u in self.users.items() if u.server_id == server_id}
        server_pets = {uid: p.to_dict() for uid, p in self.pets.items() if uid in server_users}
        server_premium = [uid for uid in self.premium_users if uid in server_users]
        
        save_data = {
            "users": server_users,
            "pets": server_pets,
            "premium": server_premium
        }
        
        try:
            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(save_data, indent=4, ensure_ascii=False))
        except Exception as e:
            print(f"Fehler beim Speichern von Server {server_id}: {e}")

# Initialisierung des Datenmanagers
state = BotStateManager()

# --- BOT CONFIGURATION ---
class MultiGuildBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Automatisches Laden im Hintergrund, wenn der Bot hochfährt
        print("Initialisiere Systeme...")

bot = MultiGuildBot()

# --- HELPER FUNCTIONS FOR BEAUTIFUL EMBEDS ---
def create_embed(title: str, description: str, color: int = Colors.DEFAULT) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color, timestamp=datetime.now())

def success_embed(text: str) -> discord.Embed:
    return create_embed("✅ Erfolg", text, Colors.SUCCESS)

def error_embed(text: str) -> discord.Embed:
    return create_embed("❌ Fehler", text, Colors.ERROR)

def info_embed(text: str) -> discord.Embed:
    return create_embed("ℹ️ Information", text, Colors.INFO)

def format_number(number: int) -> str:
    return f"{number:,}".replace(",", ".")

# ==============================================================================
# ------- ECONOMY & BANK SYSTEM -------
# ==============================================================================

@bot.tree.command(name="daily", description="Hole deine tägliche Belohnung ab!")
async def daily(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    user = state.get_user(uid, interaction.guild_id)
    
    now = datetime.now(timezone.utc)
    if user.last_daily:
        last = datetime.fromisoformat(user.last_daily)
        if now - last < timedelta(days=1):
            remaining = timedelta(days=1) - (now - last)
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            await interaction.response.send_message(
                embed=error_embed(f"Du kannst deine tägliche Belohnung erst wieder in `{hours}h {minutes}m` abholen."), 
                ephemeral=True
            )
            return

    # Basis-Belohnung: 200 Münzen. Premium-User bekommen das Doppelte (400 Münzen)!
    reward = 400 if state.is_premium(uid) else 200
    user.coins += reward
    user.last_daily = now.isoformat()
    
    await state.save_server_async(interaction.guild_id)
    
    msg = f"Du hast deine täglichen `{reward}` Münzen abgeholt!"
    if state.is_premium(uid):
        msg += " (🌟 Premium-Doppelbonus aktiv!)"
        
    await interaction.response.send_message(embed=success_embed(msg))


@bot.tree.command(name="balance", description="Zeigt dein aktuelles Bargeld und Bankguthaben.")
async def balance(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    user = state.get_user(uid, interaction.guild_id)
    
    emb = create_embed(f"💰 Finanzen von {interaction.user.display_name}", "", Colors.ECONOMY)
    emb.add_field(name="💵 Bargeld (Hand)", value=f"`{format_number(user.coins)}` Coins", inline=False)
    emb.add_field(name="🏦 Bankguthaben", value=f"`{format_number(user.family_coins)}` Coins", inline=False)
    emb.add_field(name="📊 Gesamtvermögen", value=f"`{format_number(user.coins + user.family_coins)}` Coins", inline=False)
    
    await interaction.response.send_message(embed=emb)


@bot.tree.command(name="bank_deposit", description="Zahle Münzen auf dein sicheres Bankkonto ein.")
@app_commands.describe(amount="Die Anzahl an Münzen, oder 'all' für dein gesamtes Bargeld.")
async def bank_deposit(interaction: discord.Interaction, amount: str):
    uid = str(interaction.user.id)
    user = state.get_user(uid, interaction.guild_id)
    
    if amount.lower() == "all":
        coins_to_deposit = user.coins
    else:
        try:
            coins_to_deposit = int(amount)
        except ValueError:
            await interaction.response.send_message(embed=error_embed("Bitte gib eine gültige Zahl oder 'all' ein."), ephemeral=True)
            return

    if coins_to_deposit <= 0:
        await interaction.response.send_message(embed=error_embed("Du musst mehr als 0 Münzen einzahlen."), ephemeral=True)
        return

    if user.coins < coins_to_deposit:
        await interaction.response.send_message(embed=error_embed(f"Du hast nicht genug Bargeld auf der Hand. Aktuell: `{user.coins}` Coins."), ephemeral=True)
        return

    # Geld auf die Bank verschieben
    user.coins -= coins_to_deposit
    user.family_coins += coins_to_deposit
    
    await state.save_server_async(interaction.guild_id)
    await interaction.response.send_message(embed=success_embed(
        f"Du hast `{format_number(coins_to_deposit)}` Münzen eingezahlt.\n"
        f"Handguthaben: `{format_number(user.coins)}` | Bankguthaben: `{format_number(user.family_coins)}`"
    ))


@bot.tree.command(name="bank_withdraw", description="Hebe Münzen von deinem Bankkonto ab.")
@app_commands.describe(amount="Die Anzahl an Münzen, oder 'all' für dein gesamtes Erspartes.")
async def bank_withdraw(interaction: discord.Interaction, amount: str):
    uid = str(interaction.user.id)
    user = state.get_user(uid, interaction.guild_id)
    
    if amount.lower() == "all":
        coins_to_withdraw = user.family_coins
    else:
        try:
            coins_to_withdraw = int(amount)
        except ValueError:
            await interaction.response.send_message(embed=error_embed("Bitte gib eine gültige Zahl oder 'all' ein."), ephemeral=True)
            return

    if coins_to_withdraw <= 0:
        await interaction.response.send_message(embed=error_embed("Du musst mehr als 0 Münzen abheben."), ephemeral=True)
        return

    if user.family_coins < coins_to_withdraw:
        await interaction.response.send_message(embed=error_embed(f"So viel Geld hast du nicht auf der Bank. Aktuell: `{user.family_coins}` Coins."), ephemeral=True)
        return

    # Geld von der Bank aufs Bargeldkonto verschieben
    user.family_coins -= coins_to_withdraw
    user.coins += coins_to_withdraw
    
    await state.save_server_async(interaction.guild_id)
    await interaction.response.send_message(embed=success_embed(
        f"Du hast `{format_number(coins_to_withdraw)}` Münzen abgehoben.\n"
        f"Handguthaben: `{format_number(user.coins)}` | Bankguthaben: `{format_number(user.family_coins)}`"
    ))


@bot.tree.command(name="bank_interest", description="Fordere deine täglichen Zinsen auf dein Erspartes ein.")
async def bank_interest(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    user = state.get_user(uid, interaction.guild_id)
    
    if user.family_coins <= 0:
        await interaction.response.send_message(embed=error_embed("Du hast kein Geld auf der Bank, also kannst du keine Zinsen verdienen!"), ephemeral=True)
        return

    now = datetime.now(timezone.utc)
    if user.last_interest_claim:
        last = datetime.fromisoformat(user.last_interest_claim)
        if now - last < timedelta(days=1):
            remaining = timedelta(days=1) - (now - last)
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            await interaction.response.send_message(embed=error_embed(f"Du kannst deine Zinsen erst wieder in `{hours}h {minutes}m` abholen."), ephemeral=True)
            return

    # Zinssatz berechnen: 2% für normale User, 5% für Premium-User
    interest_rate = 0.05 if state.is_premium(uid) else 0.02
    interest_gained = int(user.family_coins * interest_rate)
    
    if interest_gained < 1:
        interest_gained = 1  # Mindestens 1 Münze Zinsen

    user.family_coins += interest_gained
    user.last_interest_claim = now.isoformat()
    
    await state.save_server_async(interaction.guild_id)
    
    rate_percent = "5%" if state.is_premium(uid) else "2%"
    msg = f"Bei einem Zinssatz von **{rate_percent}** hast du heute `{format_number(interest_gained)}` Münzen Zinsen erhalten!"
    if state.is_premium(uid):
        msg += " (🌟 Premium-Zinsbonus aktiv!)"
        
    await interaction.response.send_message(embed=success_embed(msg))

# ==============================================================================
# ------- JOB & LEVEL PROGRESSION SYSTEM -------
# ==============================================================================

# Liste aller verfügbaren Berufe und deren Basis-Einkommen
JOBS_CONFIG = {
    "miner": {"name": "⛏️ Bergarbeiter", "base_pay": 150},
    "farmer": {"name": "🚜 Farmer", "base_pay": 140},
    "alchemist": {"name": "🧙‍♂️ Alchemist", "base_pay": 180},
    "chef": {"name": "🍳 Chefkoch", "base_pay": 160},
    "fisherman": {"name": "🎣 Angler", "base_pay": 130},
    "blacksmith": {"name": "🔨 Schmied", "base_pay": 170},
    "merchant": {"name": "⚖️ Händler", "base_pay": 190},
    "guard": {"name": "🛡️ Stadtwache", "base_pay": 155},
    "thief": {"name": "🥷 Dieb", "base_pay": 210}, # Höheres Risiko/Belohnung
    "hunter": {"name": "🏹 Jäger", "base_pay": 165},
    "samurai": {"name": "⚔️ Samurai", "base_pay": 220},
    "wizard": {"name": "🔮 Großmagier", "base_pay": 250}
}

@bot.tree.command(name="job_list", description="Zeigt eine Übersicht aller Berufe, die du erlernen kannst.")
async def job_list(interaction: discord.Interaction):
    emb = create_embed("💼 Arbeitsamt - Verfügbare Berufe", "Wähle einen Job mit `/job_join [ID]`, um Geld zu verdienen.", Colors.INFO)
    
    for job_id, info in JOBS_CONFIG.items():
        emb.add_field(
            name=info["name"], 
            value=f"ID: `{job_id}`\nBasis-Gehalt: `{info['base_pay']}` Coins", 
            inline=True
        )
    await interaction.response.send_message(embed=emb)


@bot.tree.command(name="job_join", description="Nimm einen neuen Beruf an.")
@app_commands.describe(job_id="Die ID des Berufs (z.B. miner, samurai, wizard)")
async def job_join(interaction: discord.Interaction, job_id: str):
    uid = str(interaction.user.id)
    user = state.get_user(uid, interaction.guild_id)
    
    job_id = job_id.lower()
    if job_id not in JOBS_CONFIG:
        await interaction.response.send_message(
            embed=error_embed("Diesen Beruf gibt es nicht. Siehe `/job_list` für alle IDs."), 
            ephemeral=True
        )
        return

    # Job wechseln und Level zurücksetzen
    user.job = job_id
    user.job_level = 1
    
    await state.save_server_async(interaction.guild_id)
    await interaction.response.send_message(
        embed=success_embed(f"Du hast den Beruf **{JOBS_CONFIG[job_id]['name']}** erfolgreich angenommen! Nutze jetzt `/work`.")
    )


@bot.tree.command(name="work", description="Gehe arbeiten, um Münzen zu verdienen.")
async def work(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    user = state.get_user(uid, interaction.guild_id)
    
    if not user.job:
        await interaction.response.send_message(
            embed=error_embed("Du hast aktuell keinen Job! Suche dir erst einen mit `/job_list` und `/job_join`."), 
            ephemeral=True
        )
        return

    now = datetime.now(timezone.utc)
    if user.last_work:
        last = datetime.fromisoformat(user.last_work)
        if now - last < timedelta(minutes=30):
            remaining = timedelta(minutes=30) - (now - last)
            minutes, seconds = divmod(remaining.seconds, 60)
            await interaction.response.send_message(
                embed=error_embed(f"Du bist noch erschöpft von der Arbeit. Warte noch `{minutes}m {seconds}s`."), 
                ephemeral=True
            )
            return

    job_info = JOBS_CONFIG[user.job]
    
    # Lohnberechnung: Basislohn + Bonus pro Job-Level
    base_pay = job_info["base_pay"]
    level_bonus = (user.job_level - 1) * 25
    final_pay = base_pay + level_bonus
    
    # Premium-Multiplikator: 25% mehr Gehalt bei der Arbeit
    if state.is_premium(uid):
        final_pay = int(final_pay * 1.25)

    user.coins += final_pay
    user.last_work = now.isoformat()
    
    # Chance auf ein Job-Level-Up (15% Chance pro Arbeitsschritt)
    lvl_up_msg = ""
    if random.random() < 0.15:
        user.job_level += 1
        lvl_up_msg = f"\n📈 **Beförderung!** Dein Job-Level in **{job_info['name']}** ist auf Level `{user.job_level}` gestiegen!"

    await state.save_server_async(interaction.guild_id)
    
    msg = f"Du hast fleißig als **{job_info['name']}** gearbeitet und `{final_pay}` Münzen verdient!{lvl_up_msg}"
    if state.is_premium(uid):
        msg += " (🌟 1.25x Premium-Verdienstbonus aktiv!)"
        
    await interaction.response.send_message(embed=success_embed(msg))


# --- AUTOMATISCHES TEXT-LEVELSYSTEM ---
@bot.event
async def on_message(message: discord.Message):
    # Verhindert, dass Bots oder Systemnachrichten XP generieren
    if message.author.bot or not message.guild:
        return

    uid = str(message.author.id)
    user = state.get_user(uid, message.guild.id)
    
    # Zufällige XP zwischen 15 und 25. Premium-User erhalten 25% mehr XP.
    xp_gained = random.randint(15, 25)
    if state.is_premium(uid):
        xp_gained = int(xp_gained * 1.25)
        
    user.xp += xp_gained
    
    # Level-Up Berechnung (Benötigte XP = Level * 100)
    needed_xp = user.level * 100
    if user.xp >= needed_xp:
        user.xp -= needed_xp
        user.level += 1
        
        # Belohnung fürs Aufsteigen
        coin_bonus = user.level * 150
        user.coins += coin_bonus
        
        # Level-Up Nachricht im Chat anzeigen
        emb = create_embed(
            "🎉 LEVEL UP!", 
            f"Herzlichen Glückwunsch {message.author.mention}!\n"
            f"Du hast **Level {user.level}** erreicht!\n"
            f"🎁 Belohnung: `+{coin_bonus}` Coins.", 
            Colors.SUCCESS
        )
        await message.channel.send(embed=emb)
        
    # Wichtig, damit die Daten sofort sicher auf der Platte landen
    await state.save_server_async(message.guild.id)
    
    # Verarbeitet alle restlichen Befehle (wichtig für die Slash Commands!)
    await bot.process_commands(message)

# ==============================================================================
# ------- BASIC PET & INVENTORY SHOP SYSTEM -------
# ==============================================================================

@bot.tree.command(name="pet_shop", description="Zeigt eine Übersicht aller adoptierbaren Haustiere auf dem Server.")
async def pet_shop(interaction: discord.Interaction):
    emb = create_embed("🐾 Der Große Haustier-Katalog", "Nutze `/pet_adopt [ID] [Name]` um einen Begleiter zu wählen.", Colors.PET)
    
    # Sortiert die Tiere nach Seltenheit für eine schönere Übersicht
    rarities = defaultdict(list)
    for p_id, p_info in PET_TYPES.items():
        prefix = "🌟 [PREMIUM] " if p_info["premium"] else ""
        rarities[p_info["rarity"]].append(
            f"`{p_id}`: {p_info['name']} {prefix}(HP: {p_info['base_hp']} | ATK: {p_info['base_atk']})"
        )
        
    for rarity, pets_list in rarities.items():
        emb.add_field(name=f"✨ Seltenheit: {rarity.upper()}", value="\n".join(pets_list), inline=False)
        
    await interaction.response.send_message(embed=emb)


@bot.tree.command(name="pet_adopt", description="Adoptiere dein erstes Haustier aus dem Katalog!")
@app_commands.describe(pet_type="Die ID des Haustiers (z.B. cat, slime_king, void_demon)", name="Wie soll dein Tier heißen?")
async def pet_adopt(interaction: discord.Interaction, pet_type: str, name: str):
    uid = str(interaction.user.id)
    
    # Prüfen, ob der User bereits ein Haustier hat
    if state.get_pet(uid) is not None:
        await interaction.response.send_message(embed=error_embed("Du besitzt bereits ein Haustier! Kümmere dich erst um dieses."), ephemeral=True)
        return

    pet_type = pet_type.lower()
    if pet_type not in PET_TYPES:
        await interaction.response.send_message(embed=error_embed("Diesen Haustier-Typ gibt es nicht. Siehe `/pet_shop`."), ephemeral=True)
        return

    type_info = PET_TYPES[pet_type]
    
    # Premium-Check für seltene Haustiere
    if type_info["premium"] and not state.is_premium(uid):
        await interaction.response.send_message(embed=error_embed(f"Das Haustier {type_info['name']} ist nur für 🌟 Premium-Mitglieder verfügbar!"), ephemeral=True)
        return

    # Neues Haustier erstellen
    new_pet = PetProfile(
        name=name,
        type=pet_type,
        max_hp=type_info["base_hp"],
        current_hp=type_info["base_hp"],
        atk=type_info["base_atk"]
    )
    
    state.pets[uid] = new_pet
    await state.save_server_async(interaction.guild_id)
    
    await interaction.response.send_message(embed=success_embed(
        f"Herzlichen Glückwunsch! Du hast dein Haustier **{name}** ({type_info['name']}) erfolgreich adoptiert! 🎉\n"
        f"Nutze `/pet_status`, um nach ihm zu sehen."
    ))


@bot.tree.command(name="pet_status", description="Sieh nach, wie es deinem Haustier aktuell geht.")
async def pet_status(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    pet = state.get_pet(uid)
    
    if not pet:
        await interaction.response.send_message(embed=error_embed("Du hast noch kein Haustier. Nutze `/pet_adopt`, um dir eins zu holen!"), ephemeral=True)
        return

    p_info = PET_TYPES.get(pet.type, {"name": pet.type, "rarity": "Unbekannt"})
    
    # Status-Balken für die Optik berechnen
    hunger_bar = "🟢" * ((20 - pet.hunger) // 4) + "🔴" * (pet.hunger // 4)
    happy_bar = "🟢" * (pet.happiness // 20) + "🔴" * ((100 - pet.happiness) // 20)
    
    emb = create_embed(f"🐾 Haustier-Status: {pet.name}", f"Typ: {p_info['name']} | Seltenheit: `{p_info['rarity'].upper()}`", Colors.PET)
    emb.add_field(name="📊 Werte", value=f"**Level:** {pet.level}\n**XP:** {pet.xp} / {pet.level * 150}\n**Angriff (ATK):** {pet.atk}", inline=True)
    emb.add_field(name="❤️ Gesundheit", value=f"`{pet.current_hp} / {pet.max_hp}` HP", inline=True)
    emb.add_field(name="🍖 Hunger (Höher = Hungriger)", value=f"{hunger_bar} ({pet.hunger}/20)", inline=False)
    emb.add_field(name="🧸 Zufriedenheit", value=f"{happy_bar} ({pet.happiness}/100)", inline=False)
    
    if getattr(pet, "evolved", False):
        emb.set_footer(text="🔱 Dieses Haustier befindet sich in seiner erweckten Form!")
        
    await interaction.response.send_message(embed=emb)


@bot.tree.command(name="pet_feed", description="Füttere dein Haustier mit Futter aus deinem Inventar.")
@app_commands.describe(item_id="Die ID des Futters (z.B. pet_food, apple, banana)")
async def pet_feed(interaction: discord.Interaction, item_id: str):
    uid = str(interaction.user.id)
    user = state.get_user(uid, interaction.guild_id)
    pet = state.get_pet(uid)
    
    if not pet:
        await interaction.response.send_message(embed=error_embed("Du hast kein Haustier, das du füttern könntest."), ephemeral=True)
        return
        
    if pet.hunger <= 0:
        await interaction.response.send_message(embed=info_embed(f"**{pet.name}** ist bereits pappsatt!"), ephemeral=True)
        return

    item = ALL_ITEMS.get(item_id)
    if not item or "hunger" not in item:
        await interaction.response.send_message(embed=error_embed("Das ist kein gültiges Futter. Nutze `pet_food`, `apple` oder `banana`."), ephemeral=True)
        return

    # Prüfen, ob der User das Item besitzt
    if user.inventory.get(item_id, 0) <= 0:
        await interaction.response.send_message(embed=error_embed(f"Du hast kein(e) **{item['name']}** im Inventar!"), ephemeral=True)
        return

    # Füttern berechnen
    user.inventory[item_id] -= 1
    pet.hunger = max(0, pet.hunger + item["hunger"])
    pet.happiness = min(100, pet.happiness + 8) # Füttern macht glücklich
    
    await state.save_server_async(interaction.guild_id)
    await interaction.response.send_message(embed=success_embed(
        f"Du hast **{pet.name}** ein(e) {item['name']} gegeben!\nDer Hunger liegt nun bei `{pet.hunger}/20`."
    ))


@bot.tree.command(name="pet_heal", description="Heile dein Haustier mit einem Heiltrank (health_potion oder elixir).")
@app_commands.describe(item_id="Welchen Trank möchtest du nutzen? (health_potion oder elixir)")
async def pet_heal(interaction: discord.Interaction, item_id: str = "health_potion"):
    uid = str(interaction.user.id)
    user = state.get_user(uid, interaction.guild_id)
    pet = state.get_pet(uid)
    
    if not pet:
        await interaction.response.send_message(embed=error_embed("Du hast kein Haustier zum Heilen."), ephemeral=True)
        return
        
    if pet.current_hp >= pet.max_hp:
        await interaction.response.send_message(embed=info_embed(f"**{pet.name}** hat bereits volle HP!"), ephemeral=True)
        return

    item = ALL_ITEMS.get(item_id)
    if not item or "heal" not in item:
        await interaction.response.send_message(embed=error_embed("Das ist kein gültiger Heiltrank."), ephemeral=True)
        return

    if user.inventory.get(item_id, 0) <= 0:
        await interaction.response.send_message(embed=error_embed(f"Du hast keine `{item_id}` im Inventar!"), ephemeral=True)
        return

    # Heilung anwenden
    user.inventory[item_id] -= 1
    pet.current_hp = min(pet.max_hp, pet.current_hp + item["heal"])
    
    await state.save_server_async(interaction.guild_id)
    await interaction.response.send_message(embed=success_embed(
        f"❤️ Du hast {item['name']} benutzt! **{pet.name}** hat jetzt wieder `{pet.current_hp}/{pet.max_hp}` HP."
    ))


@bot.tree.command(name="inventory", description="Zeigt die Gegenstände in deinem Rucksack an.")
async def inventory(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    user = state.get_user(uid, interaction.guild_id)
    
    emb = create_embed(f"🎒 Rucksack von {interaction.user.display_name}", "", Colors.INFO)
    
    has_items = False
    for item_id, count in user.inventory.items():
        if count > 0:
            item_info = ALL_ITEMS.get(item_id, {"name": item_id})
            emb.add_field(name=item_info["name"], value=f"Anzahl: `{count}` (ID: `{item_id}`)", inline=True)
            has_items = True
            
    if not has_items:
        emb.description = "*Dein Rucksack ist aktuell komplett leer.*"
        
    await interaction.response.send_message(embed=emb)

# ==============================================================================
# ------- MMO COMBAT SYSTEM (PvE DUNGEONS & PvP ARENA) -------
# ==============================================================================

# Abenteuer-Regionen (Dungeons) mit spezifischen Monstern und Beute-Werten
DUNGEON_ZONES = {
    "forest": {
        "name": "🌲 Düsterwald (Level 1-5)",
        "monsters": [
            {"name": "🍄 Giftpilz-Spion", "hp": 50, "atk": 6, "xp": 25, "coins": 30},
            {"name": "🐺 Schattenwolf", "hp": 80, "atk": 12, "xp": 45, "coins": 60}
        ]
    },
    "volcano": {
        "name": "🌋 Vulkan-Festung (Level 5-10)",
        "monsters": [
            {"name": "🔥 Feuer-Elementar", "hp": 140, "atk": 20, "xp": 90, "coins": 120},
            {"name": "🦎 Magma-Eidechse", "hp": 180, "atk": 25, "xp": 130, "coins": 180}
        ]
    },
    "abyss": {
        "name": "🌌 Das Drachen-Nest & Abyss (Level 10+)",
        "monsters": [
            {"name": "💀 Knochen-General", "hp": 280, "atk": 38, "xp": 250, "coins": 300},
            {"name": "🐉 Uralter Urzeit-Drache", "hp": 450, "atk": 55, "xp": 500, "coins": 600}
        ]
    }
}

# Hilfsfunktion zur Berechnung der Arena-Punkte (Elo-System)
def get_pvp_points(user_profile) -> int:
    return 1000 + (user_profile.wins * 20) - (user_profile.losses * 15)


@bot.tree.command(name="adventure_zone", description="Schicke dein Haustier in eine gezielte Kampf-Region (Dungeon).")
@app_commands.describe(zone="Wähle die Region: forest, volcano, abyss")
async def adventure_zone(interaction: discord.Interaction, zone: str):
    uid = str(interaction.user.id)
    user = state.get_user(uid, interaction.guild_id)
    pet = state.get_pet(uid)
    
    if not pet:
        await interaction.response.send_message(embed=error_embed("Du brauchst ein Haustier für Dungeons! Leg dir eins mit `/pet_adopt` zu."), ephemeral=True)
        return
        
    if pet.current_hp <= 20:
        await interaction.response.send_message(embed=error_embed("Dein Haustier ist zu schwach. Heile es mit `/pet_heal`!"), ephemeral=True)
        return

    zone = zone.lower()
    if zone not in DUNGEON_ZONES:
        await interaction.response.send_message(embed=error_embed("Ungültige Region! Wähle: `forest`, `volcano` oder `abyss`."), ephemeral=True)
        return

    # Cooldown Check (3 Minuten Pause zwischen Abenteuern)
    now = datetime.now(timezone.utc)
    if pet.last_adventure:
        last = datetime.fromisoformat(pet.last_adventure)
        if now - last < timedelta(minutes=3):
            rem = timedelta(minutes=3) - (now - last)
            await interaction.response.send_message(embed=error_embed(f"Dein Haustier ruht sich noch aus. Warte `{rem.seconds}`s."), ephemeral=True)
            return

    pet.last_adventure = now.isoformat()
    zone_info = DUNGEON_ZONES[zone]
    monster = random.choice(zone_info["monsters"])
    
    m_hp = monster["hp"]
    p_hp = pet.current_hp
    log = [f"🏰 **Du betrittst: {zone_info['name']}**", f"⚔️ **{pet.name}** kämpft gegen **{monster['name']}**!"]
    
    # Rundenbasierter Kampf im Hintergrund
    while m_hp > 0 and p_hp > 0:
        # Haustier greift an
        dmg = int(pet.atk * random.uniform(0.9, 1.3))
        m_hp -= dmg
        log.append(f"💥 {pet.name} trifft für `{dmg}` Schaden.")
        if m_hp <= 0: break
        
        # Monster kontert
        m_dmg = int(monster["atk"] * random.uniform(0.8, 1.2))
        p_hp -= m_dmg
        log.append(f"👾 {monster['name']} kontert mit `{m_dmg}` Schaden.")

    pet.current_hp = max(0, p_hp)
    
    if m_hp <= 0:
        # Sieg-Auswertung
        user.coins += monster["coins"]
        pet.xp += monster["xp"]
        pet.hunger = min(20, pet.hunger + 2)
        
        # Pet Level Up Check (Bedarf steigt um 150 pro Stufe)
        lvl_msg = ""
        if pet.xp >= pet.level * 150:
            pet.xp -= (pet.level * 150)
            pet.level += 1
            pet.max_hp += 20
            pet.atk += 4
            pet.current_hp = pet.max_hp
            lvl_msg = f"\n🌟 **LEVEL UP!** {pet.name} ist jetzt **Level {pet.level}**!"

        emb = create_embed("🏆 Dungeon-Sieg!", "\n".join(log[-3:]), Colors.SUCCESS)
        emb.add_field(name="Beute", value=f"+`{monster['xp']}` Pet XP\n+`{monster['coins']}` Coins{lvl_msg}")
    else:
        # Niederlage
        pet.happiness = max(0, pet.happiness - 20)
        emb = create_embed("💀 Im Dungeon besiegt...", "\n".join(log[-2:]), Colors.ERROR)
        emb.add_field(name="Status", value=f"⚠️ **{pet.name}** wurde ohnmächtig und musste fliehen (`0` HP). Nutze `/pet_heal`.")

    await state.save_server_async(interaction.guild_id)
    await interaction.response.send_message(embed=emb)


# ------- MULTIPLAYER ARENA (RATED PVP) -------
@bot.tree.command(name="arena_match", description="Fordere ein Server-Mitglied zu einem gewerteten Ranglisten-Match heraus!")
@app_commands.describe(player="Dein Wunschgegner auf dem Server")
async def arena_match(interaction: discord.Interaction, player: discord.User):
    if player.id == interaction.user.id:
        await interaction.response.send_message(embed=error_embed("Du kannst dich nicht selbst herausfordern! Definiere einen Gegner."), ephemeral=True)
        return
        
    p1_id, p2_id = str(interaction.user.id), str(player.id)
    u1, u2 = state.get_user(p1_id, interaction.guild_id), state.get_user(p2_id, interaction.guild_id)
    pet1, pet2 = state.get_pet(p1_id), state.get_pet(p2_id)
    
    if not pet1 or not pet2:
        await interaction.response.send_message(embed=error_embed("Beide Kontrahenten müssen ein registriertes Haustier besitzen!"), ephemeral=True)
        return
        
    if pet1.current_hp <= 20 or pet2.current_hp <= 20:
        await interaction.response.send_message(embed=error_embed("Eines der Haustiere ist zu erschöpft für die Arena (Unter 20 HP)."), ephemeral=True)
        return

    p1_hp, p2_hp = pet1.current_hp, pet2.current_hp
    log = [f"🏟️ **WILLKOMMEN IN DER ARENA** 🏟️", f"🔹 <@{p1_id}>s **{pet1.name}** vs. 🔸 <@{p2_id}>s **{pet2.name}**"]
    
    # Arena-Schlagabtausch
    for _ in range(1, 10):
        # Angreifer 1 schlägt zu
        d1 = int(pet1.atk * random.uniform(0.85, 1.25))
        p2_hp -= d1
        log.append(f"⚔️ **{pet1.name}** teilt `{d1}` DMG aus!")
        if p2_hp <= 0: break
        
        # Angreifer 2 kontert
        d2 = int(pet2.atk * random.uniform(0.85, 1.25))
        p1_hp -= d2
        log.append(f"⚔️ **{pet2.name}** kontert mit `{d2}` DMG!")
        if p1_hp <= 0: break

    # Pets behalten minimal 1 HP im PvP (Sterben nicht endgültig)
    pet1.current_hp = max(1, p1_hp)
    pet2.current_hp = max(1, p2_hp)

    # Punkteverteilung
    if p1_hp > p2_hp:
        u1.wins += 1
        u2.losses += 1
        msg = f"🎉 **Gewinner:** <@{p1_id}>! (+20 Arena-Punkte, +250 Coins)"
        u1.coins += 250
    else:
        u2.wins += 1
        u1.losses += 1
        msg = f"🎉 **Gewinner:** <@{p2_id}>! (+20 Arena-Punkte, +250 Coins)"
        u2.coins += 250

    emb = create_embed("⚔️ Arena-Kampf Beendet", "\n".join(log[-4:]), Colors.PREMIUM)
    emb.add_field(name="Ergebnis", value=msg)
    emb.add_field(name="Aktuelle Punkte", value=f"<@{p1_id}>: `{get_pvp_points(u1)}` Pkt\n<@{p2_id}>: `{get_pvp_points(u2)}` Pkt", inline=False)
    
    await state.save_server_async(interaction.guild_id)
    await interaction.response.send_message(embed=emb)


@bot.tree.command(name="arena_leaderboard", description="Zeigt die aktuelle Rangliste der besten Haustiertrainer des Servers.")
async def arena_leaderboard(interaction: discord.Interaction):
    server_users = []
    
    # Filtert alle User heraus, die auf diesem Server aktiv sind und Haustiere besitzen
    for uid, user_profile in state.users.items():
        if user_profile.server_id == interaction.guild_id:
            pet = state.get_pet(uid)
            if pet:
                points = get_pvp_points(user_profile)
                server_users.append((uid, points, pet.name))
                
    server_users.sort(key=lambda x: x[1], reverse=True)
    
    if not server_users:
        await interaction.response.send_message(embed=info_embed("Es gibt noch keine gewerteten Arena-Kämpfe auf diesem Server."), ephemeral=True)
        return
        
    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for idx, (uid, pts, pet_name) in enumerate(server_users[:10]):
        prefix = medals[idx] if idx < 3 else f"`#{idx+1}`"
        lines.append(f"{prefix} <@{uid}> — **{pts} Pkt** (Pet: *{pet_name}*)")
        
    emb = create_embed("🏆 Arena-Rangliste (Top 10)", "\n".join(lines), Colors.PREMIUM)
    await interaction.response.send_message(embed=emb)

# ==============================================================================
# ------- 🌟 EXCLUSIVE PREMIUM MEMBER CATEGORY & ADMIN & START -------
# ==============================================================================

# Exklusive Boss-Monster für den Premium-Dungeon
PREMIUM_MONSTERS = [
    {"name": "✨ Kosmischer Sternen-Zerstörer", "hp": 600, "atk": 65, "xp": 1000, "coins": 1500},
    {"name": "👑 Goldener Golem-König", "hp": 800, "atk": 50, "xp": 1200, "coins": 2500},
    {"name": "🌌 Void-Gott (Endboss)", "hp": 1200, "atk": 85, "xp": 2500, "coins": 5000}
]

@bot.tree.command(name="premium_claim", description="🌟 Exklusiv: Hole dein tägliches Premium-Paket ab!")
async def premium_claim(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    user = state.get_user(uid, interaction.guild_id)
    
    if not state.is_premium(uid):
        await interaction.response.send_message(embed=error_embed("❌ Dieser Befehl ist nur für 🌟 Premium-Mitglieder reserviert!"), ephemeral=True)
        return

    now = datetime.now(timezone.utc)
    last_claim_str = getattr(user, "last_premium_claim", None)
    
    if last_claim_str:
        last = datetime.fromisoformat(last_claim_str)
        if now - last < timedelta(days=1):
            rem = timedelta(days=1) - (now - last)
            hours, remainder = divmod(rem.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            await interaction.response.send_message(embed=error_embed(f"Du hast dein Premium-Paket heute schon abgeholt. Warte noch `{hours}h {minutes}m`."), ephemeral=True)
            return

    # Belohnungen eintragen
    premium_coins = 2000
    user.coins += premium_coins
    user.inventory["pet_food"] = user.inventory.get("pet_food", 0) + 3
    user.inventory["health_potion"] = user.inventory.get("health_potion", 0) + 2
    
    user.last_premium_claim = now.isoformat()
    await state.save_server_async(interaction.guild_id)
    
    emb = create_embed("🌟 Premium-Tagesbelohnung", "Dein exklusives VIP-Paket wurde geliefert!", Colors.PREMIUM)
    emb.add_field(name="💰 Münzen", value=f"+`{premium_coins}` Coins", inline=True)
    emb.add_field(name="📦 Items", value="+`3x` Haustierfutter\n+`2x` Heiltrank", inline=True)
    await interaction.response.send_message(embed=emb)


@bot.tree.command(name="premium_dungeon", description="🌟 Exklusiv: Betritt die Astralebene für legendäre Bosskämpfe!")
async def premium_dungeon(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    user = state.get_user(uid, interaction.guild_id)
    pet = state.get_pet(uid)
    
    if not state.is_premium(uid):
        await interaction.response.send_message(embed=error_embed("❌ Nur 🌟 Premium-Mitglieder können die Astralebene betreten!"), ephemeral=True)
        return
        
    if not pet:
        await interaction.response.send_message(embed=error_embed("Du brauchst ein Haustier, um diesen Dungeon zu betreten!"), ephemeral=True)
        return
        
    if pet.current_hp < 50:
        await interaction.response.send_message(embed=error_embed(f"Dein Haustier hat zu wenig Leben (`{pet.current_hp} HP`). Heile es zuerst!"), ephemeral=True)
        return

    boss = random.choice(PREMIUM_MONSTERS)
    b_hp = boss["hp"]
    p_hp = pet.current_hp
    log = [f"🌌 **{interaction.user.display_name} öffnet das Portal zur Astralebene!**", f"💥 **{pet.name}** fordert den Boss **{boss['name']}** heraus!"]
    
    while b_hp > 0 and p_hp > 0:
        dmg = int(pet.atk * random.uniform(1.0, 1.4))
        b_hp -= dmg
        log.append(f"⚔️ {pet.name} trifft den Boss für `{dmg}` Schaden.")
        if b_hp <= 0: break
        
        b_dmg = int(boss["atk"] * random.uniform(0.8, 1.1))
        p_hp -= b_dmg
        log.append(f"⚡ {boss['name']} entfesselt Magie für `{b_dmg}` Schaden.")

    pet.current_hp = max(0, p_hp)
    
    if b_hp <= 0:
        user.coins += boss["coins"]
        pet.xp += boss["xp"]
        pet.hunger = min(20, pet.hunger + 1)
        
        lvl_msg = ""
        if pet.xp >= pet.level * 150:
            pet.xp -= (pet.level * 150)
            pet.level += 1
            pet.max_hp += 25
            pet.atk += 5
            pet.current_hp = pet.max_hp
            lvl_msg = f"\n🔥 **LEGENDÄRES LEVEL UP!** {pet.name} erreicht **Level {pet.level}**!"

        emb = create_embed("👑 PREMIUM-SIEG!", "\n".join(log[-3:]), Colors.SUCCESS)
        emb.add_field(name="💎 Legendäre Beute", value=f"+`{boss['xp']}` Pet XP\n+`{boss['coins']}` Coins{lvl_msg}")
    else:
        pet.happiness = max(0, pet.happiness - 10)
        emb = create_embed("🔮 Im Astral-Spalt versagt...", "\n".join(log[-2:]), Colors.ERROR)
        emb.add_field(name="Status", value=f"Der Boss war zu stark. **{pet.name}** wurde zurückgeschleudert (`0` HP).")

    await state.save_server_async(interaction.guild_id)
    await interaction.response.send_message(embed=emb)


@bot.tree.command(name="premium_train", description="🌟 Exklusiv: Trainiere dein Haustier absolut sicher und effektiv.")
async def premium_train(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    pet = state.get_pet(uid)
    
    if not state.is_premium(uid):
        await interaction.response.send_message(embed=error_embed("❌ Dieser Befehl ist nur für 🌟 Premium-Mitglieder!"), ephemeral=True)
        return
        
    if not pet:
        await interaction.response.send_message(embed=error_embed("Du hast kein Haustier zum Trainieren."), ephemeral=True)
        return

    now = datetime.now(timezone.utc)
    last_train_str = getattr(pet, "last_premium_train", None)
    
    if last_train_str:
        last = datetime.fromisoformat(last_train_str)
        if now - last < timedelta(hours=12):
            rem = timedelta(hours=12) - (now - last)
            hours, remainder = divmod(rem.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            await interaction.response.send_message(embed=error_embed(f"Dein Haustier hat Muskelkater. Warte noch `{hours}h {minutes}m`."), ephemeral=True)
            return

    xp_reward = pet.level * 80
    pet.xp += xp_reward
    pet.happiness = min(100, pet.happiness + 15)
    pet.hunger = min(20, pet.hunger + 1)
    
    lvl_msg = ""
    if pet.xp >= pet.level * 150:
        pet.xp -= (pet.level * 150)
        pet.level += 1
        pet.max_hp += 20
        pet.atk += 4
        pet.current_hp = pet.max_hp
        lvl_msg = f"\n🎉 **LEVEL UP!** {pet.name} steigt auf **Level {pet.level}**!"

    pet.last_premium_train = now.isoformat()
    await state.save_server_async(interaction.guild_id)
    
    emb = create_embed(f"🏋️‍♂️ VIP-Spezialtraining für {pet.name}", "Das Training verlief absolut perfekt und ohne Verletzungen!", Colors.PREMIUM)
    emb.add_field(name="Ergebnis", value=f"+`{xp_reward}` Pet XP\n+`15` Zufriedenheit{lvl_msg}")
    await interaction.response.send_message(embed=emb)


@bot.tree.command(name="premium_evolve", description="🌟 Exklusiv: Entwickle dein Haustier ab Level 15 weiter!")
async def premium_evolve(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    pet = state.get_pet(uid)
    
    if not state.is_premium(uid):
        await interaction.response.send_message(embed=error_embed("❌ Dieser Befehl ist nur für 🌟 Premium-Mitglieder!"), ephemeral=True)
        return
        
    if not pet:
        await interaction.response.send_message(embed=error_embed("Du hast kein Haustier."), ephemeral=True)
        return
        
    if pet.level < 15:
        await interaction.response.send_message(embed=error_embed(f"Dein Haustier muss mindestens **Level 15** sein. Aktuell: Level `{pet.level}`."), ephemeral=True)
        return
        
    if getattr(pet, "evolved", False):
        await interaction.response.send_message(embed=error_embed("Dein Haustier hat bereits seine finale Evolutionsstufe erreicht!"), ephemeral=True)
        return

    pet.evolved = True
    pet.name = f"🔱 Erweckter {pet.name}"
    pet.max_hp += 100
    pet.current_hp = pet.max_hp
    pet.atk += 25
    
    await state.save_server_async(interaction.guild_id)
    
    emb = create_embed("✨ GÖTTLICHE EVOLUTION ✨", "Die Energie der Astralebene durchströmt dein Haustier!", Colors.PREMIUM)
    emb.add_field(name="Neuer Status", value=f"Dein Begleiter heißt nun: **{pet.name}**!\n❤️ Max HP: `+100`\n⚔️ ATK: `+25`")
    await interaction.response.send_message(embed=emb)


@bot.tree.command(name="premium_blessing", description="🌟 Exklusiv: Heile und füttere dein Tier sofort komplett kostenlos (Alle 4h).")
async def premium_blessing(interaction: discord.Interaction):
    uid = str(interaction.user.id)
    pet = state.get_pet(uid)
    
    if not state.is_premium(uid):
        await interaction.response.send_message(embed=error_embed("❌ Nur für 🌟 Premium-Mitglieder!"), ephemeral=True)
        return
        
    if not pet:
        await interaction.response.send_message(embed=error_embed("Du hast kein Haustier."), ephemeral=True)
        return

    now = datetime.now(timezone.utc)
    last_bless_str = getattr(pet, "last_premium_bless", None)
    
    if last_bless_str:
        last = datetime.fromisoformat(last_bless_str)
        if now - last < timedelta(hours=4):
            rem = timedelta(hours=4) - (now - last)
            hours, remainder = divmod(rem.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            await interaction.response.send_message(embed=error_embed(f"Der Segen lädt noch auf. Warte noch `{hours}h {minutes}m`."), ephemeral=True)
            return

    pet.current_hp = pet.max_hp
    pet.hunger = 0
    pet.happiness = 100
    pet.last_premium_bless = now.isoformat()
    
    await state.save_server_async(interaction.guild_id)
    
    emb = create_embed("✨ Göttlicher Segen aktiviert", f"Eine magische Aura umhüllt **{pet.name}**!", Colors.SUCCESS)
    emb.add_field(name="Effekt", value="❤️ HP komplett geheilt!\n🍖 Hunger auf 0 reduziert!\n🧸 Zufriedenheit auf 100%!")
    await interaction.response.send_message(embed=emb)


@bot.tree.command(name="premium_market", description="🌟 Exklusiv: Kaufe seltene Gegenstände auf dem VIP-Schwarzmarkt.")
@app_commands.describe(item_id="Welches Item? (elixir, golden_apple)", amount="Wie viele?")
async def premium_market(interaction: discord.Interaction, item_id: str, amount: int = 1):
    uid = str(interaction.user.id)
    user = state.get_user(uid, interaction.guild_id)
    
    if not state.is_premium(uid):
        await interaction.response.send_message(embed=error_embed("❌ Zutritt zum Schwarzmarkt nur für 🌟 Premium-Mitglieder!"), ephemeral=True)
        return

    vip_shop = {
        "elixir": {"name": "🧪 Elixier der Götter (Heilt 200 HP)", "price": 1500},
        "golden_apple": {"name": "🍏 Goldenes Futter (Sättigt komplett)", "price": 1000}
    }

    if item_id not in vip_shop:
        await interaction.response.send_message(embed=error_embed("Dieses Item gibt es nicht. Verfügbar: `elixir`, `golden_apple`."), ephemeral=True)
        return

    if amount <= 0:
        await interaction.response.send_message(embed=error_embed("Ungültige Menge!"), ephemeral=True)
        return

    item_info = vip_shop[item_id]
    total_cost = item_info["price"] * amount

    if user.coins < total_cost:
        await interaction.response.send_message(embed=error_embed(f"Du hast nicht genug Coins! Kosten: `{total_cost}` Coins."), ephemeral=True)
        return

    user.coins -= total_cost
    user.inventory[item_id] = user.inventory.get(item_id, 0) + amount
    
    await state.save_server_async(interaction.guild_id)
    await interaction.response.send_message(embed=success_embed(f"🛍️ Du hast `{amount}x` **{item_info['name']}** für `{total_cost}` Coins gekauft!"))


# ------- 🛠️ ADMIN COMMANDS -------
@bot.tree.command(name="admin_add_premium", description="Füge ein Mitglied der Premium-Liste hinzu (Nur Administratoren).")
@app_commands.describe(user="Der Spieler, der Premium erhalten soll")
@commands.has_permissions(administrator=True)
async def admin_add_premium(interaction: discord.Interaction, user: discord.User):
    target_id = str(user.id)
    state.premium_users.add(target_id)
    await state.save_server_async(interaction.guild_id)
    await interaction.response.send_message(embed=success_embed(f"🌟 <@{target_id}> wurde erfolgreich zur Premium-Gruppe hinzugefügt!"))


@bot.tree.command(name="admin_remove_premium", description="Entferne den Premium-Status eines Nutzers (Nur Administratoren).")
@app_commands.describe(user="Der Spieler, dem Premium entzogen werden soll")
@commands.has_permissions(administrator=True)
async def admin_remove_premium(interaction: discord.Interaction, user: discord.User):
    target_id = str(user.id)
    if target_id in state.premium_users:
        state.premium_users.remove(target_id)
        await state.save_server_async(interaction.guild_id)
        await interaction.response.send_message(embed=success_embed(f"❌ <@{target_id}> wurde aus der Premium-Gruppe entfernt."))
    else:
        await interaction.response.send_message(embed=error_embed("Dieser Nutzer hat kein Premium."), ephemeral=True)


# --- START EVENT & SYNCHRONISATION ---
@bot.event
async def on_ready():
    print(f"🤖 {bot.user.name} ist jetzt online und betriebsbereit!")
    
    # Lädt die Daten für jeden Server, auf dem der Bot aktiv ist
    for guild in bot.guilds:
        await state.load_server_async(guild.id)
        print(f"📁 Daten für Server '{guild.name}' ({guild.id}) geladen.")
        
    try:
        synced = await bot.tree.sync()
        print(f"🔄 {len(synced)} Slash Commands erfolgreich global synchronisiert!")
    except Exception as e:
        print(f"Fehler beim Synchronisieren der Befehle: {e}")


# --- BOT AUSFÜHREN ---
if __name__ == "__main__":
    # Ersetze 'DEIN_BOT_TOKEN_HIER' durch das echte Token aus dem Discord Developer Portal
    bot.run("DEIN_BOT_TOKEN_HIER")

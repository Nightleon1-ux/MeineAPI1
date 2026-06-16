import discord
from discord import app_commands
import os
import json
import random
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# ─── OWNER CONFIGURATION ───────────────────────────────────
OWNER_ID = 1405193599984861255  # Deine Discord-ID (Nightleon1)

# ─── COLOR PALETTE ─────────────────────────────────────────
class BotFarben:
    INFO = 0x5DADE2
    ERFOLG = 0x57F287
    FEHLER = 0xED4245
    PREMIUM = 0xD4AF37  # Edles VIP-Gold
    WIRTSCHAFT = 0xE67E22

# ─── DATEN-MODELLE FÜR DAS GESAMTE SYSTEM ───────────────────
@dataclass
class UserProfile:
    xp: int = 0
    level: int = 1
    gesamt_xp: int = 0
    muenzen: int = 100
    server_id: Optional[int] = None  
    inventar: Dict[str, int] = field(default_factory=dict)  
    
    # Familien-System
    partner_id: Optional[str] = None
    hochzeits_datum: Optional[str] = None
    ehe_konto: int = 0
    letzter_zins_claim: Optional[str] = None
    kinder: Dict[str, dict] = field(default_factory=dict)
    
    # Standard-Cooldowns
    letztes_daily: Optional[str] = None
    letzte_arbeit: Optional[str] = None
    letzte_mine: Optional[str] = None
    
    # Premium-Kosmetik & -Eigenschaften
    premium_bis: Optional[str] = None  
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
    letztes_abenteuer: Optional[str] = None
    premium_verkleidung: Optional[str] = None

# ─── SYSTEM-STATE & DATENBANK-VERWALTUNG ────────────────────
class BotState:
    def __init__(self, datei_pfad: str = "global_bot_daten.json"):
        self.datei_pfad = datei_pfad
        self.user_daten: Dict[str, UserProfile] = {}
        self.pet_daten: Dict[str, PetProfile] = {}
        self.laden()

    def get_user(self, user_id: str, server_id: Optional[int] = None) -> UserProfile:
        if user_id not in self.user_daten:
            self.user_daten[user_id] = UserProfile()
        if server_id:
            self.user_daten[user_id].server_id = server_id
        return self.user_daten[user_id]

    def ist_premium(self, user_id: str) -> bool:
        u = self.get_user(user_id)
        if not u.premium_bis: 
            return False
        if u.premium_bis == "permanent": 
            return True
        try:
            bis_zeit = datetime.fromisoformat(u.premium_bis)
            if datetime.now(timezone.utc) < bis_zeit:
                return True
            else:
                u.premium_bis = None  
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
            print(f"⚠️ Fehler beim Speichern der Datenbank: {e}")

    def laden(self):
        if os.path.exists(self.datei_pfad):
            try:
                with open(self.datei_pfad, "r", encoding="utf-8") as f:
                    daten = json.load(f)
                    self.user_daten = {
                        uid: UserProfile(**{k: v for k, v in val.items() if k in UserProfile.__dataclass_fields__}) 
                        for uid, val in daten.get("users", {}).items()
                    }
                    self.pet_daten = {
                        uid: PetProfile(**{k: v for k, v in val.items() if k in PetProfile.__dataclass_fields__}) 
                        for uid, val in daten.get("pets", {}).items()
                    }
            except Exception as e:
                print(f"⚠️ Fehler beim Laden der Datenbank: {e}")

state = BotState()

# ─── ERWEITERTE SHOP-DATENBANK ─────────────────────────────
NAHRUNG_ITEMS = {
    "erdbeere": {"name": "🍓 Frische Erdbeere", "preis": 5, "hunger": -5, "typ": "food"},
    "blaubeere": {"name": "🫐 Blaubeere", "preis": 5, "hunger": -5, "typ": "food"},
    "himbeere": {"name": "🍒 Himbeere", "preis": 8, "hunger": -8, "typ": "food"},
    "kirsche": {"name": "🍒 Kirsche", "preis": 8, "hunger": -8, "typ": "food"},
    "wassermelone": {"name": "🍉 Wassermelonen-Stück", "preis": 12, "hunger": -12, "typ": "food"},
    "apfel_gruen": {"name": "🍏 Grüner Apfel", "preis": 15, "hunger": -15, "typ": "food"},
    "banane": {"name": "🍌 Gelbe Banane", "preis": 15, "hunger": -15, "typ": "food"},
    "birne": {"name": "🍐 Flussbirne", "preis": 18, "hunger": -18, "typ": "food"},
    "pflaume": {"name": "🫐 Pflaume", "preis": 18, "hunger": -18, "typ": "food"},
    "pfirsich": {"name": "🍑 Pfirsich", "preis": 20, "hunger": -20, "typ": "food"},
    "karotte": {"name": "🥕 Karotte", "preis": 22, "hunger": -22, "typ": "food"},
    "gurke": {"name": "🥒 Gurkenscheibe", "preis": 22, "hunger": -22, "typ": "food"},
    "tomate": {"name": "🍅 Tomate", "preis": 25, "hunger": -25, "typ": "food"},
    "radieschen": {"name": "🥗 Radieschen", "preis": 25, "hunger": -25, "typ": "food"},
    "salat": {"name": "🥬 Salatblatt", "preis": 30, "hunger": -25, "typ": "food"},
    "baguette": {"name": "🥖 Frisches Baguette", "preis": 35, "hunger": -30, "typ": "food"},
    "vollkornbrot": {"name": "🍞 Vollkornbrot", "preis": 38, "hunger": -32, "typ": "food"},
    "brezel": {"name": "🥨 Brezel", "preis": 40, "hunger": -35, "typ": "food"},
    "kaesebrot": {"name": "🧀 Käsebrot", "preis": 45, "hunger": -40, "typ": "food"},
    "ruehrei": {"name": "🍳 Rührei", "preis": 50, "hunger": -45, "typ": "food"},
    "kartoffelsalat": {"name": "🥗 Kartoffelsalat", "preis": 55, "hunger": -50, "typ": "food"},
    "spaghetti": {"name": "🍝 Spaghetti Bolognese", "preis": 60, "hunger": -55, "typ": "food"},
    "gemuesesuppe": {"name": "🥣 Gemüsesuppe", "preis": 65, "hunger": -55, "typ": "food"},
    "reispfanne": {"name": "🍛 Reispfanne", "preis": 70, "hunger": -60, "typ": "food"},
    "haehnchen": {"name": "🍗 Hähnchenschenkel", "preis": 75, "hunger": -60, "typ": "food"},
    "fischstaebchen": {"name": "🐟 Fischstäbchen", "preis": 80, "hunger": -65, "typ": "food"},
    "lachs": {"name": "🍣 Lachsfilet", "preis": 85, "hunger": -65, "typ": "food"},
    "sandwich": {"name": "🥪 Thunfisch-Sandwich", "preis": 85, "hunger": -65, "typ": "food"},
    "spaetzle": {"name": "🍜 Käse-Spätzle", "preis": 90, "hunger": -70, "typ": "food"},
    "pommes": {"name": "🍟 Pommes Rot-Weiß", "preis": 90, "hunger": -70, "typ": "food"},
    "donut": {"name": "🍩 Schokorand-Donut", "preis": 40, "hunger": -35, "typ": "food"},
    "zuckerwatte": {"name": "🍭 Zuckerwatte", "preis": 45, "hunger": -35, "typ": "food"},
    "muffin": {"name": "🧁 Muffin", "preis": 50, "hunger": -40, "typ": "food"},
    "erdbeerkuchen": {"name": "🍰 Erdbeerkuchen", "preis": 65, "hunger": -50, "typ": "food"},
    "schokolade": {"name": "🍫 Schokoladentafel", "preis": 70, "hunger": -50, "typ": "food"},
    "gummibaerchen": {"name": "🧸 Gummibärchen", "preis": 75, "hunger": -55, "typ": "food"},
    "hamburger": {"name": "🍔 Hamburger", "preis": 100, "hunger": -70, "typ": "food"},
    "cheeseburger": {"name": "🧀 Cheeseburger", "preis": 110, "hunger": -72, "typ": "food"},
    "hotdog": {"name": "🌭 Hotdog", "preis": 115, "hunger": -75, "typ": "food"},
    "taco": {"name": "🌮 Knusprige Taco-Schale", "preis": 120, "hunger": -75, "typ": "food"},
}

SAMMLER_ITEMS = {
    "statue": {"name": "🗿 Antike Marmor-Statue", "preis": 15000, "wert": 15000, "typ": "collector", "premium": False},
    "vase": {"name": "🏺 Goldene Pharaonen-Vase", "preis": 35000, "wert": 35000, "typ": "collector", "premium": False},
    "gemaelde": {"name": "🖼️ Das geheimnisvolle Gemälde", "preis": 75000, "wert": 75000, "typ": "collector", "premium": False},
    "excalibur": {"name": "⚔️ Königsschwert Excalibur", "preis": 150000, "wert": 150000, "typ": "collector", "premium": True},
    "astral_diamant": {"name": "💎 Funkelnder Astral-Diamant", "preis": 300000, "wert": 300000, "typ": "collector", "premium": True},
    "kaiserkrone": {"name": "👑 Kaiserkrone von Nightleon1", "preis": 1000000, "wert": 1000000, "typ": "collector", "premium": True}
}

ALL_ITEMS = {**NAHRUNG_ITEMS, **SAMMLER_ITEMS}

PREMIUM_WELTEN = {
    "chronos": {"name": "⏳ Der Chronos-Riss", "min_level": 15, "boss": "🕒 Temporaler Wächter", "boss_hp": 350, "belohnung_min": 800, "belohnung_max": 1500},
    "astral": {"name": "🌌 Die Astral-Ebene", "min_level": 25, "boss": "✨ Sternen-Phönix", "boss_hp": 600, "belohnung_min": 1800, "belohnung_max": 3000},
    "obsidian": {"name": "🌋 Die Obsidian-Hölle", "min_level": 40, "boss": "🔥 Höllenfürst Malakor", "boss_hp": 1200, "belohnung_min": 5000, "belohnung_max": 8500}
}

# ─── UTILS ─────────────────────────────────────────────────
def erstelle_embed(titel: str, beschreibung: str, farbe: int) -> discord.Embed:
    return discord.Embed(title=titel, description=beschreibung, color=farbe, timestamp=datetime.now(timezone.utc))

def fehler_embed(text: str) -> discord.Embed:
    return erstelle_embed("❌ Fehler", text, BotFarben.FEHLER)

def xp_hinzufuegen(user_id: str, menge: int) -> bool:
    u = state.get_user(user_id)
    if state.ist_premium(user_id):
        menge = int(menge * 1.25)  
        
    u.xp += menge
    u.gesamt_xp += menge
    benoetigt = u.level * 100
    level_up = False
    
    while u.xp >= benoetigt:
        u.xp -= benoetigt
        u.level += 1
        bonus = u.level * 50
        if state.ist_premium(user_id): 
            bonus = int(bonus * 1.25)  
        u.muenzen += bonus
        benoetigt = u.level * 100
        level_up = True
    return level_up

def hole_sortierte_liste(kategorie: str, scope: str, guild_id: Optional[int] = None) -> list:
    gefilterte_liste = []
    for u_id, u_profile in state.user_daten.items():
        if scope == "server" and (u_profile.server_id != guild_id):
            continue
            
        if kategorie == "level":
            wert = u_profile.level
            sub_wert = u_profile.xp
        elif kategorie == "money":
            wert = u_profile.muenzen
            sub_wert = u_profile.level
        elif kategorie == "collector":
            wert = sum(SAMMLER_ITEMS[iid]["wert"] * anz for iid, anz in u_profile.inventar.items() if iid in SAMMLER_ITEMS)
            sub_wert = u_profile.muenzen
            
        if wert > 0 or kategorie != "collector":
            gefilterte_liste.append({
                "id": int(u_id),
                "wert": wert,
                "sub_wert": sub_wert,
                "premium": state.ist_premium(u_id),
                "titel": u_profile.premium_titel
            })
            
    gefilterte_liste.sort(key=lambda x: (x["wert"], x["sub_wert"]), reverse=True)
    return gefilterte_liste

def berechne_ehe_zinsen(user_id: str) -> int:
    u = state.get_user(user_id)
    if not u.partner_id or u.ehe_konto <= 0:
        return 0
    if not (state.ist_premium(user_id) or state.ist_premium(u.partner_id)):
        return 0
        
    jetzt = datetime.now(timezone.utc)
    if not u.letzter_zins_claim:
        u.letzter_zins_claim = jetzt.isoformat()
        state.speichern()
        return 0
        
    letzter_claim = datetime.fromisoformat(u.letzter_zins_claim)
    tage = (jetzt - letzter_claim).days
    
    if tage >= 1:
        zins_satz = 0.02
        gesamt_zins = 0
        konto_stand = u.ehe_konto
        for _ in range(min(tage, 30)):
            täglicher_zins = min(int(konto_stand * zins_satz), 500)
            gesamt_zins += täglicher_zins
            konto_stand += täglicher_zins
        return gesamt_zins
    return 0

# ─── SHOP UI COMPONENTS ────────────────────────────────────
class ItemKaufDropdown(discord.ui.Select):
    def __init__(self, items_dict: dict, placeholder_text: str, user_premium: bool):
        options = [
            discord.SelectOption(
                label=f"{'⭐ [VIP] ' if i.get('premium', False) else ''}{i['name']}", 
                description=f"Preis: {i['preis']} Münzen", 
                value=k
            ) for k, i in items_dict.items()
        ]
        super().__init__(placeholder=placeholder_text, min_values=1, max_values=1, options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        item_id = self.values[0]
        item = ALL_ITEMS[item_id]
        u_id = str(interaction.user.id)
        u = state.get_user(u_id, server_id=interaction.guild_id)
        
        if item.get("premium", False) and not state.ist_premium(u_id):
            return await interaction.response.send_message(embed=fehler_embed("Dieses seltene Sammlerstück ist exklusiv für Premium-Mitglieder!"), ephemeral=True)
            
        if u.muenzen < item["preis"]:
            return await interaction.response.send_message(embed=fehler_embed(f"Du hast nicht genug Geld! Dir fehlen {item['preis'] - u.muenzen} Münzen."), ephemeral=True)
            
        u.muenzen -= item["preis"]
        u.inventar[item_id] = u.inventar.get(item_id, 0) + 1
        state.speichern()
        
        await interaction.response.send_message(
            embed=erstelle_embed("🛒 Kauf erfolgreich!", f"Du hast **{item['name']}** für **{item['preis']} Münzen** gekauft!", BotFarben.ERFOLG),
            ephemeral=True
        )

class MegaShopView(discord.ui.View):
    def __init__(self, user_premium: bool, kategorie: str):
        super().__init__(timeout=120)
        if kategorie == "food":
            all_food = list(NAHRUNG_ITEMS.items())
            self.add_item(ItemKaufDropdown(dict(all_food[:20]), "🍏 Snacks & Kleines kaufen...", user_premium))
            self.add_item(ItemKaufDropdown(dict(all_food[20:]), "🍔 Mahlzeiten & Fast-Food kaufen...", user_premium))
        elif kategorie == "collector":
            self.add_item(ItemKaufDropdown(SAMMLER_ITEMS, "👑 Teure Statussymbole & Relikte...", user_premium))

# ─── DISCORD BOT CORE ──────────────────────────────────────
class PremiumCoreBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

bot = PremiumCoreBot()

@bot.event
async def on_ready():
    print(f"💎 System vollständig geladen! Bereit als {bot.user.name} (Owner-ID aktiv)")

@bot.event
async def on_message(message):
    if message.author.bot or not message.guild: 
        return
    user_id = str(message.author.id)
    state.get_user(user_id, server_id=message.guild.id)
    
    if len(message.content) > 3 and not message.content.startswith("/"):
        if xp_hinzufuegen(user_id, 3):
            u = state.get_user(user_id)
            state.speichern()
            await message.channel.send(f"🎉 **Level Up!** {message.author.mention} hat Stufe **{u.level}** erreicht!")

# ─── OWNER SYSTEM COMMANDS ──────────────────────────────────
@bot.tree.command(name="premium-give", description="Schaltet den Premium-Status zeitbasiert frei (Nur Owner).")
@app_commands.choices(paket=[
    app_commands.Choice(name="1 Monat (30 Tage)", value="1m"),
    app_commands.Choice(name="3 Monate (90 Tage)", value="3m"),
    app_commands.Choice(name="6 Monate (180 Tage)", value="6m"),
    app_commands.Choice(name="Permanent (Lebenslang)", value="perm")
])
async def premium_give(interaction: discord.Interaction, user: discord.User, paket: app_commands.Choice[str]):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message(embed=fehler_embed("Du bist nicht der Owner!"), ephemeral=True)
    
    u = state.get_user(str(user.id), server_id=interaction.guild_id)
    jetzt = datetime.now(timezone.utc)
    
    if paket.value == "1m": u.premium_bis = (jetzt + timedelta(days=30)).isoformat()
    elif paket.value == "3m": u.premium_bis = (jetzt + timedelta(days=90)).isoformat()
    elif paket.value == "6m": u.premium_bis = (jetzt + timedelta(days=180)).isoformat()
    elif paket.value == "perm": u.premium_bis = "permanent"
        
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("💎 Premium aktiviert!", f"Laufzeit für {user.mention}: **{paket.name}**\n📈 Passive +25% Boosts sind aktiv!", BotFarben.PREMIUM))

@bot.tree.command(name="premium-remove", description="Entzieht einem User sämtliche Premium-Rechte (Nur Owner).")
async def premium_remove(interaction: discord.Interaction, user: discord.User):
    if interaction.user.id != OWNER_ID:
        return await interaction.response.send_message(embed=fehler_embed("Zugriff verweigert."), ephemeral=True)
    u.premium_bis = None
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🗑️ Premium beendet", f"VIP-Rechte für {user.mention} gelöscht.", BotFarben.FEHLER))

@bot.tree.command(name="premium-status", description="Überprüft deine restliche VIP-Laufzeit.")
async def premium_status(interaction: discord.Interaction):
    u_id = str(interaction.user.id)
    u = state.get_user(u_id, server_id=interaction.guild_id)
    if not state.ist_premium(u_id):
        return await interaction.response.send_message(embed=erstelle_embed("🕊️ Premium-Status", "Du besitzt aktuell kein aktives Premium-Paket.", BotFarben.INFO), ephemeral=True)
    zeit_anzeige = "∞ Lebenslang" if u.premium_bis == "permanent" else f"{datetime.fromisoformat(u.premium_bis).strftime('%d.%m.%Y um %H:%M UTC')}"
    await interaction.response.send_message(embed=erstelle_embed("💎 VIP-Status", f"Status: **AKTIV**\nLaufzeit bis: **{zeit_anzeige}**", BotFarben.PREMIUM))

# ─── WIRTSCHAFTS- & SHOP-COMMANDS ───────────────────────────
@bot.tree.command(name="shop", description="Öffnet den Marktplatz.")
@app_commands.choices(kategorie=[
    app_commands.Choice(name="🍏 Nahrungsmittel (40+ Items)", value="food"),
    app_commands.Choice(name="👑 Luxus-Sammlerstücke (Prestige)", value="collector")
])
async def shop(interaction: discord.Interaction, kategorie: app_commands.Choice[str]):
    view = MegaShopView(user_premium=state.ist_premium(str(interaction.user.id)), kategorie=kategorie.value)
    embed = erstelle_embed("🛒 Shop", f"Wähle deine Kategorie: **{kategorie.name}**", BotFarben.WIRTSCHAFT if kategorie.value == "food" else BotFarben.PREMIUM)
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="inventory", description="Zeigt deine Gegenstände.")
async def inventory(interaction: discord.Interaction):
    u = state.get_user(str(interaction.user.id), server_id=interaction.guild_id)
    food, coll, gesamt = [], [], 0
    for iid, anz in u.inventar.items():
        if anz <= 0: continue
        if iid in NAHRUNG_ITEMS: food.append(f"• {NAHRUNG_ITEMS[iid]['name']} x**{anz}**")
        elif iid in SAMMLER_ITEMS:
            coll.append(f"• {SAMMLER_ITEMS[iid]['name']} x**{anz}**")
            gesamt += SAMMLER_ITEMS[iid]["wert"] * anz
    embed = discord.Embed(title=f"🎒 Inventar von {interaction.user.name}", color=BotFarben.INFO)
    if food: embed.add_field(name="🍏 Vorräte", value="\n".join(food), inline=False)
    if coll: embed.add_field(name="🏛️ Sammlerstücke", value="\n".join(coll), inline=False)
    if coll: embed.add_field(name="📊 Sammlungswert", value=f"`🪙 {gesamt:,} Münzen`", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="item-give", description="Gibt Gegenstände an jemanden weiter.")
async def item_give(interaction: discord.Interaction, empfaenger: discord.Member, item_id: str, anzahl: int = 1):
    u = state.get_user(str(interaction.user.id)); empf = state.get_user(str(empfaenger.id))
    if item_id not in ALL_ITEMS or u.inventar.get(item_id, 0) < anzahl or anzahl <= 0:
        return await interaction.response.send_message(embed=fehler_embed("Ungültige Übergabe."), ephemeral=True)
    u.inventar[item_id] -= anzahl; empf.inventar[item_id] = empf.inventar.get(item_id, 0) + anzahl
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("📦 Item-Transfer", f"{anzahl}x {ALL_ITEMS[item_id]['name']} an {empfaenger.mention} übergeben!", BotFarben.ERFOLG))

# ─── RANKINGS / LEADERBOARD COMMANDS ────────────────────────
@bot.tree.command(name="leaderboard", description="Zeigt die Bestenliste für Level oder Münzen.")
@app_commands.choices(kategorie=[app_commands.Choice(name="Level", value="level"), app_commands.Choice(name="Münzen", value="money")])
@app_commands.choices(typ=[app_commands.Choice(name="Server", value="server"), app_commands.Choice(name="Global", value="global")])
@app_commands.choices(plaetze=[app_commands.Choice(name="Top 10", value=10), app_commands.Choice(name="Top 25", value=25), app_commands.Choice(name="Top 50", value=50)])
async def leaderboard(interaction: discord.Interaction, kategorie: app_commands.Choice[str], typ: app_commands.Choice[str], plaetze: app_commands.Choice[int]):
    await interaction.response.defer()
    daten = hole_sortierte_liste(kategorie.value, typ.value, interaction.guild_id)[:plaetze.value]
    zeilen = [f"{'🥇' if i==0 else '🥈' if i==1 else '🥉' if i==2 else f'`#{i+1:02d}`'} {'💎 ' if d['premium'] else ''}<@{d['id']}> — " + (f"Lvl **{d['wert']}**" if kategorie.value == "level" else f"`🪙 {d['wert']:,}`") for i, d in enumerate(daten)]
    embed = discord.Embed(title=f"🏆 Top {len(daten)} Ranking ({typ.name})", color=BotFarben.PREMIUM if typ.value == "global" else BotFarben.INFO)
    embed.description = "\n".join(zeilen) if len("\n".join(zeilen)) <= 4000 else "Liste zu lang zum Darstellen."
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="leaderboard-sammler", description="Bestenliste des Sammlungswertes.")
@app_commands.choices(typ=[app_commands.Choice(name="Server", value="server"), app_commands.Choice(name="Global", value="global")])
@app_commands.choices(plaetze=[app_commands.Choice(name="Top 10", value=10), app_commands.Choice(name="Top 25", value=25), app_commands.Choice(name="Top 50", value=50)])
async def leaderboard_sammler(interaction: discord.Interaction, typ: app_commands.Choice[str], plaetze: app_commands.Choice[int]):
    await interaction.response.defer()
    daten = hole_sortierte_liste("collector", typ.value, interaction.guild_id)[:plaetze.value]
    zeilen = [f"{'👑' if i==0 else '💎' if i==1 else '🔱' if i==2 else f'`#{i+1:02d}`'} {'✨ ' if d['premium'] else ''}<@{d['id']}>\n  ↳ Wert: **{d['wert']:,} Münzen**" for i, d in enumerate(daten)]
    embed = discord.Embed(title=f"🏛️ Top {len(daten)} Antiquitäten-Sammler ({typ.name})", color=BotFarben.PREMIUM)
    embed.description = "\n".join(zeilen) if len("\n".join(zeilen)) <= 4000 else "Liste zu lang."
    await interaction.followup.send(embed=embed)

# ─── PREMIUM FAMILY SYSTEMS ─────────────────────────────────
@bot.tree.command(name="family-bank", description="Verwalte das gemeinsame Ehekonto.")
@app_commands.choices(aktion=[app_commands.Choice(name="Prüfen", value="check"), app_commands.Choice(name="Einzahlen", value="deposit"), app_commands.Choice(name="Auszahlen", value="withdraw")])
async def family_bank(interaction: discord.Interaction, aktion: app_commands.Choice[str], betrag: Optional[int] = None):
    u_id = str(interaction.user.id); u = state.get_user(u_id)
    if not u.partner_id: return await interaction.response.send_message(embed=fehler_embed("Du bist nicht verheiratet!"), ephemeral=True)
    p = state.get_user(u.partner_id)
    
    zinsen = berechne_ehe_zinsen(u_id)
    if zinsen > 0:
        u.ehe_konto += zinsen; p.ehe_konto = u.ehe_konto
        u.letzter_zins_claim = p.letzter_zins_claim = datetime.now(timezone.utc).isoformat()
        await interaction.channel.send(f"📈 **VIP-Zinsen!** Das Ehekonto hat **{zinsen} Münzen** generiert!")

    if aktion.value == "check":
        return await interaction.response.send_message(embed=erstelle_embed("🏦 Ehekonto", f"Kontostand: `🪙 {u.ehe_konto:,} Münzen`", BotFarben.PREMIUM))
    if betrag is None or betrag <= 0: return await interaction.response.send_message(embed=fehler_embed("Ungültiger Betrag."), ephemeral=True)

    if aktion.value == "deposit":
        if u.muenzen < betrag: return await interaction.response.send_message(embed=fehler_embed("Zu wenig Geld."), ephemeral=True)
        u.muenzen -= betrag; u.ehe_konto += betrag; p.ehe_konto = u.ehe_konto
    elif aktion.value == "withdraw":
        if u.ehe_konto < betrag: return await interaction.response.send_message(embed=fehler_embed("Zu wenig Guthaben auf der Bank."), ephemeral=True)
        u.ehe_konto -= betrag; u.muenzen += betrag; p.ehe_konto = u.ehe_konto
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🏦 Bank-Update", "Transaktion durchgeführt!", BotFarben.ERFOLG))

@bot.tree.command(name="premium-baby-academy", description="Schickt euer Kind auf das VIP-Elite-Internat.")
async def baby_academy(interaction: discord.Interaction, kind_name: str):
    u_id = str(interaction.user.id); u = state.get_user(u_id)
    if not state.ist_premium(u_id) or kind_name not in u.kinder:
        return await interaction.response.send_message(embed=fehler_embed("Fehler beim Zugriff oder kein VIP-Status."), ephemeral=True)
    u.kinder[kind_name]["in_akademie_bis"] = (datetime.now(timezone.utc) + timedelta(hours=3)).isoformat()
    u.kinder[kind_name]["level"] = u.kinder[kind_name].get("level", 1) + 1
    u.kinder[kind_name]["hunger"] = 0
    if u.partner_id: state.get_user(u.partner_id).kinder[kind_name] = u.kinder[kind_name]
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🎓 VIP-Akademie", f"**{kind_name}** lernt im Internat und stieg direkt ein Level auf!", BotFarben.PREMIUM))

@bot.tree.command(name="premium-family-vacation", description="VIP-Urlaub sättigt alle Kinder.")
async def family_vacation(interaction: discord.Interaction):
    u_id = str(interaction.user.id); u = state.get_user(u_id)
    if not state.ist_premium(u_id) or not u.partner_id: return await interaction.response.send_message(embed=fehler_embed("Nur für verheiratete VIPs!"), ephemeral=True)
    for k in u.kinder.values(): k["hunger"] = 0
    if u.partner_id:
        for k in state.get_user(u.partner_id).kinder.values(): k["hunger"] = 0
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("✈️ VIP-Urlaub", "Malediven-Reise beendet! Alle Kinder sind satt (0% Hunger).", BotFarben.PREMIUM))

# ─── PREMIUM PET & BOSS SYSTEM ──────────────────────────────
@bot.tree.command(name="premium-pet-adopt", description="Adoptiere ein Premium-Haustier.")
@app_commands.choices(typ=[app_commands.Choice(name="Drache", value="Drache"), app_commands.Choice(name="Einhorn", value="Einhorn"), app_commands.Choice(name="Phönix-Löwe", value="Phönix-Löwe")])
async def premium_pet_adopt(interaction: discord.Interaction, typ: app_commands.Choice[str], name: str):
    u_id = str(interaction.user.id)
    if not state.ist_premium(u_id) or u_id in state.pet_daten: return await interaction.response.send_message(embed=fehler_embed("Nicht berechtigt oder bereits Tier vorhanden."), ephemeral=True)
    state.pet_daten[u_id] = PetProfile(name=name, typ=typ.value, max_hp=150 if typ.value == "Einhorn" else 120, aktuelle_hp=120, atk=18 if typ.value == "Drache" else 14)
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🐾 Adoption", f"Dein legendärer **{typ.value}** namens **{name}** wurde geboren!", BotFarben.PREMIUM))

@bot.tree.command(name="premium-adventure", description="Kämpfe gegen Bosse in den Premium-Welten.")
@app_commands.choices(welt=[app_commands.Choice(name="⏳ Chronos-Riss (Lvl 15)", value="chronos"), app_commands.Choice(name="🌌 Astral-Ebene (Lvl 25)", value="astral"), app_commands.Choice(name="🌋 Obsidian-Hölle (Lvl 40)", value="obsidian")])
async def premium_adventure(interaction: discord.Interaction, welt: app_commands.Choice[str]):
    u_id = str(interaction.user.id)
    if not state.ist_premium(u_id) or u_id not in state.pet_daten: return await interaction.response.send_message(embed=fehler_embed("Bedingungen nicht erfüllt."), ephemeral=True)
    pet = state.pet_daten[u_id]; w_daten = PREMIUM_WELTEN[welt.value]
    if pet.level < w_daten["min_level"] or pet.aktuelle_hp <= 20: return await interaction.response.send_message(embed=fehler_embed("Haustier zu schwach oder zu wenig HP."), ephemeral=True)
    
    await interaction.response.defer()
    b_hp = w_daten["boss_hp"]
    while b_hp > 0 and pet.aktuelle_hp > 0:
        b_hp -= random.randint(pet.atk - 3, pet.atk + 7)
        if b_hp <= 0: break
        pet.aktuelle_hp -= random.randint(10, 25)

    if b_hp <= 0:
        beute = int(random.randint(w_daten["belohnung_min"], w_daten["belohnung_max"]) * 1.25)
        state.get_user(u_id).muenzen += beute; pet.level += 1; pet.zufriedenheit = min(100, pet.zufriedenheit + 15)
        pet.aktuelle_hp = max(10, pet.aktuelle_hp)
        emb = erstelle_embed("⚔️ SIEG", f"**{pet.name}** bezwang den Boss!\n💰 Beute: `🪙 {beute:,} Münzen`\n📈 Stufe: Lvl **{pet.level}**", BotFarben.ERFOLG)
    else:
        pet.aktuelle_hp = 10; pet.zufriedenheit = max(0, pet.zufriedenheit - 20)
        emb = erstelle_embed("💀 NIEDERLAGE", f"Der Boss war zu stark. {pet.name} musste verletzt fliehen.", BotFarben.FEHLER)
    state.speichern()
    await interaction.followup.send(embed=emb)

@bot.tree.command(name="premium-pet-heal", description="Heilt dein Tier kostenfrei auf.")
async def premium_pet_heal(interaction: discord.Interaction):
    u_id = str(interaction.user.id)
    if not state.ist_premium(u_id) or u_id not in state.pet_daten: return await interaction.response.send_message(embed=fehler_embed("Fehler."), ephemeral=True)
    state.pet_daten[u_id].aktuelle_hp = state.pet_daten[u_id].max_hp
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("💖 Heilung", "Dein Haustier wurde komplett geheilt!", BotFarben.ERFOLG))

@bot.tree.command(name="premium-pet-rename", description="Benennt dein Premium-Tier um.")
async def premium_pet_rename(interaction: discord.Interaction, neuer_name: str):
    u_id = str(interaction.user.id)
    if not state.ist_premium(u_id) or u_id not in state.pet_daten: return await interaction.response.send_message(embed=fehler_embed("Mangelnde Rechte."), ephemeral=True)
    state.pet_daten[u_id].name = neuer_name
    state.speichern()
    await interaction.response.send_message(embed=erstelle_embed("🏷️ Umbenannt", f"Neuer Name: **{neuer_name}**", BotFarben.ERFOLG))

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)

import discord
from discord.ext import commands
import json
import os
import random
from datetime import datetime, timedelta

# ==========================================
# 1. KONFIGURATION & EINSTELLUNGEN
# ==========================================

# Ersetze diese ID mit deiner echten Discord-User-ID (Nightleon1)
OWNER_ID = 123456789012345678 

# Hier stellen wir die Rechte (Intents) ein, die der Bot auf dem Server braucht
intents = discord.Intents.default()
intents.message_content = True  # Erlaubt dem Bot, !-Befehle zu lesen
intents.members = True          # Erlaubt dem Bot, Server-Mitglieder zu sehen

# Wir starten den Bot mit dem Präfix '!' für Text-Befehle
bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================================
# 2. DER GLOBALE DATENSPEICHER (STATE)
# ==========================================

class BotState:
    def __init__(self):
        # --- WIRTSCHAFT & STATUS ---
        self.premium_users = set()       # Speichert die IDs der Premium-Mitglieder
        self.premium_expires = {}        # Wann läuft das Premium ab? (z.B. {"user_id": "2026-12-31"})
        self.user_coins = {}             # Das Bargeld der User (z.B. {"user_id": 1000})
        self.user_bank = {}              # Das Bankguthaben der User (z.B. {"user_id": 5000})
        self.user_jobs = {}              # Der zuletzt ausgeübte Beruf (z.B. {"user_id": "VIP-Chauffeur"})
        self.work_cooldowns = {}         # Zeitstempel für die 2-Stunden-Arbeitssperre
        
        # --- INVENTAR & SHOP ---
        self.premium_inventories = {}    # Der Rucksack voller Items (z.B. {"user_id": ["Apfel", "Premium-Tierfutter"]})
        
        # --- HAUSTIER-SYSTEM ---
        self.premium_pets = {}           # Alle adoptierten Tiere eines Users (z.B. {"user_id": ["VIP-Kätzchen Luna"]})
        self.active_pet = {}             # Welches Tier läuft gerade mit? (z.B. {"user_id": "VIP-Kätzchen Luna"})
        self.pet_xp = {}                 # Die XP der Haustiere (z.B. {"user_id": {"VIP-Kätzchen Luna": 45}})
        self.pet_level = {}              # Das Level der Haustiere (z.B. {"user_id": {"VIP-Kätzchen Luna": 2}})
        self.user_titles = {}            # Freigeschaltete Profil-Titel (z.B. {"user_id": ["Tierliebhaber"]})

    def is_premium(self, user_id: int) -> bool:
        """Hilfsfunktion: Prüft blitzschnell, ob ein User Premium-Rechte hat."""
        return user_id in self.premium_users

    # --- BACKUP-FUNKTIONEN (EXPORT & IMPORT) ---
    def export_to_json(self) -> str:
        """Wandelt alle aktuellen Live-Daten in einen sauberen JSON-Text um."""
        daten_paket = {
            "premium_users": list(self.premium_users),
            "premium_expires": self.premium_expires,
            "user_coins": self.user_coins,
            "user_bank": self.user_bank,
            "user_jobs": self.user_jobs,
            "work_cooldowns": self.work_cooldowns,
            "premium_inventories": self.premium_inventories,
            "premium_pets": self.premium_pets,
            "active_pet": self.active_pet,
            "pet_xp": self.pet_xp,
            "pet_level": self.pet_level,
            "user_titles": self.user_titles
        }
        return json.dumps(daten_paket, indent=4, ensure_ascii=False)

    def import_from_json(self, json_text: str):
        """Lädt Daten aus einem JSON-Text direkt zurück in den Bot-Arbeitsspeicher."""
        daten = json.loads(json_text)
        self.premium_users = set(daten.get("premium_users", []))
        self.premium_expires = daten.get("premium_expires", {})
        self.user_coins = daten.get("user_coins", {})
        self.user_bank = daten.get("user_bank", {})
        self.user_jobs = daten.get("user_jobs", {})
        self.work_cooldowns = daten.get("work_cooldowns", {})
        self.premium_inventories = daten.get("premium_inventories", {})
        self.premium_pets = daten.get("premium_pets", {})
        self.active_pet = daten.get("active_pet", {})
        self.pet_xp = daten.get("pet_xp", {})
        self.pet_level = daten.get("pet_level", {})
        self.user_titles = daten.get("user_titles", {})

# Instanz des Datenspeichers erstellen, die wir im gesamten Bot nutzen
state = BotState()

# ==========================================
# 3. BOT-EVENTS (START & SYNCHRONISATION)
# ==========================================

@bot.event
async def on_ready():
    """Wird ausgelöst, wenn der Bot erfolgreich online geht."""
    print(f"==========================================")
    print(f"🤖 Bot-System erfolgreich gestartet!")
    print(f"👑 Eingeloggt als: {bot.user.name} ({bot.user.id})")
    print(f"📅 Datum/Zeit: {datetime.now().strftime('%d.%m.%Y - %H:%M:%S')}")
    print(f"==========================================")
    
    try:
        # Hier synchronisieren wir die Slash-Commands (wie /hilfe_standard) global mit Discord
        synced = await bot.tree.sync()
        print(f"✨ {len(synced)} Slash-Commands erfolgreich synchronisiert!")
    except Exception as e:
        print(f"❌ Fehler beim Synchronisieren der Slash-Commands: {e}")


# ==========================================
# 4. SICHERHEITS-CHECKS & HILFSFUNKTIONEN
# ==========================================

async def check_premium_context(ctx: commands.Context) -> bool:
    """
    Prüft bei einem Text-Befehl (!), ob der ausführende User Premium-Rechte besitzt.
    Wenn nicht, wird eine feine, informative Fehlermeldung gesendet.
    """
    if state.is_premium(ctx.author.id):
        return True
        
    # Wenn der User kein Premium-Mitglied ist, schicken wir ein schickes Embed
    emb_no_vip = discord.Embed(
        title="🔒 Exklusiver Premium-Befehl",
        description=f"Huch **{ctx.author.display_name}**, dieser Befehl steht aktuell nur unseren VIP-Mitgliedern zur Verfügung! ✨\n\n"
                    f"Premium-Mitglieder genießen besondere Vorteile wie:\n"
                    f"• 🐾 Einzigartige Haustiere adoptieren & leveln\n"
                    f"• 💼 Den doppelten Lohn bei der Arbeit (`!work`)\n"
                    f"• 🛍️ Einen exklusiven VIP-Marktplatz\n\n"
                    f"Frage die Administration oder nutze `/premium_help` für mehr Infos!",
        color=discord.Color.red()
    )
    await ctx.send(embed=emb_no_vip)
    return False


@bot.event
async def on_command_error(ctx: commands.Context, error):
    """Fängt Fehler bei Text-Befehlen ab, damit der Bot nicht unschön abstürzt."""
    if isinstance(error, commands.CommandOnCooldown):
        # Falls wir später globale Standard-Cooldowns nutzen
        minuten, sekunden = divmod(error.retry_after, 60)
        await ctx.send(f"⏳ Hektik bringt nichts! Bitte warte noch {int(minuten)}m und {int(sekunden)}s.", delete_after=5)
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Da fehlt eine Angabe! Bitte überprüfe die Schreibweise des Befehls.", delete_after=5)
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send(f"❌ Dieser Spieler konnte auf dem Server nicht gefunden werden.", delete_after=5)
    else:
        # Andere Fehler loggen wir leise in der Konsole
        print(f"⚠️ Befehlsfehler aufgetreten: {error}")

# ==========================================
# 5. DIE INTERAKTIVEN MENÜS (SHOP & HANDEL)
# ==========================================

class PremiumShopSelect(discord.ui.Select):
    def __init__(self, ctx: commands.Context):
        self.ctx = ctx
        
        # Unser Marktplatz-Sortiment
        options = [
            discord.SelectOption(label="Apfel", description="Ein saftiger Premium-Apfel. (Preis: 50 Münzen)", emoji="🍎"),
            discord.SelectOption(label="Exotische Banane", description="Gibt dir extra Energie. (Preis: 120 Münzen)", emoji="🍌"),
            discord.SelectOption(label="VIP Diamant-Ring", description="Der absolute Luxus für dein Profil. (Preis: 5000 Münzen)", emoji="💍"),
            discord.SelectOption(label="Premium-Tierfutter", description="Köstliche Knabbereien für dein Haustier. (Preis: 80 Münzen)", emoji="🍖")
        ]
        super().__init__(placeholder="🏪 Wähle ein Item zum Kaufen aus...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ Das ist nicht dein Shop-Menü!", ephemeral=True)
            return

        item_name = self.values[0]
        user_id = str(self.ctx.author.id)
        
        # Preise festlegen
        preise = {"Apfel": 50, "Exotische Banane": 120, "VIP Diamant-Ring": 500, "Premium-Tierfutter": 80}
        preis = preise[item_name]
        
        # Guthaben prüfen
        aktuelles_geld = state.user_coins.get(user_id, 0)
        if aktuelles_geld < preis:
            await interaction.response.send_message(f"❌ Du hast nicht genug Bargeld! Dir fehlen {preis - aktuelles_geld} Münzen. 💸", ephemeral=True)
            return

        # Kauf abwickeln
        state.user_coins[user_id] -= preis
        if user_id not in state.premium_inventories:
            state.premium_inventories[user_id] = []
        state.premium_inventories[user_id].append(item_name)

        # Speichern
        if hasattr(state, "save_server_async"):
            await state.save_server_async(interaction.guild_id)

        emb = discord.Embed(
            title="🛍️ Einkauf erfolgreich!",
            description=f"✨ **<@{user_id}>** hat erfolgreich eingekauft!\n\n"
                        f"📦 **Gegenstand:** {item_name}\n"
                        f"💰 **Bezahlt:** `{preis} Münzen`\n\n"
                        f"*Das Item wurde sicher in deinen Rucksack gepackt.*",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=emb, view=None)


class PremiumShopView(discord.ui.View):
    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=60)
        self.add_item(PremiumShopSelect(ctx))


# --- VERSCHENKEN SYSTEM ---

class PremiumGiftSelect(discord.ui.Select):
    def __init__(self, ctx: commands.Context, target: discord.Member, user_items: list):
        self.ctx = ctx
        self.target = target
        self.user_items = user_items

        from collections import Counter
        item_counts = Counter(user_items)
        
        options = []
        for item, anzahl in item_counts.items():
            emoji = "🍎" if "Apfel" in item else "🍌" if "Banane" in item else "💍" if "Ring" in item else "🍖" if "Futter" in item else "📦"
            options.append(discord.SelectOption(label=item, description=f"In deinem Besitz: {anzahl}x", emoji=emoji))
            
        super().__init__(placeholder="🎁 Wähle ein Geschenk aus deinem Rucksack...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ Das ist nicht dein Geschenk-Menü!", ephemeral=True)
            return

        ausgewaehltes_item = self.values[0]
        giver_id = str(self.ctx.author.id)
        receiver_id = str(self.target.id)

        if giver_id not in state.premium_inventories or ausgewaehltes_item not in state.premium_inventories[giver_id]:
            await interaction.response.send_message("❌ Dieses Item befindet sich nicht mehr in deinem Rucksack.", ephemeral=True)
            return

        # Item übertragen
        state.premium_inventories[giver_id].remove(ausgewaehltes_item)
        if receiver_id not in state.premium_inventories:
            state.premium_inventories[receiver_id] = []
        state.premium_inventories[receiver_id].append(ausgewaehltes_item)

        emb = discord.Embed(
            title="🎁 Ein VIP-Geschenk wurde überreicht!",
            description=f"✨ Eine glitzernde Geschenkbox öffnet sich...\n\n"
                        f"👑 **<@{giver_id}>** schenkt \n"
                        f"🤝 **<@{receiver_id}>** das Item: **{ausgewaehltes_item}**!\n\n"
                        f"*„Ein exklusives Mitbringsel für dich!“*",
            color=discord.Color.from_rgb(255, 105, 180)
        )
        await interaction.response.edit_message(embed=emb, view=None)


class PremiumGiftView(discord.ui.View):
    def __init__(self, ctx: commands.Context, target: discord.Member, user_items: list):
        super().__init__(timeout=60)
        self.add_item(PremiumGiftSelect(ctx, target, user_items))

# ==========================================
# 6. VERBRAUCHS-LOGIK & HAUSTIER-SYSTEM
# ==========================================

class PremiumUseSelect(discord.ui.Select):
    def __init__(self, ctx: commands.Context, user_items: list):
        self.ctx = ctx
        self.user_items = user_items

        from collections import Counter
        item_counts = Counter(user_items)
        
        options = []
        for item, anzahl in item_counts.items():
            if "Apfel" in item or "Banane" in item or "Ring" in item or "Futter" in item:
                emoji = "🍎" if "Apfel" in item else "🍌" if "Banane" in item else "💍" if "Ring" in item else "🍖"
                options.append(discord.SelectOption(label=item, description=f"Im Rucksack: {anzahl}x", emoji=emoji))
            
        super().__init__(placeholder="🎒 Wähle ein Item zum Benutzen/Essen...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ Das ist nicht dein Rucksack-Menü!", ephemeral=True)
            return

        ausgewaehltes_item = self.values[0]
        user_id = str(self.ctx.author.id)

        if user_id not in state.premium_inventories or ausgewaehltes_item not in state.premium_inventories[user_id]:
            await interaction.response.send_message("❌ Dieses Item liegt nicht mehr in deinem Rucksack.", ephemeral=True)
            return

        # --- SPECIAL CHECK FÜR TIERFUTTER ---
        if "Futter" in ausgewaehltes_item:
            aktives_pet = state.active_pet.get(user_id, None)
            if not aktives_pet:
                await interaction.response.send_message("❌ Du hast gerade kein Haustier aktiv, das du füttern könntest!", ephemeral=True)
                return

            # Futter abziehen
            state.premium_inventories[user_id].remove(ausgewaehltes_item)

            # XP & Level Logik fürs Füttern (+40 XP)
            if user_id not in state.pet_xp: state.pet_xp[user_id] = {}
            if user_id not in state.pet_level: state.pet_level[user_id] = {}

            aktuelle_xp = state.pet_xp[user_id].get(aktives_pet, 0)
            aktuelles_lvl = state.pet_level[user_id].get(aktives_pet, 1)

            neue_xp = aktuelle_xp + 40
            xp_fuer_next_level = aktuelles_lvl * 100
            level_up_nachricht = ""

            if neue_xp >= xp_fuer_next_level:
                neue_xp -= xp_fuer_next_level
                aktuelles_lvl += 1
                level_up_nachricht = f"\n\n🎉 **LEVEL UP!** {aktives_pet} ist durch gute Pflege auf **Level {aktuelles_lvl}** aufgestiegen! 🚀"
                if user_id not in state.user_titles: state.user_titles[user_id] = []
                if aktuelles_lvl >= 2 and "Tierliebhaber" not in state.user_titles[user_id]:
                    state.user_titles[user_id].append("Tierliebhaber")
                    level_up_nachricht += "\n🏅 *Titel freigeschaltet: **`Tierliebhaber`***"

            state.pet_xp[user_id][aktives_pet] = neue_xp
            state.pet_level[user_id][aktives_pet] = aktuelles_lvl

            # Storys fürs Füttern
            title_text = "🍖 Mampf! Fütterungszeit!"
            embed_color = discord.Color.green()
            if "Drache" in aktives_pet:
                description_text = f"🔥 **<@{user_id}>** öffnet das Futter. **Ember** grillt die Häppchen kurz in der Luft und verschlingt sie!"
            elif "Kätzchen" in aktives_pet:
                description_text = f"🐈 **<@{user_id}>** füllt das Futter ein. **Luna** schleicht herbei und knuspert alles laut schnurrend auf."
            else:
                description_text = f"🐕 **<@{user_id}>** wirft Futter. **Bolt** fängt es elegant mit einem lauten *Klack* seines mechanischen Kiefers."

            description_text += f"\n\n📊 **Fortschritt:** {neue_xp}/{xp_fuer_next_level} XP" + level_up_nachricht
            
        else:
            # Logik für normale Items (Apfel, Banane, Ring)
            state.premium_inventories[user_id].remove(ausgewaehltes_item)
            title_text = "✨ Gegenstand benutzt!"
            embed_color = discord.Color.gold()
            
            if "Apfel" in ausgewaehltes_item:
                title_text = "🍎 Knackig & Frisch!"
                description_text = f"✨ **<@{user_id}>** beißt in den Premium-Apfel! Du fühlst dich erfrischt. ⭐"
                embed_color = discord.Color.red()
            elif "Banane" in ausgewaehltes_item:
                title_text = "🍌 Exotischer Kick!"
                description_text = f"⚡ **<@{user_id}>** isst die Banane. Die Vitamine kicken sofort rein! 🚀"
            elif "Ring" in ausgewaehltes_item:
                title_text = "💍 Funkelnder Moment..."
                description_text = f"👑 **<@{user_id}>** steckt sich den Diamant-Ring an. Absolute Aura! 💎"
                embed_color = discord.Color.blue()

        if hasattr(state, "save_server_async"): await state.save_server_async(interaction.guild_id)

        emb = discord.Embed(title=title_text, description=description_text, color=embed_color)
        await interaction.response.edit_message(embed=emb, view=None)


class PremiumUseView(discord.ui.View):
    def __init__(self, ctx: commands.Context, user_items: list):
        super().__init__(timeout=60)
        self.add_item(PremiumUseSelect(ctx, user_items))


# --- HAUSTIER ADOPTION ---

class PremiumPetSelect(discord.ui.Select):
    def __init__(self, ctx: commands.Context):
        self.ctx = ctx
        options = [
            discord.SelectOption(label="Baby-Drache Ember", description="Ein kleiner, feuriger Begleiter.", emoji="🐉"),
            discord.SelectOption(label="VIP-Kätzchen Luna", description="Sehr elegant. Trägt ein goldenes Halsband.", emoji="🐱"),
            discord.SelectOption(label="Cyber-Hund Bolt", description="Ein treuer, mechanischer Beschützer.", emoji="🤖")
        ]
        super().__init__(placeholder="🐾 Wähle ein Haustier zum Adoptieren...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id: return
        tier_auswahl = self.values[0]
        user_id = str(self.ctx.author.id)

        if user_id not in state.premium_pets: state.premium_pets[user_id] = []
        if tier_auswahl in state.premium_pets[user_id]:
            await interaction.response.send_message(f"🐾 Du besitzt **{tier_auswahl}** bereits!", ephemeral=True)
            return

        state.premium_pets[user_id].append(tier_auswahl)
        state.active_pet[user_id] = tier_auswahl
        if hasattr(state, "save_server_async"): await state.save_server_async(interaction.guild_id)

        emb = discord.Embed(
            title="🐾 Ein neues Familienmitglied!",
            description=f"👑 **<@{user_id}>** hat soeben **{tier_auswahl}** adoptiert und als aktiven Begleiter gesetzt!",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=emb, view=None)


class PremiumPetView(discord.ui.View):
    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=60)
        self.add_item(PremiumPetSelect(ctx))


# --- HAUSTIER TRAINING ---

class PremiumTrainSelect(discord.ui.Select):
    def __init__(self, ctx: commands.Context):
        self.ctx = ctx
        options = [
            discord.SelectOption(label="Kunststück beibringen", description="Übe ein lustiges Kunststück.", emoji="🎪"),
            discord.SelectOption(label="Ausdauer-Lauf", description="Sprintet gemeinsam durch den VIP-Garten.", emoji="🏃"),
            discord.SelectOption(label="Aura & Stolz trainieren", description="Bringe deinem Pet bei, wie ein VIP zu posieren.", emoji="✨")
        ]
        super().__init__(placeholder="🎯 Wähle eine Trainings-Übung aus...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id: return
        uebung = self.values[0]
        user_id = str(self.ctx.author.id)
        aktives_pet = state.active_pet.get(user_id, None)

        if not aktives_pet:
            await interaction.response.send_message("❌ Kein Haustier aktiv!", ephemeral=True)
            return

        # XP-Berechnung (+25 XP pro Training)
        if user_id not in state.pet_xp: state.pet_xp[user_id] = {}
        if user_id not in state.pet_level: state.pet_level[user_id] = {}
        
        aktuelle_xp = state.pet_xp[user_id].get(aktives_pet, 0)
        aktuelles_lvl = state.pet_level[user_id].get(aktives_pet, 1)
        
        neue_xp = aktuelle_xp + 25
        xp_fuer_next_level = aktuelles_lvl * 100
        level_up_nachricht = ""

        if neue_xp >= xp_fuer_next_level:
            neue_xp -= xp_fuer_next_level
            aktuelles_lvl += 1
            level_up_nachricht = f"\n\n🎉 **LEVEL UP!** {aktives_pet} ist auf **Level {aktuelles_lvl}** aufgestiegen! 🚀"
            if user_id not in state.user_titles: state.user_titles[user_id] = []
            if aktuelles_lvl >= 2 and "Tierliebhaber" not in state.user_titles[user_id]:
                state.user_titles[user_id].append("Tierliebhaber")
                level_up_nachricht += "\n🏅 *Titel freigeschaltet: **`Tierliebhaber`***"
            elif aktuelles_lvl >= 5 and "Bestienmeister" not in state.user_titles[user_id]:
                state.user_titles[user_id].append("Bestienmeister")
                level_up_nachricht += "\n🏅 *Titel freigeschaltet: **`Bestienmeister`***"

        state.pet_xp[user_id][aktives_pet] = neue_xp
        state.pet_level[user_id][aktives_pet] = aktuelles_lvl

        # Storys fürs Training
        description_text = f"🎯 **<@{user_id}>** trainiert mit **{aktives_pet}** die Übung *{uebung}*.\n\nDas Training zeigt Wirkung!"
        description_text += f"\n\n📊 **Fortschritt:** {neue_xp}/{xp_fuer_next_level} XP" + level_up_nachricht

        if hasattr(state, "save_server_async"): await state.save_server_async(interaction.guild_id)

        emb = discord.Embed(title="🎪 Trainingsakademie", description=description_text, color=discord.Color.purple())
        await interaction.response.edit_message(embed=emb, view=None)


class PremiumTrainView(discord.ui.View):
    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=60)
        self.add_item(PremiumTrainSelect(ctx))

# ==========================================
# 7. BANK- UND ARBEITSSYSTEM (WIRTSCHAFT)
# ==========================================

class PremiumWorkSelect(discord.ui.Select):
    def __init__(self, ctx: commands.Context):
        self.ctx = ctx
        
        # Übersicht aller 5 Berufe (Standard- und Premium-Möglichkeiten)
        options = [
            discord.SelectOption(label="Restaurant-Kellner", description="Normal: Serviere Speisen und sammle Trinkgeld.", emoji="🍽️"),
            discord.SelectOption(label="Paket-Lieferant", description="Normal: Bringer Pakete sicher an ihr Ziel.", emoji="📦"),
            discord.SelectOption(label="VIP-Chauffeur", description="Sicher: Fahre reiche Server-Gäste herum.", emoji="🚗"),
            discord.SelectOption(label="Kristall-Mineur", description="Risiko: Suche nach wertvollen Edelsteinen.", emoji="⛏️"),
            discord.SelectOption(label="Aktien-Trader", description="Sehr hoch: Spekuliere an der VIP-Börse.", emoji="📈"),
            discord.SelectOption(label="Tiefen-Mineur", description="Geheimnisvoll: Grabe in einer verlassenen Goldmine.", emoji="🌋"),
            discord.SelectOption(label="VIP-Sicherheitschef", description="Verantwortungsvoll: Beschütze den Server-Club.", emoji="🛡️")
        ]
        super().__init__(placeholder="💼 Wähle deinen heutigen Beruf aus...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message("❌ Das ist nicht deine Schicht! Nutze selber `!work`.", ephemeral=True)
            return

        user_id = str(self.ctx.author.id)
        
        # --- 2 STUNDEN COOLDOWN CHECK ---
        jetzt = datetime.now()
        if user_id in state.work_cooldowns:
            naechste_schicht = datetime.fromisoformat(state.work_cooldowns[user_id])
            if jetzt < naechste_schicht:
                restzeit = naechste_schicht - jetzt
                minuten, sekunden = divmod(restzeit.seconds, 60)
                stunden, minuten = divmod(minuten, 60)
                
                await interaction.response.send_message(
                    f"🛑 **Du bist noch erschöpft!** Deine Muskeln brennen von der letzten Schicht.\n"
                    f"Ruh dich noch **{stunden} Std. und {minuten} Min.** aus, bevor du wieder schuftest! 💤",
                    ephemeral=True
                )
                return

        beruf = self.values[0]
        verdienst = 0
        beschreibung = ""
        titel_text = "💼 Schicht beendet!"
        embed_color = discord.Color.green()
        ist_premium = state.is_premium(interaction.user.id)

        # --- JOBLOGIK ---
        if beruf == "Restaurant-Kellner":
            verdienst = random.randint(150, 300)
            beschreibung = f"🍽️ **<@{user_id}>** hat ein paar Stunden im Server-Bistro gekellnert. Die Gäste waren nett und gaben gutes Trinkgeld!"
            embed_color = discord.Color.light_grey()
        elif beruf == "Paket-Lieferant":
            verdienst = random.randint(180, 320)
            beschreibung = f"📦 **<@{user_id}>** hat den Lieferwagen beladen und fleißig Pakete in der Server-Nachbarschaft verteilt."
            embed_color = discord.Color.light_grey()
        elif beruf == "VIP-Chauffeur":
            verdienst = random.randint(200, 400)
            beschreibung = f"🚗 **<@{user_id}>** hat eine wichtige Persönlichkeit im Luxus-Schlitten sicher durch die Stadt chauffiert."
            embed_color = discord.Color.blue()
        elif beruf == "Kristall-Mineur":
            if random.random() > 0.3:
                verdienst = random.randint(350, 600)
                beschreibung = f"⛏️ **<@{user_id}>** hat eine wunderschöne funkelnde Kristallader in den Minen freigelegt!"
            else:
                verdienst = random.randint(50, 100)
                beschreibung = f"🦇 **<@{user_id}>** hat stundenlang die Wände abgeklopft, aber außer Kieselsteinen nichts gefunden."
                embed_color = discord.Color.orange()
        elif beruf == "Aktien-Trader":
            if random.random() > 0.5:
                verdienst = random.randint(700, 1200)
                beschreibung = f"📈 **<@{user_id}>** hat im perfekten Moment an der VIP-Börse zugeschlagen. Die Kurse explodieren!"
                embed_color = discord.Color.gold()
            else:
                verdienst = random.randint(10, 50)
                beschreibung = f"📉 **<@{user_id}>** hat die Marktlage falsch eingeschätzt. Die Investition bricht komplett ein!"
                embed_color = discord.Color.red()
        elif beruf == "Tiefen-Mineur":
            if random.random() > 0.4:
                verdienst = random.randint(500, 850)
                beschreibung = f"🌋 **<@{user_id}>** ist tief in die Lava-Goldmine hinabgestiegen und hat einen dicken Klumpen pures Gold geschmolzen!"
                embed_color = discord.Color.dark_red()
            else:
                verdienst = random.randint(20, 60)
                beschreibung = f"🥵 In der Lava-Mine war es viel zu heiß! Du musstest die Flucht ergreifen, bevor die Ausrüstung schmilzt."
                embed_color = discord.Color.dark_orange()
        elif beruf == "VIP-Sicherheitschef":
            verdienst = random.randint(400, 550)
            beschreibung = f"🛡️ **<@{user_id}>** hat das Kommando über die VIP-Lounge übernommen und zwei Randalierer elegant vor die Tür gesetzt."
            embed_color = discord.Color.dark_blue()

        # --- PREMIUM BONUS ---
        premium_text = ""
        if ist_premium:
            verdienst = verdienst * 2
            premium_text = f"\n\n💎 **Premium-Bonus aktiviert:** Dein Verdienst wurde **verdoppelt**! 🎉"

        # Kontostand aktualisieren, Job merken und Cooldown setzen
        if user_id not in state.user_coins: state.user_coins[user_id] = 0
        state.user_coins[user_id] += verdienst
        state.user_jobs[user_id] = beruf
        
        sperr_zeit = jetzt + timedelta(hours=2)
        state.work_cooldowns[user_id] = sperr_zeit.isoformat()

        if hasattr(state, "save_server_async"): await state.save_server_async(interaction.guild_id)

        emb = discord.Embed(
            title=titel_text,
            description=f"{beschreibung}\n\n💰 **Lohn:** +`{verdienst} Münzen`{premium_text}",
            color=embed_color
        )
        await interaction.response.edit_message(embed=emb, view=None)


class PremiumWorkView(discord.ui.View):
    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=60)
        self.add_item(PremiumWorkSelect(ctx))


# --- BANK AUTOMAT ---

class PremiumBankSelect(discord.ui.Select):
    def __init__(self, ctx: commands.Context):
        self.ctx = ctx
        options = [
            discord.SelectOption(label="💰 500 Münzen einzahlen", description="Überweise 500 Münzen auf dein sicheres Tresorkonto.", value="ein_500"),
            discord.SelectOption(label="💰 ALLES einzahlen", description="Bringe dein gesamtes Bargeld zur Bank.", value="ein_all"),
            discord.SelectOption(label="💳 500 Münzen abheben", description="Hole dir 500 Münzen als Bargeld auf die Hand.", value="aus_500"),
            discord.SelectOption(label="💳 ALLES abheben", description="Leere dein Bankkonto komplett.", value="aus_all")
        ]
        super().__init__(placeholder="🏦 Wähle eine Bank-Aktion aus...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.ctx.author.id: return

        aktion = self.values[0]
        user_id = str(self.ctx.author.id)
        
        bargeld = state.user_coins.get(user_id, 0)
        bankguthaben = state.user_bank.get(user_id, 0)
        betrag = 0
        ist_einzahlung = True

        if aktion == "ein_500":
            betrag = 500
            if bargeld < betrag:
                await interaction.response.send_message("❌ Du hast nicht genug Bargeld!", ephemeral=True)
                return
        elif aktion == "ein_all":
            betrag = bargeld
            if betrag <= 0:
                await interaction.response.send_message("❌ Deine Taschen sind leer!", ephemeral=True)
                return
        elif aktion == "aus_500":
            betrag = 500
            ist_einzahlung = False
            if bankguthaben < betrag:
                await interaction.response.send_message("❌ So viel Geld liegt nicht auf deinem Konto!", ephemeral=True)
                return
        elif aktion == "aus_all":
            betrag = bankguthaben
            ist_einzahlung = False
            if betrag <= 0:
                await interaction.response.send_message("❌ Dein Bankkonto ist leer!", ephemeral=True)
                return

        # Abrechnung
        if ist_einzahlung:
            state.user_coins[user_id] = bargeld - betrag
            state.user_bank[user_id] = bankguthaben + betrag
            title_text = "🏦 Erfolgreich eingezahlt!"
            story_text = f"💸 **<@{user_id}>** zahlt **{betrag} Münzen** am Schalter ein. Das Geld liegt nun sicher im Tresor."
            embed_color = discord.Color.green()
        else:
            state.user_coins[user_id] = bargeld + betrag
            state.user_bank[user_id] = bankguthaben - betrag
            title_text = "💳 Erfolgreich abgehoben!"
            story_text = f"🏧 *Summ...* **<@{user_id}>** hebt **{betrag} Münzen** als frisches Bargeld ab."
            embed_color = discord.Color.blue()

        if hasattr(state, "save_server_async"): await state.save_server_async(interaction.guild_id)

        emb = discord.Embed(title=title_text, description=story_text, color=embed_color)
        emb.add_field(name="💵 Bargeld", value=f"`{state.user_coins[user_id]} Münzen`", inline=True)
        emb.add_field(name="🏛️ Bankkonto", value=f"`{state.user_bank[user_id]} Münzen`", inline=True)
        await interaction.response.edit_message(embed=emb, view=None)


class PremiumBankView(discord.ui.View):
    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=60)
        self.add_item(PremiumBankSelect(ctx))

# ==========================================
# 8. DIE TEXT-BEFEHLE (CHAT-MANDATE)
# ==========================================

@bot.command(name="p_profil")
async def p_profil_cmd(ctx: commands.Context):
    """Zeigt deine exklusive Profilkarte inklusive Premium-Erkennung, Levels und Titeln"""
    user_id = str(ctx.author.id)
    
    # Daten sammeln
    aktives_pet = state.active_pet.get(user_id, "Kein Haustier aktiv")
    titel_liste = state.user_titles.get(user_id, ["Keine Titel freigeschaltet"])
    anzahl_items = len(state.premium_inventories.get(user_id, []))
    aktueller_beruf = state.user_jobs.get(user_id, "💼 Arbeitslos")
    bank_geld = state.user_bank.get(user_id, 0)
    bar_geld = state.user_coins.get(user_id, 0)
    
    # Premium-Status prüfen
    ist_vip = state.is_premium(ctx.author.id)
    status_abzeichen = "💎 **PREMIUM-MITGLIED** 👑" if ist_vip else "⚪ Standard-User"

    if aktives_pet != "Kein Haustier aktiv":
        lvl = state.pet_level.get(user_id, {}).get(aktives_pet, 1)
        xp = state.pet_xp.get(user_id, {}).get(aktives_pet, 0)
        next_xp = lvl * 100
        pet_info = f"{aktives_pet} (Lvl. {lvl}) — *{xp}/{next_xp} XP*"
    else:
        pet_info = "💤 *Nutze `!p_adoptieren`, um einen Begleiter zu rufen.*"

    formatierte_titel = " ".join([f"[`{t}`]" for t in titel_liste]) if titel_liste and titel_liste[0] != "Keine Titel freigeschaltet" else "`Keine`"

    emb = discord.Embed(
        title=f"👑 Profil von {ctx.author.display_name}",
        description=f"Hier ist deine offizielle Statuskarte.\n\n✨ **Rang:** {status_abzeichen}",
        color=discord.Color.from_rgb(255, 215, 0) if ist_vip else discord.Color.light_grey()
    )
    
    if ctx.author.avatar:
        emb.set_thumbnail(url=ctx.author.avatar.url)

    emb.add_field(name="🏅 Freigeschaltete Titel", value=formatierte_titel, inline=False)
    emb.add_field(name="💼 Aktueller Beruf", value=f"`{aktueller_beruf}`", inline=False)
    emb.add_field(name="🐾 Aktiver Begleiter", value=pet_info, inline=False)
    emb.add_field(name="🎒 Rucksack-Inhalt", value=f"{anzahl_items} Items", inline=True)
    emb.add_field(name="💵 Bargeld", value=f"`{bar_geld} Münzen`", inline=True)
    emb.add_field(name="🏛️ Bankkonto", value=f"`{bank_geld} Münzen`", inline=True)
    
    emb.set_footer(text="VIP-System | Profilkarte")
    await ctx.send(embed=emb)


@bot.command(name="work")
async def work_cmd(ctx: commands.Context):
    """Öffnet das interaktive Arbeitsamt für alle User"""
    emb = discord.Embed(
        title="💼 Das Server-Arbeitsamt",
        description=f"Hallo **{ctx.author.display_name}**! Zeit, ein paar Münzen zu verdienen.\n\n"
                    f"Wähle unten im Menü deinen gewünschten Beruf für die nächste Schicht aus.\n\n"
                    f"💎 *Premium-Mitglieder erhalten automatisch den **doppelten Lohn**!*",
        color=discord.Color.light_grey()
    )
    await ctx.send(embed=emb, view=PremiumWorkView(ctx))


@bot.command(name="p_bank")
async def p_bank_cmd(ctx: commands.Context):
    """Öffnet den interaktiven Bankautomaten für den Spieler"""
    user_id = str(ctx.author.id)
    bargeld = state.user_coins.get(user_id, 0)
    bankguthaben = state.user_bank.get(user_id, 0)

    emb = discord.Embed(
        title="🏛️ Die staatliche Server-Zentralbank",
        description=f"Hallo **{ctx.author.display_name}**, willkommen am Schalter!\n\n"
                    f"Sichere dein Erspartes vor Langfingern.\n\n"
                    f"💰 **Dein Bargeld:** `{bargeld} Münzen`\n"
                    f"💳 **Auf dem Konto:** `{bankguthaben} Münzen` \n\n"
                    f"👇 *Wähle im Menü unten deine Transaktion aus:*",
        color=discord.Color.teal()
    )
    await ctx.send(embed=emb, view=PremiumBankView(ctx))


@bot.command(name="p_zahlen")
async def p_zahlen_cmd(ctx: commands.Context, target: discord.Member, anzahl: int):
    """Überweist eine bestimmte Menge Münzen an einen anderen Spieler"""
    giver_id = str(ctx.author.id)
    receiver_id = str(target.id)

    if anzahl <= 0:
        await ctx.send("❌ Bitte gib einen gültigen Betrag über 0 Münzen ein.")
        return
    if target.id == ctx.author.id:
        await ctx.send("❌ Du kannst dir selbst kein Geld überweisen.")
        return

    aktuelles_geld = state.user_coins.get(giver_id, 0)
    if aktuelles_geld < anzahl:
        await ctx.send(f"❌ Zu wenig Münzen! Du besitzt aktuell nur `{aktuelles_geld} Münzen`.")
        return

    state.user_coins[giver_id] -= anzahl
    if receiver_id not in state.user_coins: state.user_coins[receiver_id] = 0
    state.user_coins[receiver_id] += anzahl

    if hasattr(state, "save_server_async"): await state.save_server_async(ctx.guild_id)

    ist_premium = state.is_premium(ctx.author.id)
    if ist_premium:
        emb = discord.Embed(
            title="✨ Eine exklusive VIP-Überweisung!",
            description=f"👑 **<@{giver_id}>** öffnet eine edle Brieftasche und übergibt **{anzahl} funkelnde Münzen** per Express-Kurier an **<@{receiver_id}>**! 🥂",
            color=discord.Color.from_rgb(255, 215, 0)
        )
    else:
        emb = discord.Embed(
            title="💰 Münzen erfolgreich übergeben!",
            description=f"🤝 **<@{giver_id}>** übergibt **{anzahl} Münzen** direkt in die Hand von **<@{receiver_id}>**. Ein ehrlicher Deal!",
            color=discord.Color.green()
        )
    await ctx.send(embed=emb)


# --- NUN DIE PREMIUM-EXKLUSIVEN BEFEHLE (DURCH CHECK_PREMIUM_CONTEXT GESCHÜTZT) ---

@bot.command(name="p_shop")
async def p_shop_cmd(ctx: commands.Context):
    """Öffnet den VIP-Marktplatz"""
    if not await check_premium_context(ctx): return
    emb = discord.Embed(title="🛒 VIP-Premium-Marktplatz", description="Willkommen im edlen Shop! Wähle ein Item aus:", color=discord.Color.gold())
    await ctx.send(embed=emb, view=PremiumShopView(ctx))


@bot.command(name="p_rucksack")
async def p_rucksack_cmd(ctx: commands.Context):
    """Zeigt dein Inventar und lässt dich Gegenstände verbrauchen"""
    if not await check_premium_context(ctx): return
    user_id = str(ctx.author.id)
    items = state.premium_inventories.get(user_id, [])
    
    if not items:
        await ctx.send("🎒 Dein Rucksack ist aktuell komplett leer! Kaufe Items im `!p_shop`.")
        return
        
    emb = discord.Embed(title="🎒 Dein Premium-Rucksack", description="Wähle ein Item aus dem Menü, um es zu essen oder zu benutzen:", color=discord.Color.blue())
    await ctx.send(embed=emb, view=PremiumUseView(ctx, items))


@bot.command(name="p_schenken")
async def p_schenken_cmd(ctx: commands.Context, target: discord.Member):
    """Verschenkt ein Item aus deinem Rucksack an ein anderes Mitglied"""
    if not await check_premium_context(ctx): return
    user_id = str(ctx.author.id)
    items = state.premium_inventories.get(user_id, [])
    
    if target.id == ctx.author.id:
        await ctx.send("❌ Du kannst dir nicht selbst etwas schenken.")
        return
    if not items:
        await ctx.send("❌ Dein Rucksack ist leer. Du hast nichts zum Verschenken!")
        return
        
    emb = discord.Embed(title="🎁 VIP-Geschenk-Express", description=f"Wähle aus, welches Item du an **{target.display_name}** überreichen möchtest:", color=discord.Color.magenta())
    await ctx.send(embed=emb, view=PremiumGiftView(ctx, target, items))


@bot.command(name="p_adoptieren")
async def p_adoptieren_cmd(ctx: commands.Context):
    """Öffnet die VIP-Tierhandlung für Haustiere"""
    if not await check_premium_context(ctx): return
    emb = discord.Embed(title="🐾 VIP-Tierhandlung", description="Adoptiere ein einzigartiges Haustier, das dich im Server begleitet:", color=discord.Color.green())
    await ctx.send(embed=emb, view=PremiumPetView(ctx))


@bot.command(name="p_trainieren")
async def p_trainieren_cmd(ctx: commands.Context):
    """Trainiert dein Haustier, um es zu leveln"""
    if not await check_premium_context(ctx): return
    user_id = str(ctx.author.id)
    if not state.active_pet.get(user_id, None):
        await ctx.send("❌ Du hast aktuell kein aktives Haustier! Nutze zuerst `!p_adoptieren`.")
        return
    emb = discord.Embed(title="🎪 Haustier-Trainingsakademie", description="Verpasse deinem Begleiter wertvolle XP durch sportliche Übungen:", color=discord.Color.purple())
    await ctx.send(embed=emb, view=PremiumTrainView(ctx))


# --- HIGH-SECURITY OWNER BACKUP BEFEHL ---

@bot.command(name="p_backup")
async def p_backup_cmd(ctx: commands.Context):
    """Erstellt ein globales JSON-Daten-Backup (Nur für Nightleon1)"""
    if ctx.author.id != OWNER_ID:
        await ctx.send("❌ Zugriff verweigert. Dieser Befehl ist strengstens für die Administration reserviert.")
        return

    wartemeldung = await ctx.send("⏳ Erstelle globalen Daten-Snapshot...")
    try:
        backup_inhalt = state.export_to_json()
        dateiname = "bot_global_backup.json"
        with open(dateiname, "w", encoding="utf-8") as datei:
            datei.write(backup_inhalt)

        emb = discord.Embed(title="💾 Globales System-Backup erfolgreich!", description=f"✅ Alle Live-Daten wurden gesichert.", color=discord.Color.blue())
        emb.set_footer(text=f"Generiert am: {datetime.now().strftime('%d.%m.%Y um %H:%M:%S')}")

        await ctx.send(embed=emb, file=discord.File(dateiname))
        await wartemeldung.delete()
        
        if os.path.exists(dateiname): os.remove(dateiname)
    except Exception as e:
        await ctx.send(f"❌ Kritischer Fehler: `{e}`")


# ==========================================
# 9. SLASH COMMANDS (HILFE-SYSTEM)
# ==========================================

@bot.tree.command(name="hilfe_standard", description="⚪ Zeigt die Hilfe-Kategorie für alle normalen Mitglieder.")
async def hilfe_standard(interaction: discord.Interaction):
    emb = discord.Embed(
        title="⚪ Standard Server-Befehle",
        description="Übersicht aller normalen Textbefehle, die jeder auf dem Server nutzen kann:\n\n💡 *Tippe die Befehle einfach mit einem '!' in den Chat!*",
        color=discord.Color.light_grey()
    )
    emb.add_field(
        name="💼 WIRTSCHAFT & ARBEIT", 
        value="`!work` - Öffnet das Arbeitsamt mit allen normalen und Premium-Berufen.\n"
              "`!p_bank` - Öffnet das Menü der Zentralbank zum sicheren Ein- und Auszahlen.\n"
              "`!p_zahlen @User [Menge]` - Überweise einem anderen Spieler sicher Münzen.\n"
              "`!p_profil` - Zeigt deine Profilkarte, deine Titel, deinen Beruf und dein Geld.", 
        inline=False
    )
    emb.set_footer(text="Nutze /premium_help für die VIP-Befehle!")
    await interaction.response.send_message(embed=emb)


@bot.tree.command(name="premium_help", description="💎 Zeigt die exklusiven VIP-Vorteile und Befehle.")
async def premium_help(interaction: discord.Interaction):
    emb = discord.Embed(
        title="💎 VIP Premium-Befehle",
        description="Diese exklusiven Funktionen stehen dir als Premium-Mitglied zur Verfügung:\n\n💡 *Tippe die Befehle einfach mit einem '!' in den Chat!*",
        color=discord.Color.gold()
    )
    emb.add_field(
        name="🛍️ VIP MARKTPLATZ & HANDEL",
        value="`!p_shop` - Öffnet den exklusiven Premium-Shop.\n"
              "`!p_rucksack` - Sieh in deinen Rucksack und verwende Items.\n"
              "`!p_schenken @User` - Verschenke ein wertvolles Item aus deinem Besitz.",
        inline=False
    )
    emb.add_field(
        name="🐾 INTERAKTIVES HAUSTIER-SYSTEM",
        value="`!p_adoptieren` - Adoptiere Ember, Luna oder Bolt.\n"
              "`!p_trainieren` - Trainiere deinen Begleiter für XP und Level-Ups.\n"
              "🍖 *Tipp:* Füttere dein Haustier über den Rucksack für satte **+40 XP**!",
        inline=False
    )
    emb.set_footer(text="Premium-System | Viel Spaß mit deinen VIP-Vorteilen!")
    await interaction.response.send_message(embed=emb)

# ==========================================
# 10. BOT-START (RAILWAY & LIVE-SCHALTUNG)
# ==========================================

if __name__ == "__main__":
    # Der Bot sucht auf Railway nach der geheimen Variable 'DISCORD_TOKEN'
    token = os.getenv("DISCORD_TOKEN")
    
    if token:
        bot.run(token)
    else:
        # Falls du den Bot lokal auf dem PC testest und keine Variable gesetzt hast,
        # kannst du deinen Token übergangsweise hier in die Anführungszeichen einfügen:
        print("⚠️ 'DISCORD_TOKEN' wurde nicht in den Umgebungsvariablen gefunden.")
        # bot.run("DEIN_LOCALER_TOKEN_HIER")

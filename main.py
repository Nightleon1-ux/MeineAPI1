from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from groq import Groq
import os
import base64
from dotenv import load_dotenv
from typing import Optional, List
import json

load_dotenv()

app = FastAPI(title="Meine KI API", version="2.0.0")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

ERLAUBTE_KEYS = [
    "mein-geheimer-key-123",
    "discord-bot-key-456",
]

# Chat Verlauf speichern (im Arbeitsspeicher)
chat_verlaeufe = {}

# ─── Modelle ───────────────────────────────────────────────
VERFUEGBARE_MODELLE = {
    "schnell": "llama-3.1-8b-instant",
    "gut": "llama-3.3-70b-versatile",
    "code": "llama-3.3-70b-versatile",
}

# ─── Datenmodelle ──────────────────────────────────────────
class ChatAnfrage(BaseModel):
    nachricht: str
    system: str = "Du bist ein hilfreicher Assistent."
    modell: str = "gut"
    session_id: Optional[str] = None  # Für Chat Verlauf

class BildAnfrage(BaseModel):
    bild_base64: str  # Bild als Base64 String
    frage: str = "Was siehst du auf diesem Bild?"

# ─── Startseite ────────────────────────────────────────────
@app.get("/")
def startseite():
    return {
        "status": "online",
        "version": "2.0.0",
        "nachricht": "Meine KI API läuft! 🚀",
        "funktionen": ["/chat", "/bild", "/modelle", "/verlauf/{session_id}", "/verlauf/{session_id}/loeschen"]
    }

# ─── Chat mit Verlauf ──────────────────────────────────────
@app.post("/chat")
def chat(anfrage: ChatAnfrage, api_key: str = Header(None)):
    if api_key not in ERLAUBTE_KEYS:
        raise HTTPException(status_code=401, detail="Ungültiger API Key!")

    # Modell auswählen
    modell = VERFUEGBARE_MODELLE.get(anfrage.modell, VERFUEGBARE_MODELLE["gut"])

    # Chat Verlauf laden
    session_id = anfrage.session_id or "default"
    if session_id not in chat_verlaeufe:
        chat_verlaeufe[session_id] = []

    verlauf = chat_verlaeufe[session_id]
    verlauf.append({"role": "user", "content": anfrage.nachricht})

    try:
        nachrichten = [{"role": "system", "content": anfrage.system}] + verlauf

        antwort = client.chat.completions.create(
            model=modell,
            messages=nachrichten,
            max_tokens=1000
        )

        antwort_text = antwort.choices[0].message.content
        verlauf.append({"role": "assistant", "content": antwort_text})

        # Max 20 Nachrichten im Verlauf behalten
        if len(verlauf) > 20:
            chat_verlaeufe[session_id] = verlauf[-20:]

        return {
            "antwort": antwort_text,
            "modell": modell,
            "session_id": session_id,
            "nachrichten_anzahl": len(verlauf),
            "status": "ok"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── Bild beschreiben ──────────────────────────────────────
@app.post("/bild")
def bild_beschreiben(anfrage: BildAnfrage, api_key: str = Header(None)):
    if api_key not in ERLAUBTE_KEYS:
        raise HTTPException(status_code=401, detail="Ungültiger API Key!")

    try:
        antwort = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{anfrage.bild_base64}"
                            }
                        },
                        {
                            "type": "text",
                            "text": anfrage.frage
                        }
                    ]
                }
            ],
            max_tokens=1000
        )

        return {
            "antwort": antwort.choices[0].message.content,
            "status": "ok"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── Modelle anzeigen ──────────────────────────────────────
@app.get("/modelle")
def modelle(api_key: str = Header(None)):
    if api_key not in ERLAUBTE_KEYS:
        raise HTTPException(status_code=401, detail="Ungültiger API Key!")

    return {
        "modelle": [
            {"kuerzel": "schnell", "modell": VERFUEGBARE_MODELLE["schnell"], "beschreibung": "Sehr schnell, gut für einfache Fragen"},
            {"kuerzel": "gut", "modell": VERFUEGBARE_MODELLE["gut"], "beschreibung": "Beste Qualität (Standard)"},
            {"kuerzel": "code", "modell": VERFUEGBARE_MODELLE["code"], "beschreibung": "Gut für Code & Technik"},
        ]
    }

# ─── Chat Verlauf anzeigen ─────────────────────────────────
@app.get("/verlauf/{session_id}")
def verlauf_anzeigen(session_id: str, api_key: str = Header(None)):
    if api_key not in ERLAUBTE_KEYS:
        raise HTTPException(status_code=401, detail="Ungültiger API Key!")

    verlauf = chat_verlaeufe.get(session_id, [])
    return {
        "session_id": session_id,
        "nachrichten": verlauf,
        "anzahl": len(verlauf)
    }

# ─── Chat Verlauf löschen ──────────────────────────────────
@app.delete("/verlauf/{session_id}/loeschen")
def verlauf_loeschen(session_id: str, api_key: str = Header(None)):
    if api_key not in ERLAUBTE_KEYS:
        raise HTTPException(status_code=401, detail="Ungültiger API Key!")

    if session_id in chat_verlaeufe:
        del chat_verlaeufe[session_id]

    return {"nachricht": f"Verlauf '{session_id}' gelöscht!", "status": "ok"}
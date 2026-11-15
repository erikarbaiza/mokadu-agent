"""
MOKADU WhatsApp Agent — Servidor FastAPI

Soporta tres modos de integración:
  1. Baileys (WhatsApp Web, gratis)   → POST /respond
  2. Twilio WhatsApp Sandbox          → POST /webhook/twilio
  3. Meta WhatsApp Cloud API          → GET+POST /webhook/meta

Arrancar:
  uvicorn server:app --host 0.0.0.0 --port 8000 --reload
"""

import os
import httpx
from fastapi import FastAPI, Form, Request, Response, HTTPException
from fastapi.responses import PlainTextResponse
from dotenv import load_dotenv

from agent import RestaurantAgent, load_config

load_dotenv()

_cfg = load_config()
app = FastAPI(title=f"{_cfg['nombre']} WhatsApp Agent", version="1.0.0")
agent = RestaurantAgent()


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/")
def health():
    return {"status": "ok", **agent.stats()}


# ── Endpoint genérico (usado por Baileys y para testing) ──────────────────────

@app.post("/respond")
async def respond_direct(request: Request):
    """
    Endpoint simple para el bridge de Baileys o para testing.

    Body JSON: { "phone": "34612345678@s.whatsapp.net", "message": "Hola" }
    Respuesta: { "reply": "..." }
    """
    data = await request.json()
    phone = data.get("phone", "desconocido")
    message = data.get("message", "")
    if not message.strip():
        return {"reply": ""}
    reply = agent.respond(phone, message)
    return {"reply": reply}


@app.delete("/history/{phone}")
def clear_history(phone: str):
    """Borra el historial de conversación de un usuario."""
    agent.clear_history(phone)
    return {"status": "borrado", "phone": phone}


# ── Twilio WhatsApp ───────────────────────────────────────────────────────────

@app.post("/webhook/twilio")
async def twilio_webhook(
    From: str = Form(...),
    Body: str = Form(...),
):
    """
    Webhook para Twilio WhatsApp Sandbox.
    En Twilio console → Messaging → Settings → WhatsApp Sandbox Settings
    → When a message comes in: https://TU-DOMINIO/webhook/twilio
    """
    reply = agent.respond(From, Body)
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f"<Response><Message>{reply}</Message></Response>"
    )
    return Response(content=twiml, media_type="application/xml")


# ── Meta WhatsApp Cloud API ────────────────────────────────────────────────────

VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")


@app.get("/webhook/meta")
async def meta_verify(request: Request):
    """Verificación inicial del webhook con Meta."""
    params = dict(request.query_params)
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == VERIFY_TOKEN
    ):
        return PlainTextResponse(params["hub.challenge"])
    raise HTTPException(status_code=403, detail="Token de verificación incorrecto")


@app.post("/webhook/meta")
async def meta_webhook(request: Request):
    """Recibe mensajes entrantes de Meta WhatsApp Cloud API."""
    try:
        data = await request.json()
        entry = data["entry"][0]["changes"][0]["value"]
        messages = entry.get("messages", [])

        for msg in messages:
            if msg.get("type") != "text":
                continue
            phone = msg["from"]
            text = msg["text"]["body"]
            reply = agent.respond(phone, text)
            await _send_meta_message(phone, reply)

    except (KeyError, IndexError, TypeError):
        pass  # Webhooks de estado (delivered, read) no tienen "messages"

    return {"status": "ok"}


async def _send_meta_message(to: str, text: str):
    """Envía un mensaje via Meta WhatsApp Cloud API."""
    if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_ID:
        return
    url = f"https://graph.facebook.com/v19.0/{WHATSAPP_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(url, headers=headers, json=payload)

"""
MOKADU WhatsApp Agent — Núcleo del agente de IA
Gestiona la conversación con los clientes usando Claude.
"""

import json
import os
from datetime import datetime, time, timedelta
from pathlib import Path

from dotenv import load_dotenv
from anthropic import Anthropic

load_dotenv(Path(__file__).parent / ".env")

# ── Sistema de prompt ──────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Eres el asistente de WhatsApp de MOKADU, un restaurante en el barrio de Pozas de Bilbao.

Tu personalidad: cercana, natural y directa. Eres parte del equipo, no un robot corporativo. Hablas con normalidad — sin formalismos pero tampoco con argot excesivo. Nada de "tío", "hermano", "macho" o expresiones demasiado coloquiales. Breve siempre.

━━━ DATOS DEL RESTAURANTE ━━━

📍 Dirección: Licenciado Poza, 34, 48009 Bilbao (barrio de Pozas)
📞 Teléfono: +34 621 011 201
📱 Instagram: @mokadubilbao  |  TikTok: @mokadu.bilbao
⭐ 9,8 sobre 10 (292 reseñas) · ~30 € por persona · +40 comensales

━━━ HORARIOS ━━━
• Lunes: CERRADO
• Martes y Miércoles: 13:30–16:30 (última mesa 15:45, cocina cierra 16:00) · 19:15–23:00 (última mesa 21:45, cocina cierra 22:15)
• Jueves: 13:30–16:30 (última mesa 15:45, cocina cierra 16:00) · 19:15–00:15 (última mesa 21:45, cocina cierra 22:15)
• Viernes y Sábado: 13:30–17:30 (última mesa 16:00, cocina cierra 16:45) · 19:15–01:30 (última mesa 22:30, cocina cierra 23:15)
• Domingo: CERRADO

━━━ LA CARTA ━━━

ABRIMOS (para empezar):
• PDT — Patatas triple cocción con mayonesa de tres ajos (frito, crudo y negro)
• Playeros — Tostones playeros con colslaw y salsa agridulce de tamarindo (opcional: cerdo asado con especias jamaicanas)
• Sa-aM — Saam de pollo frito, kimchi de pepino y salsa dulce de ají amarillo
• Crème à la Edgar — Crema de berenjena asada, queso azul y requesón con cerezas y crujientes de maíz

SEGUIMOS (plato fuerte):
• Nikita — Burrito de atún o bonito macerado en aceite de sésamo y soja, arroz, crema de frijol, salsa de crema fresca, pimientos del piquillo y cebolla quemada
• La Chilenita — Arepa de pollo mechado, aguacate, aliño asiático (soja, aceite de sésamo, jengibre, ajo) y col lombarda encurtida
• Sal del Coche — Sandwich vegetal en focaccia: rostí de patata, escalibada de berenjena y pimiento del piquillo, mojo picón canario y salsa de ciruela (collab @saldelcoche)
• Rosbiti — Sandwich de redondo de ternera (roastbeef), lechuga, tomate asado y albahaca

POSTRES:
• Brigadeiros — Receta de Ana, nuestra cocinera de Brasil. De chocolate negro, haba tonka o pimentón
• Ice-Dwich — Cookies con 5 especias chinas y helado de nata

BEBIDAS:
• Espresso Martini (vodka, licor de café, espresso)
• Margabirra (margarita frozen con cerveza artesana)
• Margarita Frozen (tequila, triple sec, lima)
• Porn Star (vodka, fruta de la pasión, prosecco)
• Lemonada de Albahaca (sin alcohol)
• Vinos de pequeños productores — selección curada por Inés

━━━ RESERVAS ━━━
Reservas online (recomendado): https://mokadu.myrestoo.net/v2?view=reservation&lang=es
También por teléfono (+34 621 011 201) o en persona.
Si preguntan sobre reservas, da primero el link de Restoo y luego el teléfono como alternativa.

━━━ REGLAS DE RESPUESTA ━━━
1. Mensajes CORTOS: máximo 3-4 líneas. La gente está en WhatsApp, no leyendo un email.
2. Responde SIEMPRE en español. Si te hablan en euskera, responde en euskera.
3. Si no tienes la información exacta (precio concreto de un plato, alérgenos, disponibilidad), di que llamen al +34 621 011 201.
4. No inventes ingredientes ni información que no tengas.
5. Un emoji como máximo, y solo si encaja de forma natural.
6. Para preguntas de reservas → siempre da el teléfono.
7. Si alguien quiere el menú completo, dáselo ordenado y claro.
8. Si alguien pregunta si estás abierto AHORA → usa la información de contexto del sistema.
9. FORMATO: Solo texto plano. NO uses ** para negrita, NO uses # para títulos, NO uses markdown. Usa • para listas. Los números de teléfono escríbelos tal cual: 621 011 201.
"""


# ── Utilidades de horario ──────────────────────────────────────────────────────

def get_schedule_context() -> str:
    """Genera un bloque de contexto con el estado actual del restaurante."""
    now = datetime.now()
    weekday = now.weekday()  # 0=lunes … 6=domingo
    t = now.time()

    horarios: dict[int, list[tuple[time, time]]] = {
        0: [],
        1: [(time(13, 30), time(16, 30)), (time(19, 15), time(23, 0))],
        2: [(time(13, 30), time(16, 30)), (time(19, 15), time(23, 0))],
        3: [(time(13, 30), time(16, 30)), (time(19, 15), time(23, 59))],  # cierra 00:15
        4: [(time(13, 30), time(17, 30)), (time(19, 15), time(23, 59))],  # cierra 01:30
        5: [(time(13, 30), time(17, 30)), (time(19, 15), time(23, 59))],  # cierra 01:30
        6: [],
    }

    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    dia = dias[weekday]
    slots = horarios[weekday]

    if not slots:
        estado = f"Hoy es {dia} — estamos CERRADOS."
    else:
        abierto = any(s <= t <= e for s, e in slots)
        franjas = " y ".join(f"{s.strftime('%H:%M')}–{e.strftime('%H:%M')}" for s, e in slots)
        if abierto:
            estado = f"Hoy es {dia} y ahora mismo estamos ABIERTOS. Cerramos hoy: {franjas}."
        else:
            estado = f"Hoy es {dia} — ahora mismo estamos CERRADOS. Hoy abrimos: {franjas}."

    return f"[CONTEXTO DEL SISTEMA — {now.strftime('%d/%m/%Y %H:%M')} — {estado}]"


# ── Agente principal ───────────────────────────────────────────────────────────

class MokaduAgent:
    """Agente de conversación con memoria persistente por número de teléfono."""

    CONVERSATIONS_FILE = Path(os.getenv("DATA_DIR", str(Path(__file__).parent))) / "conversations.json"
    MAX_HISTORY = 20          # Máximo de mensajes en memoria por usuario
    SESSION_TIMEOUT_H = 24    # Horas sin actividad para reiniciar contexto

    def __init__(self):
        self.client = Anthropic()
        self.conversations: dict[str, dict] = {}
        self._load()

    # ── Persistencia ──

    def _load(self):
        if self.CONVERSATIONS_FILE.exists():
            try:
                with open(self.CONVERSATIONS_FILE, "r", encoding="utf-8") as f:
                    self.conversations = json.load(f)
            except Exception:
                self.conversations = {}

    def _save(self):
        try:
            with open(self.CONVERSATIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.conversations, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ── Gestión de historial ──

    def _get_history(self, phone: str) -> list:
        entry = self.conversations.get(phone)
        if not entry:
            return []

        # Expirar sesiones inactivas
        last_ts = entry.get("last_ts", "")
        if last_ts:
            try:
                last_dt = datetime.fromisoformat(last_ts)
                if datetime.now() - last_dt > timedelta(hours=self.SESSION_TIMEOUT_H):
                    self.conversations.pop(phone, None)
                    return []
            except ValueError:
                pass

        return entry.get("messages", [])

    def _set_history(self, phone: str, messages: list):
        self.conversations[phone] = {
            "messages": messages[-self.MAX_HISTORY:],
            "last_ts": datetime.now().isoformat(),
        }

    # ── API pública ──

    def respond(self, phone: str, user_message: str) -> str:
        """Procesa un mensaje y devuelve la respuesta del bot."""
        history = self._get_history(phone)
        history.append({"role": "user", "content": user_message})

        system = SYSTEM_PROMPT.strip() + "\n\n" + get_schedule_context()

        response = self.client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=system,
            messages=history,
        )

        reply = response.content[0].text.strip()
        history.append({"role": "assistant", "content": reply})
        self._set_history(phone, history)
        self._save()
        return reply

    def clear_history(self, phone: str):
        """Borra el historial de un usuario."""
        self.conversations.pop(phone, None)
        self._save()

    def stats(self) -> dict:
        """Estadísticas básicas del agente."""
        return {
            "usuarios_activos": len(self.conversations),
            "modelo": "claude-haiku-4-5-20251001",
        }

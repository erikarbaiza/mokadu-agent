"""
WhatsApp Restaurant Agent — núcleo del agente de IA.
Toda la información del restaurante vive en config.json.
"""

import json
import os
import re
from datetime import datetime, time, timedelta
from pathlib import Path

from dotenv import load_dotenv
from anthropic import Anthropic
from restoo_client import check_availability, format_availability_message, restoo_enabled

load_dotenv(Path(__file__).parent / ".env")

CONFIG_PATH = Path(os.getenv("CONFIG_PATH", str(Path(__file__).parent / "config.json")))


# ── Carga de configuración ─────────────────────────────────────────────────────

def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


# ── Construcción del system prompt ─────────────────────────────────────────────

_DIAS_ORDEN = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
_DIAS_DISPLAY = {
    "lunes": "Lunes", "martes": "Martes", "miercoles": "Miércoles",
    "jueves": "Jueves", "viernes": "Viernes", "sabado": "Sábado", "domingo": "Domingo",
}


def _build_horarios_text(horarios: dict) -> str:
    lines = []
    for dia in _DIAS_ORDEN:
        franjas = horarios[dia]["franjas"]
        label = _DIAS_DISPLAY[dia]
        if not franjas:
            lines.append(f"• {label}: CERRADO")
        else:
            partes = [
                f"{f['apertura']}–{f['cierre']} (última mesa {f['ultima_mesa']}, cocina cierra {f['cierre_cocina']})"
                for f in franjas
            ]
            lines.append(f"• {label}: {' · '.join(partes)}")
    return "\n".join(lines)


def _build_carta_text(carta: dict) -> str:
    lines = [
        f"Leyenda: {carta['leyenda']}",
        f"IMPORTANTE: {carta['nota_trazas']}",
        "",
    ]
    for cat in carta["categorias"]:
        lines.append(cat["nombre"] + ":")
        for p in cat["platos"]:
            alg = f" · {p['alergenos']}" if p.get("alergenos") else ""
            lines.append(f"• {p['nombre']} {p['precio']} — {p['descripcion']}{alg}")
        lines.append("")

    if carta.get("fuera_carta"):
        lines.append("FUERA CARTA (a veces, preguntar si hay hoy):")
        for item in carta["fuera_carta"]:
            lines.append(f"• {item}")

    return "\n".join(lines)


def _build_reglas_text(reglas: list, cfg: dict) -> str:
    lines = []
    for i, regla in enumerate(reglas, 1):
        texto = regla.replace("{{telefono_display}}", cfg["contacto"]["telefono_display"])
        lines.append(f"{i}. {texto}")
    return "\n".join(lines)


def build_system_prompt(cfg: dict) -> str:
    c = cfg["contacto"]
    e = cfg["estadisticas"]
    return f"""Eres el asistente de WhatsApp de {cfg['nombre']}, {cfg['descripcion']}.

Tu personalidad: {cfg['personalidad']}

━━━ DATOS DEL RESTAURANTE ━━━

📍 Dirección: {c['direccion']}
📞 Teléfono: {c['telefono']}
📱 Instagram: {c['instagram']}  |  TikTok: {c['tiktok']}
⭐ {e['resenas']} · {e['precio_medio']} · {e['aforo']}

━━━ HORARIOS ━━━
{_build_horarios_text(cfg['horarios'])}

━━━ LA CARTA ({cfg['carta']['version']} — temporada actual) ━━━

{_build_carta_text(cfg['carta'])}

━━━ BEBIDAS ━━━

{cfg['bebidas_texto']}

━━━ RESERVAS Y CANCELACIONES ━━━
IMPORTANTE: No atendemos el teléfono durante el servicio. Para reservas y cancelaciones usa SIEMPRE Restoo:
→ {cfg['reservas_url']}

Cuando alguien quiera RESERVAR:
1. Pregunta: ¿Para qué día? ¿Comida (13:30) o cena (19:15)? ¿Cuántas personas?
2. Con esa info, manda el link: "Perfecto, reserva aquí y selecciona [día], [franja] y [X personas]: {cfg['reservas_url']}"

Cuando alguien quiera CANCELAR:
1. Manda el link de Restoo: "Para cancelar entra en: {cfg['reservas_url']} y gestiona tu reserva desde el email de confirmación que recibiste."

NUNCA digas "llama por teléfono" para reservas o cancelaciones. El teléfono solo para urgencias del día.

━━━ REGLAS DE RESPUESTA ━━━
{_build_reglas_text(cfg['reglas_respuesta'], cfg)}
"""


# ── Utilidades de horario ──────────────────────────────────────────────────────

def _parse_time(s: str) -> time:
    """Convierte "HH:MM" a time. Horas pasadas de medianoche se tratan como 23:59."""
    h, m = map(int, s.split(":"))
    if h < 6:  # 00:xx, 01:xx, etc. → pasada de medianoche
        return time(23, 59)
    return time(h, m)


def get_schedule_context(cfg: dict) -> str:
    """Genera un bloque de contexto con el estado actual del restaurante."""
    now = datetime.now()
    dia_key = _DIAS_ORDEN[now.weekday()]
    dia_display = _DIAS_DISPLAY[dia_key]
    franjas = cfg["horarios"][dia_key]["franjas"]
    t = now.time()

    if not franjas:
        estado = f"Hoy es {dia_display} — estamos CERRADOS."
    else:
        slots = [(_parse_time(f["apertura"]), _parse_time(f["cierre"])) for f in franjas]
        abierto = any(s <= t <= e for s, e in slots)
        franjas_text = " y ".join(f"{s.strftime('%H:%M')}–{e.strftime('%H:%M')}" for s, e in slots)
        if abierto:
            estado = f"Hoy es {dia_display} y ahora mismo estamos ABIERTOS. Cerramos hoy: {franjas_text}."
        else:
            estado = f"Hoy es {dia_display} — ahora mismo estamos CERRADOS. Hoy abrimos: {franjas_text}."

    return f"[CONTEXTO DEL SISTEMA — {now.strftime('%d/%m/%Y %H:%M')} — {estado}]"


# ── Agente principal ───────────────────────────────────────────────────────────

class RestaurantAgent:
    """Agente de conversación con memoria persistente por número de teléfono."""

    MAX_HISTORY = 20
    SESSION_TIMEOUT_H = 24

    def __init__(self):
        self.cfg = load_config()
        self.client = Anthropic()
        self.conversations: dict[str, dict] = {}
        data_dir = Path(os.getenv("DATA_DIR", str(Path(__file__).parent)))
        self._conversations_file = data_dir / "conversations.json"
        self._load()

    def _load(self):
        if self._conversations_file.exists():
            try:
                with open(self._conversations_file, encoding="utf-8") as f:
                    self.conversations = json.load(f)
            except Exception:
                self.conversations = {}

    def _save(self):
        try:
            with open(self._conversations_file, "w", encoding="utf-8") as f:
                json.dump(self.conversations, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _get_history(self, phone: str) -> list:
        entry = self.conversations.get(phone)
        if not entry:
            return []
        last_ts = entry.get("last_ts", "")
        if last_ts:
            try:
                if datetime.now() - datetime.fromisoformat(last_ts) > timedelta(hours=self.SESSION_TIMEOUT_H):
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

    def _restoo_context(self, user_message: str) -> str:
        """Si el mensaje pregunta por disponibilidad para una fecha concreta y la API está activa,
        consulta Restoo y devuelve un bloque de contexto para el system prompt."""
        if not restoo_enabled():
            return ""

        # Detecta patrones como "viernes", "mañana", "14 de noviembre", "para 3 personas"
        msg_lower = user_message.lower()
        reservation_keywords = [
            "reserv", "mesa", "disponib", "hay sitio", "hay hueco",
            "mañana", "pasado", "semana", "viernes", "sábado", "jueves",
            "lunes", "martes", "miércoles", "domingo",
        ]
        if not any(k in msg_lower for k in reservation_keywords):
            return ""

        # Intenta extraer número de personas
        pax_match = re.search(r"(\d+)\s*(?:persona|comensal|adulto|gente|nos)", msg_lower)
        pax = int(pax_match.group(1)) if pax_match else 2

        # Intenta extraer fecha: "mañana", "pasado mañana", o día de la semana
        today = datetime.now()
        date_str = None
        if "mañana" in msg_lower and "pasado" not in msg_lower:
            date_str = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "pasado mañana" in msg_lower:
            date_str = (today + timedelta(days=2)).strftime("%Y-%m-%d")
        else:
            dias_map = {
                "lunes": 0, "martes": 1, "miércoles": 2, "miercoles": 2,
                "jueves": 3, "viernes": 4, "sábado": 5, "sabado": 5, "domingo": 6,
            }
            for nombre, weekday in dias_map.items():
                if nombre in msg_lower:
                    days_ahead = (weekday - today.weekday()) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    date_str = (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
                    break

        if not date_str:
            return ""

        result = check_availability(date_str, pax)
        if not result:
            return ""

        msg = format_availability_message(result, pax, self.cfg["reservas_url"])
        return f"\n\n[DISPONIBILIDAD EN TIEMPO REAL — Restoo API]\n{msg}"

    def respond(self, phone: str, user_message: str) -> str:
        history = self._get_history(phone)
        history.append({"role": "user", "content": user_message})

        restoo_ctx = self._restoo_context(user_message)
        system = build_system_prompt(self.cfg) + "\n\n" + get_schedule_context(self.cfg) + restoo_ctx

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
        self.conversations.pop(phone, None)
        self._save()

    def stats(self) -> dict:
        return {
            "restaurante": self.cfg["nombre"],
            "usuarios_activos": len(self.conversations),
            "modelo": "claude-haiku-4-5-20251001",
        }


# Alias de compatibilidad — se puede eliminar cuando se actualice server.py
MokaduAgent = RestaurantAgent

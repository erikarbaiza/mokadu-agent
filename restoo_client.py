"""
restoo_client.py — cliente mínimo para la API de Restoo.
Requiere en .env:
  RESTOO_API_KEY=rst_...
  RESTOO_ACCOUNT_ID=mokadu        (el slug/subdominio del restaurante)
  RESTOO_PARTNER_ID=...           (pedirlo a soporte de Restoo)
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

try:
    import httpx
    _HTTP_OK = True
except ImportError:
    _HTTP_OK = False

_BASE = "https://api.myrestoo.net/v3"
_API_KEY = os.getenv("RESTOO_API_KEY", "")
_PARTNER_ID = os.getenv("RESTOO_PARTNER_ID", "")
_USER_ID = os.getenv("RESTOO_USER_ID", "")
_ACCOUNT_ID = os.getenv("RESTOO_ACCOUNT_ID", "")

_DIAS_ES = {
    0: "lunes", 1: "martes", 2: "miércoles", 3: "jueves",
    4: "viernes", 5: "sábado", 6: "domingo",
}


def _is_configured() -> bool:
    return bool(_API_KEY and _ACCOUNT_ID and _PARTNER_ID and _USER_ID and _HTTP_OK)


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_API_KEY}",
        "Content-Type": "application/json",
        "Restoo-Partner-Id": _PARTNER_ID,
        "Restoo-User-Id": _USER_ID,
        "Restoo-Account-Id": _ACCOUNT_ID,
    }


def check_availability(date_str: str, pax: int, pax_children: int = 0) -> dict | None:
    """
    Consulta disponibilidad para una fecha (YYYY-MM-DD).
    Devuelve dict con 'available', 'shifts', 'message', o None si hay error.
    """
    if not _is_configured():
        return None

    url = f"{_BASE}/availability/work-days/{date_str}"
    body = {"pax": pax, "paxChildren": pax_children, "status": "CONFIRMED"}

    try:
        r = httpx.post(url, json=body, headers=_headers(), timeout=8)
    except Exception:
        return None

    if r.status_code != 200:
        return None

    data = r.json()
    avail = data.get("availability", {})
    is_available = avail.get("isAvailable", False)

    # Extrae los turnos con horario
    shifts = []
    for s in data.get("shifts", []):
        if not s.get("availability", {}).get("isAvailable", False):
            continue
        name = s.get("type", {}).get("name", "")
        first = s.get("firstBookingAt", "")
        last = s.get("lastBookingAt", "")
        if name and first:
            shifts.append({"nombre": name, "primera": first[:5], "ultima": last[:5]})

    # Fecha legible en español
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        dia_nombre = _DIAS_ES[dt.weekday()]
        fecha_es = f"{dia_nombre} {dt.day} de {_mes(dt.month)}"
    except Exception:
        fecha_es = date_str

    return {
        "available": is_available,
        "shifts": shifts,
        "fecha_es": fecha_es,
        "date_str": date_str,
    }


def format_availability_message(result: dict, pax: int, reservas_url: str) -> str:
    """Convierte el resultado de la API en texto para WhatsApp."""
    fecha = result["fecha_es"]

    if not result["available"]:
        return (
            f"Para el {fecha} no hay disponibilidad para {pax} personas. "
            f"Prueba otra fecha en {reservas_url}"
        )

    if not result["shifts"]:
        return f"Hay mesa el {fecha} para {pax} personas. Reserva aquí: {reservas_url}"

    lineas = [f"El {fecha} hay disponibilidad para {pax} personas:"]
    for s in result["shifts"]:
        lineas.append(f"• {s['nombre']}: {s['primera']}–{s['ultima']}")
    lineas.append(f"Reserva aquí: {reservas_url}")
    return "\n".join(lineas)


def _mes(n: int) -> str:
    return ["enero","febrero","marzo","abril","mayo","junio",
            "julio","agosto","septiembre","octubre","noviembre","diciembre"][n - 1]


def restoo_enabled() -> bool:
    return _is_configured()

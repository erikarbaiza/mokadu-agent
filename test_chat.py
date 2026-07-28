"""
test_chat.py — Tester de consola para el agente MOKADU

Úsalo para probar el bot antes de conectarlo a WhatsApp.

Uso:
  python test_chat.py
"""

import os
import sys
from agent import MokaduAgent


def main():
    # Comprobación rápida de variables de entorno
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("❌  Falta ANTHROPIC_API_KEY en el entorno.")
        print("   Crea un archivo .env con: ANTHROPIC_API_KEY=sk-ant-...")
        print("   O exporta la variable: set ANTHROPIC_API_KEY=sk-ant-...")
        sys.exit(1)

    agent = MokaduAgent()
    phone = "test_consola"

    banner = """
╔══════════════════════════════════════════════╗
║  🤌  MOKADU Bot — Tester de consola          ║
║                                              ║
║  'salir'  → terminar                         ║
║  'reset'  → borrar historial                 ║
║  'stats'  → ver estadísticas                 ║
╚══════════════════════════════════════════════╝
"""
    print(banner)

    while True:
        try:
            user_input = input("Tú: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n¡Hasta luego!")
            break

        if not user_input:
            continue

        match user_input.lower():
            case "salir" | "exit" | "quit":
                print("¡Hasta luego!")
                break
            case "reset":
                agent.clear_history(phone)
                print("[Historial borrado — nueva conversación]\n")
            case "stats":
                print(f"[Estadísticas: {agent.stats()}]\n")
            case _:
                reply = agent.respond(phone, user_input)
                print(f"\nBot: {reply}\n")


if __name__ == "__main__":
    main()

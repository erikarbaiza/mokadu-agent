#!/bin/sh
set -e

# Crear carpeta de datos persistentes si no existe
mkdir -p /app/data/auth_info

echo "🐍 Arrancando servidor Python..."
uvicorn server:app --host 0.0.0.0 --port "${PORT:-8000}" &

# Esperar a que el servidor esté listo
sleep 3

echo "🤖 Arrancando bridge de WhatsApp (Baileys)..."
cd /app/baileys
node index.js

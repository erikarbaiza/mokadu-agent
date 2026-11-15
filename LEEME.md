# 🤌 MOKADU WhatsApp Bot

Agente de IA que responde automáticamente los mensajes de WhatsApp del restaurante. Usa Claude (Anthropic) para entender las preguntas y contestar como si fuera el equipo de Mokadu.

---

## Qué hace

- Responde preguntas sobre **horarios**, **carta**, **reservas**, **ubicación** y cócteles
- Sabe si el restaurante **está abierto ahora mismo** en tiempo real
- Recuerda el **contexto de la conversación** (no le tienes que repetir lo que ya le dijiste)
- Responde en **español** (o en euskera si le hablan en euskera)
- Mensajes cortos y naturales — no suena a bot

---

## Paso 1 — Instalar dependencias Python

```bash
cd mokadu-agent
pip install -r requirements.txt
```

---

## Paso 2 — Configurar la API key

Copia `.env.example` a `.env` y pon tu clave de Anthropic:

```bash
copy .env.example .env
```

Edita `.env` y pon:
```
ANTHROPIC_API_KEY=sk-ant-api03-TU-CLAVE-AQUI
```

Tu clave está en: https://console.anthropic.com/settings/keys

---

## Paso 3 — Probar el bot en consola (sin WhatsApp)

Antes de conectarlo a WhatsApp, prueba que funciona:

```bash
python test_chat.py
```

Escríbele cosas como:
- "¿Estáis abiertos ahora?"
- "¿Qué hay de comer?"
- "Quiero reservar una mesa para 4 personas el viernes"
- "¿Dónde estáis?"

---

## Paso 4 — Conectar a WhatsApp

Tienes **dos opciones**. Elige una:

---

### OPCIÓN A — Baileys (gratis, con el número real del restaurante) ✅ Recomendada

Usa el número de WhatsApp ya existente del restaurante, sin pagar nada.

**Primero**, arranca el servidor Python en una terminal:
```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

**Luego**, en otra terminal, arranca el bridge de Baileys:
```bash
cd baileys
npm install
node index.js
```

Aparecerá un **código QR** en la terminal. Ábrelo con el móvil del restaurante:
1. WhatsApp → ⋮ → Dispositivos vinculados → Vincular dispositivo
2. Escanea el QR

✅ Listo. El bot ya responde automáticamente desde ese número.

> **Nota**: La sesión se guarda en `baileys/auth_info/`. No hace falta volver a escanear el QR a menos que cierres la sesión manualmente.

> **Limitación**: Baileys usa WhatsApp Web. El teléfono del restaurante necesita tener conexión a internet. Si el teléfono se desconecta durante más de 14 días, habrá que volver a escanear.

---

### OPCIÓN B — Twilio (sandbox gratuito para probar, luego 0,005 €/mensaje)

Útil si quieres un número de WhatsApp separado para el bot.

1. Crea cuenta en https://www.twilio.com (gratis)
2. Ve a **Console → Messaging → Try it out → Send a WhatsApp message**
3. Sigue las instrucciones para activar el Sandbox
4. En la sección **Sandbox Settings**, pon como webhook:
   ```
   https://TU-DOMINIO/webhook/twilio
   ```
5. Rellena `TWILIO_ACCOUNT_SID` y `TWILIO_AUTH_TOKEN` en el `.env`
6. Arranca el servidor:
   ```bash
   uvicorn server:app --host 0.0.0.0 --port 8000
   ```

Para exponer el servidor localmente durante las pruebas, usa **ngrok**:
```bash
# Instalar ngrok: https://ngrok.com/download
ngrok http 8000
# Copia la URL https://xxxx.ngrok.io y úsala como webhook en Twilio
```

---

## Deploy en la nube (para que funcione 24/7 sin dejar el PC encendido)

### Railway (gratis hasta 500 horas/mes)

1. Crea cuenta en https://railway.app
2. Conecta el repo de GitHub
3. Añade la variable `ANTHROPIC_API_KEY` en Environment Variables
4. Railway detecta automáticamente Python y arranca el servidor

### Render (plan gratuito disponible)

1. Crea cuenta en https://render.com
2. New → Web Service → conecta el repo
3. Start command: `uvicorn server:app --host 0.0.0.0 --port $PORT`
4. Añade `ANTHROPIC_API_KEY` en Environment

---

## Estructura de archivos

```
mokadu-agent/
├── config.json        # Datos del restaurante (editar esto para cada cliente)
├── agent.py           # Núcleo del agente (Claude + memoria)
├── server.py          # Servidor FastAPI (Twilio + Meta + Baileys)
├── test_chat.py       # Tester de consola
├── requirements.txt   # Dependencias Python
├── .env.example       # Plantilla de credenciales
├── conversations.json # Historial de conversaciones (se crea automáticamente)
└── baileys/
    ├── index.js       # Bridge WhatsApp Web
    ├── package.json   # Dependencias Node.js
    └── auth_info/     # Sesión de WhatsApp (se crea al escanear el QR)
```

---

## Preguntas frecuentes

**¿Cuánto cuesta?**
- Claude Haiku: ~0,001 € por conversación típica (muy barato)
- Baileys: gratis
- Twilio sandbox: gratis para probar, luego ~0,005 €/mensaje en producción

**¿Qué pasa si le preguntan algo que no sabe?**
El bot da el teléfono del restaurante (configurado en `config.json`). Nunca inventa información.

**¿Puede hacer reservas?**
No las gestiona directamente — da el teléfono para reservar. Si en el futuro quieres integrar un sistema de reservas, se puede añadir.

**¿Habla en euskera?**
Sí, si el cliente escribe en euskera, el bot responde en euskera.

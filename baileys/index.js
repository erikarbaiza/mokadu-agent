/**
 * MOKADU WhatsApp Bot — Baileys Bridge
 *
 * Conecta el número de WhatsApp del restaurante con el agente de IA Python.
 * No necesita cuenta de Twilio ni de Meta — funciona con WhatsApp Web.
 *
 * SETUP (una sola vez):
 *   cd baileys
 *   npm install
 *   node index.js
 *   → Escanea el QR que aparece en consola con el WhatsApp del restaurante
 *   → La sesión se guarda en auth_info/ y no necesitas volver a escanear
 *
 * REQUISITOS:
 *   - El servidor Python debe estar corriendo: uvicorn server:app --port 8000
 *   - Node.js 18+
 */

require("dotenv").config({ path: "../.env" });

const fs = require("fs");
const path = require("path");
const cfg = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "config.json"), "utf8"));
const FALLBACK_PHONE = cfg.contacto.telefono;
const RESTAURANT_NAME = cfg.nombre;

const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  isJidBroadcast,
} = require("@whiskeysockets/baileys");

const http = require("http");
const axios = require("axios");
const pino = require("pino");
const qrcode = require("qrcode-terminal");
const QRCode = require("qrcode");

const AGENT_URL = process.env.AGENT_URL || `http://localhost:${process.env.PORT || 8000}/respond`;
const RECONNECT_DELAY_MS = 5000;
const MANUAL_PAUSE_MS = 30 * 60 * 1000; // 30 minutos
const HTTP_PORT = process.env.BAILEYS_PORT || process.env.PORT || 3000;

// Rastrear mensajes enviados por el bot para no confundirlos con respuestas manuales
const botSentTo = new Set(); // JIDs a los que el bot acaba de responder

// ── Servidor HTTP mínimo: health check + QR para escanear desde el navegador ──
let _lastQR = null;

http.createServer(async (req, res) => {
  if (req.url === "/qr") {
    if (!_lastQR) {
      res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      res.end("<h2>✅ Bot ya conectado — no hay QR pendiente</h2>");
      return;
    }
    const imgData = await QRCode.toDataURL(_lastQR);
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
    res.end(`<!DOCTYPE html><html><body style="text-align:center;font-family:sans-serif">
      <h2>Escanea con el WhatsApp del restaurante</h2>
      <img src="${imgData}" style="max-width:300px"><br>
      <small>Recarga la página si el QR expira</small>
    </body></html>`);
  } else {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok", connected: _lastQR === null }));
  }
}).listen(HTTP_PORT, () => {
  console.log(`🌐 Servidor HTTP escuchando en puerto ${HTTP_PORT} (GET /qr para escanear)`);
});

const logger = pino({ level: "warn" }); // "info" para más detalle

// ── Pausa manual: si el equipo responde a mano, el bot se aparta 4h ───────────
const manualOverride = new Map(); // phone → timestamp hasta el que está pausado

function setManualPause(phone) {
  manualOverride.set(phone, Date.now() + MANUAL_PAUSE_MS);
  console.log(`⏸  Bot pausado 4h para ${phone} (respuesta manual detectada)`);
}

function isPaused(phone) {
  const until = manualOverride.get(phone);
  if (!until) return false;
  if (Date.now() > until) {
    manualOverride.delete(phone);
    return false;
  }
  return true;
}

// ── Llamada al agente Python ──────────────────────────────────────────────────

async function askAgent(phone, message) {
  try {
    const res = await axios.post(
      AGENT_URL,
      { phone, message },
      { timeout: 20000 }
    );
    return res.data.reply;
  } catch (err) {
    console.error("❌ Error al contactar el agente:", err.message);
    return `Ahora estamos ocupados, pero te respondemos en breve 🙏`;
  }
}

// ── Filtros ───────────────────────────────────────────────────────────────────

function shouldIgnore(msg) {
  // Ignorar mensajes propios, de grupos y de broadcast
  if (msg.key.fromMe) return true;
  if (isJidBroadcast(msg.key.remoteJid)) return true;
  if (msg.key.remoteJid.endsWith("@g.us")) return true; // grupos
  return false;
}

function extractText(msg) {
  const m = msg.message;
  if (!m) return null;
  return (
    m.conversation ||
    m.extendedTextMessage?.text ||
    m.ephemeralMessage?.message?.extendedTextMessage?.text ||
    null
  );
}

// ── Bot principal ─────────────────────────────────────────────────────────────

async function startBot() {
  const { state, saveCreds } = await useMultiFileAuthState(process.env.AUTH_DIR || "auth_info");
  const { version, isLatest } = await fetchLatestBaileysVersion();
  console.log(`🤖 ${RESTAURANT_NAME} Bot — WA v${version.join(".")} ${isLatest ? "(latest)" : ""}`);

  const sock = makeWASocket({
    version,
    logger,
    auth: state,
    printQRInTerminal: false, // Usamos qrcode-terminal para mejor visual
    browser: [`${RESTAURANT_NAME} Bot`, "Chrome", "120.0.0"],
    connectTimeoutMs: 60000,
    keepAliveIntervalMs: 30000,
  });

  // Guardar credenciales cuando cambien
  sock.ev.on("creds.update", saveCreds);

  // Gestión de conexión
  sock.ev.on("connection.update", ({ connection, lastDisconnect, qr }) => {
    if (qr) {
      _lastQR = qr;
      console.log("\n📱 Escanea este QR con el WhatsApp del restaurante:\n");
      qrcode.generate(qr, { small: true });
      console.log(`\n🌐 O abre en el navegador: http://localhost:${HTTP_PORT}/qr\n`);
    }

    if (connection === "close") {
      const code = lastDisconnect?.error?.output?.statusCode;
      const loggedOut = code === DisconnectReason.loggedOut;
      console.log(`⚠️  Conexión cerrada (código ${code})`);

      if (loggedOut) {
        console.log("🔒 Sesión cerrada. Borra la carpeta auth_info/ y vuelve a escanear el QR.");
      } else {
        console.log(`↩️  Reconectando en ${RECONNECT_DELAY_MS / 1000}s...`);
        setTimeout(startBot, RECONNECT_DELAY_MS);
      }
    }

    if (connection === "open") {
      _lastQR = null;
      console.log("✅ MOKADU Bot conectado a WhatsApp y listo para responder\n");
    }
  });

  // Detectar respuestas manuales del equipo → pausar bot para ese cliente
  // Solo mensajes recientes (< 2 min) para ignorar el sync histórico inicial
  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;

    const now = Math.floor(Date.now() / 1000);
    for (const msg of messages) {
      const msgTs = msg.messageTimestamp || 0;
      if (now - msgTs > 120) continue; // ignorar mensajes con más de 2 min de antigüedad

      if (
        msg.key.fromMe &&
        !msg.key.remoteJid.endsWith("@g.us") &&
        !isJidBroadcast(msg.key.remoteJid) &&
        !botSentTo.has(msg.key.remoteJid) // ignorar mensajes que envió el propio bot
      ) {
        setManualPause(msg.key.remoteJid);
      }
    }
  });

  // Procesar mensajes entrantes de clientes
  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;

    for (const msg of messages) {
      if (shouldIgnore(msg)) continue;

      const phone = msg.key.remoteJid;

      // Si el equipo lleva la conversación manualmente, el bot no interviene
      if (isPaused(phone)) {
        console.log(`⏭  [${phone}] en modo manual, bot silenciado`);
        continue;
      }

      const text = extractText(msg);
      if (!text || !text.trim()) continue;

      console.log(`📩 [${new Date().toLocaleTimeString()}] ${phone}: ${text}`);

      await sock.sendPresenceUpdate("composing", phone);
      const reply = await askAgent(phone, text);
      await sock.sendPresenceUpdate("paused", phone);
      botSentTo.add(phone);
      setTimeout(() => botSentTo.delete(phone), 10000); // limpiar tras 10s
      await sock.sendMessage(phone, { text: reply });

      console.log(`💬 Bot → ${phone}: ${reply}\n`);
    }
  });
}

// ── Arranque ──────────────────────────────────────────────────────────────────

console.log("══════════════════════════════════════");
console.log(`  🤌  ${RESTAURANT_NAME} WhatsApp Bot  `);
console.log("══════════════════════════════════════");
console.log(`  Agente Python en: ${AGENT_URL}`);
console.log("  Asegúrate de que el servidor Python esté corriendo:");
console.log("  > uvicorn server:app --port 8000\n");

startBot().catch(console.error);

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

const {
  default: makeWASocket,
  useMultiFileAuthState,
  DisconnectReason,
  fetchLatestBaileysVersion,
  isJidBroadcast,
} = require("@whiskeysockets/baileys");

const axios = require("axios");
const pino = require("pino");
const qrcode = require("qrcode-terminal");

const AGENT_URL = process.env.AGENT_URL || `http://localhost:${process.env.PORT || 8000}/respond`;
const RECONNECT_DELAY_MS = 5000;

const logger = pino({ level: "warn" }); // "info" para más detalle

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
    return "Ahora mismo no puedo responder. Llámanos al +34 621 011 201 🙏";
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
  console.log(`🤖 MOKADU Bot — WA v${version.join(".")} ${isLatest ? "(latest)" : ""}`);

  const sock = makeWASocket({
    version,
    logger,
    auth: state,
    printQRInTerminal: false, // Usamos qrcode-terminal para mejor visual
    browser: ["MOKADU Bot", "Chrome", "120.0.0"],
    connectTimeoutMs: 60000,
    keepAliveIntervalMs: 30000,
  });

  // Guardar credenciales cuando cambien
  sock.ev.on("creds.update", saveCreds);

  // Gestión de conexión
  sock.ev.on("connection.update", ({ connection, lastDisconnect, qr }) => {
    if (qr) {
      console.log("\n📱 Escanea este QR con el WhatsApp del restaurante:\n");
      qrcode.generate(qr, { small: true });
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
      console.log("✅ MOKADU Bot conectado a WhatsApp y listo para responder\n");
    }
  });

  // Procesar mensajes entrantes
  sock.ev.on("messages.upsert", async ({ messages, type }) => {
    if (type !== "notify") return;

    for (const msg of messages) {
      if (shouldIgnore(msg)) continue;

      const phone = msg.key.remoteJid;
      const text = extractText(msg);

      if (!text || !text.trim()) continue;

      console.log(`📩 [${new Date().toLocaleTimeString()}] ${phone}: ${text}`);

      // Indicador "escribiendo..."
      await sock.sendPresenceUpdate("composing", phone);

      const reply = await askAgent(phone, text);

      await sock.sendPresenceUpdate("paused", phone);
      await sock.sendMessage(phone, { text: reply });

      console.log(`💬 Bot → ${phone}: ${reply}\n`);
    }
  });
}

// ── Arranque ──────────────────────────────────────────────────────────────────

console.log("══════════════════════════════════════");
console.log("  🤌  MOKADU WhatsApp Bot  ");
console.log("══════════════════════════════════════");
console.log(`  Agente Python en: ${AGENT_URL}`);
console.log("  Asegúrate de que el servidor Python esté corriendo:");
console.log("  > uvicorn server:app --port 8000\n");

startBot().catch(console.error);

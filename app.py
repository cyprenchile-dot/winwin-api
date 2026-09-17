#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClient.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <DNSServer.h>
#include <Wire.h>
#include <Arduino_GFX_Library.h>
#include <qrcode.h>
#include <Preferences.h>
#include <time.h>

// ==========================================================
// 1. CONFIGURACIÓN Y CALIBRACIÓN DE FÁBRICA
// ==========================================================
const int PRECIO_BASE_JUEGO        = 500; 
const int PULSO_ON_MS              = 100; 
const int PULSO_OFF_MS             = 120; 
const int TIMEOUT_QR_SEG           = 180; 

// Asignación de pines
const int PIN_RELE      = 18; 
const int PIN_LCD_BL    = 1;  

// Táctil I2C (AXS15231B)
#define TOUCH_ADDR 0x3B
#define TOUCH_SDA  4
#define TOUCH_SCL  8

// ==========================================================
// 2. CONTROLADOR DE PANTALLA QSPI + CANVAS
// ==========================================================
Arduino_DataBus *bus = new Arduino_ESP32QSPI(
    45 /* CS */, 47 /* SCK */, 21 /* D0 */, 48 /* D1 */, 40 /* D2 */, 39 /* D3 */);

Arduino_GFX *panel = new Arduino_AXS15231B(bus, GFX_NOT_DEFINED, 0, false, 320, 480);
Arduino_Canvas *gfx = new Arduino_Canvas(320, 480, panel, 0, 0, 0);

// ==========================================================
// 3. VARIABLES Y PREFERENCES
// ==========================================================
Preferences prefs;
WebServer server(80);
DNSServer dnsServer;
const byte DNS_PORT = 53;
IPAddress apIP(192, 168, 4, 1);
bool modo_setup = false;
bool solicitudReinicioPendiente = false;
unsigned long tiempoSolicitudReinicio = 0;
bool sesionAdminOK = false; // Variable de sesión segura en RAM

String machine_name = "VENDI-Q 01";
String wifi_ssid    = "";
String wifi_pass    = "";
String mp_token     = "";
String bot_token    = "8733497588:AAGAfbPdPJXrGxa5EsTZiDn-drSPy7Wwo6s";
String chat_id_personal = "8802293137";
String admin_user   = "admin";
String admin_pass   = "123456";

const char* ping_url = "http://hc-ping.com/436f3027-afdb-4595-97b0-3d924431b295";

long cajaMercadoPago = 0;
long totalJugadas    = 0;
long totalPremios    = 0;

String geoCiudad = "Detectando...";
String geoISP    = "Internet Local";
float geoLat     = 0.0;
float geoLon     = 0.0;
bool geoDisponible = false;

enum EstadoApp { ESTADO_MENU, ESTADO_QR, ESTADO_EXITO, ESTADO_RECHAZADO };
EstadoApp estadoActual = ESTADO_MENU;

int montoActual = 500;
int jugadasActuales = 1;
int pulsosActuales = 5;
String externalRefActual = "";
String qrUrlActual = "";
unsigned long ultimoCheckMP = 0;
unsigned long tiempoInicioQR = 0;

unsigned long ultimoPingHeartbeat = 0;
const unsigned long INTERVALO_PING = 60000;
unsigned long ultimoCheckWiFi = 0;

unsigned long tiempoInicioToqueLogo = 0;
bool tocandoLogo = false;
unsigned long tiempoInicioToqueSetup = 0;
bool tocandoSetup = false;

// Prototipos
void cargarParametrosMemoria();
void guardarContadoresFlash();
void iniciarModoSetup();
void mostrarPantallaSetup();
void dibujarMenuPrincipal();
void dibujarPantallaQR();
void procesarPagoExitoso(int monto, int jugadas, int pulsos, bool esDigital);
void procesarPagoRechazado();
void entregarPulsosRele(int pulsos);
bool enviarMensajeTelegram(String texto);
void enviarUbicacionTelegram(float lat, float lon);
void obtenerUbicacionPorIP();
String obtenerFechaHoraActual();
void enviarLatidoHeartbeat();
void verificarConexionWiFi();
void ejecutarCierreDeCaja();
int verificarEstadoPago(String extRef);

// ==========================================================
// 4. INTERFACES WEB (LOGIN Y CONFIGURACIÓN)
// ==========================================================
const char LOGIN_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Acceso VENDI-Q</title>
  <style>
    body { font-family: sans-serif; background-color: #111; color: #eee; margin: 0; display: flex; align-items: center; justify-content: center; height: 100vh; }
    .card { width: 100%; max-width: 360px; background: #1c1c1e; padding: 24px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); box-sizing: border-box; }
    h2 { color: #00d2ff; text-align: center; margin-top: 0; }
    label { display: block; margin-top: 12px; font-size: 13px; color: #aaa; }
    input { width: 100%; padding: 12px; margin-top: 6px; background: #2c2c2e; border: 1px solid #444; border-radius: 6px; color: #fff; box-sizing: border-box; font-size: 15px; }
    .btn { background: #00d2ff; color: #000; font-weight: bold; border: none; padding: 14px; width: 100%; border-radius: 8px; cursor: pointer; font-size: 16px; margin-top: 20px; }
    .error { color: #ff453a; font-size: 13px; text-align: center; margin-top: 12px; font-weight: bold; }
  </style>
</head>
<body>
  <div class="card">
    <h2>VENDI-Q Admin</h2>
    <form action="/login" method="POST" autocomplete="off">
      <label>Usuario:</label>
      <input type="text" name="user" required>
      <label>Contraseña:</label>
      <input type="password" name="pass" required>
      <button type="submit" class="btn">Ingresar al Sistema</button>
      %ERROR_MSG%
    </form>
  </div>
</body>
</html>
)rawliteral";

const char CONFIG_HTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Configuración VENDI-Q</title>
  <style>
    body { font-family: sans-serif; background-color: #111; color: #eee; margin: 0; padding: 18px; }
    .card { max-width: 440px; margin: 0 auto; background: #1c1c1e; padding: 20px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
    h1 { color: #00d2ff; text-align: center; margin: 0 0 16px 0; }
    fieldset { border: 1px solid #333; border-radius: 8px; margin-bottom: 14px; padding: 12px; }
    legend { color: #00d2ff; font-weight: bold; font-size: 13px; }
    label { display: block; margin-top: 8px; font-size: 12px; color: #aaa; }
    input { width: 100%; padding: 10px; margin-top: 4px; background: #2c2c2e; border: 1px solid #444; border-radius: 6px; color: #fff; box-sizing: border-box; font-size: 14px; }
    .pass-container { display: flex; gap: 8px; align-items: center; }
    .pass-container input { flex: 1; }
    .pass-btn { background: #333; color: #fff; border: 1px solid #555; padding: 10px; border-radius: 6px; cursor: pointer; font-size: 12px; margin-top: 4px; }
    .btn { background: #00d2ff; color: #000; font-weight: bold; border: none; padding: 14px; width: 100%; border-radius: 8px; cursor: pointer; font-size: 15px; margin-top: 14px; }
    .hint { font-size: 11px; color: #777; margin-top: 2px; }
  </style>
  <script>
    function togglePass() {
      var passInput = document.getElementById("wifi_pass");
      var btnPass = document.getElementById("btnPass");
      if (passInput.type === "password") {
        passInput.type = "text";
        btnPass.textContent = "Ocultar";
      } else {
        passInput.type = "password";
        btnPass.textContent = "Ver";
      }
    }
  </script>
</head>
<body>
  <div class="card">
    <h1>VENDI-Q</h1>
    <form action="/guardar" method="POST" autocomplete="off">
      <fieldset>
        <legend>1. Red Wi-Fi & Nombre</legend>
        <label>Nombre de Máquina / Local:</label>
        <input type="text" name="m_name" value="%M_NAME%">
        <label>Red Wi-Fi (SSID 2.4 GHz):</label>
        <input type="text" name="ssid" value="%SSID%">
        <label>Contraseña Wi-Fi:</label>
        <div class="pass-container">
          <input type="password" id="wifi_pass" name="pass" value="%PASS%">
          <button type="button" id="btnPass" class="pass-btn" onclick="togglePass()">Ver</button>
        </div>
      </fieldset>
      <fieldset>
        <legend>2. Mercado Pago</legend>
        <label>Access Token (Producción):</label>
        <input type="text" name="mp_token" value="%MP_TOKEN%">
      </fieldset>
      <fieldset>
        <legend>3. Telegram</legend>
        <label>Bot Token de Telegram:</label>
        <input type="text" name="bot_token" value="%BOT_TOKEN%">
        <label>IDs de Telegram (separados por coma):</label>
        <input type="text" name="tg_chat_p" value="%TG_CHAT_P%">
        <div class="hint">Ej: 8802293137, 987654321</div>
      </fieldset>
      <fieldset>
        <legend>4. Seguridad Panel Admin</legend>
        <label>Usuario Administrador:</label>
        <input type="text" name="admin_user" value="%ADMIN_USER%">
        <label>Contraseña Administrador:</label>
        <input type="text" name="admin_pass" value="%ADMIN_PASS%">
      </fieldset>
      <button type="submit" class="btn">Guardar y Reiniciar Máquina</button>
    </form>
  </div>
</body>
</html>
)rawliteral";

void cargarParametrosMemoria() {
  prefs.begin("vendi_cfg", true);
  machine_name     = prefs.getString("m_name", "VENDI-Q 01");
  wifi_ssid        = prefs.getString("ssid", "");
  wifi_pass        = prefs.getString("pass", "");
  mp_token         = prefs.getString("mp_tok", "");
  bot_token        = prefs.getString("bot_tok", "8733497588:AAGAfbPdPJXrGxa5EsTZiDn-drSPy7Wwo6s");
  chat_id_personal = prefs.getString("tg_chat_p", "8802293137");
  admin_user       = prefs.getString("adm_user", "admin");
  admin_pass       = prefs.getString("adm_pass", "123456");
  prefs.end();

  machine_name.trim();
  wifi_ssid.trim();
  wifi_pass.trim();
  mp_token.trim();
  bot_token.trim();
  chat_id_personal.trim();
  admin_user.trim();
  admin_pass.trim();

  prefs.begin("vendi_q", true);
  cajaMercadoPago  = prefs.getLong("caja_mp", 0);
  totalJugadas     = prefs.getLong("jugadas", 0);
  totalPremios     = prefs.getLong("premios", 0);
  prefs.end();
}

void guardarContadoresFlash() {
  prefs.begin("vendi_q", false);
  prefs.putLong("caja_mp", cajaMercadoPago);
  prefs.putLong("jugadas", totalJugadas);
  prefs.putLong("premios", totalPremios);
  prefs.end();
}

String procesarHTML(const char* html) {
  String s = html;
  s.replace("%M_NAME%", machine_name);
  s.replace("%SSID%", wifi_ssid);
  s.replace("%PASS%", wifi_pass);
  s.replace("%MP_TOKEN%", mp_token);
  s.replace("%BOT_TOKEN%", bot_token);
  s.replace("%TG_CHAT_P%", chat_id_personal);
  s.replace("%ADMIN_USER%", admin_user);
  s.replace("%ADMIN_PASS%", admin_pass);
  return s;
}

void mostrarPantallaSetup() {
  gfx->fillScreen(0x0000);
  gfx->fillRect(0, 0, 320, 50, 0xF940);
  gfx->setTextColor(0xFFFF);
  gfx->setTextSize(3);
  gfx->setCursor(45, 12);
  gfx->println("VENDI-Q");

  gfx->fillRoundRect(15, 70, 290, 380, 12, 0x0273);
  gfx->drawRoundRect(15, 70, 290, 380, 12, 0x07E0);

  gfx->setTextColor(0x07E0);
  gfx->setTextSize(2);
  gfx->setCursor(35, 95);
  gfx->println("MODO CONFIGURACION");

  gfx->setTextColor(0xFFFF);
  gfx->setTextSize(1);
  gfx->setCursor(35, 145);
  gfx->println("1. Conectate a la red Wi-Fi:");
  gfx->setTextColor(0xFFE0);
  gfx->setTextSize(2);
  gfx->setCursor(40, 170);
  gfx->println("VENDI-Q-SETUP");

  gfx->setTextColor(0xFFFF);
  gfx->setTextSize(1);
  gfx->setCursor(35, 220);
  gfx->println("2. Entra al navegador en:");
  gfx->setTextColor(0x07FF);
  gfx->setTextSize(2);
  gfx->setCursor(55, 245);
  gfx->println("192.168.4.1");

  gfx->setTextColor(0x07E0);
  gfx->setTextSize(2);
  gfx->setCursor(65, 380);
  gfx->println("ESPERANDO DATOS...");
  gfx->flush();
}

void iniciarModoSetup() {
  cargarParametrosMemoria(); 
  modo_setup = true;
  sesionAdminOK = false; // Reinicia la sesión al entrar al setup
  mostrarPantallaSetup();

  WiFi.disconnect();
  delay(100);
  WiFi.mode(WIFI_AP);
  WiFi.softAPConfig(apIP, apIP, IPAddress(255, 255, 255, 0));
  WiFi.softAP("VENDI-Q-SETUP");

  dnsServer.start(DNS_PORT, "*", apIP);

  // Ruta Raíz (/): Valida la sesión en RAM
  server.on("/", HTTP_GET, []() {
    if (!sesionAdminOK) {
      server.sendHeader("Location", "/login", true);
      server.send(302, "text/plain", "");
      return;
    }
    server.sendHeader("Cache-Control", "no-cache, no-store, must-revalidate");
    server.sendHeader("Pragma", "no-cache");
    server.sendHeader("Expires", "-1");
    server.send(200, "text/html", procesarHTML(CONFIG_HTML));
  });

  // Ruta Pantalla de Login (GET)
  server.on("/login", HTTP_GET, []() {
    String pag = LOGIN_HTML;
    pag.replace("%ERROR_MSG%", "");
    server.send(200, "text/html", pag);
  });

  // Ruta Validación Login (POST) - Sin cookies, directo con bandera en RAM
  server.on("/login", HTTP_POST, []() {
    String u = server.hasArg("user") ? server.arg("user") : "";
    String p = server.hasArg("pass") ? server.arg("pass") : "";
    u.trim(); p.trim();
    u.toLowerCase(); 

    String usuarioValidar = admin_user;
    usuarioValidar.trim();
    usuarioValidar.toLowerCase();

    if (u == usuarioValidar && p == admin_pass) {
      sesionAdminOK = true; // Activa la sesión en RAM
      server.sendHeader("Location", "/", true);
      server.send(302, "text/plain", "");
    } else {
      String pag = LOGIN_HTML;
      pag.replace("%ERROR_MSG%", "<div class='error'>Usuario o contraseña incorrectos</div>");
      server.send(200, "text/html", pag);
    }
  });

  // Ruta Guardar Cambios (POST)
  server.on("/guardar", HTTP_POST, []() {
    if (!sesionAdminOK) {
      server.sendHeader("Location", "/login", true);
      server.send(302, "text/plain", "");
      return;
    }

    String mName = server.hasArg("m_name") ? server.arg("m_name") : "VENDI-Q 01";
    String sSid  = server.hasArg("ssid") ? server.arg("ssid") : "";
    String pAss  = server.hasArg("pass") ? server.arg("pass") : "";
    String mpTok = server.hasArg("mp_token") ? server.arg("mp_token") : "";
    String bTok  = server.hasArg("bot_token") ? server.arg("bot_token") : "8733497588:AAGAfbPdPJXrGxa5EsTZiDn-drSPy7Wwo6s";
    String idTg  = server.hasArg("tg_chat_p") ? server.arg("tg_chat_p") : "8802293137";
    String aUser = server.hasArg("admin_user") ? server.arg("admin_user") : "admin";
    String aPass = server.hasArg("admin_pass") ? server.arg("admin_pass") : "123456";

    mName.trim(); sSid.trim(); pAss.trim(); mpTok.trim(); bTok.trim(); idTg.trim(); aUser.trim(); aPass.trim();

    prefs.begin("vendi_cfg", false);
    prefs.putString("m_name", mName);
    prefs.putString("ssid", sSid);
    prefs.putString("pass", pAss);
    prefs.putString("mp_tok", mpTok);
    prefs.putString("bot_tok", bTok);
    prefs.putString("tg_chat_p", idTg);
    prefs.putString("adm_user", aUser);
    prefs.putString("adm_pass", aPass);
    prefs.end();
    
    String resp = "<body style='background:#111;color:#eee;text-align:center;padding-top:70px;font-family:sans-serif;'>"
                  "<h2 style='color:#07E0;'>¡Todo listo a vender..!!</h2>"
                  "<p style='color:#aaa;font-size:15px;line-height:1.5;'>La máquina se reiniciará para aplicar los cambios.</p>"
                  "<div style='margin-top:30px;padding:14px;background:#222;border-radius:8px;display:inline-block;color:#00d2ff;font-weight:bold;'>Ya puedes cerrar esta ventana.</div>"
                  "</body>";
    server.send(200, "text/html", resp);

    solicitudReinicioPendiente = true;
    tiempoSolicitudReinicio = millis();
  });

  server.on("/generate_204", HTTP_GET, []() { server.sendHeader("Location", "http://192.168.4.1/", true); server.send(302, "text/plain", ""); });
  server.on("/fwlink", HTTP_GET, []() { server.sendHeader("Location", "http://192.168.4.1/", true); server.send(302, "text/plain", ""); });

  server.onNotFound([]() {
    server.sendHeader("Location", "http://192.168.4.1/", true);
    server.send(302, "text/plain", "");
  });

  server.begin();
  Serial.println("\n[VENDI-Q] Modo Setup ACTIVO con Sesión en RAM en 192.168.4.1");
}

// ==========================================================
// 5. CONTROLADOR TÁCTIL I2C
// ==========================================================
void inicializarTouch() {
  Wire.begin(TOUCH_SDA, TOUCH_SCL, 400000);
}

bool leerTouch(uint16_t &touchX, uint16_t &touchY) {
  uint8_t data[8] = {0};
  const uint8_t cmd[11] = { 0xb5, 0xab, 0xa5, 0x5a, 0x00, 0x00, 0x00, 0x08, 0x00, 0x00, 0x00 };

  Wire.beginTransmission(TOUCH_ADDR);
  Wire.write(cmd, 11);
  if (Wire.endTransmission() != 0) return false;

  if (Wire.requestFrom((uint8_t)TOUCH_ADDR, (uint8_t)8) != 8) return false;

  for (int i = 0; i < 8; i++) {
    data[i] = Wire.read();
  }

  if (data[1] > 0 && data[1] <= 2) {
    uint16_t rawX = ((data[2] & 0x0F) << 8) | data[3];
    uint16_t rawY = ((data[4] & 0x0F) << 8) | data[5];

    if (rawX <= 320 && rawY <= 480) {
      touchX = rawX;
      touchY = rawY;
      return true;
    }
  }
  return false;
}

// ==========================================================
// 6. CÓDIGO QR
// ==========================================================
void renderizarQRCallback(esp_qrcode_handle_t qrcode) {
  int size = esp_qrcode_get_size(qrcode);
  int escala = 260 / size;
  if (escala < 1) escala = 1;
  while ((size * escala) > 270 && escala > 1) {
    escala--;
  }

  int tamanoQR = size * escala;
  int centroX = 160;
  int centroY = 228;
  int origenX = centroX - (tamanoQR / 2);
  int origenY = centroY - (tamanoQR / 2);

  gfx->fillRect(origenX - 10, origenY - 10, tamanoQR + 20, tamanoQR + 20, 0xFFFF);

  for (int y = 0; y < size; y++) {
    for (int x = 0; x < size; x++) {
      if (esp_qrcode_get_module(qrcode, x, y)) {
        gfx->fillRect(origenX + (x * escala), origenY + (y * escala), escala, escala, 0x0000);
      }
    }
  }
}

void dibujarCodigoQR(const char* url) {
  esp_qrcode_config_t cfg;
  memset(&cfg, 0, sizeof(cfg));
  cfg.display_func = renderizarQRCallback;
  cfg.max_qrcode_version = 15;
  cfg.qrcode_ecc_level = ESP_QRCODE_ECC_LOW;
  esp_qrcode_generate(&cfg, url);
}

// ==========================================================
// 7. TELEMETRÍA Y GEOLOCALIZACIÓN TELEGRAM
// ==========================================================
String obtenerFechaHoraActual() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo, 1500)) {
    return "Hora sincronizando...";
  }
  char buffer[32];
  strftime(buffer, sizeof(buffer), "%d/%m/%Y - %H:%M:%S", &timeinfo);
  return String(buffer);
}

void obtenerUbicacionPorIP() {
  if (WiFi.status() != WL_CONNECTED) return;

  WiFiClient client;
  HTTPClient http;
  http.begin(client, "http://ip-api.com/json/?fields=status,city,regionName,isp,lat,lon");
  http.setTimeout(3500);

  int httpCode = http.GET();
  if (httpCode == 200) {
    String payload = http.getString();
    if (payload.indexOf("\"status\":\"success\"") != -1) {
      int idxCity = payload.indexOf("\"city\":\"");
      if (idxCity != -1) {
        int finCity = payload.indexOf("\"", idxCity + 8);
        geoCiudad = payload.substring(idxCity + 8, finCity);
      }
      int idxLat = payload.indexOf("\"lat\":");
      if (idxLat != -1) {
        int finLat = payload.indexOf(",", idxLat + 6);
        geoLat = payload.substring(idxLat + 6, finLat).toFloat();
      }
      int idxLon = payload.indexOf("\"lon\":");
      if (idxLon != -1) {
        int finLon = payload.indexOf("}", idxLon + 6);
        int comaLon = payload.indexOf(",", idxLon + 6);
        if (comaLon != -1 && comaLon < finLon) finLon = comaLon;
        geoLon = payload.substring(idxLon + 6, finLon).toFloat();
      }
      int idxIsp = payload.indexOf("\"isp\":\"");
      if (idxIsp != -1) {
        int finIsp = payload.indexOf("\"", idxIsp + 7);
        geoISP = payload.substring(idxIsp + 7, finIsp);
      }
      geoDisponible = true;
      Serial.printf("[GeoIP OK] %s (Lat: %.4f, Lon: %.4f)\n", geoCiudad.c_str(), geoLat, geoLon);
    }
  }
  http.end();
}

void enviarLatidoHeartbeat() {
  if (WiFi.status() != WL_CONNECTED) return;

  WiFiClient client;
  HTTPClient http;
  http.begin(client, ping_url);
  http.setTimeout(800);

  int codigo = http.GET();
  if (codigo == 200) {
    Serial.println("[HEARTBEAT OK] Latido recibido.");
  }
  http.end();
}

void verificarConexionWiFi() {
  if (WiFi.status() != WL_CONNECTED && !modo_setup) {
    Serial.println("[Wi-Fi] Reconectando red...");
    WiFi.reconnect();
  }
}

bool enviarMensajeTelegram(String texto) {
  chat_id_personal.trim();
  bot_token.trim();

  if (WiFi.status() != WL_CONNECTED || bot_token == "" || chat_id_personal == "") {
    Serial.println("[Telegram] Omitido: Wi-Fi desconectado o credenciales faltantes.");
    return false;
  }

  String textoFormateado = texto;
  textoFormateado.replace("\\", "\\\\");
  textoFormateado.replace("\"", "\\\"");
  textoFormateado.replace("\n", "\\n");
  textoFormateado.replace("\r", "");

  bool algunExito = false;
  String idsRestantes = chat_id_personal;

  while (idsRestantes.length() > 0) {
    int comaIdx = idsRestantes.indexOf(',');
    String currentId = "";
    if (comaIdx != -1) {
      currentId = idsRestantes.substring(0, comaIdx);
      idsRestantes = idsRestantes.substring(comaIdx + 1);
    } else {
      currentId = idsRestantes;
      idsRestantes = "";
    }
    currentId.trim();
    if (currentId.length() == 0) continue;
    bool entregadoParaEsteID = false;
    for (int intento = 1; intento <= 3 && !entregadoParaEsteID; intento++) {
      Serial.printf("[Telegram] Enviando a chat %s (Intento %d)...\n", currentId.c_str(), intento);

      WiFiClientSecure client;
      client.setInsecure();
      client.setTimeout(7000);

      HTTPClient http;
      http.setTimeout(7000);
      String url = "https://api.telegram.org/bot" + bot_token + "/sendMessage";

      if (http.begin(client, url)) {
        http.addHeader("Content-Type", "application/json");
        String payload = "{\"chat_id\":\"" + currentId + "\",\"text\":\"" + textoFormateado + "\"}";
        int httpCodigo = http.POST(payload);

        if (httpCodigo == 200) {
          Serial.printf("[Telegram] ¡Mensaje entregado a %s con EXITO!\n", currentId.c_str());
          entregadoParaEsteID = true;
          algunExito = true;
        } else {
          Serial.printf("[Telegram] ERROR HTTP %d para chat %s en intento %d.\n", httpCodigo, currentId.c_str(), intento);
          delay(1000);
        }
        http.end();
      }
      client.stop();
    }
  }

  return algunExito;
}

void enviarUbicacionTelegram(float lat, float lon) {
  chat_id_personal.trim();
  bot_token.trim();

  if (WiFi.status() != WL_CONNECTED || bot_token == "" || chat_id_personal == "" || (lat == 0.0 && lon == 0.0)) return;

  String idsRestantes = chat_id_personal;

  while (idsRestantes.length() > 0) {
    int comaIdx = idsRestantes.indexOf(',');
    String currentId = "";
    if (comaIdx != -1) {
      currentId = idsRestantes.substring(0, comaIdx);
      idsRestantes = idsRestantes.substring(comaIdx + 1);
    } else {
      currentId = idsRestantes;
      idsRestantes = "";
    }
    currentId.trim();
    if (currentId.length() == 0) continue;

    WiFiClientSecure client;
    client.setInsecure();
    client.setTimeout(6000);

    HTTPClient http;
    http.setTimeout(6000);
    String url = "https://api.telegram.org/bot" + bot_token + "/sendLocation";

    if (http.begin(client, url)) {
      http.addHeader("Content-Type", "application/json");
      String payload = "{\"chat_id\":\"" + currentId + "\",\"latitude\":" + String(lat, 6) + ",\"longitude\":" + String(lon, 6) + "}";
      int httpCodigo = http.POST(payload);
      if (httpCodigo == 200) {
        Serial.printf("[Telegram] Mapa entregado a %s con EXITO.\n", currentId.c_str());
      }
      http.end();
    }
    client.stop();
  }
}

String crearOrdenMercadoPago(int monto, const char* titulo, String extRef) {
  if (WiFi.status() != WL_CONNECTED || mp_token == "") {
    return "https://www.mercadopago.cl";
  }

  WiFiClientSecure client;
  client.setInsecure();
  client.setTimeout(8000);

  HTTPClient http;
  http.begin(client, "https://api.mercadopago.com/checkout/preferences");
  http.addHeader("Content-Type", "application/json");
  http.addHeader("Authorization", String("Bearer ") + mp_token);

  String jsonBody = "{\"items\":[{\"title\":\"" + String(titulo) + "\",\"quantity\":1,\"currency_id\":\"CLP\",\"unit_price\":" + String(monto) + "}],\"external_reference\":\"" + extRef + "\"}";

  int codigoRespuesta = http.POST(jsonBody);
  String linkPago = "";

  if (codigoRespuesta == 200 || codigoRespuesta == 201) {
    String respuesta = http.getString();
    int idx = respuesta.indexOf("\"init_point\":\"");
    if (idx != -1) {
      int ini = idx + 14;
      int fin = respuesta.indexOf("\"", ini);
      linkPago = respuesta.substring(ini, fin);
      linkPago.replace("\\/", "/");
      Serial.printf("[MP OK] Orden creada: %s\n", extRef.c_str());
    }
  } else {
    linkPago = "https://www.mercadopago.cl";
  }

  http.end();
  client.stop();
  return linkPago;
}

int verificarEstadoPago(String extRef) {
  if (WiFi.status() != WL_CONNECTED || extRef == "" || mp_token == "") return 0;

  WiFiClientSecure client;
  client.setInsecure();
  client.setTimeout(4000);

  HTTPClient http;
  String urlConsulta = "https://api.mercadopago.com/v1/payments/search?external_reference=" + extRef;
  http.begin(client, urlConsulta);
  http.addHeader("Authorization", String("Bearer ") + mp_token);

  int codigo = http.GET();
  int resultadoPago = 0; // 0: Pendiente

  if (codigo == 200) {
    String resp = http.getString();
    Serial.println("[MP Search Resp]: " + resp);
    if (resp.indexOf("\"status\":\"approved\"") != -1) {
      resultadoPago = 1; // APROBADO
      Serial.println("\n>>> ¡PAGO DIGITAL APROBADO EN MERCADO PAGO! <<<");
    } 
    else if (resp.indexOf("\"status\":\"rejected\"") != -1 || resp.indexOf("\"status\":\"cancelled\"") != -1) {
      resultadoPago = 2; // RECHAZADO O CANCELADO
      Serial.println("\n>>> ¡PAGO RECHAZADO O CANCELADO EN LA APP! <<<");
    } else {
      Serial.print(".");
    }
  } else {
    Serial.printf("[MP Error] HTTP Code: %d\n", codigo);
  }

  http.end();
  client.stop();
  return resultadoPago;
}

// ==========================================================
// 8. CIERRE DE CAJA ADMINISTRATIVO
// ==========================================================
void ejecutarCierreDeCaja() {
  long totalRecaudado = cajaMercadoPago;

  gfx->fillScreen(0x0000);
  gfx->fillRoundRect(15, 60, 290, 340, 16, 0x0273);
  gfx->drawRoundRect(15, 60, 290, 340, 16, 0x07E0);

  gfx->setTextColor(0xFFFF);
  gfx->setTextSize(3);
  gfx->setCursor(45, 95);
  gfx->println("CIERRE DE");
  gfx->setCursor(95, 130);
  gfx->println("CAJA");

  gfx->drawFastHLine(35, 175, 250, 0x07E0);

  gfx->setTextColor(0x07FF);
  gfx->setTextSize(2);
  gfx->setCursor(40, 205);
  gfx->println("ENVIANDO DATOS");

  gfx->setTextColor(0xFFFF);
  gfx->setTextSize(1);
  gfx->setCursor(40, 240);
  gfx->println("Conectando con Telegram...");
  gfx->flush();

  String redActual = WiFi.SSID();
  if (redActual == "") redActual = wifi_ssid;

  obtenerUbicacionPorIP();
  String horaCierre = obtenerFechaHoraActual();
  String linkMaps = "https://maps.google.com/?q=" + String(geoLat, 6) + "," + String(geoLon, 6);

  String mensajeCierre = "📋 CIERRE DE CAJA - " + machine_name + "\n"
                         "🕒 Fecha/Hora: " + horaCierre + "\n"
                         "📶 Wi-Fi: " + redActual + "\n"
                         "📍 Ciudad (IP): " + geoCiudad + " (" + geoISP + ")\n"
                         "🗺️ Ver Mapa: " + linkMaps + "\n"
                         "------------------------------------\n"
                         "💳 Mercado Pago: $" + String(cajaMercadoPago) + " CLP\n"
                         "💰 TOTAL RECAUDADO: $" + String(totalRecaudado) + " CLP\n"
                         "🕹️ Partidas despachadas: " + String(totalJugadas) + "\n"
                         "------------------------------------\n"
                         "✅ Caja reiniciada a $0 CLP para nueva jornada.";

  bool enviadoConExito = enviarMensajeTelegram(mensajeCierre);

  if (enviadoConExito) {
    if (geoDisponible) {
      enviarUbicacionTelegram(geoLat, geoLon);
    }
    cajaMercadoPago = 0;
    totalJugadas    = 0;
    totalPremios    = 0;
    guardarContadoresFlash();

    gfx->fillRect(30, 195, 260, 180, 0x0273);
    gfx->setTextColor(0x07E0);
    gfx->setTextSize(2);
    gfx->setCursor(65, 215);
    gfx->println("ENTREGADO OK");

    gfx->setTextColor(0xFFFF);
    gfx->setTextSize(1);
    gfx->setCursor(55, 265);
    gfx->println("Reporte recibido en Telegram");
    gfx->setCursor(50, 285);
    gfx->println("Datos respaldados con exito");

    gfx->setTextColor(0xFFE0);
    gfx->setTextSize(2);
    gfx->setCursor(35, 335);
    gfx->println("SISTEMA EN CERO");
    gfx->flush();
  } else {
    gfx->fillRect(30, 195, 260, 180, 0x0273);
    gfx->setTextColor(0xF800);
    gfx->setTextSize(2);
    gfx->setCursor(55, 215);
    gfx->println("ERROR DE ENVIO");

    gfx->setTextColor(0xFFFF);
    gfx->setTextSize(1);
    gfx->setCursor(45, 260);
    gfx->println("No se pudo conectar a Telegram");
    gfx->setCursor(45, 280);
    gfx->println("Verifica Wi-Fi o ID de chat");

    gfx->setTextColor(0x07FF);
    gfx->setTextSize(2);
    gfx->setCursor(35, 335);
    gfx->println("CAJA PRESERVADA");
    gfx->flush();
  }

  delay(4000);
  dibujarMenuPrincipal();
}

// ==========================================================
// 9. INTERFAZ GRÁFICA (UI) CON EFECTO INTERACTIVO
// ==========================================================
void dibujarBotonMenu(int y, uint16_t colFondo, uint16_t colBorde, const char* txtPrecio, const char* txtJugadas) {
  gfx->fillRoundRect(15, y, 290, 46, 10, colFondo);
  gfx->drawRoundRect(15, y, 290, 46, 10, colBorde);

  gfx->setTextColor(0xFFFF);
  gfx->setTextSize(2);
  gfx->setCursor(30, y + 15);
  gfx->print(txtPrecio);

  gfx->setTextColor(0xFFE0);
  gfx->setCursor(165, y + 15);
  gfx->print(txtJugadas);
}

void dibujarMenuPrincipal() {
  estadoActual = ESTADO_MENU;
  tiempoInicioToqueLogo = 0;
  tocandoLogo = false;
  tiempoInicioToqueSetup = 0;
  tocandoSetup = false;

  gfx->fillScreen(0x0841);

  // Encabezado
  gfx->fillRect(0, 0, 320, 42, 0xF940);
  gfx->drawFastHLine(0, 42, 320, 0xFFFF);

  gfx->setTextColor(0xFFFF);
  gfx->setTextSize(3);
  gfx->setCursor(97, 10);
  gfx->print("VENDI-Q");

  gfx->setTextSize(2);
  gfx->setTextColor(0x07FF);
  gfx->setCursor(35, 50);
  gfx->println("ELIGE TUS JUGADAS");

  // 6 Opciones tarifarias
  dibujarBotonMenu(74,  0x1A25, 0x07E0, "$500",   "1 JUEGO");
  dibujarBotonMenu(130, 0x1A25, 0x07E0, "$1.000",  "2 JUEGOS");
  dibujarBotonMenu(186, 0x0273, 0x051F, "$2.000",  "4 JUEGOS");
  dibujarBotonMenu(242, 0x8000, 0xF800, "$5.000",  "10 JUEGOS");
  dibujarBotonMenu(298, 0x8A00, 0xFD20, "$10.000", "20 JUEGOS");
  dibujarBotonMenu(354, 0x4809, 0xF81F, "$20.000", "40 JUEGOS");

  // Pie con textos ampliados para medios de pago
  gfx->fillRect(0, 406, 320, 74, 0x0000);
  gfx->drawFastHLine(0, 406, 320, 0x07E0);

  gfx->setTextSize(2);
  gfx->setTextColor(0xFFFF);
  gfx->setCursor(70, 412);
  gfx->println("TOCA PARA PAGAR");

  gfx->setTextColor(0x07FF);
  gfx->setCursor(46, 436);
  gfx->println("CUENTA RUT Y DEBITO");
  gfx->setCursor(46, 458);
  gfx->println("TARJETAS DE CREDITO");

  gfx->flush();
}

void dibujarPantallaQR() {
  estadoActual = ESTADO_QR;
  tiempoInicioQR = millis();
  gfx->fillScreen(0x0841);

  gfx->fillRect(0, 0, 320, 42, 0xF940);
  gfx->setTextColor(0xFFFF);
  gfx->setTextSize(2);
  gfx->setCursor(30, 13);
  gfx->println("PAGO CON CODIGO QR");

  gfx->setTextSize(2);
  gfx->setTextColor(0xFFE0);
  gfx->setCursor(20, 52);
  gfx->printf("Total: $%d CLP", montoActual);

  gfx->setTextSize(1);
  gfx->setTextColor(0x07FF);
  gfx->setCursor(20, 74);
  gfx->printf("Recibes: %d Jugadas (%d Creditos)", jugadasActuales, pulsosActuales);

  dibujarCodigoQR(qrUrlActual.c_str());

  gfx->setTextSize(1);
  gfx->setTextColor(0xFFFF);
  gfx->setCursor(38, 370);
  gfx->println("Escanea con la camara de tu celular");
  gfx->setTextColor(0x07E0);
  gfx->setCursor(55, 386);
  gfx->println("Cualquier banco o Mercado Pago");

  gfx->fillRoundRect(20, 415, 280, 48, 12, 0x9000);
  gfx->drawRoundRect(20, 415, 280, 48, 12, 0xFFFF);
  gfx->setTextColor(0xFFFF);
  gfx->setTextSize(2);
  gfx->setCursor(45, 431);
  gfx->println("<< VOLVER AL MENU");

  gfx->flush();
}

void procesarPagoExitoso(int monto, int jugadas, int pulsos, bool esDigital) {
  estadoActual = ESTADO_EXITO;

  cajaMercadoPago += monto;
  totalJugadas += jugadas;
  guardarContadoresFlash();

  gfx->fillScreen(0x07E0);
  gfx->setTextColor(0x0000);
  gfx->setTextSize(3);
  gfx->setCursor(30, 90);
  gfx->println("PAGO EXITOSO!");

  gfx->setTextSize(2);
  gfx->setCursor(40, 150);
  gfx->println("GRACIAS POR JUGAR");

  gfx->setTextColor(0x001F);
  gfx->setTextSize(3);
  gfx->setCursor(20, 210);
  gfx->printf("CARGANDO %d...", jugadas);

  gfx->setTextSize(2);
  gfx->setTextColor(0x0000);
  gfx->setCursor(40, 290);
  gfx->println("Buena suerte atrapando");
  gfx->setCursor(75, 315);
  gfx->println("tu peluche!");

  gfx->flush();

  String metodo = "💳 Mercado Pago QR";
  String horaPago = obtenerFechaHoraActual();

  String mensaje = "🕹️ " + machine_name + "\n"
                   "🕒 " + horaPago + "\n"
                   "Metodo: " + metodo + "\n"
                   "💰 Monto: $" + String(monto) + " CLP\n"
                   "🎟️ Entregados: " + String(jugadas) + " juegos (" + String(pulsos) + " creditos)\n"
                   "--------------------------\n"
                   "💳 Acumulado MP: $" + String(cajaMercadoPago) + " CLP\n"
                   "💰 Caja Total: $" + String(cajaMercadoPago) + " CLP\n"
                   "🕹️ Total jugadas: " + String(totalJugadas);
  enviarMensajeTelegram(mensaje);

  entregarPulsosRele(pulsos);

  delay(2500);
  dibujarMenuPrincipal();
}

void procesarPagoRechazado() {
  estadoActual = ESTADO_RECHAZADO;

  gfx->fillScreen(0xF800); // Rojo brillante (RGB565)
  gfx->setTextColor(0xFFFF);
  gfx->setTextSize(3);
  gfx->setCursor(20, 90);
  gfx->println("PAGO RECHAZADO");

  gfx->setTextSize(2);
  gfx->setCursor(35, 150);
  gfx->println("SIN SALDO O CANCELADO");

  gfx->setTextColor(0xFFE0);
  gfx->setTextSize(2);
  gfx->setCursor(40, 220);
  gfx->println("Intenta con otra");
  gfx->setCursor(65, 250);
  gfx->println("tarjeta o banco");

  gfx->flush();

  delay(3500);
  dibujarMenuPrincipal();
}

// ==========================================================
// 10. DESPACHO DE PULSOS AL RELÉ
// ==========================================================
void entregarPulsosRele(int pulsos) {
  Serial.printf("\n[RELE] Despachando %d pulsos a la maquina...\n", pulsos);
  for (int i = 1; i <= pulsos; i++) {
    digitalWrite(PIN_RELE, HIGH);
    delay(PULSO_ON_MS);
    digitalWrite(PIN_RELE, LOW);
    delay(PULSO_OFF_MS);
    Serial.printf(" Pulso #%d enviado.\n", i);
  }
  Serial.println("[RELE] Creditos entregados con exito.\n");
}

// ==========================================================
// 11. CONFIGURACIÓN INICIAL (SETUP)
// ==========================================================
void setup() {
  Serial.begin(115200);
  delay(500);

  pinMode(PIN_RELE, OUTPUT);
  digitalWrite(PIN_RELE, LOW);

  pinMode(PIN_LCD_BL, OUTPUT);
  digitalWrite(PIN_LCD_BL, HIGH);

  gfx->begin();
  inicializarTouch();

  cargarParametrosMemoria();

  if (wifi_ssid == "") {
    Serial.println("[VENDI-Q] Sin Wi-Fi configurado. Iniciando Setup...");
    iniciarModoSetup();
  } else {
    Serial.print("[VENDI-Q] Conectando a Wi-Fi: [");
    Serial.print(wifi_ssid);
    Serial.println("]");

    // Limpieza de caché previa para evitar conflictos de credenciales
    WiFi.persistent(false);
    WiFi.disconnect(true, true);
    delay(500);

    WiFi.mode(WIFI_STA);
    WiFi.begin(wifi_ssid.c_str(), wifi_pass.c_str());

    int intentos = 0;
    // Ampliado a 40 intentos (20 segundos) para darle margen al router
    while (WiFi.status() != WL_CONNECTED && intentos < 40) {
      delay(500);
      Serial.print(".");
      intentos++;
    }

    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("\n[Wi-Fi] ¡Conectado exitosamente!");
      Serial.print("Dirección IP: ");
      Serial.println(WiFi.localIP());
      
      dibujarMenuPrincipal();

      configTime(-3 * 3600, 0, "pool.ntp.org", "time.google.com");
      obtenerUbicacionPorIP();

      String linkMaps = "https://maps.google.com/?q=" + String(geoLat, 6) + "," + String(geoLon, 6);
      long totalCajaInicial = cajaMercadoPago;
      
      String mensajeArranque = "🚀 " + machine_name + ": En linea y operativa.\n"
                            "🕒 " + obtenerFechaHoraActual() + "\n"
                            "📍 Ciudad (IP): " + geoCiudad + " (" + geoISP + ")\n"
                            "🗺️ Ver Mapa: " + linkMaps + "\n"
                            "📶 Red: " + String(WiFi.SSID()) + "\n"
                            "💰 Caja acumulada: $" + String(totalCajaInicial) + " CLP";
      enviarMensajeTelegram(mensajeArranque);

      if (geoDisponible) {
        enviarUbicacionTelegram(geoLat, geoLon);
      }
      
      enviarLatidoHeartbeat();
      ultimoPingHeartbeat = millis();
    } else {
      Serial.println("\n[Wi-Fi] No conecta. Abriendo red Setup...");
      iniciarModoSetup();
    }
  }
}

// ==========================================================
// 12. BUCLE PRINCIPAL (LOOP)
// ==========================================================
void loop() {
  if (modo_setup) {
    dnsServer.processNextRequest();
    server.handleClient();

    if (solicitudReinicioPendiente && (millis() - tiempoSolicitudReinicio > 1500)) {
      Serial.println("[Setup] Reiniciando placa para aplicar cambios...");
      delay(200);
      ESP.restart();
    }

    delay(5);
    return;
  }

  if (millis() - ultimoCheckWiFi > 15000) {
    ultimoCheckWiFi = millis();
    verificarConexionWiFi();
  }

  if (millis() - ultimoPingHeartbeat >= INTERVALO_PING) {
    ultimoPingHeartbeat = millis();
    if (estadoActual == ESTADO_MENU) {
      enviarLatidoHeartbeat();
    }
  }

  // Lectura Táctil
  uint16_t touchX = 0, touchY = 0;
  bool tocado = leerTouch(touchX, touchY);

  if (estadoActual == ESTADO_MENU) {
    // Cierre de caja en Logo VENDI-Q (7 segs con tolerancia)
    static unsigned long ultimoToqueLogoValido = 0;

    if (tocado && touchX >= 10 && touchX <= 310 && touchY >= 0 && touchY <= 45) {
      if (!tocandoLogo) {
        tocandoLogo = true;
        tiempoInicioToqueLogo = millis();
      }
      ultimoToqueLogoValido = millis();

      unsigned long duracion = millis() - tiempoInicioToqueLogo;
      int progresoAncho = map(constrain(duracion, 0, 7000), 0, 7000, 0, 320);
      gfx->fillRect(0, 38, progresoAncho, 4, 0x07E0);
      gfx->flush();

      if (duracion >= 7000) {
        tocandoLogo = false;
        ejecutarCierreDeCaja();
      }
      return;
    } else {
      if (tocandoLogo && (millis() - ultimoToqueLogoValido > 250)) {
        tocandoLogo = false;
        tiempoInicioToqueLogo = 0;
        gfx->fillRect(0, 38, 320, 4, 0xF940);
        gfx->flush();
      }
    }

    // Modo Setup en el Pie (5 segs)
    if (tocado && touchX >= 10 && touchX <= 310 && touchY >= 445 && touchY <= 480) {
      if (!tocandoSetup) {
        tocandoSetup = true;
        tiempoInicioToqueSetup = millis();
      }

      unsigned long duracionSetup = millis() - tiempoInicioToqueSetup;
      int progresoSetup = map(constrain(duracionSetup, 0, 5000), 0, 5000, 0, 320);
      gfx->fillRect(0, 476, progresoSetup, 4, 0x07FF);
      gfx->flush();

      if (duracionSetup >= 5000) {
        iniciarModoSetup();
      }
      return;
    } else {
      if (tocandoSetup) {
        tocandoSetup = false;
        tiempoInicioToqueSetup = 0;
        gfx->fillRect(0, 476, 320, 4, 0x0000);
        gfx->flush();
      }
    }

    // Opciones tarifarias con respuesta visual interactiva y texto "GENERANDO TU QR"
    if (tocado) {
      int yBotonSeleccionado = -1;
      if (touchY >= 74 && touchY < 125) {
        montoActual = 500;   jugadasActuales = 1;  pulsosActuales = 5; yBotonSeleccionado = 74;
      } else if (touchY >= 125 && touchY < 181) {
        montoActual = 1000;  jugadasActuales = 2;  pulsosActuales = 10; yBotonSeleccionado = 130;
      } else if (touchY >= 181 && touchY < 237) {
        montoActual = 2000;  jugadasActuales = 4;  pulsosActuales = 20; yBotonSeleccionado = 186;
      } else if (touchY >= 237 && touchY < 293) {
        montoActual = 5000;  jugadasActuales = 10; pulsosActuales = 50; yBotonSeleccionado = 242;
      } else if (touchY >= 293 && touchY < 349) {
        montoActual = 10000; jugadasActuales = 20; pulsosActuales = 100; yBotonSeleccionado = 298;
      } else if (touchY >= 349 && touchY <= 405) {
        montoActual = 20000; jugadasActuales = 40; pulsosActuales = 200; yBotonSeleccionado = 354;
      } else {
        return;
      }

      if (yBotonSeleccionado != -1) {
        // Dibuja el botón en Cyan y escribe "GENERANDO TU QR"
        gfx->fillRoundRect(15, yBotonSeleccionado, 290, 46, 10, 0x07FF);
        gfx->drawRoundRect(15, yBotonSeleccionado, 290, 46, 10, 0xFFFF);
        gfx->setTextColor(0x0000);
        gfx->setTextSize(2);
        gfx->setCursor(52, yBotonSeleccionado + 15);
        gfx->print("GENERANDO TU QR");
        gfx->flush();
      }

      // Limpia los espacios del nombre de la máquina para evitar el Error 400 en la URL de Mercado Pago
      String machineClean = machine_name;
      machineClean.replace(" ", "_");

      externalRefActual = machineClean + "_" + String(montoActual) + "_" + String(millis());
      String titulo = machine_name + " " + String(jugadasActuales) + " Juegos";

      qrUrlActual = crearOrdenMercadoPago(montoActual, titulo.c_str(), externalRefActual);
      dibujarPantallaQR();
      delay(300);
    }
  } 
  else if (estadoActual == ESTADO_QR) {
    if (tocado && touchY >= 410 && touchY <= 470) {
      dibujarMenuPrincipal();
      delay(300);
    }
  }

  if (estadoActual == ESTADO_QR) {
    if (millis() - ultimoCheckMP > 2000) {
      ultimoCheckMP = millis();
      int estadoPago = verificarEstadoPago(externalRefActual);
      
      if (estadoPago == 1) {
        procesarPagoExitoso(montoActual, jugadasActuales, pulsosActuales, true);
      } 
      else if (estadoPago == 2) {
        procesarPagoRechazado();
      }
    }

    if (millis() - tiempoInicioQR > ((unsigned long)TIMEOUT_QR_SEG * 1000)) {
      dibujarMenuPrincipal();
    }
  }

  delay(20);
}
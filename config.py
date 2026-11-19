"""Konfigurasi terpusat untuk gateway Raspberry Pi.

Nilai sensitif (broker, UUID) dibaca dari environment variable.
Buat file .env di root proyek berdasarkan .env.example, lalu isi nilainya.

Nilai non-sensitif (pin GPIO, tinggi tangki, dll.) tetap hardcode di sini
karena terikat langsung ke hardware dan tidak berubah antar deployment.
"""

import os

from dotenv import load_dotenv

# Muat .env jika ada (development / Raspberry Pi dengan file .env)
# Jika env var sudah di-set dari luar (misal systemd EnvironmentFile),
# load_dotenv tidak akan menimpa nilai yang sudah ada.
load_dotenv()


def _wajib(key: str) -> str:
    """Ambil env var; raise RuntimeError jika tidak ditemukan."""
    nilai = os.getenv(key)
    if not nilai:
        raise RuntimeError(
            f"Environment variable '{key}' belum di-set. "
            f"Salin .env.example menjadi .env lalu isi nilainya."
        )
    return nilai


# =============================================================================
# MQTT  —  nilai sensitif, dari .env
# =============================================================================

MQTT_BROKER   = _wajib("MQTT_BROKER")
MQTT_PORT     = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER     = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")

# =============================================================================
# BACKEND SYNC API — Dynamic Provisioning
# =============================================================================

BACKEND_API_URL  = os.getenv("BACKEND_API_URL", "https://ubuntu-luis.tail7e12bf.ts.net/api")
GATEWAY_CODE     = os.getenv("GATEWAY_CODE", "GW-HUB-01")
GATEWAY_SYNC_KEY = os.getenv("GATEWAY_SYNC_KEY", "secret_gateway_rsa_ugm_2026")


# =============================================================================
# TANGKI  —  terikat hardware, hardcode
# =============================================================================

TANK_HEIGHT_CM       = 100   # tinggi fisik tangki (cm)
TANK_CAPACITY_LITERS = 200   # kapasitas penuh tangki (liter)


# =============================================================================
# LoRa E220-900T22D  —  terikat hardware, hardcode
# =============================================================================

# Port serial penerima:
# - "/dev/serial0" : jika modul LoRa E220 terhubung langsung ke pin GPIO Raspberry Pi (UART0).
# - "/dev/ttyUSB0" atau "/dev/ttyACM0" : jika menggunakan STM32 RX Hub via kabel USB.
LORA_SERIAL_PORT = os.getenv("LORA_SERIAL_PORT", "/dev/serial0")
LORA_BAUD        = int(os.getenv("LORA_BAUD", "9600"))

# Register E220 — 8 byte: ADDH ADDL REG0 REG1 REG2 REG3 CRYPT_H CRYPT_L
# Sesuai RF Setting Tool EBYTE (gambar konfigurasi lokal):
# Parameter: 0xc0 0x00 0x08 0x01 0x03 0x62 0x62 0x19 0x88 0x00 0x00
#
#   ADDH 0x01, ADDL 0x03 → Address = 259 (0x0103)
#   REG0 0x62             → UART 9600 bps, 8N1, Air rate 2.4 kbps
#   REG1 0x62             → Sub-packet 128 bytes, RSSI ambient noise, Power 13 dBm
#   REG2 0x19             → Channel 25 (0x19) -> 435.125 MHz (atau 850.125 + 25 = 875.125 MHz)
#   REG3 0x88             → Enable Packet RSSI Byte (bit 7), Normal Transparent Mode (bit 6=0), WOR 500ms
#   CRYPT_H 0x00, CRYPT_L 0x00 → Key = 0
LORA_CFG = bytes([0x01, 0x03, 0x62, 0x62, 0x19, 0x88, 0x00, 0x00])

# GPIO BCM numbering
LORA_PIN_M0  = 23
LORA_PIN_M1  = 24
LORA_PIN_AUX = 25

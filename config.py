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

MQTT_BROKER = _wajib("MQTT_BROKER")
MQTT_PORT   = int(os.getenv("MQTT_PORT", "1883"))

TANK_ID        = _wajib("TANK_ID")
SENSOR_NODE_ID = _wajib("SENSOR_NODE_ID")

MQTT_TOPIC = f"hospital/{TANK_ID}/level"


# =============================================================================
# TANGKI  —  terikat hardware, hardcode
# =============================================================================

TANK_HEIGHT_CM       = 100   # tinggi fisik tangki (cm)
TANK_CAPACITY_LITERS = 200   # kapasitas penuh tangki (liter)


# =============================================================================
# LoRa E220-900T22D  —  terikat hardware, hardcode
# =============================================================================

LORA_SERIAL_PORT = "/dev/serial0"   # UART0 Raspberry Pi
LORA_BAUD        = 9600

# Register E220 — 6 byte: ADDH ADDL REG0 REG1 REG2 REG3
# Harus sama persis dengan konfigurasi STM32 (pengirim)!
#
#   ADDH 0x00, ADDL 0x00 → alamat modul 0x0000
#   REG0 0x62             → UART 9600 bps, 8N1, air rate 2.4 kbps
#   REG1 0x03             → TX power 10 dBm
#                           (sengaja diturunkan: antena 433 MHz dipakai untuk
#                            uji coba pada modul 900 MHz — kembalikan ke 0x00
#                            = 22 dBm setelah antena 915 MHz terpasang)
#   REG2 0x48             → channel 72 → 850.125 + 72 = 922.125 MHz
#   REG3 0x03             → mode transparan, LBT OFF
LORA_CFG = bytes([0x00, 0x00, 0x62, 0x03, 0x48, 0x03])

# GPIO BCM numbering
LORA_PIN_M0  = 23
LORA_PIN_M1  = 24
LORA_PIN_AUX = 25

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

LORA_SERIAL_PORT = "/dev/serial0"   # UART0 Raspberry Pi
LORA_BAUD        = 9600

# Register E220 — 6 byte: ADDH ADDL REG0 REG1 REG2 REG3
# Harus sama persis dengan konfigurasi STM32 (pengirim)!
#
#   ADDH 0x00, ADDL 0x00 → alamat modul 0x0000
#   REG0 0x62             → UART 9600 bps, 8N1, air rate 2.4 kbps
#   REG1 0x00             → TX power 22 dBm (maksimal, sudah aman dengan antena 915 MHz)
#                           [0x00 = 22 dBm, 0x01 = 17 dBm, 0x02 = 13 dBm, 0x03 = 10 dBm]
#   REG2: Channel frekuensi (Frekuensi = 850.125 MHz + Channel * 1 MHz)
#         - 0x41 (CH 65) → 850.125 + 65 = 915.125 MHz (Center 915 MHz)
#         - 0x48 (CH 72) → 850.125 + 72 = 922.125 MHz (Standar AS923 / Regulasi ISM Indonesia)
#   REG3 0x03             → mode transparan, LBT OFF
#
# Default diset ke 0x41 (915.125 MHz) sesuai antena 915 MHz. Jika node STM32 memakai 922.125 MHz, ganti byte ke-5 menjadi 0x48.
LORA_CFG = bytes([0x00, 0x00, 0x62, 0x00, 0x41, 0x03])

# GPIO BCM numbering
LORA_PIN_M0  = 23
LORA_PIN_M1  = 24
LORA_PIN_AUX = 25

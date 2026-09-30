"""Konfigurasi terpusat untuk gateway Raspberry Pi.

Ubah nilai di sini sesuai kebutuhan deployment — tidak perlu menyentuh
file logika lainnya.
"""

# =============================================================================
# MQTT
# =============================================================================

MQTT_BROKER = "100.94.192.102"
MQTT_PORT   = 1883

TANK_ID        = "a6f5ade5-777c-4871-a584-de40d11df30d"
SENSOR_NODE_ID = "6b464034-79f0-46fe-a7e4-7bd3b7fa9c8a"

MQTT_TOPIC = f"hospital/{TANK_ID}/level"


# =============================================================================
# TANGKI
# =============================================================================

TANK_HEIGHT_CM       = 100   # tinggi fisik tangki (cm)
TANK_CAPACITY_LITERS = 200   # kapasitas penuh tangki (liter)


# =============================================================================
# LoRa E220-900T22D
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

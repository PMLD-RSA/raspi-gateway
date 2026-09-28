#!/usr/bin/env python3
"""Gateway Raspberry Pi: terima data jarak dari STM32 via LoRa E220, kirim ke MQTT broker.

Modul LoRa : Ebyte E220-900T22D (915 MHz, 22 dBm)
Format data : "JARAK,<cm>,<nomor_urut>\r\n"   (dikirim STM32 via LoRa)

Wiring (nomor = pin fisik header 40-pin Raspberry Pi):
  E220 VCC -> pin  2 (5V)          E220 GND -> pin  6 (GND)
  E220 TXD -> pin 10 (GPIO15 RXD)  E220 RXD -> pin  8 (GPIO14 TXD)
  E220 M0  -> pin 16 (GPIO23)      E220 M1  -> pin 18 (GPIO24)
  E220 AUX -> pin 22 (GPIO25)

Persiapan sekali saja:
  sudo raspi-config -> Interface Options -> Serial Port
      "login shell over serial?" -> No,  "serial port hardware?" -> Yes  -> reboot
  pip install pyserial gpiozero paho-mqtt
"""

import json
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
import serial
from gpiozero import DigitalInputDevice, DigitalOutputDevice


# =============================================================================
# KONFIGURASI MQTT
# =============================================================================

MQTT_BROKER = "100.94.192.102"
MQTT_PORT   = 1883

TANK_ID         = "a6f5ade5-777c-4871-a584-de40d11df30d"
SENSOR_NODE_ID  = "6b464034-79f0-46fe-a7e4-7bd3b7fa9c8a"

TANK_HEIGHT_CM       = 100   # tinggi fisik tangki (cm)
TANK_CAPACITY_LITERS = 200   # kapasitas penuh tangki (liter)

MQTT_TOPIC = f"hospital/{TANK_ID}/level"


# =============================================================================
# KONFIGURASI LoRa E220
# =============================================================================

PORT = "/dev/serial0"   # UART0 Raspberry Pi

# Register E220 — 6 byte (ADDH ADDL REG0 REG1 REG2 REG3)
# Harus sama persis dengan LORA_CFG di src/main.cpp (STM32 / pengirim)!
#
#   ADDH 0x00, ADDL 0x00 → alamat modul 0x0000
#   REG0 0x62 → UART 9600 bps, 8N1, air rate 2.4 kbps
#   REG1 0x03 → sub-packet 200B, TX power 10 dBm
#               (sengaja diturunkan karena antena 433 MHz dipakai untuk uji coba
#                pada modul 900 MHz — kembalikan ke 0x00 = 22 dBm setelah
#                antena 915 MHz terpasang)
#   REG2 0x48 → channel 72 → 850.125 + 72 = 922.125 MHz
#   REG3 0x03 → mode transparan, LBT OFF
LORA_CFG = bytes([0x00, 0x00, 0x62, 0x03, 0x48, 0x03])

# GPIO BCM numbering
PIN_M0  = 23
PIN_M1  = 24
PIN_AUX = 25

m0  = DigitalOutputDevice(PIN_M0)
m1  = DigitalOutputDevice(PIN_M1)
aux = DigitalInputDevice(PIN_AUX, pull_up=None, active_state=True)


# =============================================================================
# FUNGSI LoRa — MODE & KONFIGURASI
# =============================================================================

def tunggu_aux(timeout: float = 2.0) -> bool:
    """AUX LOW = modul sibuk. Tunggu sampai HIGH (idle)."""
    t0 = time.monotonic()
    while not aux.value:
        if time.monotonic() - t0 > timeout:
            print("[LoRa] PERINGATAN: AUX timeout")
            return False
        time.sleep(0.001)
    time.sleep(0.002)   # settling time minimal setelah AUX HIGH
    return True


def set_mode(nilai_m0: int, nilai_m1: int):
    """Ganti mode E220. Harus tunggu AUX sebelum dan sesudah ganti pin."""
    tunggu_aux()
    m0.value = nilai_m0
    m1.value = nilai_m1
    time.sleep(0.002)
    tunggu_aux()


def konfigurasi_lora(ser: serial.Serial) -> bool:
    """Baca register E220, tulis permanen (C0) hanya kalau berbeda.

    Mengembalikan True jika modul merespons dengan benar.
    """
    n = len(LORA_CFG)

    # Mode konfigurasi: M0=1 M1=1, UART wajib 9600 8N1
    set_mode(1, 1)
    ser.reset_input_buffer()

    # Perintah baca register: C1 ADDR LEN
    ser.write(bytes([0xC1, 0x00, n]))
    resp = ser.read(3 + n)

    if len(resp) != 3 + n or resp[0] != 0xC1:
        print(f"[LoRa] Gagal baca register (resp={resp.hex()})")
        set_mode(0, 0)
        return False

    register_terbaca = resp[3:]
    print(f"[LoRa] Register terbaca  : {register_terbaca.hex()}")
    print(f"[LoRa] Target konfigurasi: {LORA_CFG.hex()}")

    if register_terbaca != LORA_CFG:
        print("[LoRa] Konfigurasi berbeda, menulis ulang...")
        # Modul balas FF FF FF kalau tulis dikirim langsung setelah baca
        time.sleep(0.05)
        tunggu_aux()
        # Perintah tulis permanen: C0 ADDR LEN + DATA
        ser.write(bytes([0xC0, 0x00, n]) + LORA_CFG)
        resp = ser.read(3 + n)
        if len(resp) == 3 + n and resp[0] == 0xC1:
            print("[LoRa] Konfigurasi berhasil ditulis.")
        else:
            print(f"[LoRa] Gagal tulis konfigurasi (resp={resp.hex()})")
            set_mode(0, 0)
            return False
    else:
        print("[LoRa] Konfigurasi sudah sesuai, tidak perlu menulis ulang.")

    # Kembali ke mode normal: M0=0 M1=0
    set_mode(0, 0)
    return True


# =============================================================================
# MQTT
# =============================================================================

try:
    mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)  # paho-mqtt 2.x
except AttributeError:
    mqtt_client = mqtt.Client()  # paho-mqtt 1.x (mis. dari apt)


# Signature dibuat cocok untuk paho-mqtt 1.x maupun 2.x (callback API v2)
def _on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("[MQTT] Terhubung ke broker.")
    else:
        print(f"[MQTT] Gagal terhubung, kode: {rc}")


def _on_disconnect(client, userdata, *args):
    print("[MQTT] Terputus dari broker, loop_start() akan menyambung ulang otomatis.")


def connect_mqtt():
    mqtt_client.on_connect    = _on_connect
    mqtt_client.on_disconnect = _on_disconnect
    print(f"[MQTT] Menghubungi {MQTT_BROKER}:{MQTT_PORT} ...")
    # connect_async: tidak crash kalau broker belum bisa dijangkau saat start
    mqtt_client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=60)
    mqtt_client.loop_start()   # background thread → reconnect otomatis
    time.sleep(1.0)            # beri waktu handshake selesai


def publish_payload(payload: dict):
    """Kirim payload JSON ke MQTT. Reconnect ditangani loop_start()."""
    message = json.dumps(payload)
    result  = mqtt_client.publish(MQTT_TOPIC, message, qos=1)

    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        print(f"[MQTT] Terkirim → {message}")
    else:
        print(f"[MQTT] Gagal kirim (rc={result.rc}), broker belum terhubung")


# =============================================================================
# PROCESSING DATA SENSOR
# =============================================================================

def process_sensor_data(distance_cm: float, nomor_urut: int) -> dict:
    """Ubah jarak sensor → payload siap kirim ke backend.

    Sensor ultrasonik dipasang di atas tangki mengukur jarak ke permukaan air.
    Semakin kecil jarak → semakin penuh tangki.
    """
    water_height = TANK_HEIGHT_CM - distance_cm
    water_height = max(0.0, min(float(TANK_HEIGHT_CM), water_height))

    level_percent = (water_height / TANK_HEIGHT_CM) * 100
    volume_liters = (level_percent / 100) * TANK_CAPACITY_LITERS

    return {
        "tank_id":        TANK_ID,
        "sensor_node_id": SENSOR_NODE_ID,
        "level_percent":  round(level_percent, 2),
        "volume_liters":  round(volume_liters, 2),
        "distance_cm":    distance_cm,
        "sequence":       nomor_urut,
        "timestamp":      datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# MAIN
# =============================================================================

def main():
    # Inisialisasi MQTT
    connect_mqtt()

    # Inisialisasi LoRa & buka port serial
    with serial.Serial(PORT, 9600, timeout=1) as ser:
        print("[LoRa] Mengkonfigurasi modul E220...")
        if not konfigurasi_lora(ser):
            print("[LoRa] Modul tidak merespons. Periksa kabel dan pengaturan serial.")
            return

        print("[LoRa] Siap. Menunggu data dari STM32...\n")

        while True:
            try:
                raw_bytes = ser.readline()
                if not raw_bytes:
                    continue

                baris = raw_bytes.decode("ascii", errors="replace").strip()
                if not baris:
                    continue

                bagian = baris.split(",")

                # Format yang diharapkan dari STM32: "JARAK,<cm>,<nomor_urut>"
                if len(bagian) == 3 and bagian[0] == "JARAK":
                    try:
                        jarak_cm   = float(bagian[1])
                        nomor_urut = int(bagian[2])
                    except ValueError:
                        print(f"[LoRa] Format angka salah: {baris!r}")
                        continue

                    teks_jarak = (
                        "tidak ada pantulan" if jarak_cm == 0
                        else f"{jarak_cm:.1f} cm"
                    )
                    print(f"[{time.strftime('%H:%M:%S')}] Ukur #{nomor_urut}: {teks_jarak}")

                    # Kirim ke MQTT hanya jika data valid (jarak > 0)
                    if jarak_cm > 0:
                        payload = process_sensor_data(jarak_cm, nomor_urut)
                        publish_payload(payload)

                else:
                    print(f"[LoRa] Data tidak dikenal: {baris!r}")

            except KeyboardInterrupt:
                print("\n[Gateway] Dihentikan oleh pengguna.")
                break
            except serial.SerialException as e:
                print(f"[Serial] Error: {e}. Menunggu 3 detik...")
                time.sleep(3)

    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    print("[Gateway] Selesai.")


if __name__ == "__main__":
    main()
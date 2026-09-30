#!/usr/bin/env python3
"""Gateway Raspberry Pi — entrypoint utama.

Orkestrasi:
  1. Hubungkan ke MQTT broker (background thread, reconnect otomatis)
  2. Konfigurasi modul LoRa E220 via GPIO + UART
  3. Loop: terima frame dari STM32 → proses → publish ke MQTT

Struktur proyek:
  config.py              → semua konstanta konfigurasi
  lora/e220.py           → driver GPIO + UART modul E220
  mqtt_client/publisher.py → koneksi & publish ke MQTT broker
  sensor/processor.py    → parsing frame & kalkulasi payload

Persiapan sekali saja di Raspberry Pi:
  sudo raspi-config -> Interface Options -> Serial Port
      "login shell over serial?" -> No,  "serial port hardware?" -> Yes  -> reboot
  pip install pyserial gpiozero paho-mqtt
"""

import time

import serial

from lora.e220 import E220
from mqtt_client.publisher import MQTTPublisher
from sensor.processor import hitung_payload, parse_frame


def main() -> None:
    # ------------------------------------------------------------------
    # 1. MQTT
    # ------------------------------------------------------------------
    mqtt = MQTTPublisher()
    mqtt.connect()

    # ------------------------------------------------------------------
    # 2. LoRa E220 — konfigurasi & loop terima data
    # ------------------------------------------------------------------
    with E220() as lora:
        print("[LoRa] Mengkonfigurasi modul E220...")
        if not lora.konfigurasi():
            print("[LoRa] Modul tidak merespons. Periksa kabel dan pengaturan serial.")
            mqtt.disconnect()
            return

        print("[LoRa] Siap. Menunggu data dari STM32...\n")

        while True:
            try:
                baris = lora.baca_baris()
                if baris is None:
                    continue

                hasil = parse_frame(baris)

                if hasil is None:
                    print(f"[LoRa] Data tidak dikenal: {baris!r}")
                    continue

                jarak_cm, nomor_urut = hasil

                teks_jarak = (
                    "tidak ada pantulan" if jarak_cm == 0
                    else f"{jarak_cm:.1f} cm"
                )
                print(f"[{time.strftime('%H:%M:%S')}] Ukur #{nomor_urut}: {teks_jarak}")

                # Kirim ke MQTT hanya jika jarak valid (> 0)
                if jarak_cm > 0:
                    payload = hitung_payload(jarak_cm, nomor_urut)
                    mqtt.publish(payload)

            except KeyboardInterrupt:
                print("\n[Gateway] Dihentikan oleh pengguna.")
                break
            except serial.SerialException as e:
                print(f"[Serial] Error: {e}. Menunggu 3 detik...")
                time.sleep(3)

    # ------------------------------------------------------------------
    # 3. Cleanup
    # ------------------------------------------------------------------
    mqtt.disconnect()
    print("[Gateway] Selesai.")


if __name__ == "__main__":
    main()

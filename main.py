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

from config import (
    BACKEND_API_URL,
    GATEWAY_CODE,
    GATEWAY_SYNC_KEY,
    TANK_HEIGHT_CM,
)
from lora.e220 import E220
from mqtt_client.publisher import MQTTPublisher
from sensor.processor import hitung_payload, parse_frame
from sensor.syncer import GatewaySyncer


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Sync Konfigurasi Tangki dari Backend
    # ------------------------------------------------------------------
    syncer = GatewaySyncer(
        api_base_url=BACKEND_API_URL,
        gateway_code=GATEWAY_CODE,
        sync_key=GATEWAY_SYNC_KEY,
    )
    # Lakukan sinkronisasi (jika gagal, akan otomatis membaca cache lokal)
    syncer.fetch_sync()

    # ------------------------------------------------------------------
    # 2. MQTT Publisher (dengan Store-and-Forward SQLite buffer)
    # ------------------------------------------------------------------
    mqtt = MQTTPublisher()
    mqtt.connect()

    # ------------------------------------------------------------------
    # 3. LoRa E220 — konfigurasi & loop terima data
    # ------------------------------------------------------------------
    with E220() as lora:
        print("[LoRa] Mengkonfigurasi modul E220...")
        if not lora.konfigurasi():
            print("[LoRa] Modul tidak merespons. Periksa kabel dan pengaturan serial.")
            mqtt.disconnect()
            return

        print("[LoRa] Siap. Menunggu data dari node STM32...\n")

        while True:
            try:
                baris = lora.baca_baris()
                if baris is None:
                    continue

                hasil = parse_frame(baris)
                if hasil is None:
                    print(f"[LoRa] Data tidak dikenal: {baris!r}")
                    continue

                device_code, jarak_cm, nomor_urut = hasil

                teks_jarak = (
                    "tidak ada pantulan" if jarak_cm == 0
                    else f"{jarak_cm:.1f} cm"
                )
                print(f"[{time.strftime('%H:%M:%S')}] [{device_code}] Ukur #{nomor_urut}: {teks_jarak}")

                # Kirim ke MQTT hanya jika jarak valid (> 0)
                if jarak_cm > 0:
                    node_info = syncer.get_node(device_code)

                    if not node_info:
                        print(f"[Gateway] Peringatan: Node '{device_code}' tidak terdaftar di mapping! Abaikan.")
                        continue

                    tank_id        = node_info["tankId"]
                    sensor_node_id = node_info["sensorNodeId"]
                    capacity       = node_info.get("capacityLiters", 200.0)

                    payload = hitung_payload(
                        jarak_cm=jarak_cm,
                        nomor_urut=nomor_urut,
                        tank_id=tank_id,
                        sensor_node_id=sensor_node_id,
                        tank_capacity_liters=capacity,
                        tank_height_cm=TANK_HEIGHT_CM,
                    )

                    topic = f"hospital/{tank_id}/level"
                    mqtt.publish(payload, topic=topic)

            except KeyboardInterrupt:
                print("\n[Gateway] Dihentikan oleh pengguna.")
                break
            except serial.SerialException as e:
                print(f"[Serial] Error: {e}. Menunggu 3 detik...")
                time.sleep(3)

    # ------------------------------------------------------------------
    # 4. Cleanup
    # ------------------------------------------------------------------
    mqtt.disconnect()
    print("[Gateway] Selesai.")


if __name__ == "__main__":
    main()

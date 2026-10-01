"""Script pengujian mandiri untuk simulasi pengiriman data ke backend.

Alur:
1. Memanggil GET /api/gateways/{GATEWAY_CODE}/sync untuk mendapatkan mapping tangki.
2. Membuka koneksi MQTT ke broker di VPS (QoS 0).
3. Mengirim payload uji coba untuk setiap node tangki yang terdaftar.
"""

import time

from config import (
    BACKEND_API_URL,
    GATEWAY_CODE,
    GATEWAY_SYNC_KEY,
    TANK_HEIGHT_CM,
)
from mqtt_client.publisher import MQTTPublisher
from sensor.processor import hitung_payload
from sensor.syncer import GatewaySyncer


def test_kirim():
    print("=" * 60)
    print(" [TEST] UJI PENGIRIMAN DATA KE BACKEND (QoS 0)")
    print("=" * 60)

    # 1. Sync dari backend
    syncer = GatewaySyncer(
        api_base_url=BACKEND_API_URL,
        gateway_code=GATEWAY_CODE,
        sync_key=GATEWAY_SYNC_KEY,
    )
    sukses = syncer.fetch_sync()
    if not sukses or not syncer.mappings:
        print("[TEST] Gagal mendapatkan mapping dari backend atau cache kosong!")
        return

    print(f"[TEST] Mapping ditemukan ({len(syncer.mappings)} node):")
    for code, info in syncer.mappings.items():
        print(f"  - {code} -> Tangki: '{info['tankName']}' ({info['tankId']}), Kapasitas: {info['capacityLiters']}L")

    # 2. Hubungkan ke MQTT Broker
    print("\n[TEST] Menghubungkan ke broker MQTT...")
    publisher = MQTTPublisher()
    publisher.connect()

    # Beri jeda 1.5 detik agar koneksi MQTT stabil
    time.sleep(1.5)

    # 3. Kirim sampel data untuk setiap tangki
    print("\n[TEST] Mulai mengirim sampel data telemetri...")
    for idx, (code, node) in enumerate(syncer.mappings.items(), start=1):
        # Simulasi jarak 35.0 cm, urutan ke-idx
        jarak_simulasi = 35.0
        payload = hitung_payload(
            jarak_cm=jarak_simulasi,
            nomor_urut=idx,
            tank_id=node["tankId"],
            sensor_node_id=node["sensorNodeId"],
            tank_capacity_liters=node["capacityLiters"],
            tank_height_cm=TANK_HEIGHT_CM,
        )

        topic = f"hospital/{node['tankId']}/level"
        print(f"\n[TEST] Mengirim data untuk node [{code}]:")
        publisher.publish(payload, topic=topic)
        time.sleep(0.5)

    time.sleep(1.0)
    publisher.disconnect()
    print("\n[TEST] Pengujian selesai! Cek log backend atau dashboard kamu.")


if __name__ == "__main__":
    test_kirim()

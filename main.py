import json
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt


# =========================
# KONFIGURASI
# =========================

MQTT_BROKER = "100.94.192.102"
MQTT_PORT = 1883

TANK_ID = "a6f5ade5-777c-4871-a584-de40d11df30d"
SENSOR_NODE_ID = "6b464034-79f0-46fe-a7e4-7bd3b7fa9c8a"

TANK_HEIGHT_CM = 100
TANK_CAPACITY_LITERS = 200

MQTT_TOPIC = f"hospital/{TANK_ID}/level"


# =========================
# MQTT
# =========================

client = mqtt.Client()


def connect_mqtt():
    print("Connecting to MQTT broker...")

    client.connect(
        MQTT_BROKER,
        MQTT_PORT,
        60
    )

    print("Connected!")


# =========================
# PROCESSING DATA
# =========================

def process_sensor_data(raw_value, rssi):
    """
    Mengubah data mentah sensor menjadi
    data yang siap dikirim ke backend.
    """

    # Contoh:
    # raw_value dianggap sebagai jarak
    # sensor -> permukaan air

    distance_cm = raw_value

    # Hitung tinggi air
    water_height = TANK_HEIGHT_CM - distance_cm

    # Batasi supaya tidak keluar range
    water_height = max(
        0,
        min(TANK_HEIGHT_CM, water_height)
    )

    # Hitung persentase
    level_percent = (
        water_height / TANK_HEIGHT_CM
    ) * 100

    # Hitung volume
    volume_liters = (
        level_percent / 100
    ) * TANK_CAPACITY_LITERS

    # Timestamp UTC
    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    payload = {
        "tank_id": TANK_ID,
        "sensor_node_id": SENSOR_NODE_ID,
        "level_percent": round(level_percent, 2),
        "volume_liters": round(volume_liters, 2),
        "raw_value": raw_value,
        "rssi": rssi,
        "timestamp": timestamp
    }

    return payload


# =========================
# MAIN
# =========================

def main():

    connect_mqtt()

    print("Gateway started.")
    print("Waiting for sensor data...")

    while True:

        # ==========================
        # SIMULASI DATA SENSOR
        # ==========================

        raw_value = 20
        rssi = -78

        # ==========================
        # PROCESSING
        # ==========================

        payload = process_sensor_data(
            raw_value,
            rssi
        )

        # ==========================
        # MQTT PUBLISH
        # ==========================

        message = json.dumps(payload)

        result = client.publish(
            MQTT_TOPIC,
            message,
            qos=1
        )

        if result.rc == mqtt.MQTT_ERR_SUCCESS:

            print("\nData published:")
            print(message)

        else:

            print("Failed to publish")

        # Kirim setiap 5 detik
        time.sleep(5)


if __name__ == "__main__":
    main()


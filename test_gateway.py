```python
import json
import time
import serial
import paho.mqtt.client as mqtt

# =========================
# KONFIGURASI
# =========================

SERIAL_PORT = "/dev/serial0"
BAUDRATE = 9600

MQTT_HOST = "100.94.192.102"
MQTT_PORT = 1883

TANK_ID = "a6f5ade5-777c-4871-a584-de40d11df30d"
SENSOR_NODE_ID = "6b464034-79f0-46fe-a7e4-7bd3b7fa9c8a"

MQTT_TOPIC = f"hospital/{TANK_ID}/level"


# =========================
# MQTT CALLBACK
# =========================

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("[MQTT] Terhubung ke VPS broker.")
        print(f"[MQTT] Topic: {MQTT_TOPIC}")
    else:
        print(f"[MQTT] Gagal terhubung. RC={rc}")


def on_disconnect(client, userdata, rc):
    print(f"[MQTT] Terputus. RC={rc}")


# =========================
# SETUP MQTT
# =========================

mqtt_client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION1
)

mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect

print(f"[MQTT] Menghubungi {MQTT_HOST}:{MQTT_PORT} ...")

mqtt_client.connect(
    MQTT_HOST,
    MQTT_PORT,
    keepalive=60
)

mqtt_client.loop_start()


# =========================
# SETUP SERIAL / LORA
# =========================

print(f"[LoRa] Membuka {SERIAL_PORT}...")

ser = serial.Serial(
    SERIAL_PORT,
    BAUDRATE,
    timeout=1
)

print("[LoRa] Siap menerima data dari STM32.")
print("[Gateway] Menunggu data...\n")


# =========================
# MAIN LOOP
# =========================

sequence = 0

try:
    while True:

        if ser.in_waiting > 0:

            raw = ser.readline()

            try:
                data = raw.decode("utf-8").strip()
            except UnicodeDecodeError:
                print("[LoRa] Data bukan UTF-8:", raw)
                continue

            if not data:
                continue

            sequence += 1

            # ---------------------------------
            # DATA DITERIMA DARI STM32
            # ---------------------------------

            print("=" * 60)

            print(f"[LoRa] Data #{sequence} diterima dari STM32:")
            print(data)

            # ---------------------------------
            # COBA PARSE JSON
            # ---------------------------------

            try:
                stm_data = json.loads(data)

            except json.JSONDecodeError:

                print("[LoRa] Data bukan JSON.")
                print("[Gateway] Tidak diteruskan ke MQTT.")
                continue

            # ---------------------------------
            # TAMBAHKAN INFORMASI GATEWAY
            # ---------------------------------

            payload = {
                "tank_id": TANK_ID,
                "sensor_node_id": SENSOR_NODE_ID,
                "sequence": sequence,
                "data": stm_data,
                "gateway": "raspberry-pi"
            }

            payload_json = json.dumps(payload)

            # ---------------------------------
            # KIRIM KE MQTT VPS
            # ---------------------------------

            print("[MQTT] Mengirim ke VPS...")

            result = mqtt_client.publish(
                MQTT_TOPIC,
                payload_json,
                qos=1
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:

                print("[MQTT] ✓ Publish berhasil.")
                print(f"[MQTT] Topic   : {MQTT_TOPIC}")
                print(f"[MQTT] Payload : {payload_json}")

            else:

                print(
                    f"[MQTT] ✗ Publish gagal. RC={result.rc}"
                )

            print("=" * 60)
            print()

        time.sleep(0.01)


except KeyboardInterrupt:

    print("\n[Gateway] Menghentikan program...")

finally:

    ser.close()

    mqtt_client.loop_stop()
    mqtt_client.disconnect()

    print("[Gateway] Selesai.")
```

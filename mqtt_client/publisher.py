"""MQTT publisher untuk gateway Raspberry Pi.

Mengelola koneksi ke broker dan pengiriman payload JSON.
Reconnect ditangani secara otomatis oleh loop_start() paho-mqtt.
"""

import json
import time

import paho.mqtt.client as mqtt

from config import MQTT_BROKER, MQTT_PORT, MQTT_TOPIC


class MQTTPublisher:
    """Wrapper tipis di atas paho-mqtt Client dengan reconnect otomatis."""

    def __init__(self):
        # Dukung paho-mqtt 1.x (dari apt) maupun 2.x (dari pip)
        try:
            self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        except AttributeError:
            self._client = mqtt.Client()

        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect

    # ------------------------------------------------------------------
    # Callback internal
    # ------------------------------------------------------------------

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            print("[MQTT] Terhubung ke broker.")
        else:
            print(f"[MQTT] Gagal terhubung, kode: {rc}")

    def _on_disconnect(self, client, userdata, *args):
        print("[MQTT] Terputus dari broker — loop_start() akan menyambung ulang.")

    # ------------------------------------------------------------------
    # Koneksi
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Hubungkan ke broker secara asinkron dan mulai background loop."""
        print(f"[MQTT] Menghubungi {MQTT_BROKER}:{MQTT_PORT} ...")
        # connect_async: tidak crash jika broker belum bisa dijangkau saat start
        self._client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=60)
        self._client.loop_start()   # background thread → reconnect otomatis
        time.sleep(1.0)             # beri waktu handshake selesai

    def disconnect(self) -> None:
        """Hentikan background loop dan putus koneksi dengan bersih."""
        self._client.loop_stop()
        self._client.disconnect()
        print("[MQTT] Koneksi ditutup.")

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    def publish(self, payload: dict) -> None:
        """Serialisasi payload ke JSON dan kirim ke broker dengan QoS 1."""
        message = json.dumps(payload)
        result  = self._client.publish(MQTT_TOPIC, message, qos=1)

        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            print(f"[MQTT] Terkirim → {message}")
        else:
            print(f"[MQTT] Gagal kirim (rc={result.rc}) — broker belum terhubung?")

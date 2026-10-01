import json
import threading
import time
from typing import Optional

import paho.mqtt.client as mqtt

from config import (
    MQTT_BROKER,
    MQTT_PASSWORD,
    MQTT_PORT,
    MQTT_USER,
)
from storage.buffer import MessageBuffer


class MQTTPublisher:
    """Wrapper di atas paho-mqtt Client dengan reconnect otomatis dan Store-and-Forward."""

    def __init__(self, buffer_db_path: str = "buffer.db"):
        self.buffer = MessageBuffer(db_path=buffer_db_path)
        self.is_connected = False
        self._flushing_lock = threading.Lock()

        # Dukung paho-mqtt 1.x (dari apt) maupun 2.x (dari pip)
        try:
            self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        except AttributeError:
            self._client = mqtt.Client()

        # Autentikasi jika username/password didefinisikan
        if MQTT_USER and MQTT_PASSWORD:
            self._client.username_pw_set(MQTT_USER, MQTT_PASSWORD)

        self._client.on_connect    = self._on_connect
        self._client.on_disconnect = self._on_disconnect

    # ------------------------------------------------------------------
    # Callback internal
    # ------------------------------------------------------------------

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            self.is_connected = True
            print("[MQTT] Terhubung ke broker.")
            # Begitu terhubung, flush data yang tertahan di SQLite secara async
            threading.Thread(target=self._flush_buffer, daemon=True).start()
        else:
            self.is_connected = False
            print(f"[MQTT] Gagal terhubung, kode respon: {rc}")

    def _on_disconnect(self, client, userdata, *args):
        self.is_connected = False
        print("[MQTT] Terputus dari broker. Data baru akan disimpan ke buffer lokal.")

    def _flush_buffer(self) -> None:
        """Kirim pesan-pesan yang tertunda di SQLite ke broker."""
        with self._flushing_lock:
            jumlah_antrean = self.buffer.hitung_antrean()
            if jumlah_antrean == 0:
                return

            print(f"[Buffer] Mengirim {jumlah_antrean} data tertunda dari penyimpanan lokal...")
            while self.is_connected:
                pesan_list = self.buffer.ambil_pesan_tertunda(limit=20)
                if not pesan_list:
                    break

                for msg_id, topic, payload in pesan_list:
                    if not self.is_connected:
                        break
                    try:
                        # Tandai payload bahwa ini data yang dikirim dari buffer tertunda
                        payload["is_buffered"] = True
                        res = self._client.publish(topic, json.dumps(payload), qos=1)
                        res.wait_for_publish(timeout=5.0)
                        if res.rc == mqtt.MQTT_ERR_SUCCESS:
                            self.buffer.hapus(msg_id)
                        else:
                            # Jika gagal di tengah jalan, hentikan pengurasan
                            return
                    except Exception as e:
                        print(f"[Buffer] Gagal mengirim pesan ID {msg_id}: {e}")
                        return
                    time.sleep(0.05)  # Beri jeda kecil agar broker tidak kebanjiran

            sisa = self.buffer.hitung_antrean()
            if sisa == 0:
                print("[Buffer] Semua data tertunda berhasil dikirim!")
            else:
                print(f"[Buffer] Masih ada {sisa} data tertunda yang belum terkirim.")

    # ------------------------------------------------------------------
    # Koneksi
    # ------------------------------------------------------------------

    def connect(self) -> None:
        """Hubungkan ke broker secara asinkron dan mulai background loop."""
        print(f"[MQTT] Menghubungi {MQTT_BROKER}:{MQTT_PORT} ...")
        self._client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=60)
        self._client.loop_start()   # background thread → reconnect otomatis
        time.sleep(1.0)             # beri waktu handshake selesai

    def disconnect(self) -> None:
        """Hentikan background loop dan putus koneksi dengan bersih."""
        self._client.loop_stop()
        self._client.disconnect()
        self.is_connected = False
        print("[MQTT] Koneksi ditutup.")

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    def publish(self, payload: dict, topic: Optional[str] = None) -> None:
        """Kirim ke MQTT. Jika offline/gagal, simpan otomatis ke SQLite."""
        target_topic = topic or f"hospital/{payload.get('tank_id', 'unknown')}/level"
        message = json.dumps(payload)

        # Jika offline, langsung simpan ke buffer lokal tanpa buang data
        if not self.is_connected:
            self.buffer.simpan(target_topic, payload)
            print(f"[Buffer] Offline: Data disimpan ke buffer lokal (total antrean: {self.buffer.hitung_antrean()})")
            return

        try:
            result = self._client.publish(target_topic, message, qos=0)
            # Cek status publish
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"[MQTT] Terkirim (QoS 0) -> {target_topic}: {message}")
            else:
                # Simpan ke buffer jika broker menolak/putus
                self.buffer.simpan(target_topic, payload)
                print(f"[Buffer] Gagal kirim (rc={result.rc}). Disimpan ke buffer lokal.")
        except Exception as e:
            self.buffer.simpan(target_topic, payload)
            print(f"[Buffer] Terjadi error ({e}). Disimpan ke buffer lokal.")


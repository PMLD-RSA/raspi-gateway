"""Pemrosesan data sensor ultrasonik dan parsing frame LoRa.

Modul ini murni logika bisnis — tidak bergantung pada hardware apa pun
sehingga mudah diuji dengan unit test tanpa Pi fisik.
"""

from datetime import datetime, timezone
from typing import Optional

from config import TANK_CAPACITY_LITERS, TANK_HEIGHT_CM


# ---------------------------------------------------------------------------
# Parsing frame LoRa
# ---------------------------------------------------------------------------

def parse_frame(baris: str) -> Optional[tuple[str, float, int, Optional[int]]]:
    """Urai baris teks menjadi (device_code, jarak_cm, nomor_urut, rssi_dbm).

    Mendukung format:
    1. Format Baru (DYP-A01 Mesh): ``N<id>,D<distance_mm>,S<seq>,H<hop>``
       Contoh: ``N1,D452,S10,H0`` (distance dalam mm -> dikonversi ke cm)
    2. Format JSON (dari RX_Gabungan.ino):
       ``{"node":1,"distance":452,"rssi":-65,"hop":0,...}``
    3. Format Lama: ``JARAK,<device_code>,<cm>,<nomor_urut>``
       Contoh: ``JARAK,STM32-ATA,45.2,10``
    4. Format Legacy: ``JARAK,<cm>,<nomor_urut>``

    Mengembalikan tuple ``(device_code, jarak_cm, nomor_urut, rssi_dbm)`` atau ``None``.
    """
    baris = baris.strip()
    if not baris:
        return None

    # 1. Format JSON (jika menggunakan RX Hub via USB Serial)
    if baris.startswith("{") and baris.endswith("}"):
        try:
            import json
            data = json.loads(baris)
            node_id = data.get("node")
            dist_mm = data.get("distance", -1)
            seq = data.get("ts", 0)  # atau timestamp/seq jika ada
            rssi = data.get("rssi")

            if node_id is not None and dist_mm is not None:
                device_code = str(node_id)
                jarak_cm = float(dist_mm) / 10.0  # mm -> cm
                return device_code, jarak_cm, int(seq), int(rssi) if rssi else None
        except Exception:
            pass

    # 2. Format Baru Transmitter: N<origin>,D<dist_mm>,S<seq>,H<hop>
    # Catatan: Jika Packet RSSI aktif di E220, modul menambahkan 1 byte RSSI biner di akhir tiap paket.
    # Terkadang saat dibaca serial per baris, byte RSSI dari paket sebelumnya menempel di depan paket berikutnya ('íN1,...')
    idx_N = baris.find("N")
    if idx_N != -1:
        # Periksa apakah ada karakter RSSI di depan 'N'
        rssi_val = None
        if idx_N > 0:
            prefix_char = baris[idx_N - 1]
            raw_rssi = ord(prefix_char)
            # Konversi byte RSSI EBYTE (0-255) ke dBm: -(256 - raw)
            rssi_val = -(256 - raw_rssi) if raw_rssi > 127 else -raw_rssi

        clean_baris = baris[idx_N:]
        try:
            pD = clean_baris.find(",D")
            pS = clean_baris.find(",S")
            pH = clean_baris.find(",H")

            if pD > 0 and pS > pD and pH > pS:
                origin_str = clean_baris[1:pD]
                dist_str   = clean_baris[pD + 2:pS]
                seq_str    = clean_baris[pS + 2:pH]
                hop_raw    = clean_baris[pH + 2:]

                # Ekstrak angka hop (buang jika ada byte trailing RSSI di ujung hop)
                hop_digits = ""
                for char in hop_raw:
                    if char.isdigit():
                        hop_digits += char
                    else:
                        # Jika ada karakter biner RSSI di akhir paket
                        if rssi_val is None:
                            raw_r = ord(char)
                            rssi_val = -(256 - raw_r) if raw_r > 127 else -raw_r
                        break

                device_code = origin_str.strip()
                dist_mm     = float(dist_str.strip())
                nomor_urut  = int(seq_str.strip())

                jarak_cm = dist_mm / 10.0  # DYP-A01 mm -> cm
                return device_code, jarak_cm, nomor_urut, rssi_val
        except (ValueError, IndexError):
            pass

    # 3. Format Lama: JARAK,...
    bagian = [b.strip() for b in baris.split(",")]
    if bagian and bagian[0] == "JARAK":
        if len(bagian) == 4:
            try:
                device_code = bagian[1]
                jarak_cm    = float(bagian[2])
                nomor_urut  = int(bagian[3])
                return device_code, jarak_cm, nomor_urut, None
            except ValueError:
                return None
        elif len(bagian) == 3:
            try:
                device_code = "DEFAULT"
                jarak_cm    = float(bagian[1])
                nomor_urut  = int(bagian[2])
                return device_code, jarak_cm, nomor_urut, None
            except ValueError:
                return None

    return None


# ---------------------------------------------------------------------------
# Pemrosesan data
# ---------------------------------------------------------------------------

def hitung_payload(
    jarak_cm: float,
    nomor_urut: int,
    tank_id: str,
    sensor_node_id: str,
    tank_capacity_liters: float = TANK_CAPACITY_LITERS,
    tank_height_cm: float = TANK_HEIGHT_CM,
    rssi: Optional[int] = None,
    min_distance_cm: float = 30.0,
    max_distance_cm: float = 350.0,
) -> dict:
    """Ubah jarak sensor → payload JSON sesuai kontrak MQTT backend.

    Sesuai kontrak MQTT backend (`mqttLevelPayloadSchema`):
    - `sensor_node_id`: UUID node sensor (wajib)
    - `tank_id`: UUID tangki (opsional tapi disarankan)
    - `distance_cm`: float positif jarak fisik sensor (wajib)
    - `raw_value`: float jarak sensor fisik
    - `level_percent`: persentase ketinggian air (0-100%)
    - `volume_liters`: volume air terhitung (liter)
    - `sequence`: nomor urut paket
    - `rssi`: kekuatan sinyal radio (dBm)
    - `is_buffered`: false (true saat di-flush dari SQLite)
    - `timestamp`: format ISO 8601 UTC string

    Rumus kalibrasi:
      min_distance_cm = jarak saat tangki penuh (100%)
      max_distance_cm = jarak saat tangki kosong (0%)
    """
    min_dist = max(0.0, float(min_distance_cm))
    max_dist = max(min_dist + 1.0, float(max_distance_cm))
    rentang_efektif = max_dist - min_dist

    # Hitung persentase ketinggian air
    raw_percent = ((max_dist - jarak_cm) / rentang_efektif) * 100.0
    clamped_percent = max(0.0, min(100.0, raw_percent))

    level_percent = round(clamped_percent, 2)
    volume_liters = round((level_percent / 100.0) * float(tank_capacity_liters), 2)

    payload = {
        "tank_id":        tank_id,
        "sensor_node_id": sensor_node_id,
        "distance_cm":    round(float(jarak_cm), 2),
        "raw_value":      round(float(jarak_cm), 2),
        "level_percent":  level_percent,
        "volume_liters":  volume_liters,
        "sequence":       nomor_urut,
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "is_buffered":    False,
    }
    if rssi is not None:
        payload["rssi"] = int(rssi)
    return payload

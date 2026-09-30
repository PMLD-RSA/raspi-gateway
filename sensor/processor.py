"""Pemrosesan data sensor ultrasonik dan parsing frame LoRa.

Modul ini murni logika bisnis — tidak bergantung pada hardware apa pun
sehingga mudah diuji dengan unit test tanpa Pi fisik.
"""

from datetime import datetime, timezone
from typing import Optional

from config import (
    SENSOR_NODE_ID,
    TANK_CAPACITY_LITERS,
    TANK_HEIGHT_CM,
    TANK_ID,
)


# ---------------------------------------------------------------------------
# Parsing frame LoRa
# ---------------------------------------------------------------------------

def parse_frame(baris: str) -> Optional[tuple[float, int]]:
    """Urai baris teks menjadi (jarak_cm, nomor_urut).

    Format yang dikirim STM32: ``JARAK,<cm>,<nomor_urut>``

    Mengembalikan tuple ``(jarak_cm, nomor_urut)`` atau ``None`` jika
    format tidak dikenal / nilai tidak bisa dikonversi.
    """
    bagian = baris.split(",")

    if len(bagian) != 3 or bagian[0] != "JARAK":
        return None

    try:
        jarak_cm   = float(bagian[1])
        nomor_urut = int(bagian[2])
    except ValueError:
        print(f"[Sensor] Format angka salah: {baris!r}")
        return None

    return jarak_cm, nomor_urut


# ---------------------------------------------------------------------------
# Pemrosesan data
# ---------------------------------------------------------------------------

def hitung_payload(jarak_cm: float, nomor_urut: int) -> dict:
    """Ubah jarak sensor → payload JSON siap kirim ke backend.

    Sensor ultrasonik dipasang di atas tangki dan mengukur jarak ke
    permukaan air. Semakin kecil jarak → semakin penuh tangki.

    Args:
        jarak_cm:   Jarak sensor ke permukaan air dalam sentimeter.
        nomor_urut: Nomor urut pengukuran dari STM32.

    Returns:
        Dict payload yang nantinya di-serialize ke JSON.
    """
    water_height  = TANK_HEIGHT_CM - jarak_cm
    water_height  = max(0.0, min(float(TANK_HEIGHT_CM), water_height))

    level_percent = (water_height / TANK_HEIGHT_CM) * 100
    volume_liters = (level_percent / 100) * TANK_CAPACITY_LITERS

    return {
        "tank_id":        TANK_ID,
        "sensor_node_id": SENSOR_NODE_ID,
        "level_percent":  round(level_percent, 2),
        "volume_liters":  round(volume_liters, 2),
        "distance_cm":    jarak_cm,
        "sequence":       nomor_urut,
        "timestamp":      datetime.now(timezone.utc).isoformat(),
    }

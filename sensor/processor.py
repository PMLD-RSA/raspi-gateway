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

def parse_frame(baris: str) -> Optional[tuple[str, float, int]]:
    """Urai baris teks menjadi (device_code, jarak_cm, nomor_urut).

    Mendukung dua format:
    1. Multi-tank (Rekomendasi): ``JARAK,<device_code>,<cm>,<nomor_urut>``
       Contoh: ``JARAK,STM32-ATA,45.2,10``
    2. Format tunggal (Legacy): ``JARAK,<cm>,<nomor_urut>``
       Contoh: ``JARAK,45.2,10`` (device_code default: "DEFAULT")

    Mengembalikan tuple ``(device_code, jarak_cm, nomor_urut)`` atau ``None``.
    """
    bagian = [b.strip() for b in baris.split(",")]

    if not bagian or bagian[0] != "JARAK":
        return None

    # Format 4 bagian: JARAK, device_code, jarak_cm, seq
    if len(bagian) == 4:
        try:
            device_code = bagian[1]
            jarak_cm    = float(bagian[2])
            nomor_urut  = int(bagian[3])
            return device_code, jarak_cm, nomor_urut
        except ValueError:
            print(f"[Sensor] Format angka salah: {baris!r}")
            return None

    # Format 3 bagian (legacy): JARAK, jarak_cm, seq
    elif len(bagian) == 3:
        try:
            device_code = "DEFAULT"
            jarak_cm    = float(bagian[1])
            nomor_urut  = int(bagian[2])
            return device_code, jarak_cm, nomor_urut
        except ValueError:
            print(f"[Sensor] Format angka salah: {baris!r}")
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
) -> dict:
    """Ubah jarak sensor → payload JSON siap kirim ke backend.

    Sensor ultrasonik dipasang di atas tangki dan mengukur jarak ke
    permukaan air. Semakin kecil jarak → semakin penuh tangki.

    Args:
        jarak_cm:             Jarak sensor ke permukaan air dalam sentimeter.
        nomor_urut:           Nomor urut pengukuran dari STM32.
        tank_id:              UUID tangki dari backend.
        sensor_node_id:       UUID sensor node dari backend.
        tank_capacity_liters: Kapasitas total tangki dalam liter.
        tank_height_cm:       Tinggi fisik tangki dalam sentimeter.

    Returns:
        Dict payload yang nantinya di-serialize ke JSON.
    """
    water_height  = tank_height_cm - jarak_cm
    water_height  = max(0.0, min(float(tank_height_cm), water_height))

    level_percent = (water_height / tank_height_cm) * 100
    volume_liters = (level_percent / 100) * tank_capacity_liters

    return {
        "tank_id":        tank_id,
        "sensor_node_id": sensor_node_id,
        "level_percent":  round(level_percent, 2),
        "volume_liters":  round(volume_liters, 2),
        "distance_cm":    jarak_cm,
        "sequence":       nomor_urut,
        "timestamp":      datetime.now(timezone.utc).isoformat(),
        "is_buffered":    False,
    }

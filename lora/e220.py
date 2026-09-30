"""Driver modul LoRa Ebyte E220-900T22D untuk Raspberry Pi.

Mengelola:
  - Kontrol pin GPIO (M0, M1, AUX)
  - Pergantian mode operasi (normal / konfigurasi / WOR / sleep)
  - Baca & tulis register permanen via UART
  - Menerima frame data serial dari STM32

Wiring (pin fisik header 40-pin Raspberry Pi):
  E220 VCC -> pin  2 (5V)          E220 GND -> pin  6 (GND)
  E220 TXD -> pin 10 (GPIO15 RXD)  E220 RXD -> pin  8 (GPIO14 TXD)
  E220 M0  -> pin 16 (GPIO23)      E220 M1  -> pin 18 (GPIO24)
  E220 AUX -> pin 22 (GPIO25)
"""

import time

import serial
from gpiozero import DigitalInputDevice, DigitalOutputDevice

from config import (
    LORA_BAUD,
    LORA_CFG,
    LORA_PIN_AUX,
    LORA_PIN_M0,
    LORA_PIN_M1,
    LORA_SERIAL_PORT,
)


class E220:
    """Driver tingkat rendah untuk modul LoRa Ebyte E220."""

    def __init__(self):
        self._m0  = DigitalOutputDevice(LORA_PIN_M0)
        self._m1  = DigitalOutputDevice(LORA_PIN_M1)
        self._aux = DigitalInputDevice(LORA_PIN_AUX, pull_up=None, active_state=True)
        self._ser: serial.Serial | None = None

    # ------------------------------------------------------------------
    # Kontrol GPIO
    # ------------------------------------------------------------------

    def tunggu_aux(self, timeout: float = 2.0) -> bool:
        """Tunggu sampai pin AUX HIGH (modul idle).

        AUX LOW berarti modul sedang memproses data / konfigurasi.
        Mengembalikan False jika timeout terlampaui.
        """
        t0 = time.monotonic()
        while not self._aux.value:
            if time.monotonic() - t0 > timeout:
                print("[E220] PERINGATAN: AUX timeout")
                return False
            time.sleep(0.001)
        time.sleep(0.002)   # settling time minimal setelah AUX HIGH
        return True

    def set_mode(self, m0: int, m1: int) -> None:
        """Ganti mode operasi E220.

        Mode  M0  M1  Keterangan
        ----  --  --  ----------
        0     0   0   Transmisi normal (transparan / fixed)
        1     1   0   WOR (Wake-on-Radio) pengirim
        2     0   1   WOR penerima
        3     1   1   Konfigurasi via UART / sleep
        """
        self.tunggu_aux()
        self._m0.value = m0
        self._m1.value = m1
        time.sleep(0.002)
        self.tunggu_aux()

    # ------------------------------------------------------------------
    # Koneksi serial
    # ------------------------------------------------------------------

    def buka(self) -> "E220":
        """Buka port serial. Gunakan sebagai context manager."""
        self._ser = serial.Serial(LORA_SERIAL_PORT, LORA_BAUD, timeout=1)
        return self

    def tutup(self) -> None:
        """Tutup port serial dan lepas GPIO."""
        if self._ser and self._ser.is_open:
            self._ser.close()
        self._m0.close()
        self._m1.close()
        self._aux.close()

    def __enter__(self) -> "E220":
        return self.buka()

    def __exit__(self, *_) -> None:
        self.tutup()

    # ------------------------------------------------------------------
    # Konfigurasi register
    # ------------------------------------------------------------------

    def konfigurasi(self) -> bool:
        """Baca register E220, tulis permanen (C0) hanya jika berbeda.

        Mengembalikan True jika modul merespons dengan benar.
        """
        if self._ser is None:
            raise RuntimeError("Port serial belum dibuka. Panggil buka() atau gunakan 'with'.")

        n = len(LORA_CFG)

        # Masuk mode konfigurasi (M0=1, M1=1) — UART wajib 9600 8N1
        self.set_mode(1, 1)
        self._ser.reset_input_buffer()

        # Perintah baca register: C1 ADDR LEN
        self._ser.write(bytes([0xC1, 0x00, n]))
        resp = self._ser.read(3 + n)

        if len(resp) != 3 + n or resp[0] != 0xC1:
            print(f"[E220] Gagal baca register (resp={resp.hex()})")
            self.set_mode(0, 0)
            return False

        reg_terbaca = resp[3:]
        print(f"[E220] Register terbaca  : {reg_terbaca.hex()}")
        print(f"[E220] Target konfigurasi: {LORA_CFG.hex()}")

        if reg_terbaca != LORA_CFG:
            print("[E220] Konfigurasi berbeda, menulis ulang...")
            # Jeda singkat sebelum tulis agar modul tidak membalas FF FF FF
            time.sleep(0.05)
            self.tunggu_aux()
            # Perintah tulis permanen: C0 ADDR LEN + DATA
            self._ser.write(bytes([0xC0, 0x00, n]) + LORA_CFG)
            resp = self._ser.read(3 + n)
            if len(resp) == 3 + n and resp[0] == 0xC1:
                print("[E220] Konfigurasi berhasil ditulis.")
            else:
                print(f"[E220] Gagal tulis konfigurasi (resp={resp.hex()})")
                self.set_mode(0, 0)
                return False
        else:
            print("[E220] Konfigurasi sudah sesuai, tidak perlu ditulis ulang.")

        # Kembali ke mode transmisi normal
        self.set_mode(0, 0)
        return True

    # ------------------------------------------------------------------
    # Terima data
    # ------------------------------------------------------------------

    def baca_baris(self) -> str | None:
        """Baca satu baris ASCII dari UART.

        Mengembalikan string yang sudah di-strip, atau None jika kosong /
        timeout.
        """
        if self._ser is None:
            raise RuntimeError("Port serial belum dibuka.")

        raw = self._ser.readline()
        if not raw:
            return None

        baris = raw.decode("ascii", errors="replace").strip()
        return baris if baris else None

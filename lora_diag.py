#!/usr/bin/env python3
"""Diagnosa tulis register E220: cari perintah/register mana yang ditolak (FF FF FF).

Wiring sama dengan main.py. Hentikan main.py dulu sebelum menjalankan ini.
Jalankan:  python3 lora_diag.py
"""

import time

import serial
from gpiozero import DigitalInputDevice, DigitalOutputDevice

m0 = DigitalOutputDevice(23)
m1 = DigitalOutputDevice(24)
aux = DigitalInputDevice(25, pull_up=None, active_state=True)


def tunggu_aux(timeout=2.0):
    t0 = time.monotonic()
    while not aux.value:
        if time.monotonic() - t0 > timeout:
            print("  (AUX timeout)")
            return
        time.sleep(0.001)
    time.sleep(0.05)


def kirim(ser, label, cmd):
    tunggu_aux()
    ser.reset_input_buffer()
    ser.write(cmd)
    resp = ser.read(3 + cmd[2])
    status = "OK" if resp[:1] == b"\xC1" else "DITOLAK"
    print(f"{label:<34} kirim={cmd.hex(' ')}  balas={resp.hex(' ') or '(kosong)'}  {status}")


with serial.Serial("/dev/serial0", 9600, timeout=1) as ser:
    m0.value, m1.value = 1, 1
    time.sleep(0.1)
    tunggu_aux()

    # Semua pakai C2 (sementara, hilang saat modul mati) supaya aman dicoba
    kirim(ser, "1. baca 8 register", bytes([0xC1, 0x00, 0x08]))
    kirim(ser, "2. tulis ulang nilai sekarang", bytes([0xC2, 0x00, 0x06, 0x00, 0x00, 0x62, 0x00, 0x12, 0x03]))
    kirim(ser, "3. REG1 saja -> 0x03 (10 dBm)", bytes([0xC2, 0x03, 0x01, 0x03]))
    kirim(ser, "4. REG2 saja -> 0x48 (ch 72)", bytes([0xC2, 0x04, 0x01, 0x48]))
    kirim(ser, "5. 8 byte lengkap (plus CRYPT)", bytes([0xC2, 0x00, 0x08, 0x00, 0x00, 0x62, 0x03, 0x48, 0x03, 0x00, 0x00]))
    kirim(ser, "6. baca lagi", bytes([0xC1, 0x00, 0x08]))

    m0.value, m1.value = 0, 0
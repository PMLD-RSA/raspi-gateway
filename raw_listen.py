#!/usr/bin/env python3
"""Dengarkan byte mentah dari E220 — debug apakah ada data masuk sama sekali.

Jalankan:  python3 raw_listen.py
Hentikan:  Ctrl+C
"""

import time
import serial
from gpiozero import DigitalInputDevice, DigitalOutputDevice

M0  = DigitalOutputDevice(23)
M1  = DigitalOutputDevice(24)
AUX = DigitalInputDevice(25, pull_up=None, active_state=True)

# Pastikan mode normal (M0=0, M1=0)
M0.value = 0
M1.value = 0
time.sleep(0.1)

print(f"[AUX] Status awal: {'HIGH (idle)' if AUX.value else 'LOW (sibuk!)'}")

ser = serial.Serial("/dev/serial0", 9600, timeout=0.1)
ser.reset_input_buffer()

print("[RAW] Menunggu byte dari E220... (Ctrl+C untuk stop)\n")

try:
    while True:
        # Cek AUX — LOW sekilas saat ada data masuk
        if not AUX.value:
            print(f"[AUX] LOW — E220 sedang menerima/memproses!")

        raw = ser.read(256)
        if raw:
            ts = time.strftime("%H:%M:%S")
            print(f"[{ts}] {len(raw)} byte: hex={raw.hex(' ')}  ascii={raw.decode('ascii', errors='replace')}")
        # Kalau tidak ada data, loop tanpa print supaya tidak spam
except KeyboardInterrupt:
    print("\nDihentikan.")
finally:
    ser.close()
    M0.close()
    M1.close()
    AUX.close()


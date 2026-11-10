#!/usr/bin/env python3
"""Tes loopback RF: Raspi → STM Relay → Raspi.

Raspi mengirim frame JARAK palsu ke STM relay via LoRa (fixed mode).
Kalau relay berjalan, ia akan meneruskan frame balik ke Raspi.
Jika data kembali = KEDUA E220 bekerja + firmware relay OK.

Jalankan:  python3 tes_loopback.py   (pastikan main.py sudah distop)
"""

import time

import serial
from gpiozero import DigitalInputDevice, DigitalOutputDevice

M0  = DigitalOutputDevice(23)
M1  = DigitalOutputDevice(24)
AUX = DigitalInputDevice(25, pull_up=None, active_state=True)

M0.value = 0
M1.value = 0
time.sleep(0.1)

ser = serial.Serial("/dev/serial0", 9600, timeout=0.5)
ser.reset_input_buffer()

# Target: STM relay (ADDH=0x00, ADDL=0x01, CH=0x42)
TARGET = bytes([0x00, 0x01, 0x42])
FRAME  = b"JARAK,LOOPBACK,42,0\n"

print("=" * 50)
print("Tes Loopback: Raspi -> Relay -> Raspi")
print("=" * 50)

for i in range(1, 4):
    # Tunggu AUX HIGH
    t0 = time.monotonic()
    while not AUX.value:
        if time.monotonic() - t0 > 2:
            print(f"[{i}] AUX timeout saat mau kirim!")
            break
        time.sleep(0.001)

    print(f"\n[{i}/3] Mengirim ke relay... ", end="", flush=True)
    ser.write(TARGET + FRAME)
    ser.flush()
    print("terkirim. Menunggu balasan...", flush=True)

    # Tunggu balasan max 8 detik (relay kirim tiap 5s + jitter)
    deadline = time.monotonic() + 8
    diterima = False
    while time.monotonic() < deadline:
        raw = ser.read(256)
        if raw:
            ts = time.strftime("%H:%M:%S")
            print(f"  [{ts}] DITERIMA {len(raw)} byte!")
            print(f"         hex  : {raw.hex(' ')}")
            print(f"         ascii: {raw.decode('ascii', errors='replace')}")
            diterima = True
            break

    if diterima:
        print("\n✅ Loopback BERHASIL — kedua E220 dan relay firmware bekerja!")
        break
    else:
        print(f"  Tidak ada balasan (percobaan {i}/3)")

    time.sleep(1)

else:
    print("\n❌ 3x percobaan gagal. Kemungkinan:")
    print("   1. Antena E220 relay tidak terpasang")
    print("   2. Kabel E220 ↔ STM32 terbalik (TX/RX swap)")
    print("   3. E220 relay dan Raspi beda model (900 vs 400 MHz)")
    print("   4. Jarak terlalu jauh (coba < 1 meter)")
    print("   5. E220 relay rusak / tidak dapat daya 5V cukup")

ser.close()
M0.close()
M1.close()
AUX.close()


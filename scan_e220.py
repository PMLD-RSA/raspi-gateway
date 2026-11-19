#!/usr/bin/env python3
"""Scanner baudrate dan tes komunikasi E220.
Mencoba semua kemungkinan baudrate (9600, 115200, 19200, 38400, 57600, 4800, 2400, 1200)
untuk menemukan baudrate aktif modul baru.
"""

import time
import serial
from gpiozero import DigitalInputDevice, DigitalOutputDevice

def main():
    print("=" * 60)
    print(" SCANNER KONEKSI & BAUDRATE MODUL E220 BARU")
    print("=" * 60)

    m0 = DigitalOutputDevice(23)
    m1 = DigitalOutputDevice(24)
    aux = DigitalInputDevice(25, pull_up=None, active_state=True)

    print(f"Status pin AUX saat ini: {'HIGH (Ready)' if aux.value else 'LOW (Busy/Floating)'}")
    
    print("\n[1] Mengaktifkan Mode Konfigurasi (M0=1, M1=1)...")
    m0.value = 1
    m1.value = 1
    time.sleep(0.2)
    print(f"Status pin AUX setelah M0=1, M1=1: {'HIGH (Ready)' if aux.value else 'LOW (Busy/Floating)'}")

    baudrates = [9600, 115200, 19200, 38400, 57600, 4800]
    cmd_baca = bytes([0xC1, 0x00, 0x08])

    modul_ditemukan = False

    for baud in baudrates:
        print(f"\nMencoba Baudrate: {baud} bps ...")
        try:
            with serial.Serial("/dev/serial0", baud, timeout=0.5) as ser:
                ser.reset_input_buffer()
                ser.write(cmd_baca)
                time.sleep(0.1)
                resp = ser.read(11)

                if resp:
                    print(f"  --> RESPON DITERIMA: {resp.hex(' ')}")
                    if resp[0] == 0xC1:
                        print(f"  [✓] DITEMUKAN! Modul E220 merespons di baudrate {baud} bps!")
                        print(f"      Register: {resp[3:].hex(' ')}")
                        modul_ditemukan = True
                        break
                else:
                    print("  --> Tidak ada respon (kosong)")
        except Exception as e:
            print(f"  --> Error port serial: {e}")

    m0.value = 0
    m1.value = 0
    m0.close()
    m1.close()
    aux.close()

    print("\n" + "=" * 60)
    if not modul_ditemukan:
        print("KESIMPULAN: Tidak ada respons di semua baudrate.")
        print("Kemungkinan penyebab:")
        print("1. Jalur serial hardware belum aktif atau bentrok dengan Console Linux.")
        print("2. Kabel jumper longgar / pin header Raspberry Pi tidak kontak.")
        print("3. Catu daya modul belum cukup.")
    print("=" * 60)

if __name__ == "__main__":
    main()

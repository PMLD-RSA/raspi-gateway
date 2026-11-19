#!/usr/bin/env python3
"""Script satu kali jalan untuk mengatur register modul E220 ke Channel 25 secara bertahap.

Mengatasi respon 'FF FF FF':
1. Menunggu settling time pin AUX & reset buffer serial.
2. Mencoba menulis dengan perintah C0 (permanen) per blok kecil (Channel saja dan full).
3. Jika modul menolak 8-byte sekaligus karena format register E220 versi 6-byte,
   akan dicoba varian 6-byte yang didukung.
"""

import time
import serial
from gpiozero import DigitalInputDevice, DigitalOutputDevice

def main():
    print("=" * 65)
    print(" PROGRAM SETTING REGISTER E220 KE CHANNEL 25 (EBYTE)")
    print("=" * 65)

    m0 = DigitalOutputDevice(23)
    m1 = DigitalOutputDevice(24)
    aux = DigitalInputDevice(25, pull_up=None, active_state=True)

    print("[1] Memasuki mode konfigurasi (M0=1, M1=1)...")
    m0.value = 1
    m1.value = 1
    time.sleep(0.15)

    # Tunggu AUX HIGH
    t0 = time.monotonic()
    while not aux.value:
        if time.monotonic() - t0 > 2.0:
            print("    (AUX timeout, lanjut...)")
            break
        time.sleep(0.01)
    time.sleep(0.05)

    def kirim_perintah(ser, label, cmd):
        time.sleep(0.05)
        # Tunggu AUX
        t_start = time.monotonic()
        while not aux.value:
            if time.monotonic() - t_start > 1.5:
                break
            time.sleep(0.005)
        time.sleep(0.02)

        ser.reset_input_buffer()
        ser.write(cmd)
        # Respons E220 adalah: Header balasan (C1) + Addr + Len + Data
        expected_len = 3 + cmd[2]
        resp = ser.read(expected_len)
        sukses = len(resp) == expected_len and resp[0] == 0xC1
        status = "OK" if sukses else f"GAGAL ({resp.hex(' ') or 'kosong'})"
        print(f"    {label:<32} -> {status}")
        return sukses, resp

    with serial.Serial("/dev/serial0", 9600, timeout=1.5) as ser:
        print("\n[2] Membaca konfigurasi modul...")
        ok, resp = kirim_perintah(ser, "Baca 8 Register", bytes([0xC1, 0x00, 0x08]))
        if ok:
            print(f"    Data saat ini : {resp[3:].hex(' ')}")
            print(f"    Channel lama  : {resp[3+4]} (0x{resp[3+4]:02X})")

        print("\n[3] Mencoba menulis Channel 25 (0x19)...")
        # Strategi A: Tulis hanya Channel (Register 0x04, panjang 1 byte, nilai 0x19)
        # C0 04 01 19
        ok_ch, _ = kirim_perintah(ser, "Tulis Channel Saja (0x19)", bytes([0xC0, 0x04, 0x01, 0x19]))

        # Strategi B: Tulis Address (Register 0x00, panjang 2 byte, nilai 0x01 0x03)
        ok_addr, _ = kirim_perintah(ser, "Tulis Address Saja (259)", bytes([0xC0, 0x00, 0x02, 0x01, 0x03]))

        # Strategi C: Tulis 6-byte standar
        # 0x01 0x03 0x62 0x62 0x19 0x88
        cfg_6byte = bytes([0x01, 0x03, 0x62, 0x62, 0x19, 0x88])
        ok_6b, _ = kirim_perintah(ser, "Tulis 6-Byte Konfigurasi", bytes([0xC0, 0x00, 0x06]) + cfg_6byte)

        # Strategi D: Tulis 8-byte lengkap
        cfg_8byte = bytes([0x01, 0x03, 0x62, 0x62, 0x19, 0x88, 0x00, 0x00])
        ok_8b, _ = kirim_perintah(ser, "Tulis 8-Byte Lengkap", bytes([0xC0, 0x00, 0x08]) + cfg_8byte)

        print("\n[4] Membaca hasil akhir...")
        ok_verif, resp_verif = kirim_perintah(ser, "Verifikasi 8 Register", bytes([0xC1, 0x00, 0x08]))
        if ok_verif:
            ch_baru = resp_verif[3+4]
            addr_baru = (resp_verif[3] << 8) | resp_verif[4]
            print("\n" + "-" * 50)
            print(f" HASIL AKHIR REGISTER : {resp_verif[3:].hex(' ')}")
            print(f" ADDRESS TERBACA      : {addr_baru} (0x{addr_baru:04X})")
            print(f" CHANNEL TERBACA      : {ch_baru} (0x{ch_baru:02X})")
            print("-" * 50)
            if ch_baru == 25:
                print(" ✓ SUKSES BESAR! Modul E220 Anda resmi berpindah ke CHANNEL 25!")
            else:
                print(" ! Catatan: Channel belum berubah ke 25.")

    m0.value = 0
    m1.value = 0
    m0.close()
    m1.close()
    aux.close()
    print("\n[5] Pin GPIO dikembalikan ke Mode Normal (M0=0, M1=0). Selesai.")

if __name__ == "__main__":
    main()

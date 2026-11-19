#!/usr/bin/env python3
"""Script satu kali jalan untuk mengatur register modul E220 ke Channel 25 secara permanen.

Konfigurasi sesuai EBYTE RF Setting Tool:
- Header perintah: 0xC0 0x00 0x08 (Tulis permanen mulai register 0x00 sebanyak 8 byte)
- Target parameter:
    ADDH    : 0x01 (Address = 259)
    ADDL    : 0x03
    REG0    : 0x62 (UART 9600 8N1, Air Rate 2.4 kbps)
    REG1    : 0x62 (128 bytes, Channel RSSI Enable, Power 13 dBm)
    REG2    : 0x19 (Channel 25)
    REG3    : 0x88 (Packet RSSI Enable, Normal Mode, WOR 500ms)
    CRYPT_H : 0x00
    CRYPT_L : 0x00

Cara Pakai:
1. Pasang kabel M0 (Pin 16 / GPIO23) dan M1 (Pin 18 / GPIO24).
   (Jika ada kabel AUX, pasang ke Pin 22 / GPIO25).
2. Jalankan: python set_channel25.py
3. Setelah tertulis OK, lepas kembali kabel M0 dan M1 (kembali ke mode 4-kabel).
4. Jalankan: python main.py
"""

import time
import serial

# Target konfigurasi 8 byte
TARGET_CFG = bytes([0x01, 0x03, 0x62, 0x62, 0x19, 0x88, 0x00, 0x00])

def main():
    print("=" * 60)
    print(" PROGRAM SETTING PERMANEN E220 KE CHANNEL 25 (EBYTE)")
    print("=" * 60)

    # Coba gunakan GPIO jika pin terpasang
    try:
        from gpiozero import DigitalInputDevice, DigitalOutputDevice
        m0 = DigitalOutputDevice(23)
        m1 = DigitalOutputDevice(24)
        has_gpio = True
        print("[GPIO] Mengatur pin M0=1, M1=1 (Mode Konfigurasi)...")
        m0.value = 1
        m1.value = 1
        time.sleep(0.15)
    except Exception as e:
        has_gpio = False
        print(f"[GPIO] Tidak mendeteksi GPIO ({e}). Pastikan pin M0 & M1 terhubung ke HIGH (3.3V).")

    with serial.Serial("/dev/serial0", 9600, timeout=1.5) as ser:
        ser.reset_input_buffer()

        # 1. Baca register saat ini
        print("\n[1] Membaca register saat ini...")
        ser.write(bytes([0xC1, 0x00, 0x08]))
        resp = ser.read(11)

        if len(resp) == 11 and resp[0] == 0xC1:
            curr_cfg = resp[3:]
            print(f"    Register terbaca  : {curr_cfg.hex(' ')}")
            print(f"    Channel sekarang  : {curr_cfg[4]} (0x{curr_cfg[4]:02X})")
        else:
            print(f"    Gagal membaca register (respons={resp.hex(' ') or 'kosong'}).")
            print("    TIPS: Pastikan pin M0 dan M1 terhubung ke 3.3V saat menjalankan script ini.")

        # 2. Tulis parameter permanen (C0)
        print("\n[2] Menulis konfigurasi Channel 25 (0xC0)...")
        cmd_write = bytes([0xC0, 0x00, 0x08]) + TARGET_CFG
        ser.write(cmd_write)
        resp_write = ser.read(11)

        if len(resp_write) == 11 and resp_write[0] == 0xC1:
            print("    ✓ SUKSES! Konfigurasi berhasil disimpan permanen ke EEPROM.")
            print(f"    Data tersimpan: {resp_write[3:].hex(' ')}")
        else:
            print(f"    ✗ Gagal menulis (respons={resp_write.hex(' ') or 'kosong'}).")

        # 3. Verifikasi ulang pembacaan
        print("\n[3] Memverifikasi hasil...")
        ser.reset_input_buffer()
        ser.write(bytes([0xC1, 0x00, 0x08]))
        resp_cek = ser.read(11)
        if len(resp_cek) == 11 and resp_cek[3:] == TARGET_CFG:
            print("    ✓ VERIFIKASI BERHASIL 100%! Modul E220 kini berada di Channel 25.")
        else:
            print(f"    Hasil verifikasi: {resp_cek[3:].hex(' ') if len(resp_cek) == 11 else 'gagal'}")

    # Kembalikan pin ke mode normal jika pakai GPIO
    if has_gpio:
        m0.value = 0
        m1.value = 0
        m0.close()
        m1.close()
        print("\n[GPIO] Pin M0 & M1 telah dikembalikan ke LOW (Mode Normal).")

    print("\n" + "=" * 60)
    print(" SELESAI. Lepas kembali kabel M0 dan M1, lalu jalankan:")
    print(" python main.py")
    print("=" * 60)

if __name__ == "__main__":
    main()

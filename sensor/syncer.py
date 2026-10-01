"""Sinkronisasi dinamis mapping gateway dari backend REST API.

Mengambil data node sensor, ID tangki, dan kapasitas dari endpoint:
  GET /api/gateways/{deviceCode}/sync
Header:
  X-gateway-key: {GATEWAY_SYNC_KEY}

Jika offline saat boot, modul ini memuat data dari cache lokal (gateway_cache.json).
"""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Optional


class GatewaySyncer:
    """Mengelola sinkronisasi konfigurasi node tangki ke backend."""

    def __init__(
        self,
        api_base_url: str,
        gateway_code: str,
        sync_key: str,
        cache_file: str = "gateway_cache.json",
    ):
        self.api_base_url = api_base_url.rstrip("/")
        self.gateway_code = gateway_code
        self.sync_key = sync_key
        self.cache_file = cache_file

        # Key: deviceCode (contoh: "STM32-ATA", atau "1") -> dict data mapping
        self.mappings: dict[str, dict[str, Any]] = {}

    def fetch_sync(self) -> bool:
        """Panggil endpoint backend untuk mendapatkan mapping tangki terbaru."""
        url = f"{self.api_base_url}/gateways/{self.gateway_code}/sync"
        headers = {
            "User-Agent": "Raspi-Gateway-Agent/1.0",
            "X-gateway-key": self.sync_key,
        }

        print(f"[Sync] Meminta konfigurasi ke {url} ...")
        req = urllib.request.Request(url, headers=headers, method="GET")

        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    if data.get("success"):
                        self._process_mappings(data.get("mappings", []))
                        self._save_cache(data)
                        print(f"[Sync] Berhasil sinkronisasi {len(self.mappings)} node tangki dari backend.")
                        return True
                    else:
                        print(f"[Sync] Gagal: respons backend success=false -> {data}")
        except urllib.error.HTTPError as e:
            print(f"[Sync] HTTP Error {e.code}: {e.reason}")
        except urllib.error.URLError as e:
            print(f"[Sync] Gagal menghubungi backend ({e.reason}). Mencoba memuat dari cache lokal...")
        except Exception as e:
            print(f"[Sync] Error saat sinkronisasi: {e}")

        # Jika gagal menghubungi backend, coba gunakan cache lokal
        return self._load_cache()

    def _process_mappings(self, mappings_list: list[dict[str, Any]]) -> None:
        """Simpan list mapping ke dictionary pencarian cepat (O(1))."""
        self.mappings.clear()
        for item in mappings_list:
            device_code = str(item.get("deviceCode", "")).strip()
            if device_code:
                # Konversi kapasitas ke float jika dalam bentuk string
                kapasitas = item.get("capacityLiters", 200.0)
                try:
                    kapasitas_float = float(kapasitas)
                except (ValueError, TypeError):
                    kapasitas_float = 200.0

                self.mappings[device_code] = {
                    "deviceCode": device_code,
                    "sensorNodeId": item.get("sensorNodeId"),
                    "tankId": item.get("tankId"),
                    "tankName": item.get("tankName", "Tangki"),
                    "capacityLiters": kapasitas_float,
                }

    def _save_cache(self, data: dict[str, Any]) -> None:
        """Simpan data mapping ke cache lokal agar tetap bisa jalan saat boot offline."""
        try:
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[Sync] Gagal menyimpan cache: {e}")

    def _load_cache(self) -> bool:
        """Muat data mapping dari cache lokal."""
        if not os.path.exists(self.cache_file):
            print("[Sync] Cache lokal tidak ditemukan.")
            return False

        try:
            with open(self.cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._process_mappings(data.get("mappings", []))
            print(f"[Sync] Berhasil memuat {len(self.mappings)} node tangki dari cache lokal.")
            return True
        except Exception as e:
            print(f"[Sync] Gagal membaca cache: {e}")
            return False

    def get_node(self, device_code: str) -> Optional[dict[str, Any]]:
        """Cari konfigurasi node berdasarkan kode perangkat."""
        return self.mappings.get(str(device_code).strip())

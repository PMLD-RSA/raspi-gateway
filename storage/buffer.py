"""Buffer lokal SQLite untuk pola Store-and-Forward.

Menyimpan payload ke database lokal jika koneksi MQTT terputus,
dan mengirimkannya kembali secara berurutan ketika koneksi pulih.
"""

import json
import sqlite3
from typing import Any, Optional


class MessageBuffer:
    """Buffer pesan SQLite untuk memastikan tidak ada data yang hilang saat offline."""

    def __init__(self, db_path: str = "buffer.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Buka koneksi baru ke SQLite (aman untuk multi-thread)."""
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        """Buat tabel antrean jika belum ada."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def simpan(self, topic: str, payload: dict[str, Any]) -> int:
        """Simpan payload yang gagal dikirim ke antrean lokal."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO pending_messages (topic, payload) VALUES (?, ?)",
                (topic, json.dumps(payload)),
            )
            conn.commit()
            return cursor.lastrowid

    def ambil_pesan_tertunda(self, limit: int = 50) -> list[tuple[int, str, dict[str, Any]]]:
        """Ambil antrean pesan tertua yang belum terkirim."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, topic, payload FROM pending_messages ORDER BY id ASC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
            hasil = []
            for row_id, topic, payload_str in rows:
                try:
                    payload = json.loads(payload_str)
                    hasil.append((row_id, topic, payload))
                except json.JSONDecodeError:
                    # Hapus data korup jika ada
                    self.hapus(row_id)
            return hasil

    def hapus(self, message_id: int) -> None:
        """Hapus pesan dari antrean setelah berhasil dipublish."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM pending_messages WHERE id = ?", (message_id,))
            conn.commit()

    def hitung_antrean(self) -> int:
        """Hitung jumlah pesan yang masih tertahan di buffer."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM pending_messages")
            return cursor.fetchone()[0]

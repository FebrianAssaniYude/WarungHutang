"""
Penguncian satu instance aplikasi.

Backup/restore dan penulisan database tidak boleh dilakukan oleh dua
proses sekaligus. Kunci ini dipasang saat startup dan dilepas saat
aplikasi berhenti. Jika proses mati mendadak, sistem operasi akan
melepas kunci secara otomatis.
"""

from __future__ import annotations

import os


class AlreadyRunningError(RuntimeError):
    """Aplikasi lain sudah memegang kunci instance."""


class SingleInstanceLock:
    def __init__(self, path: str):
        self.path = path
        self._file = None

    def acquire(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)

        lock_file = open(self.path, "a+b")

        try:
            # msvcrt.locking membutuhkan minimal satu byte pada file.
            if os.path.getsize(self.path) == 0:
                lock_file.write(b"\0")
                lock_file.flush()
                os.fsync(lock_file.fileno())

            lock_file.seek(0)

            if os.name == "nt":
                import msvcrt

                msvcrt.locking(
                    lock_file.fileno(),
                    msvcrt.LK_NBLCK,
                    1,
                )
            else:
                import fcntl

                fcntl.flock(
                    lock_file.fileno(),
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )
        except OSError as exc:
            lock_file.close()
            raise AlreadyRunningError(
                "Warung Hutang sudah berjalan di jendela lain. "
                "Tutup aplikasi yang sudah terbuka lalu coba lagi."
            ) from exc

        self._file = lock_file

    def release(self) -> None:
        if self._file is None:
            return

        try:
            self._file.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(
                    self._file.fileno(),
                    msvcrt.LK_UNLCK,
                    1,
                )
            else:
                import fcntl

                fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        finally:
            self._file.close()
            self._file = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()

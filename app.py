"""
app.py

Entry point aplikasi Warung Hutang.

PHASE 1: inisialisasi database.
PHASE 2: + halaman login.
PHASE 3: + main window (sidebar & navigasi) dan alur login <-> logout.

Alur aplikasi saat ini:
    1. Inisialisasi database (buat tabel + akun admin default jika perlu).
    2. Tampilkan halaman login.
    3. Jika login berhasil -> tampilkan main window (sidebar + halaman
       placeholder untuk tiap menu; isi sungguhan menyusul di phase
       berikutnya).
    4. Jika pengguna menekan Logout -> kembali ke halaman login.
    5. Jika jendela ditutup langsung (tombol X) di halaman manapun ->
       aplikasi berakhir sepenuhnya.
"""

import os

from database.database import Database, get_database_path
from views.login import LoginWindow
from views.main_window import MainWindow


def initialize_database_or_exit() -> Database:
    """
    Menyiapkan database saat startup. Jika gagal (mis. folder data/ tidak
    bisa ditulis, disk penuh, atau file database rusak/terkunci), tampilkan
    pesan yang mudah dipahami lalu keluar dengan rapi - JANGAN biarkan
    traceback Python mentah muncul ke pengguna awam, dan jangan lanjut
    berjalan dengan database yang belum siap (data tidak boleh hilang/rusak).
    """
    db = Database()
    try:
        db.initialize()
    except Exception as e:
        import sys
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Gagal Memulai Aplikasi",
            "Warung Hutang tidak bisa dijalankan karena database gagal disiapkan.\n\n"
            f"Lokasi database: {get_database_path()}\n\n"
            "Kemungkinan penyebab: folder tidak bisa ditulis, disk penuh, "
            "atau file database rusak.\n\n"
            "Coba jalankan aplikasi sebagai administrator, pastikan ada "
            "ruang kosong di disk, atau pulihkan dari file backup lewat "
            "menu Pengaturan > Restore Database (jika database sebelumnya "
            "masih ada).\n\n"
            f"Detail teknis: {e}",
        )
        root.destroy()
        sys.exit(1)

    return db


def run_login(db: Database):
    """Menampilkan halaman login dan menunggu sampai jendela ditutup.

    Returns:
        dict data user jika login berhasil, None jika jendela ditutup
        tanpa login berhasil (mis. pengguna menekan tombol X).
    """
    result = {"user": None}

    def on_login_success(user):
        result["user"] = user
        login_window.destroy()

    login_window = LoginWindow(on_login_success=on_login_success, db=db)
    login_window.mainloop()
    return result["user"]


def run_main_window(user: dict, db: Database) -> bool:
    """Menampilkan main window sampai jendela ditutup.

    Returns:
        True jika ditutup karena logout (harus kembali ke halaman login),
        False jika ditutup langsung lewat tombol X (aplikasi berakhir).
    """
    main_window = MainWindow(user=user, db=db)
    main_window.mainloop()
    return getattr(main_window, "logged_out", False)


def main():
    db = initialize_database_or_exit()

    print("=" * 50)
    print("Warung Hutang - Inisialisasi Database")
    print("=" * 50)
    print(f"Lokasi database : {get_database_path()}")
    print("Status          : Berhasil diinisialisasi.")
    print("Akun default    : username='admin', password='admin'")
    print("=" * 50)

    while True:
        user = run_login(db)
        if user is None:
            # Jendela login ditutup langsung tanpa login berhasil.
            break

        print(f"[LOGIN OK] Selamat datang, {user['username']}!")
        should_return_to_login = run_main_window(user, db)

        if not should_return_to_login:
            # Main window ditutup langsung (tombol X), bukan lewat Logout.
            break

        print("[LOGOUT] Kembali ke halaman login.")


def _log_crash_to_file(exc: Exception):
    """Mencatat detail teknis ke data/error.log - untuk troubleshooting,
    TANPA pernah menampilkan traceback mentah ini ke pengguna awam."""
    import traceback
    from datetime import datetime

    try:
        data_dir = os.path.dirname(get_database_path())
        log_path = os.path.join(data_dir, "error.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.now().isoformat()} ---\n")
            f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
        return log_path
    except Exception:
        return None


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 - jaring pengaman terakhir, sengaja luas
        log_path = _log_crash_to_file(e)
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            note = f"\n\nDetail kesalahan dicatat di:\n{log_path}" if log_path else ""
            messagebox.showerror(
                "Terjadi Kesalahan Tak Terduga",
                "Warung Hutang mengalami kesalahan dan harus ditutup.\n\n"
                "Data yang sudah tersimpan sebelumnya tetap aman di database - "
                "silakan buka kembali aplikasinya." + note,
            )
            root.destroy()
        except Exception:
            # Jika bahkan menampilkan dialog error pun gagal, sudah tidak ada
            # lagi yang bisa dilakukan selain berhenti tanpa traceback ke layar.
            pass

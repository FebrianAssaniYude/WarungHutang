"""
utils/error_handler.py

Jaring pengaman terakhir untuk error handling (PHASE 11).

Semua model & halaman sudah menangani error yang bisa diprediksi
(input kosong, angka tidak valid, dsb) dengan pesannya masing-masing.
Modul ini menangani sisanya: exception TAK TERDUGA yang lolos dari
seluruh lapisan validasi (mis. database terkunci, disk penuh, bug yang
belum ketahuan) - supaya:

1. Aplikasi TIDAK CRASH dan TIDAK menampilkan traceback Python ke
   pengguna awam.
2. Detail teknisnya tetap tercatat di file log untuk keperluan
   debugging oleh pengembang, tanpa mengganggu pengguna.

Cara kerja: CustomTkinter/Tkinter memanggil `report_callback_exception`
pada jendela root setiap kali sebuah callback (command tombol, event
binding, dsb) melempar exception yang tidak ditangkap. Ini berlaku juga
untuk semua CTkToplevel (dialog) yang dibuka dari jendela root tersebut,
karena mereka berbagi interpreter Tcl yang sama.
"""

import os
import traceback
from datetime import datetime


def get_log_path() -> str:
    """Lokasi file log, di folder data/ (folder yang sama dengan database)."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "error.log")


def log_error(error_text: str) -> None:
    """Menulis detail error ke file log. Kegagalan menulis log diabaikan
    secara sengaja - logging tidak boleh sampai menyebabkan crash baru."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(get_log_path(), "a", encoding="utf-8") as f:
            f.write(f"\n--- {timestamp} ---\n{error_text}\n")
    except Exception:
        pass


def install_global_error_handler(root) -> None:
    """
    Memasang handler global di jendela root (LoginWindow / MainWindow).
    Setelah dipasang, error tak terduga dari callback mana pun (termasuk
    dialog/Toplevel yang dibuka dari jendela ini) akan ditangani di sini,
    bukan menampilkan traceback atau membuat aplikasi berhenti merespons.
    """

    def handler(exc_type, exc_value, exc_traceback):
        error_text = "".join(
            traceback.format_exception(exc_type, exc_value, exc_traceback)
        )
        log_error(error_text)

        try:
            from tkinter import messagebox
            messagebox.showerror(
                "Terjadi Kesalahan",
                "Terjadi kesalahan yang tidak terduga.\n\n"
                "Aplikasi akan tetap berjalan. Silakan coba lagi. Jika "
                "masalah terus berulang, hubungi dukungan teknis dan "
                "sertakan file data/error.log.",
            )
        except Exception:
            # Kalaupun menampilkan dialog error itu sendiri gagal,
            # jangan sampai melempar exception baru dari sini.
            pass

    root.report_callback_exception = handler

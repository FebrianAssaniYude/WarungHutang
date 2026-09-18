"""
utils/barcode.py

Widget CustomTkinter khusus untuk menangani input dari barcode scanner
USB. Scanner semacam ini bekerja sebagai keyboard (HID) - tidak butuh
driver khusus: ia hanya "mengetik" karakter barcode dengan sangat cepat
lalu menekan Enter di akhir.

BarcodeScanEntry menangkap event Enter itu, memanggil callback dengan
kode yang berhasil di-scan, lalu membersihkan input dan mengembalikan
fokus ke dirinya sendiri - supaya pengguna bisa langsung scan barang
berikutnya tanpa harus klik mouse lagi.
"""

import customtkinter as ctk


class BarcodeScanEntry(ctk.CTkEntry):
    def __init__(self, master, on_scan, **kwargs):
        """
        Args:
            on_scan: callback dipanggil dengan satu argumen (kode barcode
                     yang di-scan, sudah di-strip). Tidak dipanggil jika
                     kode kosong (mis. Enter ditekan tanpa isi).
        """
        super().__init__(master, **kwargs)
        self.on_scan = on_scan
        self.bind("<Return>", self._handle_enter)

    def _handle_enter(self, event=None):
        code = self.get().strip()
        self.delete(0, "end")
        if code and self.on_scan:
            self.on_scan(code)
        # Fokus tetap di input ini agar siap untuk scan berikutnya
        # (alur: Scan -> Scan -> Scan -> Scan -> Simpan, tanpa mouse).
        self.focus_set()

    def refocus(self):
        """Dipanggil dari luar setelah dialog lain (mis. konfirmasi) ditutup."""
        self.focus_set()

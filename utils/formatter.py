"""
utils/formatter.py

Fungsi format tampilan: Rupiah dan tanggal berformat Indonesia.
Data di database TETAP berupa angka (integer) dan tanggal ISO biasa -
formatter ini hanya dipakai saat menampilkan ke layar.
"""

from datetime import datetime

_BULAN_INDONESIA = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]

# Alias publik - dipakai modul lain (mis. halaman Laporan) untuk dropdown bulan.
BULAN_INDONESIA = _BULAN_INDONESIA


def format_rupiah(amount) -> str:
    """
    Mengubah angka menjadi format "Rp 1.250.000".
    Menerima int/float; nilai non-numerik dianggap 0 agar tidak crash.
    """
    try:
        amount = int(round(float(amount)))
    except (TypeError, ValueError):
        amount = 0

    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    grouped = f"{amount:,}".replace(",", ".")
    return f"{sign}Rp {grouped}"


def format_date_indonesia(date_str: str) -> str:
    """
    Mengubah string tanggal ("YYYY-MM-DD" atau "YYYY-MM-DD HH:MM:SS")
    menjadi format "11 September 2026". Mengembalikan string asli
    (atau "-") jika gagal di-parse, tanpa melempar exception.
    """
    if not date_str:
        return "-"

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(date_str[:19] if " " in fmt else date_str[:10], fmt)
            return f"{dt.day} {_BULAN_INDONESIA[dt.month - 1]} {dt.year}"
        except ValueError:
            continue

    return date_str

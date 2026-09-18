# -*- mode: python ; coding: utf-8 -*-
"""
build.spec - Konfigurasi PyInstaller untuk membangun WarungHutang.exe

CARA PAKAI:
    pyinstaller build.spec

Hasil build ada di folder dist/WarungHutang/ (mode "onedir" - satu folder
berisi WarungHutang.exe beserta file pendukungnya). Ini direkomendasikan
untuk aplikasi CustomTkinter karena lebih andal memuat aset tema & font
dibanding mode "onefile", dan startup-nya lebih cepat (tidak perlu
mengekstrak ulang setiap kali dijalankan).

File .exe utama ada di:
    dist/WarungHutang/WarungHutang.exe

Folder dist/WarungHutang/ inilah yang didistribusikan ke PC warung -
salin SELURUH folder ini, jangan hanya file .exe-nya saja.

Catatan:
- Data (schema.sql, aset tema CustomTkinter, data font reportlab)
  disertakan secara eksplisit lewat parameter `datas` di bawah, karena
  file non-Python semacam ini tidak ikut ter-bundle otomatis hanya
  dengan analisis import biasa.
- Ganti `icon=None` di bagian EXE jika warung punya logo sendiri
  (siapkan file .ico, taruh di assets/, lalu isi path-nya di sini).
"""

from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# CustomTkinter menyimpan file tema (.json) dan font di dalam paketnya
# sendiri - tanpa ini, aplikasi akan error "tidak menemukan file tema"
# begitu dijalankan sebagai .exe walau berjalan normal saat development.
customtkinter_datas = collect_data_files("customtkinter")

# reportlab menyimpan data font/encoding internal untuk 14 font standar
# yang dipakai fitur export PDF (Laporan Bulanan) - sertakan juga supaya
# export PDF tetap berfungsi di versi .exe.
reportlab_datas = collect_data_files("reportlab")

a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("database/schema.sql", "database"),
    ] + customtkinter_datas + reportlab_datas,
    hiddenimports=[
        "PIL._tkinter_finder",  # dibutuhkan CustomTkinter untuk render gambar di Tkinter
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WarungHutang",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # False = tanpa jendela konsol hitam (aplikasi GUI biasa)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico",  # contoh: "assets/icon.ico" jika punya logo warung
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="WarungHutang",
)

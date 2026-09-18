# Warung Hutang

Aplikasi desktop offline untuk pencatatan hutang pelanggan warung kecil.
Berjalan 100% lokal di satu PC — tanpa server, tanpa internet, tanpa cloud.

> **Status:** PHASE 13 — PyInstaller + `.exe` (SELESAI - semua 13 phase rampung).
> `build.spec` sudah dikonfigurasi lengkap: mode "onedir" (lebih andal
> untuk CustomTkinter dibanding "onefile"), menyertakan `schema.sql`,
> aset tema CustomTkinter, data font reportlab (untuk export PDF), dan
> hidden import `PIL._tkinter_finder` yang dibutuhkan CustomTkinter.
> Jalankan `build.bat` untuk build otomatis. **Catatan jujur**: saya
> tidak bisa menjalankan PyInstaller sungguhan di lingkungan saya (tidak
> ada Windows/tkinter di sandbox saya), jadi build ini BELUM pernah
> benar-benar dieksekusi - wajib kamu coba di PC Windows dan kabari jika
> ada error, supaya bisa saya perbaiki.

## Menjalankan test otomatis

```
pip install -r requirements.txt
python tests/test_integration.py
```
Skrip ini memakai database sementara di folder temp sistem (tidak
menyentuh `data/warung.db` asli) dan menghapusnya lagi setelah selesai.
Jalankan ini kapan pun setelah mengubah kode, untuk memastikan alur inti
(hutang, pembayaran, saldo, backup/restore) masih benar.

## Menjalankan (development)

1. Pastikan Python 3.x terpasang.
2. Install dependency:
   ```
   pip install -r requirements.txt
   ```
3. Jalankan:
   ```
   python app.py
   ```

Perintah di atas akan membuat folder `data/` beserta file `data/warung.db`
dan seluruh tabel yang diperlukan, serta membuat akun login default:

- **Username:** `admin`
- **Password:** `admin`

(Password ini di-hash dengan bcrypt sebelum disimpan — tidak pernah
disimpan sebagai teks biasa. Nanti bisa diganti lewat menu Pengaturan.)

## Lokasi database

`data/warung.db` (relatif terhadap folder aplikasi). Saat sudah menjadi
`.exe`, database tetap disimpan di folder `data/` di sebelah file `.exe`.

## Cara membuat file .exe (Windows)

Build otomatis:
```
build.bat
```
Ini akan memasang PyInstaller, membersihkan hasil build lama, lalu
menjalankan `pyinstaller build.spec`. Hasilnya ada di:
```
dist\WarungHutang\WarungHutang.exe
```
**Salin SELURUH folder `dist\WarungHutang\`** untuk didistribusikan ke
PC warung — bukan cuma file `.exe`-nya saja, karena folder ini juga
berisi file-file pendukung yang dibutuhkan `.exe` untuk berjalan.

Atau manual, langkah demi langkah:
```
pip install -r requirements-dev.txt
pyinstaller build.spec
```

User tidak perlu menginstal Python, XAMPP, Laragon, atau apa pun —
cukup jalankan `WarungHutang.exe`, folder `data/` beserta database akan
otomatis dibuat di sebelahnya saat pertama kali dijalankan.

### Kenapa mode "onedir", bukan "onefile"?

`build.spec` sengaja memakai mode onedir (hasil: satu folder berisi
`.exe` + file pendukung) alih-alih onefile (satu file `.exe` tunggal).
Alasannya: CustomTkinter menyimpan file tema (`.json`) yang perlu
diekstrak ke disk saat aplikasi jalan — pada mode onefile ini
terkadang gagal dimuat pada beberapa versi Windows/antivirus, dan
startup-nya lebih lambat karena harus mengekstrak ulang setiap kali
dibuka. Onedir lebih andal untuk kasus ini.

### Menambahkan ikon aplikasi (opsional)

Siapkan file `.ico`, taruh di `assets/icon.ico`, lalu di `build.spec`
ubah baris `icon=None` menjadi `icon="assets/icon.ico"`.

### Troubleshooting build

- **"ModuleNotFoundError" saat menjalankan .exe hasil build** — biasanya
  ada import yang tidak terdeteksi otomatis oleh PyInstaller. Tambahkan
  nama modulnya ke daftar `hiddenimports` di `build.spec`, lalu build ulang.
- **Aplikasi langsung tertutup tanpa pesan error saat .exe dijalankan** —
  jalankan dulu lewat Command Prompt (bukan double-click) supaya pesan
  error (jika ada) terlihat: `dist\WarungHutang\WarungHutang.exe`.
  Bisa juga cek `data/error.log` di sebelah `.exe` (dibuat otomatis oleh
  jaring pengaman error di `utils/error_handler.py` dan `app.py`).
- **Antivirus menandai .exe sebagai mencurigakan** — ini hal umum untuk
  aplikasi hasil PyInstaller yang belum ditandatangani (code signing).
  Tambahkan pengecualian di antivirus, atau pertimbangkan code signing
  jika akan didistribusikan lebih luas.
- **Export PDF Laporan Bulanan error setelah jadi .exe** — pastikan
  `reportlab_datas` di `build.spec` tidak dihapus; ini menyertakan data
  font internal reportlab yang dibutuhkan saat runtime.
- **Warna/tema CustomTkinter terlihat rusak atau error "can't find theme"**
  — pastikan `customtkinter_datas` di `build.spec` tidak dihapus.

**Catatan penting**: konfigurasi `build.spec` ini disusun mengikuti
best practice PyInstaller + CustomTkinter yang umum dipakai, tapi belum
pernah benar-benar dijalankan sampai jadi `.exe` (lingkungan pengembangan
ini tidak punya Windows/tkinter). Coba build di PC Windows kamu dan
kabari saya persis pesan errornya jika ada — akan saya perbaiki
`build.spec`-nya berdasarkan error itu.

## Struktur project (sejauh ini)

```
warung-hutang/
  app.py                  # entry point (alur: login -> main window -> logout)
  requirements.txt
  requirements-dev.txt      # + PyInstaller, hanya dibutuhkan untuk build .exe
  build.spec                 # konfigurasi PyInstaller
  build.bat                   # script build otomatis (Windows)
  README.md
  database/
    database.py            # koneksi, inisialisasi, transaksi aman
    schema.sql              # definisi seluruh tabel
  models/
    user.py                 # autentikasi, ganti username/password
    customer.py              # CRUD pelanggan + perhitungan saldo hutang
    product.py                # CRUD barang + pencarian barcode
    debt.py                    # transaksi hutang (header + detail, atomik)
    payment.py                  # pembayaran (validasi tidak boleh melebihi sisa)
    history.py                   # gabungan riwayat hutang+pembayaran, dengan filter
    report.py                     # laporan bulanan + export PDF (reportlab)
    settings.py                    # pengaturan (key-value: nama warung, dll)
  views/
    login.py                # halaman login
    main_window.py           # sidebar + navigasi
    customers.py             # halaman Pelanggan (daftar, form, detail)
    products.py               # halaman Barang (daftar, form, scan barcode)
    debts.py                   # halaman Transaksi Hutang (scan -> keranjang -> simpan)
    payments.py                 # halaman Pembayaran (pilih pelanggan -> bayar)
    history.py                   # halaman Riwayat (filter jenis/pelanggan/tanggal)
    reports.py                    # halaman Laporan Bulanan (ringkasan + export PDF)
    settings.py                    # halaman Pengaturan (warung, akun, backup/restore)
  utils/
    security.py             # hashing & verifikasi password (bcrypt)
    formatter.py             # format Rupiah & tanggal Indonesia
    barcode.py                # widget input barcode scanner (HID)
    backup.py                  # backup & restore database (dengan safety-backup)
    error_handler.py            # jaring pengaman global untuk error tak terduga di GUI
  data/
    warung.db               # dibuat otomatis saat pertama dijalankan
  tests/
    test_integration.py      # uji end-to-end seluruh alur (Phase 12)
```

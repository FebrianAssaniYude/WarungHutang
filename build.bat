@echo off
setlocal

echo ============================================
echo   Build WarungHutang.exe
echo ============================================
echo.

echo [1/4] Memasang dependency (termasuk PyInstaller)...
pip install -r requirements-dev.txt
if errorlevel 1 (
    echo.
    echo GAGAL memasang dependency. Periksa koneksi internet dan instalasi Python/pip.
    pause
    exit /b 1
)

echo.
echo [2/4] Membersihkan hasil build sebelumnya (jika ada)...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo.
echo [3/4] Menjalankan PyInstaller (build.spec)...
pyinstaller build.spec
if errorlevel 1 (
    echo.
    echo GAGAL saat build. Lihat pesan error PyInstaller di atas.
    pause
    exit /b 1
)

echo.
echo [4/4] Selesai!
echo.
echo Hasil build ada di:  dist\WarungHutang\WarungHutang.exe
echo Salin SELURUH folder dist\WarungHutang\ untuk didistribusikan
echo ke PC warung - jangan hanya file .exe-nya saja.
echo.
pause

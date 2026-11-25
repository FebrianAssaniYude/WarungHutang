import pytest


# test_integration.py adalah skrip pemeriksaan manual yang menjalankan
# seluruh alurnya saat diimpor. Jangan biarkan pytest mengeksekusinya
# sebagai efek samping koleksi. Jalankan manual dengan:
#     python tests/test_integration.py
collect_ignore = ["test_integration.py"]


@pytest.fixture
def temp_dir(tmp_path):
    """Folder sementara untuk test migrasi lama."""
    return str(tmp_path)

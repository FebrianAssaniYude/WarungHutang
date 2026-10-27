import os
import shutil
import sqlite3
import tempfile
import unittest

from database.database import Database
from models.settings import (
    SettingsModel,
    KEY_NAMA_WARUNG,
    DEFAULT_NAMA_WARUNG,
)
from utils.backup import backup_database, restore_database


class SettingsBackupTest(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()

        self.db_path = os.path.join(
            self.temp_dir,
            "warung.db",
        )

        self.backup_dir = os.path.join(
            self.temp_dir,
            "backup",
        )

        self.db = Database(self.db_path)
        self.db.initialize()

        self.settings = SettingsModel(self.db)

    def tearDown(self):
        shutil.rmtree(
            self.temp_dir,
            ignore_errors=True,
        )

    def test_default_nama_warung(self):
        self.assertEqual(
            self.settings.get_nama_warung(),
            DEFAULT_NAMA_WARUNG,
        )

    def test_set_nama_warung(self):
        saved = self.settings.set_nama_warung(
            "Warung Febrian"
        )

        self.assertEqual(
            saved,
            "Warung Febrian",
        )

        self.assertEqual(
            self.settings.get_nama_warung(),
            "Warung Febrian",
        )

    def test_empty_nama_warung_uses_default(self):
        saved = self.settings.set_nama_warung("")

        self.assertEqual(
            saved,
            DEFAULT_NAMA_WARUNG,
        )

        self.assertEqual(
            self.settings.get_nama_warung(),
            DEFAULT_NAMA_WARUNG,
        )

    def test_backup_database(self):
        self.settings.set_nama_warung(
            "Warung Backup Test"
        )

        backup_path = backup_database(
            self.db_path,
            self.backup_dir,
        )

        self.assertTrue(
            os.path.exists(backup_path)
        )

        self.assertTrue(
            backup_path.startswith(self.backup_dir)
        )

        backup_db = Database(backup_path)

        self.assertEqual(
            SettingsModel(
                backup_db
            ).get_nama_warung(),
            "Warung Backup Test",
        )

    def test_restore_database(self):
        # Database aktif
        self.settings.set_nama_warung(
            "Database Aktif"
        )

        # Buat backup dengan isi tertentu
        backup_source_path = os.path.join(
            self.temp_dir,
            "backup_source.db",
        )

        source_db = Database(
            backup_source_path
        )

        source_db.initialize()

        source_settings = SettingsModel(
            source_db
        )

        source_settings.set_nama_warung(
            "Database Backup"
        )

        backup_path = backup_database(
            backup_source_path,
            self.backup_dir,
        )

        # Restore ke database aktif
        safety_path = restore_database(
            backup_path,
            self.db_path,
        )

        self.assertIsNotNone(
            safety_path
        )

        self.assertTrue(
            os.path.exists(safety_path)
        )

        # Koneksi baru harus membaca database hasil restore
        restored_db = Database(
            self.db_path
        )

        restored_settings = SettingsModel(
            restored_db
        )

        self.assertEqual(
            restored_settings.get_nama_warung(),
            "Database Backup",
        )

    def test_backup_does_not_overwrite_same_minute(self):
        first = backup_database(
            self.db_path,
            self.backup_dir,
        )

        second = backup_database(
            self.db_path,
            self.backup_dir,
        )

        self.assertNotEqual(
            first,
            second,
        )

        self.assertTrue(
            os.path.exists(first)
        )

        self.assertTrue(
            os.path.exists(second)
        )


if __name__ == "__main__":
    unittest.main()
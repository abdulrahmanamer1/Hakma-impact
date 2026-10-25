import os
import shutil
import stat
import tempfile
import unittest
import zipfile
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backup_safety import safe_extract_backup_zip


class BackupArchiveSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="backup-safety-test-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _zip(self, entries):
        path = os.path.join(self.tmp, "fixture.zip")
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, payload in entries:
                archive.writestr(name, payload)
        return path

    def test_valid_backup_extracts_expected_files(self):
        path = self._zip([
            ("data/ahvt.sqlite", b"sqlite-placeholder"),
            ("manifest.json", b'{"version":44}'),
            ("uploads/image.jpg", b"image"),
        ])
        target = os.path.join(self.tmp, "out")
        os.makedirs(target)
        with zipfile.ZipFile(path) as archive:
            safe_extract_backup_zip(archive, target)
        self.assertTrue(os.path.isfile(os.path.join(target, "data", "ahvt.sqlite")))
        self.assertTrue(os.path.isfile(os.path.join(target, "uploads", "image.jpg")))

    def test_zip_slip_path_is_rejected(self):
        path = self._zip([
            ("data/ahvt.sqlite", b"db"),
            ("uploads/../../outside.txt", b"no"),
        ])
        target = os.path.join(self.tmp, "out")
        os.makedirs(target)
        with zipfile.ZipFile(path) as archive:
            with self.assertRaises(ValueError):
                safe_extract_backup_zip(archive, target)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "outside.txt")))

    def test_windows_style_traversal_is_rejected(self):
        path = self._zip([
            ("data/ahvt.sqlite", b"db"),
            (r"uploads\\..\\..\\outside.txt", b"no"),
        ])
        target = os.path.join(self.tmp, "out")
        os.makedirs(target)
        with zipfile.ZipFile(path) as archive:
            with self.assertRaises(ValueError):
                safe_extract_backup_zip(archive, target)

    def test_symlink_member_is_rejected(self):
        path = os.path.join(self.tmp, "symlink.zip")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("data/ahvt.sqlite", b"db")
            link = zipfile.ZipInfo("uploads/link")
            link.create_system = 3
            link.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(link, "../data/ahvt.sqlite")
        target = os.path.join(self.tmp, "out")
        os.makedirs(target)
        with zipfile.ZipFile(path) as archive:
            with self.assertRaises(ValueError):
                safe_extract_backup_zip(archive, target)

    def test_unexpected_member_is_rejected(self):
        path = self._zip([
            ("data/ahvt.sqlite", b"db"),
            ("evil.py", b"print('no')"),
        ])
        target = os.path.join(self.tmp, "out")
        os.makedirs(target)
        with zipfile.ZipFile(path) as archive:
            with self.assertRaises(ValueError):
                safe_extract_backup_zip(archive, target)

    def test_duplicate_members_are_rejected(self):
        path = self._zip([
            ("data/ahvt.sqlite", b"db1"),
            ("data/ahvt.sqlite", b"db2"),
        ])
        target = os.path.join(self.tmp, "out")
        os.makedirs(target)
        with zipfile.ZipFile(path) as archive:
            with self.assertRaises(ValueError):
                safe_extract_backup_zip(archive, target)


if __name__ == "__main__":
    unittest.main(verbosity=2)

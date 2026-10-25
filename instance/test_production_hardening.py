"""Production-hardening smoke tests. Run with: python -m unittest discover -s tests -v"""
import os
import tempfile
import unittest

_TEST_DATA = tempfile.mkdtemp(prefix="hikma-prod-tests-")
os.environ["HIKMA_DATA_DIR"] = _TEST_DATA
os.environ["HIKMA_ENV"] = "production"
os.environ["HIKMA_COOKIE_SECURE"] = "1"
os.environ["HIKMA_SECRET_KEY"] = "test-only-secret-key-with-enough-entropy-0123456789"
os.environ["HIKMA_OWNER_EMAIL"] = "test-owner@example.invalid"
os.environ["HIKMA_OWNER_PASSWORD"] = "Test-Only-Owner-Passphrase-2026!"

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app as app_module

app_module.app.config.update(TESTING=True)


class ProductionHardeningTests(unittest.TestCase):
    def setUp(self):
        self.client = app_module.app.test_client()

    def test_health_and_readiness(self):
        self.assertEqual(self.client.get("/healthz").status_code, 200)
        response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["database"], "ok")

    def test_security_headers_and_secure_cookie_config(self):
        response = self.client.get("/healthz")
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(response.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertIn("max-age=31536000", response.headers.get("Strict-Transport-Security", ""))
        self.assertTrue(app_module.app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertTrue(app_module.app.config["SESSION_COOKIE_SECURE"])
        self.assertEqual(app_module.app.config["SESSION_COOKIE_SAMESITE"], "Lax")

    def test_cross_origin_write_is_rejected(self):
        response = self.client.post(
            "/admin/login",
            data={"email": "nobody@example.invalid", "password": "wrong"},
            headers={"Origin": "https://attacker.invalid"},
        )
        self.assertEqual(response.status_code, 403)

    def test_login_attempts_are_rate_limited(self):
        for _ in range(8):
            self.client.post("/admin/login", data={
                "email": "not-a-real-user@example.invalid", "password": "wrong"
            }, environ_base={"REMOTE_ADDR": "198.51.100.99"})
        with app_module.app.app_context():
            row = app_module.get_db().execute(
                "SELECT failed_count, blocked_until FROM login_attempts WHERE ip=?",
                ("198.51.100.99",),
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["failed_count"], 8)
            self.assertTrue(row["blocked_until"])

    def test_anonymous_cannot_export_backup(self):
        response = self.client.get("/backup/export", follow_redirects=False)
        self.assertIn(response.status_code, (302, 401, 403))

    def test_task_attachment_is_not_publicly_served(self):
        filename = "task-private-test.pdf"
        path = os.path.join(app_module.UPLOAD_DIR, filename)
        with open(path, "wb") as handle:
            handle.write(b"private")
        try:
            response = self.client.get("/uploads/" + filename)
            self.assertEqual(response.status_code, 404)
        finally:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    def test_chat_media_is_not_publicly_served(self):
        filename = "chat-private-test.jpg"
        path = os.path.join(app_module.UPLOAD_DIR, filename)
        with open(path, "wb") as handle:
            handle.write(b"private")
        try:
            self.assertEqual(self.client.get("/uploads/" + filename).status_code, 404)
            self.assertIn(self.client.get("/chat/media/not-a-message").status_code, (302, 401))
        finally:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    def test_owner_can_export_json_backup_with_new_tables(self):
        response = self.client.post("/admin/login", data={
            "email": "test-owner@example.invalid",
            "password": "Test-Only-Owner-Passphrase-2026!",
        }, follow_redirects=False)
        self.assertIn(response.status_code, (302, 303))
        backup = self.client.get("/backup/export")
        self.assertEqual(backup.status_code, 200)
        payload = backup.get_json()
        self.assertIn("task_attachments", payload["tables"])
        self.assertIn("team_announcements", payload["tables"])
        self.assertIn("announcement_reads", payload["tables"])
        self.assertIn("login_attempts", payload["tables"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

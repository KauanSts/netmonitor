import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
import database as db


class DeviceWebTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = str(Path(temp.name) / "web.sqlite3")
        self.app = create_app({"TESTING": True, "DATABASE": self.path, "SECRET_KEY": "test-only"})
        self.client = self.app.test_client()
        self.token = self.get_token(self.client)

    def get_token(self, client):
        response = client.get("/devices/new")
        return re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))[1]

    def post(self, path, **data):
        return self.client.post(path, data={"csrf_token": self.token, **data}, follow_redirects=True)

    def add(self, address="::1", name="Local"):
        return self.post("/devices/new", name=name, address=address, device_type="computador", description="Teste")

    def test_create_list_edit_lookup_and_delete(self):
        response = self.add()
        self.assertEqual(response.status_code, 200)
        self.assertIn("::1", response.get_data(as_text=True))
        device = db.list_devices(self.path)[0]
        device_id = device["id"]
        response = self.client.get(f"/devices/{device_id}/edit")
        self.assertIn('value="Local"', response.get_data(as_text=True))
        response = self.post(f"/devices/{device_id}/edit", name="Renomeado", address="127.0.0.1", device_type="servidor")
        self.assertIn("Renomeado", response.get_data(as_text=True))
        self.assertEqual(db.get_device(self.path, device_id)["address"], "127.0.0.1")
        response = self.client.get(f"/devices/{device_id}/delete")
        self.assertIn("Confirmo a exclusão", response.get_data(as_text=True))
        self.assertEqual(len(db.list_devices(self.path)), 1)
        self.assertEqual(self.post(f"/devices/{device_id}/delete").status_code, 400)
        self.assertEqual(self.post(f"/devices/{device_id}/delete", confirm="yes").status_code, 200)
        self.assertEqual(db.list_devices(self.path), [])

    def test_invalid_and_duplicate_form(self):
        self.assertEqual(self.add("https://example.com").status_code, 400)
        self.add("Example.COM.")
        response = self.add("example.com")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Já existe", response.get_data(as_text=True))
        self.assertEqual(len(db.list_devices(self.path)), 1)

    def test_unknown_devices(self):
        for route in ("edit", "delete", "history"):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(f"/devices/999/{route}").status_code, 404)
        with patch("app.check_connectivity") as ping:
            self.assertEqual(self.post("/devices/999/check").status_code, 404)
            ping.assert_not_called()

    def test_csrf_all_mutations(self):
        self.add()
        device_id = db.list_devices(self.path)[0]["id"]
        for route in ("/devices/new", f"/devices/{device_id}/edit",
                      f"/devices/{device_id}/delete", f"/devices/{device_id}/check"):
            for token in (None, "wrong", "inválido"):
                with self.subTest(route=route, token=token), patch("app.check_connectivity") as ping:
                    data = {"confirm": "yes"}
                    if token is not None:
                        data["csrf_token"] = token
                    self.assertEqual(self.client.post(route, data=data).status_code, 400)
                    ping.assert_not_called()
        self.assertEqual(len(db.list_devices(self.path)), 1)
        self.assertEqual(db.get_history(self.path, device_id), [])

    def test_token_is_bound_to_session(self):
        other = self.app.test_client()
        self.get_token(other)
        self.assertEqual(other.post("/devices/new", data={"csrf_token": self.token}).status_code, 400)

    def test_manual_check_persists_and_renders_all_results(self):
        self.add()
        device_id = db.list_devices(self.path)[0]["id"]
        for status in ("online", "offline", "timeout", "error"):
            result = dict(target="::1", status=status, latency_ms=1.0 if status == "online" else None,
                          latency_is_upper_bound=status == "online", error="Falha simulada" if status != "online" else None)
            with self.subTest(status=status), patch("app.check_connectivity", return_value=result) as ping:
                response = self.post(f"/devices/{device_id}/check")
                self.assertEqual(response.status_code, 200)
                self.assertIn(f"<strong>{status}</strong>", response.get_data(as_text=True))
                ping.assert_called_once_with("::1")
        self.assertEqual(len(db.get_history(self.path, device_id)), 4)
        history = self.client.get(f"/devices/{device_id}/history").get_data(as_text=True)
        self.assertIn("&lt;1.0 ms", history)
        self.assertIn("Falha simulada", history)
        self.post(f"/devices/{device_id}/delete", confirm="yes")
        self.assertEqual(db.get_history(self.path, device_id), [])

    def test_escaped_user_input(self):
        self.add(name='<script>alert("x")</script>')
        html = self.client.get("/").get_data(as_text=True)
        self.assertNotIn('<script>alert("x")</script>', html)
        self.assertIn("&lt;script&gt;", html)

    def test_check_is_post_only(self):
        self.add()
        device_id = db.list_devices(self.path)[0]["id"]
        with patch("app.check_connectivity") as ping:
            self.assertEqual(self.client.get(f"/devices/{device_id}/check").status_code, 405)
            self.client.get("/")
            ping.assert_not_called()

    def test_untrusted_host_rejected(self):
        self.assertEqual(self.client.get("/", headers={"Host": "attacker.test"}).status_code, 400)

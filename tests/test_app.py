import unittest
from app import app


class AppTests(unittest.TestCase):
    def test_home(self):
        with app.test_client() as client:
            response = client.get("/")
            self.assertEqual(response.status_code, 200)
            self.assertIn("O NetMonitor está funcionando.", response.get_data(as_text=True))
            for path in ("/static/css/style.css", "/static/js/main.js"):
                asset = client.get(path)
                self.assertEqual(asset.status_code, 200)
                asset.close()

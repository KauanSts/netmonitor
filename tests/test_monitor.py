import subprocess
import unittest
from unittest.mock import patch

from monitor import check_connectivity


class ConnectivityTests(unittest.TestCase):
    def run_ping(self, output, code=0, system="Linux"):
        with patch("monitor.platform.system", return_value=system), patch(
            "monitor.subprocess.run", return_value=subprocess.CompletedProcess([], code, output, "")
        ) as run:
            result = check_connectivity("example.test")
            return result, run.call_args

    def test_linux_success(self):
        result, call = self.run_ping("64 bytes: time=12.4 ms TTL=64")
        self.assertEqual(result["status"], "online")
        self.assertEqual(result["latency_ms"], 12.4)
        self.assertEqual(call.args[0], ["ping", "-4", "-n", "-c", "1", "-W", "2", "example.test"])
        self.assertNotIn("shell", call.kwargs)

    def test_windows_success(self):
        result, call = self.run_ping("Resposta: bytes=32 tempo<1ms TTL=128", system="Windows")
        self.assertEqual(result["status"], "online")
        self.assertEqual(result["latency_ms"], 1.0)
        self.assertTrue(result["latency_is_upper_bound"])
        self.assertEqual(call.args[0], ["ping", "-4", "-n", "1", "-w", "2000", "example.test"])

    def test_decimal_comma(self):
        result, _ = self.run_ping("tempo=2,5 ms TTL=64")
        self.assertEqual(result["latency_ms"], 2.5)

    def test_success_without_latency(self):
        result, _ = self.run_ping("Reply: bytes=32 TTL=64")
        self.assertEqual(result["status"], "online")
        self.assertIsNone(result["latency_ms"])

    def test_offline(self):
        result, _ = self.run_ping("Destination Host Unreachable", code=1)
        self.assertEqual(result["status"], "offline")

    def test_windows_unreachable_with_zero_exit(self):
        result, _ = self.run_ping("Reply: Destination host unreachable.", system="Windows")
        self.assertEqual(result["status"], "offline")

    def test_timeout_output(self):
        for output in ["Request timed out.", "Esgotado o tempo limite do pedido.", "100% packet loss"]:
            with self.subTest(output=output):
                result, _ = self.run_ping(output, code=1)
                self.assertEqual(result["status"], "timeout")

    @patch("monitor.subprocess.run", side_effect=subprocess.TimeoutExpired("ping", 3))
    @patch("monitor.platform.system", return_value="Linux")
    def test_process_timeout(self, system, run):
        self.assertEqual(check_connectivity("127.0.0.1")["status"], "timeout")

    @patch("monitor.subprocess.run", side_effect=FileNotFoundError("ping"))
    @patch("monitor.platform.system", return_value="Linux")
    def test_missing_ping(self, system, run):
        self.assertEqual(check_connectivity("localhost")["status"], "error")

    def test_command_error(self):
        result, _ = self.run_ping("Name or service not known", code=2)
        self.assertEqual(result["status"], "error")

    @patch("monitor.subprocess.run")
    def test_invalid_target(self, run):
        for target in ["", "-c", "example.com;whoami", "https://example.com", "999.1.1.1", "::1", "a..b", " a.com", None]:
            with self.subTest(target=target), self.assertRaises(ValueError):
                check_connectivity(target)
        run.assert_not_called()

    def test_invalid_timeout(self):
        for timeout in [0, -1, float("nan"), float("inf"), True, 61, "2"]:
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                check_connectivity("localhost", timeout)

    @patch("monitor.platform.system", return_value="Darwin")
    @patch("monitor.subprocess.run")
    def test_unsupported_platform(self, run, system):
        self.assertEqual(check_connectivity("localhost")["status"], "error")
        run.assert_not_called()

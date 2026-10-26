import subprocess
import unittest
from unittest.mock import patch

from monitor import check_connectivity, validate_target


class IPv6Tests(unittest.TestCase):
    def test_valid_addresses(self):
        for target, normalized in [("::1", "::1"), ("2001:0DB8:0:0::1", "2001:db8::1"),
                                   ("192.168.1.1", "192.168.1.1"), ("example.test", "example.test")]:
            with self.subTest(target=target):
                self.assertEqual(validate_target(target), normalized)

    def test_mapped_ipv6_normalization(self):
        self.assertEqual(validate_target("::ffff:192.0.2.1"), validate_target("::ffff:c000:201"))

    @patch("monitor.subprocess.run")
    def test_invalid_ipv6_and_injection(self, run):
        for target in [":::1", "2001:db8::xyz", "1::2::3", "[::1]", "::1/128", "fe80::1%eth0",
                       "http://[::1]", "::1 -n 10", "::1;id", "::1\n", "-6", "example.com:80"]:
            with self.subTest(target=target), self.assertRaises(ValueError):
                check_connectivity(target)
        run.assert_not_called()

    def test_success_and_commands(self):
        for system, flags, output in [
            ("Linux", ["-6", "-n", "-c", "1", "-W", "2"], "64 bytes from ::1: icmp_seq=1 hlim=64 time=0.1 ms"),
            ("Windows", ["-6", "-n", "1", "-w", "2000"], "Resposta de ::1: tempo<1ms"),
        ]:
            with self.subTest(system=system), patch("monitor.platform.system", return_value=system), patch(
                "monitor.subprocess.run", return_value=subprocess.CompletedProcess([], 0, output, "")
            ) as run:
                result = check_connectivity("::1")
                self.assertEqual(result["status"], "online")
                self.assertEqual(result["target"], "::1")
                self.assertEqual(run.call_args.args[0], ["ping", *flags, "::1"])
                self.assertNotIn("shell", run.call_args.kwargs)
                self.assertEqual(result["latency_is_upper_bound"], system == "Windows")

    def test_ipv6_timeouts_both_systems(self):
        for system in ("Linux", "Windows"):
            with self.subTest(system=system), patch("monitor.platform.system", return_value=system), patch(
                "monitor.subprocess.run", side_effect=subprocess.TimeoutExpired("ping", 3)
            ):
                self.assertEqual(check_connectivity("::1")["status"], "timeout")

    def test_ipv6_offline_and_timeout_output(self):
        for code, output, status in [(1, "Destination unreachable", "offline"),
                                     (1, "100% packet loss", "timeout")]:
            with self.subTest(status=status), patch("monitor.platform.system", return_value="Linux"), patch(
                "monitor.subprocess.run", return_value=subprocess.CompletedProcess([], code, output, "")
            ):
                self.assertEqual(check_connectivity("2001:db8::1")["status"], status)

    def test_dns_failure_on_windows(self):
        with patch("monitor.platform.system", return_value="Windows"), patch(
            "monitor.subprocess.run", return_value=subprocess.CompletedProcess([], 1, "Ping request could not find host example.test", "")
        ):
            self.assertEqual(check_connectivity("example.test")["status"], "error")

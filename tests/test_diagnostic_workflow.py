"""Real socket-to-engine/CLI integration, using synthetic local peers only.

These checks do not establish live BMW, ENET hardware or all-model coverage.
No test peer is part of the application or a fallback for a failed request.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bmgarage.engine import Engine, EngineError


VIN = b"WBA00000200000000"  # Synthetic fixture; never a product default.


def receive(channel: socket.socket, count: int) -> bytes:
    result = bytearray()
    while len(result) < count:
        part = channel.recv(count - len(result))
        if not part:
            raise AssertionError("The workflow sent a truncated request.")
        result.extend(part)
    return bytes(result)


def hsfz_handler(response: bytes, *, expect_close: bool = True):
    def handle(channel: socket.socket) -> None:
        # Fixed wire assertion: exactly UDS 22 F190 to physical target 0x10.
        request = receive(channel, 11)
        if request != bytes.fromhex("000000050001f41022f190"):
            raise AssertionError(f"Unexpected workflow HSFZ request: {request.hex()}")
        payload = b"\x10\xf4" + response
        channel.sendall(struct.pack("!IH", len(payload), 1) + payload)
        if expect_close and channel.recv(1) != b"":
            raise AssertionError("Workflow sent another request after VIN retrieval.")
    return handle


def doip_handler(response: bytes):
    def handle(channel: socket.socket) -> None:
        activation = receive(channel, 19)
        if activation != bytes.fromhex("03fc00050000000b0ef4000000000000000000"):
            raise AssertionError(f"Unexpected workflow activation: {activation.hex()}")
        channel.sendall(bytes.fromhex("03fc0006000000090ef410001000000000"))
        request = receive(channel, 15)
        if request != bytes.fromhex("03fc8001000000070ef4001022f190"):
            raise AssertionError(f"Unexpected workflow DoIP request: {request.hex()}")
        payload = bytes.fromhex("00100ef4") + response
        channel.sendall(struct.pack("!BBHI", 3, 252, 0x8001, len(payload)) + payload)
        if channel.recv(1) != b"":
            raise AssertionError("Workflow sent another request after VIN retrieval.")
    return handle


@contextmanager
def local_peer(handler):
    """Own the bounded socket peer and fail if it outlives the check."""
    errors = []
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        listener.settimeout(4)

        def serve() -> None:
            try:
                channel, _ = listener.accept()
                with channel:
                    channel.settimeout(4)
                    handler(channel)
            except Exception as exc:
                errors.append(exc)

        worker = threading.Thread(target=serve, daemon=True)
        worker.start()
        try:
            yield listener.getsockname()[1]
        finally:
            worker.join(timeout=5)
            if worker.is_alive():
                raise AssertionError("Workflow test peer did not terminate.")
            if errors:
                raise AssertionError(f"Workflow test peer failed: {errors[0]}")


class DiagnosticWorkflowTests(unittest.TestCase):
    def request(self, port: int, protocol: str = "hsfz") -> dict:
        return {"protocol": protocol, "host": "127.0.0.1", "port": port,
                "targetAddress": 16, "responseTimeout": 1, "connectTimeout": 1}

    def cli(self, port: int, *, protocol: str = "hsfz", extra=()):
        environment = os.environ.copy()
        environment["PATH"] = ""  # A Java executable cannot be discovered.
        with tempfile.TemporaryDirectory() as state_dir:
            return subprocess.run(
                [sys.executable, "-S", "-m", "bmgarage", "--state-dir", state_dir,
                 "read-vin", "--protocol", protocol, "--host", "127.0.0.1",
                 "--target", "0x10", "--port", str(port), "--connect-timeout", "1",
                 "--response-timeout", "1", *extra],
                cwd=ROOT, env=environment, capture_output=True, text=True, timeout=6)

    def test_hsfz_engine_returns_only_received_vin_and_closes(self):
        with local_peer(hsfz_handler(b"\x62\xf1\x90" + VIN)) as port, Engine() as engine:
            result = engine.call("diagnostics.vin", self.request(port))
        self.assertEqual(result["vin"], VIN.decode("ascii"))
        self.assertEqual(result["source"], "received UDS 62F190 response")
        self.assertEqual(result["udsRequest"], "22F190")
        self.assertEqual(result["targetAddress"], 16)
        self.assertEqual(result["testerAddress"], 244)
        self.assertTrue(result["readOnly"])
        self.assertFalse(result["vehicleWritten"])

    def test_doip_engine_performs_activation_then_actual_vin_read(self):
        with local_peer(doip_handler(b"\x62\xf1\x90" + VIN)) as port, Engine() as engine:
            result = engine.call("diagnostics.vin", self.request(port, "doip"))
        self.assertEqual(result["vin"], VIN.decode("ascii"))
        self.assertEqual(result["testerAddress"], 0x0EF4)
        self.assertEqual(result["protocol"], "doip")
        self.assertFalse(result["tls"])

    def test_engine_preserves_security_denial_without_success(self):
        with local_peer(hsfz_handler(b"\x7f\x22\x33")) as port, Engine() as engine:
            with self.assertRaises(EngineError) as failure:
                engine.call("diagnostics.vin", self.request(port))
            self.assertEqual(failure.exception.code, "diagnostic_failed")
            self.assertIn("security access denied", str(failure.exception))
            self.assertIn("0x33", str(failure.exception))
            self.assertEqual(engine.call("system.info")["engine"], "Native Python")

    def test_doip_authentication_denial_is_not_retried_with_other_protocol(self):
        with local_peer(doip_handler(b"\x7f\x22\x34")) as port, Engine() as engine:
            with self.assertRaises(EngineError) as failure:
                engine.call("diagnostics.vin", self.request(port, "doip"))
        self.assertEqual(failure.exception.code, "diagnostic_failed")
        self.assertIn("authentication required", str(failure.exception))

    def test_engine_rejects_bad_options_before_any_network(self):
        cases = ({"protocol": "automatic"}, {"host": "vehicle.local"},
                 {"targetAddress": True}, {"targetAddress": -1}, {"targetAddress": 256},
                 {"tls": "yes"}, {"tls": True}, {"tlsCa": "unselected.pem"},
                 {"tlsName": "vehicle"}, {"protocolVersion": 3},
                 {"protocol": "doip", "protocolVersion": 1},
                 {"protocol": "doip", "targetAddress": 65536})
        with patch("socket.create_connection", side_effect=AssertionError("Unexpected network call")) as connect:
            with Engine() as engine:
                for changes in cases:
                    with self.subTest(changes=changes), self.assertRaises(EngineError) as failure:
                        engine.call("diagnostics.vin", {**self.request(6801), **changes})
                    self.assertEqual(failure.exception.code, "invalid_input")
            connect.assert_not_called()

    def test_hsfz_cli_reads_actual_socket_without_site_packages_or_java(self):
        with local_peer(hsfz_handler(b"\x62\xf1\x90" + VIN)) as port:
            result = self.cli(port)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        response = json.loads(result.stdout)
        self.assertEqual(response["vin"], VIN.decode("ascii"))
        self.assertTrue(response["readOnly"])

    def test_doip_cli_reads_actual_socket(self):
        with local_peer(doip_handler(b"\x62\xf1\x90" + VIN)) as port:
            result = self.cli(port, protocol="doip")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["vin"], VIN.decode("ascii"))

    def test_cli_denial_has_nonzero_status_and_no_json_success(self):
        with local_peer(hsfz_handler(b"\x7f\x22\x33")) as port:
            result = self.cli(port)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("security access denied", result.stderr)
        self.assertNotIn(VIN.decode("ascii"), result.stderr)

    def test_cli_incorrect_vin_response_has_no_success_output(self):
        with local_peer(hsfz_handler(b"\x62\xf1\x90SHORT")) as port:
            result = self.cli(port)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("17-character ASCII VIN", result.stderr)


if __name__ == "__main__":
    unittest.main()

"""Native wire/component tests using local peers, NOT live BMW validation.

All endpoints are temporary 127.0.0.1 TCP listeners. Packet fixtures exercise
the real socket clients; they do not prove ENET hardware, vehicle readiness,
authorization, programming or secure diagnostic compatibility.
"""

from __future__ import annotations

import socket
import ssl
import struct
import threading
import time
import unittest

from bmgarage.diagnostics import (DiagnosticError, DiagnosticTimeout, DoipClient,
                                 HsfzClient, MAX_PAYLOAD, NegativeResponse,
                                 ProtocolError, TransportRejected, encode_doip,
                                 encode_hsfz)


VIN = b"WBA00000200000000"  # Synthetic wire fixture, never a product default.
READ = b"\x22\xf1\x90"


def receive(channel, size):
    result = bytearray()
    while len(result) < size:
        part = channel.recv(size - len(result))
        if not part:
            raise AssertionError("Test peer received a truncated request.")
        result.extend(part)
    return bytes(result)


def hsfz(channel):
    size, kind = struct.unpack("!IH", receive(channel, 6))
    return kind, receive(channel, size)


def doip(channel):
    version, inverse, kind, size = struct.unpack("!BBHI", receive(channel, 8))
    if inverse != version ^ 255:
        raise AssertionError("Invalid request version complement.")
    return version, kind, receive(channel, size)


class LocalPeer:
    """An owned bounded protocol peer used only by this component test suite."""

    def __init__(self, handler):
        self.handler = handler
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.listener.settimeout(2)
        self.port = self.listener.getsockname()[1]
        self.errors = []
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        try:
            connection, _ = self.listener.accept()
            with connection:
                connection.settimeout(2)
                self.handler(connection)
        except Exception as error:
            self.errors.append(error)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_exc):
        self.thread.join(timeout=3)
        self.listener.close()
        if self.thread.is_alive():
            raise AssertionError("Local protocol test peer did not stop.")
        if self.errors:
            raise AssertionError(f"Local protocol peer failed: {self.errors[0]}")


def routing(channel, version=3, response_code=0x10, tester=0x0EF4):
    actual_version, kind, payload = doip(channel)
    if (actual_version, kind, payload) != (version, 5, tester.to_bytes(2, "big") + bytes(9)):
        raise AssertionError("Unexpected routing-activation request.")
    channel.sendall(encode_doip(6, struct.pack("!HHB", tester, 0x1000, response_code) + bytes(4), version))


class NativeFramingTests(unittest.TestCase):
    def test_fixed_hsfz_read_vin_wire_vector(self):
        self.assertEqual(encode_hsfz(1, b"\xf4\x10" + READ).hex(), "000000050001f41022f190")

    def test_fixed_doip_v3_read_vin_wire_vector(self):
        self.assertEqual(encode_doip(0x8001, b"\x0e\xf4\x00\x10" + READ).hex(),
                         "03fc8001000000070ef4001022f190")

    def test_explicit_doip_v2_and_zero_length_frames(self):
        self.assertEqual(encode_doip(7, b"", 2).hex(), "02fd000700000000")
        self.assertEqual(encode_hsfz(0x12, b"").hex(), "000000000012")

    def test_invalid_frame_arguments_rejected(self):
        for value in (True, -1, 65536, "1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                encode_hsfz(value, b"")
        for value in (True, 2.0, 1, 4):
            with self.subTest(version=value), self.assertRaises(ValueError):
                encode_doip(7, b"", value)
        with self.assertRaises(TypeError):
            encode_hsfz(1, "not-bytes")
        with self.assertRaises(ValueError):
            encode_doip(1, b"x" * (MAX_PAYLOAD + 1))

    def test_construction_requires_explicit_ip_and_valid_configuration(self):
        for constructor in (HsfzClient, DoipClient):
            for options in ({"host": "vehicle.local"}, {"host": "https://127.0.0.1"},
                            {"response_timeout": float("inf")}, {"connect_timeout": 0},
                            {"port": True}, {"max_pending": -1}):
                arguments = {"host": "127.0.0.1", "target_address": 16, **options}
                with self.subTest(constructor=constructor.__name__, options=options), self.assertRaises(ValueError):
                    constructor(**arguments)
            client = constructor("127.0.0.1", 16)
            self.assertFalse(client.connected)
            client.close()

    def test_tls_context_cannot_disable_certificate_or_hostname_verification(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        with self.assertRaises(ValueError):
            DoipClient("127.0.0.1", 16, tls_context=context)
        with self.assertRaises(ValueError):
            DoipClient("127.0.0.1", 16, tls_server_hostname="vehicle.example")

    def test_invalid_tls_hostname_rejected_before_connecting(self):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        for hostname in (1, "", " ", " vehicle.example "):
            with self.subTest(hostname=hostname), self.assertRaises(ValueError):
                DoipClient("127.0.0.1", 16, tls_context=context,
                           tls_server_hostname=hostname)


class NativeHsfzTests(unittest.TestCase):
    def test_real_socket_partial_reply_requires_actual_vin_bytes(self):
        def peer(channel):
            self.assertEqual(hsfz(channel), (1, b"\xf4\x10" + READ))
            response = encode_hsfz(1, b"\x10\xf4\x62\xf1\x90" + VIN)
            for part in (response[:2], response[2:5], response[5:9], response[9:]):
                channel.sendall(part)
                time.sleep(0.002)
        with LocalPeer(peer) as server:
            with HsfzClient("127.0.0.1", 16, port=server.port) as client:
                self.assertEqual(client.read_vin(), VIN.decode())
                self.assertTrue(client.connected)
            self.assertFalse(client.connected)

    def test_delivery_ack_is_not_diagnostic_success(self):
        def peer(channel):
            _, request = hsfz(channel)
            channel.sendall(encode_hsfz(2, request))
        with LocalPeer(peer) as server:
            client = HsfzClient("127.0.0.1", 16, port=server.port)
            with self.assertRaises(ProtocolError):
                client.read_vin()
            self.assertFalse(client.connected)

    def test_ack_alive_check_pending_and_positive_response(self):
        def peer(channel):
            _, request = hsfz(channel)
            channel.sendall(encode_hsfz(2, request[:2]))
            channel.sendall(encode_hsfz(0x12, b""))
            self.assertEqual(hsfz(channel), (0x12, b"\x00\xf4"))
            channel.sendall(encode_hsfz(1, b"\x10\xf4\x7f\x22\x78"))
            channel.sendall(encode_hsfz(1, b"\x10\xf4\x62\xf1\x90" + VIN))
        with LocalPeer(peer) as server, HsfzClient("127.0.0.1", 16, port=server.port) as client:
            self.assertEqual(client.read_vin(), VIN.decode())

    def test_security_denial_is_preserved_and_never_retried(self):
        def peer(channel):
            self.assertEqual(hsfz(channel), (1, b"\xf4\x10" + READ))
            channel.sendall(encode_hsfz(1, b"\x10\xf4\x7f\x22\x33"))
            self.assertEqual(channel.recv(1), b"")
        with LocalPeer(peer) as server:
            client = HsfzClient("127.0.0.1", 16, port=server.port)
            with self.assertRaises(NegativeResponse) as error:
                client.read_vin()
            self.assertEqual((error.exception.service, error.exception.nrc), (0x22, 0x33))
            self.assertIn("security access denied", str(error.exception))

    def test_response_identity_must_match_selected_ecu(self):
        def peer(channel):
            hsfz(channel)
            channel.sendall(encode_hsfz(1, b"\x11\xf4\x62\xf1\x90" + VIN))
        with LocalPeer(peer) as server, HsfzClient("127.0.0.1", 16, port=server.port) as client:
            with self.assertRaises(ProtocolError):
                client.read_vin()

    def test_invalid_did_vin_and_negative_service_are_rejected(self):
        responses = [b"\x62\xf1\x91" + VIN, b"\x62\xf1\x90SHORT",
                     b"\x62\xf1\x90" + b"I" * 17, b"\x7f\x10\x33"]
        for response in responses:
            def peer(channel):
                hsfz(channel)
                channel.sendall(encode_hsfz(1, b"\x10\xf4" + response))
            with self.subTest(response=response), LocalPeer(peer) as server:
                with HsfzClient("127.0.0.1", 16, port=server.port) as client:
                    with self.assertRaises(ProtocolError):
                        client.read_vin()

    def test_transport_rejection_and_ack_mismatch(self):
        for control, payload, expected in [(0x45, b"", TransportRejected),
                                           (2, b"\xf4\x11", ProtocolError)]:
            def peer(channel):
                hsfz(channel)
                channel.sendall(encode_hsfz(control, payload))
            with self.subTest(control=control), LocalPeer(peer) as server:
                with HsfzClient("127.0.0.1", 16, port=server.port) as client:
                    with self.assertRaises(expected):
                        client.read_vin()

    def test_oversized_and_truncated_frames_rejected(self):
        for packet in (struct.pack("!IH", MAX_PAYLOAD + 1, 1), b"\x00\x00\x00"):
            def peer(channel):
                hsfz(channel)
                channel.sendall(packet)
            with self.subTest(packet=packet), LocalPeer(peer) as server:
                with HsfzClient("127.0.0.1", 16, port=server.port) as client:
                    with self.assertRaises(ProtocolError):
                        client.read_vin()

    def test_absolute_response_deadline_is_enforced(self):
        def peer(channel):
            hsfz(channel)
            time.sleep(0.15)
        with LocalPeer(peer) as server:
            client = HsfzClient("127.0.0.1", 16, port=server.port, response_timeout=0.03)
            started = time.monotonic()
            with self.assertRaises(DiagnosticTimeout):
                client.read_vin()
            self.assertLess(time.monotonic() - started, 1)
            self.assertFalse(client.connected)

    def test_response_pending_count_is_bounded(self):
        def peer(channel):
            hsfz(channel)
            channel.sendall(encode_hsfz(1, b"\x10\xf4\x7f\x22\x78"))
        with LocalPeer(peer) as server, HsfzClient("127.0.0.1", 16, port=server.port, max_pending=0) as client:
            with self.assertRaises(DiagnosticTimeout):
                client.read_vin()


class NativeDoipTests(unittest.TestCase):
    def test_mutated_tls_policy_closes_without_plaintext_activation(self):
        def peer(channel):
            self.assertEqual(channel.recv(1), b"")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        with LocalPeer(peer) as server:
            client = DoipClient("127.0.0.1", 16, port=server.port, tls_context=context)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            with self.assertRaises(DiagnosticError):
                client.connect()
            self.assertFalse(client.connected)

    def test_failed_tls_handshake_has_no_plaintext_fallback(self):
        def peer(channel):
            # A real TLS ClientHello begins with a handshake record. A DoIP
            # routing activation would begin 03 FC and must never be sent.
            header = receive(channel, 5)
            self.assertEqual(header[0], 0x16)
            self.assertEqual(header[1], 0x03)
            receive(channel, int.from_bytes(header[3:5], "big"))
            channel.sendall(b"not a TLS server")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        with LocalPeer(peer) as server:
            client = DoipClient("127.0.0.1", 16, port=server.port, tls_context=context)
            with self.assertRaisesRegex(DiagnosticError, "no plaintext fallback"):
                client.connect()
            self.assertFalse(client.connected)

    def test_routing_ack_then_actual_positive_diagnostic_response(self):
        def peer(channel):
            routing(channel)
            self.assertEqual(doip(channel), (3, 0x8001, b"\x0e\xf4\x00\x10" + READ))
            channel.sendall(encode_doip(0x8002, b"\x00\x10\x0e\xf4\x00" + READ))
            packet = encode_doip(0x8001, b"\x00\x10\x0e\xf4\x62\xf1\x90" + VIN)
            channel.sendall(packet[:3]);time.sleep(0.002);channel.sendall(packet[3:])
        with LocalPeer(peer) as server:
            with DoipClient("127.0.0.1", 16, port=server.port) as client:
                self.assertEqual(client.entity_address, 0x1000)
                self.assertEqual(client.read_vin(), VIN.decode())
            self.assertFalse(client.connected)
            self.assertIsNone(client.entity_address)

    def test_explicit_protocol_version_two(self):
        def peer(channel):
            routing(channel, 2)
            self.assertEqual(doip(channel)[0], 2)
            channel.sendall(encode_doip(0x8001, b"\x00\x10\x0e\xf4\x62\xf1\x90" + VIN, 2))
        with LocalPeer(peer) as server, DoipClient("127.0.0.1", 16, port=server.port, protocol_version=2) as client:
            self.assertEqual(client.read_vin(), VIN.decode())

    def test_alive_checks_during_activation_and_diagnostic_response(self):
        def peer(channel):
            self.assertEqual(doip(channel)[1], 5)
            channel.sendall(encode_doip(7, b""))
            self.assertEqual(doip(channel), (3, 8, b"\x0e\xf4"))
            channel.sendall(encode_doip(6, b"\x0e\xf4\x10\x00\x10" + bytes(4)))
            doip(channel)
            channel.sendall(encode_doip(7, b""))
            self.assertEqual(doip(channel), (3, 8, b"\x0e\xf4"))
            channel.sendall(encode_doip(0x8001, b"\x00\x10\x0e\xf4\x62\xf1\x90" + VIN))
        with LocalPeer(peer) as server, DoipClient("127.0.0.1", 16, port=server.port) as client:
            self.assertEqual(client.read_vin(), VIN.decode())

    def test_routing_denial_does_not_send_a_diagnostic_request(self):
        def peer(channel):
            routing(channel, response_code=0x04)
            self.assertEqual(channel.recv(1), b"")
        with LocalPeer(peer) as server:
            client = DoipClient("127.0.0.1", 16, port=server.port)
            with self.assertRaises(TransportRejected) as error:
                client.connect()
            self.assertEqual(error.exception.code, 4)
            self.assertFalse(client.connected)

    def test_routing_response_for_other_tester_is_rejected(self):
        def peer(channel):
            doip(channel)
            channel.sendall(encode_doip(6, b"\x0e\xf5\x10\x00\x10" + bytes(4)))
        with LocalPeer(peer) as server, self.assertRaises(ProtocolError):
            DoipClient("127.0.0.1", 16, port=server.port).connect()

    def test_ack_alone_is_not_a_vin(self):
        def peer(channel):
            routing(channel)
            doip(channel)
            channel.sendall(encode_doip(0x8002, b"\x00\x10\x0e\xf4\x00"))
        with LocalPeer(peer) as server, DoipClient("127.0.0.1", 16, port=server.port) as client:
            with self.assertRaises(ProtocolError):
                client.read_vin()

    def test_authentication_required_is_preserved_without_unlock_attempt(self):
        def peer(channel):
            routing(channel)
            self.assertEqual(doip(channel)[2][-3:], READ)
            channel.sendall(encode_doip(0x8001, b"\x00\x10\x0e\xf4\x7f\x22\x34"))
            self.assertEqual(channel.recv(1), b"")
        with LocalPeer(peer) as server, DoipClient("127.0.0.1", 16, port=server.port) as client:
            with self.assertRaises(NegativeResponse) as error:
                client.read_vin()
            self.assertEqual(error.exception.nrc, 0x34)
            self.assertIn("authentication required", str(error.exception))

    def test_pending_response_then_vin_and_pending_count_limit(self):
        for limit in (0, 1):
            def peer(channel):
                routing(channel)
                doip(channel)
                packet = encode_doip(0x8001, b"\x00\x10\x0e\xf4\x7f\x22\x78")
                if limit:
                    packet += encode_doip(0x8001, b"\x00\x10\x0e\xf4\x62\xf1\x90" + VIN)
                channel.sendall(packet)
            with self.subTest(limit=limit), LocalPeer(peer) as server:
                with DoipClient("127.0.0.1", 16, port=server.port, max_pending=limit) as client:
                    if limit:
                        self.assertEqual(client.read_vin(), VIN.decode())
                    else:
                        with self.assertRaises(DiagnosticTimeout):
                            client.read_vin()

    def test_transport_nack_and_wrong_reply_address_are_rejected(self):
        for kind, payload, expected in [(0x8003, b"\x00\x10\x0e\xf4\x06", TransportRejected),
                                         (0x8001, b"\x00\x11\x0e\xf4\x62\xf1\x90" + VIN, ProtocolError)]:
            def peer(channel):
                routing(channel)
                doip(channel)
                channel.sendall(encode_doip(kind, payload))
            with self.subTest(kind=kind), LocalPeer(peer) as server:
                with DoipClient("127.0.0.1", 16, port=server.port) as client:
                    with self.assertRaises(expected):
                        client.read_vin()

    def test_generic_nack_and_invalid_version_are_rejected(self):
        for packet, expected in [(encode_doip(0, b"\x01"), TransportRejected),
                                  (b"\x03\x00" + bytes(6), ProtocolError),
                                  (struct.pack("!BBHI", 3, 0xFC, 6, MAX_PAYLOAD + 1), ProtocolError)]:
            def peer(channel):
                doip(channel)
                channel.sendall(packet)
            with self.subTest(packet=packet), LocalPeer(peer) as server:
                with self.assertRaises(expected):
                    DoipClient("127.0.0.1", 16, port=server.port).connect()


if __name__ == "__main__":
    unittest.main()

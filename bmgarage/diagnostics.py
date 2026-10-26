"""Native read-only VIN transport over BMW HSFZ and ISO DoIP TCP.

The supplied driver/ProDiaS classes were inspected as binary data, without
executing Java: HsfzFrame/HsfzHelper, DoipFrame/DoipHelper and the plain TCP
link classes establish the framing, addresses and activation messages used
here. Component tests use local protocol peers, not a connected BMW vehicle.

There is no programming, coding, arbitrary-UDS, security-access, authentication
bypass or synthetic-response API. The only diagnostic request sent is 22 F190.
"""

from __future__ import annotations

import ipaddress
import math
import re
import socket
import ssl
import struct
import threading
import time


MAX_PAYLOAD = 65536
MAX_FRAMES = 128
VIN_REQUEST = b"\x22\xf1\x90"
_VIN = re.compile(rb"[A-HJ-NPR-Z0-9]{17}")


class DiagnosticError(RuntimeError):
    """An actual transport or diagnostic operation failed."""


class DiagnosticTimeout(DiagnosticError):
    pass


class ProtocolError(DiagnosticError):
    pass


class TransportRejected(DiagnosticError):
    def __init__(self, protocol: str, code: int, operation: str):
        self.protocol = protocol
        self.code = code
        self.operation = operation
        super().__init__(f"{protocol} rejected {operation} with code 0x{code:02X}.")


class NegativeResponse(DiagnosticError):
    def __init__(self, service: int, nrc: int):
        self.service = service
        self.nrc = nrc
        descriptions = {0x11: "service not supported", 0x13: "incorrect message format",
                        0x22: "conditions not correct", 0x31: "request out of range",
                        0x33: "security access denied", 0x34: "authentication required",
                        0x35: "invalid key", 0x36: "attempt limit exceeded",
                        0x37: "required delay not expired"}
        reason = descriptions.get(nrc, "negative diagnostic response")
        super().__init__(f"UDS service 0x{service:02X} rejected: {reason} (NRC 0x{nrc:02X}).")


def _integer(value: object, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer from {low} to {high}.")
    return value


def _timeout(value: object, name: str, maximum: int) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a positive finite number.")
    number = float(value)
    if not math.isfinite(number) or not 0 < number <= maximum:
        raise ValueError(f"{name} must be greater than zero and no greater than {maximum} seconds.")
    return number


def _payload(value: object) -> bytes:
    if not isinstance(value, bytes):
        raise TypeError("Frame payload must be bytes.")
    if len(value) > MAX_PAYLOAD:
        raise ValueError("Frame payload exceeds the read-only transport limit.")
    return value


def encode_hsfz(control: int, payload: bytes) -> bytes:
    """HSFZ payload length includes the one-byte source/target addresses."""
    return struct.pack("!IH", len(_payload(payload)), _integer(control, "Control code", 0, 65535)) + payload


def encode_doip(payload_type: int, payload: bytes, version: int = 3) -> bytes:
    if type(version) is not int or version not in (2, 3):
        raise ValueError("Explicit DoIP version 2 or 3 is supported.")
    return struct.pack("!BBHI", version, version ^ 0xFF,
                       _integer(payload_type, "Payload type", 0, 65535), len(_payload(payload))) + payload


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise DiagnosticTimeout("The diagnostic response deadline expired.")
    return remaining


class _Client:
    def __init__(self, host: str, port: int, target_address: int, tester_address: int,
                 maximum_address: int, connect_timeout: float, response_timeout: float,
                 max_pending: int):
        if not isinstance(host, str) or not host.strip():
            raise ValueError("Supply the explicit numeric IP address of the ENET endpoint.")
        try:
            self.host = str(ipaddress.ip_address(host))
        except ValueError as error:
            raise ValueError("Only an explicit numeric IP address is supported; discovery is not performed.") from error
        self.port = _integer(port, "TCP port", 1, 65535)
        self.target_address = _integer(target_address, "ECU target address", 0, maximum_address)
        self.tester_address = _integer(tester_address, "Tester address", 0, maximum_address)
        if self.target_address == self.tester_address:
            raise ValueError("Tester and ECU target addresses must differ.")
        self.connect_timeout = _timeout(connect_timeout, "Connect timeout", 60)
        self.response_timeout = _timeout(response_timeout, "Response timeout", 120)
        self.max_pending = _integer(max_pending, "Maximum response-pending messages", 0, 128)
        self._socket: socket.socket | None = None
        self._lock = threading.RLock()

    @property
    def connected(self) -> bool:
        """TCP state only; this does not establish vehicle or ECU readiness."""
        return self._socket is not None

    def connect(self):
        with self._lock:
            if self._socket is not None:
                return self
            try:
                self._socket = socket.create_connection((self.host, self.port), self.connect_timeout)
                self._initialize()
            except (OSError, DiagnosticError) as error:
                self.close()
                if isinstance(error, DiagnosticError):
                    raise
                if isinstance(error, socket.timeout):
                    raise DiagnosticTimeout("The diagnostic connection deadline expired.") from error
                raise DiagnosticError(f"The diagnostic TCP connection failed: {error}") from error
            return self

    def _initialize(self) -> None:
        pass

    def _send(self, frame: bytes, deadline: float) -> None:
        if self._socket is None:
            raise DiagnosticError("The diagnostic connection is closed.")
        try:
            self._socket.settimeout(_remaining(deadline))
            self._socket.sendall(frame)
        except socket.timeout as error:
            raise DiagnosticTimeout("The diagnostic send deadline expired.") from error
        except OSError as error:
            raise DiagnosticError("The diagnostic request could not be sent.") from error

    def _read(self, count: int, deadline: float) -> bytes:
        if self._socket is None:
            raise DiagnosticError("The diagnostic connection is closed.")
        result = bytearray()
        while len(result) < count:
            try:
                self._socket.settimeout(_remaining(deadline))
                part = self._socket.recv(count - len(result))
            except socket.timeout as error:
                raise DiagnosticTimeout("The diagnostic response deadline expired.") from error
            except OSError as error:
                raise DiagnosticError("The diagnostic response could not be read.") from error
            if not part:
                raise ProtocolError("The peer closed before the complete diagnostic response arrived.")
            result.extend(part)
        return bytes(result)

    def _vin_from_uds(self, response: bytes) -> str | None:
        if response.startswith(b"\x7f"):
            if len(response) != 3 or response[1] != VIN_REQUEST[0]:
                raise ProtocolError("The negative response does not match the requested UDS service.")
            if response[2] == 0x78:
                return None
            raise NegativeResponse(response[1], response[2])
        if not response.startswith(b"\x62\xf1\x90"):
            raise ProtocolError("The diagnostic response does not match ReadDataByIdentifier F190.")
        vin = response[3:]
        if _VIN.fullmatch(vin) is None:
            raise ProtocolError("The returned VIN is not a 17-character ASCII VIN.")
        return vin.decode("ascii")

    def read_vin(self) -> str:
        """Send only UDS 22 F190, preserving denials and requiring real reply bytes."""
        with self._lock:
            try:
                self.connect()
                return self._read_vin(time.monotonic() + self.response_timeout)
            except (DiagnosticError, OSError):
                self.close()
                raise

    def _read_vin(self, deadline: float) -> str:
        raise NotImplementedError

    def close(self) -> None:
        with self._lock:
            channel, self._socket = self._socket, None
            if channel is not None:
                try:
                    channel.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                channel.close()

    def __enter__(self):
        return self.connect()

    def __exit__(self, *_exc) -> None:
        self.close()


class HsfzClient(_Client):
    """BMW ENET/HSFZ TCP, explicit endpoint and one physical ECU target."""

    def __init__(self, host: str, target_address: int, *, port: int = 6801,
                 tester_address: int = 0xF4, connect_timeout: float = 3,
                 response_timeout: float = 5, max_pending: int = 8):
        super().__init__(host, port, target_address, tester_address, 255,
                         connect_timeout, response_timeout, max_pending)

    def _frame(self, deadline: float) -> tuple[int, bytes]:
        size, control = struct.unpack("!IH", self._read(6, deadline))
        if size > MAX_PAYLOAD:
            raise ProtocolError("The HSFZ payload exceeds the read-only transport limit.")
        return control, self._read(size, deadline)

    def _read_vin(self, deadline: float) -> str:
        request = bytes([self.tester_address, self.target_address]) + VIN_REQUEST
        self._send(encode_hsfz(1, request), deadline)
        pending = 0
        for _ in range(MAX_FRAMES):
            control, payload = self._frame(deadline)
            if control == 0x12:
                if payload not in (b"", bytes([0, self.tester_address])):
                    raise ProtocolError("The HSFZ alive-check addresses do not match this tester.")
                # Supplied HsfzHelper.getKeepAliveLinkData uses control 0x12
                # with payload 00,<tester>; 0x13 is STATUS, not this response.
                self._send(encode_hsfz(0x12, bytes([0, self.tester_address])), deadline)
                continue
            if control in (0x40, 0x42, 0x43, 0x44, 0x45, 0xFF):
                raise TransportRejected("HSFZ", control, "diagnostic delivery")
            if control == 2:
                if len(payload) < 2 or not request.startswith(payload):
                    raise ProtocolError("The HSFZ delivery acknowledgement does not match the request.")
                continue
            if control != 1 or len(payload) < 3:
                raise ProtocolError("Unexpected or incomplete HSFZ diagnostic frame.")
            if payload[:2] != bytes([self.target_address, self.tester_address]):
                raise ProtocolError("The HSFZ reply source/target does not match the selected ECU/tester.")
            vin = self._vin_from_uds(payload[2:])
            if vin is not None:
                return vin
            pending += 1
            if pending > self.max_pending:
                raise DiagnosticTimeout("The ECU exceeded the bounded response-pending limit.")
        raise ProtocolError("Too many transport frames arrived without the requested VIN.")


class DoipClient(_Client):
    """ISO DoIP TCP read-only client; no authentication bypass or TLS downgrade."""

    def __init__(self, host: str, target_address: int, *, port: int = 13400,
                 tester_address: int = 0x0EF4, protocol_version: int = 3,
                 connect_timeout: float = 3, response_timeout: float = 5,
                 max_pending: int = 8, tls_context: ssl.SSLContext | None = None,
                 tls_server_hostname: str | None = None):
        super().__init__(host, port, target_address, tester_address, 65535,
                         connect_timeout, response_timeout, max_pending)
        if type(protocol_version) is not int or protocol_version not in (2, 3):
            raise ValueError("Explicit DoIP protocol version 2 or 3 is supported.")
        if tls_context is not None:
            if not isinstance(tls_context, ssl.SSLContext) or not tls_context.check_hostname or tls_context.verify_mode != ssl.CERT_REQUIRED:
                raise ValueError("DoIP TLS requires certificate-chain and hostname verification.")
        elif tls_server_hostname is not None:
            raise ValueError("A TLS server hostname requires an explicit verifying TLS context.")
        if tls_server_hostname is not None and (not isinstance(tls_server_hostname, str) or
                not tls_server_hostname.strip() or tls_server_hostname != tls_server_hostname.strip()):
            raise ValueError("The TLS server hostname must be nonempty text without surrounding whitespace.")
        self.protocol_version = protocol_version
        self.tls_context = tls_context
        self.tls_server_hostname = tls_server_hostname
        self.entity_address: int | None = None

    def _send_payload(self, payload_type: int, payload: bytes, deadline: float) -> None:
        self._send(encode_doip(payload_type, payload, self.protocol_version), deadline)

    def _frame(self, deadline: float) -> tuple[int, bytes]:
        version, inverse, kind, size = struct.unpack("!BBHI", self._read(8, deadline))
        if version != self.protocol_version or inverse != version ^ 0xFF:
            raise ProtocolError("The DoIP response protocol version/inverse is invalid.")
        if size > MAX_PAYLOAD:
            raise ProtocolError("The DoIP payload exceeds the read-only transport limit.")
        return kind, self._read(size, deadline)

    def _alive(self, payload: bytes, deadline: float) -> None:
        if payload:
            raise ProtocolError("The DoIP alive-check request must have an empty payload.")
        self._send_payload(8, self.tester_address.to_bytes(2, "big"), deadline)

    def _initialize(self) -> None:
        if self.tls_context is not None:
            # SSLContext is mutable and can be shared by callers. Recheck the
            # required verification policy immediately before starting TLS.
            if (not isinstance(self.tls_context, ssl.SSLContext) or
                    not self.tls_context.check_hostname or
                    self.tls_context.verify_mode != ssl.CERT_REQUIRED):
                raise DiagnosticError("DoIP TLS verification was disabled after client configuration.")
            try:
                self._socket = self.tls_context.wrap_socket(self._socket,
                    server_hostname=self.tls_server_hostname or self.host)
            except (ssl.SSLError, OSError) as error:
                raise DiagnosticError("The verifying DoIP TLS handshake failed; no plaintext fallback was attempted.") from error
        deadline = time.monotonic() + self.response_timeout
        # Supplied DoipHelper uses optional OEM reserved bytes: 2+1+4+4 = 11.
        self._send_payload(5, self.tester_address.to_bytes(2, "big") + bytes(9), deadline)
        for _ in range(MAX_FRAMES):
            kind, payload = self._frame(deadline)
            if kind == 7:
                self._alive(payload, deadline)
                continue
            if kind == 0:
                if len(payload) != 1:
                    raise ProtocolError("Malformed DoIP generic negative acknowledgement.")
                raise TransportRejected("DoIP", payload[0], "routing activation")
            if kind != 6 or len(payload) not in (9, 13):
                raise ProtocolError("Expected a complete DoIP routing-activation response.")
            tester, entity = struct.unpack("!HH", payload[:4])
            if tester != self.tester_address:
                raise ProtocolError("The routing-activation response addresses a different tester.")
            if payload[4] != 0x10:
                raise TransportRejected("DoIP", payload[4], "routing activation")
            self.entity_address = entity
            return
        raise ProtocolError("Too many frames arrived without successful routing activation.")

    def _read_vin(self, deadline: float) -> str:
        addresses = struct.pack("!HH", self.tester_address, self.target_address)
        self._send_payload(0x8001, addresses + VIN_REQUEST, deadline)
        expected = struct.pack("!HH", self.target_address, self.tester_address)
        pending = 0
        for _ in range(MAX_FRAMES):
            kind, payload = self._frame(deadline)
            if kind == 7:
                self._alive(payload, deadline)
                continue
            if kind == 0:
                if len(payload) != 1:
                    raise ProtocolError("Malformed DoIP generic negative acknowledgement.")
                raise TransportRejected("DoIP", payload[0], "diagnostic delivery")
            if kind not in (0x8001, 0x8002, 0x8003) or len(payload) < 5:
                raise ProtocolError("Unexpected or incomplete DoIP diagnostic frame.")
            if payload[:4] != expected:
                raise ProtocolError("The DoIP reply source/target does not match the selected ECU/tester.")
            if kind == 0x8003:
                raise TransportRejected("DoIP", payload[4], "diagnostic delivery")
            if kind == 0x8002:
                if payload[4] != 0:
                    raise TransportRejected("DoIP", payload[4], "diagnostic acknowledgement")
                echo = payload[5:]
                if not VIN_REQUEST.startswith(echo):
                    raise ProtocolError("The DoIP acknowledgement echoes a different diagnostic request.")
                continue
            vin = self._vin_from_uds(payload[4:])
            if vin is not None:
                return vin
            pending += 1
            if pending > self.max_pending:
                raise DiagnosticTimeout("The ECU exceeded the bounded response-pending limit.")
        raise ProtocolError("Too many transport frames arrived without the requested VIN.")

    def close(self) -> None:
        super().close()
        self.entity_address = None

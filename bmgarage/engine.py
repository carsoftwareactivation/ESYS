"""Native Python processing for the currently implemented BMGARAGE operations.

No Java runtime, vendor executable, subprocess or E-Sys installation is used.
Dataset inspection is separate from calculation.
"""

from __future__ import annotations

import platform
from pathlib import Path
import ssl
import threading

from . import __version__
from .data import inspect_data
from .diagnostics import DiagnosticError, DoipClient, HsfzClient
from .fa_editor import create_fa, update_fa
from .fp import inspect_fp
from .models import compare_isteps, inspect_fa, inspect_svt, inspect_tal, parse_istep
from .resources import find_fafp_resources


class EngineError(RuntimeError):
    def __init__(self, message: str, code: str = "operation_failed"):
        super().__init__(message)
        self.code = code


class Engine:
    """An in-process native engine, independent of the graphical interface."""

    def __init__(self, data_home: Path | str | None = None, state_dir: Path | None = None):
        self.state_dir = Path(state_dir) if state_dir is not None else None
        self.data_home = str(Path(data_home).expanduser().resolve()) if data_home else None
        self._lock = threading.RLock()
        self._closed = False

    @staticmethod
    def _text(args: dict, key: str) -> str:
        value = args.get(key)
        if not isinstance(value, str):
            raise ValueError(f"Expected text argument: {key}")
        return value

    def call(self, op: str, args: dict | None = None) -> dict:
        with self._lock:
            if self._closed:
                raise EngineError("The application engine is closed.", "closed")
            if not isinstance(op, str) or (args is not None and not isinstance(args, dict)):
                raise EngineError("Operation name and arguments have invalid types.", "invalid_request")
            params = args or {}
            try:
                if op == "system.info":
                    return {"application": "BMGARAGE", "version": __version__,
                            "engine": "Native Python", "python": platform.python_version(),
                            "os": platform.system(), "javaRequired": False,
                            "esysInstallationRequired": False}
                if op == "data.status":
                    return inspect_data(self.data_home)
                if op == "data.select":
                    value = self._text(params, "path").strip()
                    status = inspect_data(value or None)
                    self.data_home = status["path"]
                    return status
                if op == "fa.inspect":
                    return inspect_fa(self._text(params, "xml"), params.get("entryIndex"))
                if op == "fa.create":
                    return create_fa(params.get("fields"))
                if op == "fa.update":
                    return update_fa(self._text(params, "xml"), params.get("changes"), params.get("entryIndex"))
                if op == "fp.inspect":
                    fa_xml = self._text(params, "faXml") if params.get("faXml") is not None else None
                    return inspect_fp(self._text(params, "xml"), fa_xml, params.get("entryIndex"))
                if op == "fp.resources":
                    return find_fafp_resources(self.data_home, self._text(params, "series"))
                if op == "svt.inspect":
                    return inspect_svt(self._text(params, "xml"))
                if op == "tal.inspect":
                    return inspect_tal(self._text(params, "xml"))
                if op == "istep.parse":
                    return parse_istep(self._text(params, "value"))
                if op == "istep.compare":
                    return compare_isteps(self._text(params, "left"), self._text(params, "right"))
                if op == "diagnostics.vin":
                    return self._read_vin(params)
            except DiagnosticError as exc:
                raise EngineError(str(exc), "diagnostic_failed") from exc
            except (ValueError, OSError, TypeError) as exc:
                raise EngineError(str(exc), "invalid_input") from exc
            raise EngineError(f"Operation is not implemented in the Python engine: {op}", "unsupported_operation")

    def _read_vin(self, params: dict) -> dict:
        """One explicit read-only request, never an automatic startup probe."""
        protocol = self._text(params, "protocol").lower()
        host = self._text(params, "host")
        if protocol not in ("hsfz", "doip"):
            raise ValueError("Select the explicit hsfz or doip transport protocol.")
        options = {}
        for key, argument in (("port", "port"), ("testerAddress", "tester_address"),
                              ("connectTimeout", "connect_timeout"), ("responseTimeout", "response_timeout")):
            if key in params:
                options[argument] = params[key]
        tls = params.get("tls", False)
        if type(tls) is not bool:
            raise ValueError("The TLS setting must be a boolean.")
        if not tls and (params.get("tlsCa") is not None or params.get("tlsName") is not None):
            raise ValueError("TLS CA and server name require explicit TLS mode.")
        if protocol == "hsfz" and (tls or "protocolVersion" in params):
            raise ValueError("TLS and DoIP version settings apply only to DoIP.")
        if protocol == "doip":
            if "protocolVersion" in params:
                options["protocol_version"] = params["protocolVersion"]
            if tls:
                cafile = self._text(params, "tlsCa") if params.get("tlsCa") is not None else None
                options["tls_context"] = ssl.create_default_context(cafile=cafile)
                if params.get("tlsName") is not None:
                    options["tls_server_hostname"] = self._text(params, "tlsName")
        constructor = HsfzClient if protocol == "hsfz" else DoipClient
        with constructor(host, params.get("targetAddress"), **options) as client:
            vin = client.read_vin()
            return {"vin": vin, "protocol": protocol, "host": client.host, "port": client.port,
                    "targetAddress": client.target_address, "testerAddress": client.tester_address,
                    "udsRequest": "22F190", "readOnly": True, "vehicleWritten": False,
                    "source": "received UDS 62F190 response", "tls": tls}

    def close(self) -> None:
        with self._lock:
            self._closed = True

    def __enter__(self) -> Engine:
        return self

    def __exit__(self, *_exc) -> None:
        self.close()

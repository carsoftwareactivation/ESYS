"""Tk controls for the native, explicit read-only ENET VIN operation."""

from __future__ import annotations

import ipaddress
import math
import re
import tkinter as tk
from tkinter import filedialog, ttk
from typing import Callable


class DiagnosticPanel(ttk.Frame):
    """One physical ECU request; opening the panel never starts a connection.

    ``submit`` is the application's background-work queue. Its fourth argument
    receives an exception on the Tk thread and may return True to mark it
    handled. ``call_engine`` is invoked only inside the submitted worker.
    """

    def __init__(self, parent, call_engine: Callable, submit: Callable):
        super().__init__(parent)
        self.call_engine = call_engine
        self.submit = submit
        self.busy = False
        self.protocol = tk.StringVar(self, "HSFZ")
        self.host = tk.StringVar(self)
        self.target = tk.StringVar(self)
        self.port = tk.StringVar(self, "6801")
        self.tester = tk.StringVar(self, "0xF4")
        self.version = tk.StringVar(self, "3")
        self.tls = tk.BooleanVar(self, False)
        self.tls_ca = tk.StringVar(self)
        self.tls_name = tk.StringVar(self)
        self.connect_timeout = tk.StringVar(self, "3")
        self.response_timeout = tk.StringVar(self, "5")
        self.vin = tk.StringVar(self)
        self.result = tk.StringVar(self, "No request sent.")
        self.details = tk.StringVar(self)
        self._widgets: list[ttk.Widget] = []
        self._build()
        self._refresh_controls()

    def _build(self) -> None:
        ttk.Label(self, text="ENET — Read VIN", style="Title.TLabel").pack(anchor="w")
        ttk.Label(self, text="Read the VIN using UDS 22 F190 from a known endpoint and physical ECU address. Choose the transport and addresses for your vehicle; the application does not discover or probe them.", wraplength=950).pack(anchor="w", pady=(4, 12))
        form = ttk.Frame(self)
        form.pack(fill="x")
        form.columnconfigure(1, weight=1)

        def entry(row, title, variable, width=38):
            ttk.Label(form, text=title).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=4)
            widget = ttk.Entry(form, textvariable=variable, width=width)
            widget.grid(row=row, column=1, sticky="ew", pady=4)
            self._widgets.append(widget)
            return widget

        ttk.Label(form, text="Transport").grid(row=0, column=0, sticky="w", padx=(0, 12), pady=4)
        self.protocol_box = ttk.Combobox(form, textvariable=self.protocol, values=("HSFZ", "DoIP"), state="readonly", width=36)
        self.protocol_box.grid(row=0, column=1, sticky="ew", pady=4)
        self.protocol_box.bind("<<ComboboxSelected>>", self._protocol_changed)
        entry(1, "Endpoint IP address", self.host)
        entry(2, "Physical ECU address", self.target)
        entry(3, "TCP port", self.port)
        entry(4, "Tester address", self.tester)
        ttk.Label(form, text="DoIP version").grid(row=5, column=0, sticky="w", padx=(0, 12), pady=4)
        self.version_box = ttk.Combobox(form, textvariable=self.version, values=("2", "3"), state="readonly", width=36)
        self.version_box.grid(row=5, column=1, sticky="ew", pady=4)
        entry(6, "Connect timeout (seconds)", self.connect_timeout)
        entry(7, "Response timeout (seconds)", self.response_timeout)
        self.tls_check = ttk.Checkbutton(form, text="DoIP TLS — verify certificate chain and name", variable=self.tls, command=self._refresh_controls)
        self.tls_check.grid(row=8, column=0, columnspan=2, sticky="w", pady=(8, 4))
        self.ca_entry = entry(9, "Trusted CA PEM (optional)", self.tls_ca)
        self.ca_browse = ttk.Button(form, text="Browse…", command=self._choose_ca)
        self.ca_browse.grid(row=9, column=2, padx=(8, 0), pady=4)
        self.name_entry = entry(10, "Certificate name (optional)", self.tls_name)
        ttk.Label(self, text="Addresses accept decimal or 0x hexadecimal. In TLS mode, an empty CA uses system trust and an empty certificate name verifies the endpoint IP. Set the actual TLS port explicitly. TLS failures never fall back to plaintext.", wraplength=950).pack(anchor="w", pady=(8, 12))
        self.read_button = ttk.Button(self, text="Read VIN", command=self.read_vin)
        self.read_button.pack(anchor="w")
        ttk.Label(self, textvariable=self.result, wraplength=950).pack(anchor="w", pady=(14, 6))
        ttk.Label(self, textvariable=self.vin, font=("Consolas", 18, "bold")).pack(anchor="w")
        ttk.Label(self, textvariable=self.details, wraplength=950).pack(anchor="w", pady=(6, 10))
        ttk.Separator(self).pack(fill="x", pady=(8, 10))
        ttk.Label(self, text="HSFZ and DoIP framing are tested with local protocol peers. Actual ENET hardware and BMW F/G model compatibility remain unvalidated. This operation reads one identifier; it does not program or code a vehicle.", wraplength=950).pack(anchor="w")

    def _choose_ca(self) -> None:
        filename = filedialog.askopenfilename(parent=self, title="Select a trusted CA certificate PEM", filetypes=(("PEM certificates", "*.pem"), ("All files", "*.*")))
        if filename:
            self.tls_ca.set(filename)

    def _protocol_changed(self, _event=None) -> None:
        if self.protocol.get() == "DoIP":
            self.port.set("13400")
            self.tester.set("0x0EF4")
        else:
            self.port.set("6801")
            self.tester.set("0xF4")
            self.tls.set(False)
        self._refresh_controls()

    def _refresh_controls(self) -> None:
        doip = self.protocol.get() == "DoIP"
        for widget in self._widgets:
            widget.configure(state="disabled" if self.busy else "normal")
        self.protocol_box.configure(state="disabled" if self.busy else "readonly")
        self.version_box.configure(state="readonly" if doip and not self.busy else "disabled")
        self.tls_check.configure(state="normal" if doip and not self.busy else "disabled")
        tls_state = "normal" if doip and self.tls.get() and not self.busy else "disabled"
        for widget in (self.ca_entry, self.ca_browse, self.name_entry):
            widget.configure(state=tls_state)
        self.read_button.configure(state="disabled" if self.busy else "normal")

    def set_busy(self, busy: bool) -> None:
        self.busy = bool(busy)
        self._refresh_controls()

    @staticmethod
    def _address(value: str, label: str, maximum: int) -> int:
        value = value.strip()
        if re.fullmatch(r"(?:[0-9]+|0[xX][0-9a-fA-F]+)", value) is None:
            raise ValueError(f"{label} requires a decimal or 0x hexadecimal number.")
        number = int(value, 16 if value.lower().startswith("0x") else 10)
        if not 0 <= number <= maximum:
            raise ValueError(f"{label} must be between 0 and {maximum}.")
        return number

    def _arguments(self) -> dict:
        protocol = self.protocol.get().lower()
        if protocol not in ("hsfz", "doip"):
            raise ValueError("Select HSFZ or DoIP.")
        host = self.host.get().strip()
        try:
            ipaddress.ip_address(host)
        except ValueError as error:
            raise ValueError("Enter the known numeric IP address of the ENET endpoint.") from error
        maximum = 255 if protocol == "hsfz" else 65535
        args = {"protocol": protocol, "host": host,
                "targetAddress": self._address(self.target.get(), "Physical ECU address", maximum),
                "testerAddress": self._address(self.tester.get(), "Tester address", maximum),
                "port": self._address(self.port.get(), "TCP port", 65535)}
        if args["port"] == 0:
            raise ValueError("TCP port must be between 1 and 65535.")
        if args["targetAddress"] == args["testerAddress"]:
            raise ValueError("Physical ECU and tester addresses must differ.")
        for key, variable, maximum in (("connectTimeout", self.connect_timeout, 60), ("responseTimeout", self.response_timeout, 120)):
            try:
                value = float(variable.get())
            except ValueError as error:
                raise ValueError("Timeouts must be positive finite seconds.") from error
            if not math.isfinite(value) or not 0 < value <= maximum:
                raise ValueError(f"{key} must be greater than zero and no greater than {maximum} seconds.")
            args[key] = value
        if protocol == "doip":
            if self.version.get() not in ("2", "3"):
                raise ValueError("Select DoIP version 2 or 3.")
            args["protocolVersion"] = int(self.version.get())
            args["tls"] = self.tls.get()
            if self.tls.get():
                if self.tls_ca.get().strip():
                    args["tlsCa"] = self.tls_ca.get().strip()
                if self.tls_name.get().strip():
                    args["tlsName"] = self.tls_name.get().strip()
        return args

    def read_vin(self) -> None:
        if self.busy:
            return
        self.vin.set("")
        self.details.set("")
        try:
            args = self._arguments()
        except ValueError as error:
            self.result.set("Request not sent: " + str(error))
            return
        self.result.set("Waiting for the requested ECU VIN response…")
        self.set_busy(True)

        def success(data: dict) -> None:
            self.set_busy(False)
            self.vin.set(data["vin"])
            self.result.set("VIN received in a UDS 62 F190 response.")
            self.details.set(f"{data['protocol'].upper()} · {data['host']}:{data['port']} · ECU 0x{data['targetAddress']:X} · {'TLS verified' if data['tls'] else 'plain TCP'}. No vehicle write performed.")

        def failure(error: Exception) -> bool:
            self.set_busy(False)
            self.vin.set("")
            self.details.set("")
            self.result.set("VIN read failed: " + str(error))
            return True

        self.submit("Reading VIN from the explicit ENET endpoint…", lambda: self.call_engine("diagnostics.vin", args), success, failure)

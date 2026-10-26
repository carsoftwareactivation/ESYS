"""Standalone Python GUI with semantic document viewers and manual PSdZDATA selection."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

from .engine import Engine, EngineError
from .settings import default_state_dir


MAX_DOCUMENT_BYTES = 8 * 1024 * 1024
MODULES = ("FA Viewer", "FP Viewer", "SVT Viewer", "TAL Viewer", "I-Step", "System & Data", "Capabilities")
FILE_OPERATIONS = {
    "FA Viewer": "fa.inspect",
    "FP Viewer": "fp.inspect",
    "SVT Viewer": "svt.inspect",
    "TAL Viewer": "tal.inspect",
}


def _text(value: object) -> str:
    return "" if value is None else str(value)


class DataTable(ttk.Frame):
    """A flat domain table, never an XML document tree."""

    def __init__(self, parent: tk.Misc, columns: tuple[tuple[str, str, int], ...]):
        super().__init__(parent)
        names = tuple(col[0] for col in columns)
        self.tree = ttk.Treeview(self, columns=names, show="headings", selectmode="browse")
        for key, label, width in columns:
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=50, stretch=True, anchor="w")
        yscroll = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

    def clear(self) -> None:
        self.tree.delete(*self.tree.get_children())

    def add(self, values: tuple | list, *, iid: str | None = None) -> None:
        options = {"iid": iid} if iid is not None else {}
        self.tree.insert("", "end", values=tuple(_text(x) for x in values), **options)


class GarageApp:
    def __init__(
        self,
        root: tk.Tk,
        data_home: Path | str | None = None,
        state_dir: Path | str | None = None,
    ):
        self.root = root
        self.state_dir = Path(state_dir) if state_dir else default_state_dir()
        self.settings_file = self.state_dir / "gui-settings.json"
        self.preferences = self._load_preferences()
        self.data_home = _text(data_home if data_home is not None else self.preferences.get("data_home"))
        self.engine: Engine | None = None
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bmgarage-engine")
        self.events: queue.Queue = queue.Queue()
        self.busy = False
        self.closed = False
        self.active_module = tk.StringVar(root, "FA Viewer")
        self.status = tk.StringVar(root, "Starting BMGARAGE Python engine…")
        self.file_names = {name: tk.StringVar(root, "No document loaded") for name in FILE_OPERATIONS}
        self.module_notes = {name: tk.StringVar(root, "Open a document to inspect its saved contents.") for name in FILE_OPERATIONS}
        self.frames: dict[str, ttk.Frame] = {}
        self.work_buttons: list[ttk.Button] = []
        self.fa_fields: dict[str, tk.StringVar] = {}
        self.fa_options: dict[str, DataTable] = {}
        self.svt_data: list[dict] = []
        self.fp_document_xml: str | None = None
        self.fp_data: dict | None = None
        self._build_window()
        root.protocol("WM_DELETE_WINDOW", self.close)
        self._poll_after = root.after(50, self._poll_events)
        self._startup_after = root.after(100, self.refresh_system)

    def _load_preferences(self) -> dict:
        try:
            data = json.loads(self.settings_file.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _build_window(self) -> None:
        self.root.title("BMGARAGE — Python standalone")
        self.root.geometry("1240x820")
        self.root.minsize(960, 640)
        style = ttk.Style(self.root)
        for theme in ("vista", "clam"):
            if theme in style.theme_names():
                style.theme_use(theme)
                break
        style.configure("Header.TLabel", font=("Segoe UI", 16, "bold"), foreground="#173b60")
        style.configure("Title.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Nav.TButton", anchor="w", padding=(10, 10))

        menubar = tk.Menu(self.root)
        self.file_menu = tk.Menu(menubar, tearoff=False)
        for module in FILE_OPERATIONS:
            self.file_menu.add_command(label=f"Open {module.split()[0]}…", command=lambda m=module: self.open_document(m))
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.close)
        menubar.add_cascade(label="File", menu=self.file_menu)
        options = tk.Menu(menubar, tearoff=False)
        options.add_command(label="PSdZDATA settings…", command=self.show_settings)
        menubar.add_cascade(label="Options", menu=options)
        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="Capabilities and dependencies", command=lambda: self.select_module("Capabilities"))
        help_menu.add_command(label="About", command=self.show_about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

        heading = ttk.Frame(self.root, padding=(14, 10))
        heading.pack(fill="x")
        ttk.Label(heading, text="BMGARAGE", style="Header.TLabel").pack(side="left")
        ttk.Label(heading, text="Standalone Python application", padding=(18, 0)).pack(side="left")
        ttk.Label(heading, text="Vehicle: not connected").pack(side="right")
        ttk.Separator(self.root).pack(fill="x")

        body = ttk.Frame(self.root)
        body.pack(fill="both", expand=True)
        navigation = ttk.Frame(body, padding=8, width=180)
        navigation.pack(side="left", fill="y")
        navigation.pack_propagate(False)
        ttk.Label(navigation, text="Editors & Viewers", style="Title.TLabel").pack(anchor="w", pady=(5, 10))
        for name in MODULES[:5]:
            ttk.Button(navigation, text=name, style="Nav.TButton", command=lambda n=name: self.select_module(n)).pack(fill="x", pady=3)
        ttk.Separator(navigation).pack(fill="x", pady=14)
        for name in MODULES[5:]:
            ttk.Button(navigation, text=name, style="Nav.TButton", command=lambda n=name: self.select_module(n)).pack(fill="x", pady=3)
        ttk.Label(navigation, text="Local documents only\nNo vehicle writes", wraplength=155, justify="left").pack(side="bottom", anchor="w", pady=10)
        ttk.Separator(body, orient="vertical").pack(side="left", fill="y")
        self.content = ttk.Frame(body, padding=12)
        self.content.pack(side="left", fill="both", expand=True)
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)
        for name in MODULES:
            frame = ttk.Frame(self.content)
            frame.grid(row=0, column=0, sticky="nsew")
            self.frames[name] = frame
        self._build_fa(self.frames["FA Viewer"])
        self._build_fp(self.frames["FP Viewer"])
        self._build_svt(self.frames["SVT Viewer"])
        self._build_tal(self.frames["TAL Viewer"])
        self._build_istep(self.frames["I-Step"])
        self._build_system(self.frames["System & Data"])
        self._build_capabilities(self.frames["Capabilities"])
        self.select_module("FA Viewer")
        ttk.Separator(self.root).pack(fill="x")
        footer = ttk.Frame(self.root, padding=(10, 6))
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self.status, wraplength=1000).pack(side="left", fill="x", expand=True)

    def _document_header(self, frame: ttk.Frame, module: str, subtitle: str) -> None:
        ttk.Label(frame, text=module, style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text=subtitle, wraplength=950).pack(anchor="w", pady=(4, 10))
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=(0, 8))
        ttk.Label(row, text="File name:").pack(side="left", padx=(0, 8))
        ttk.Entry(row, textvariable=self.file_names[module], state="readonly").pack(side="left", fill="x", expand=True)
        button = ttk.Button(row, text="Open…", command=lambda: self.open_document(module))
        button.pack(side="left", padx=(8, 0))
        self.work_buttons.append(button)
        ttk.Label(frame, textvariable=self.module_notes[module], wraplength=950).pack(anchor="w", pady=(0, 10))

    def _build_fa(self, frame: ttk.Frame) -> None:
        self._document_header(frame, "FA Viewer", "Inspect saved vehicle-order fields and option codes with the native Python reader.")
        selection = ttk.Frame(frame)
        selection.pack(fill="x", pady=(0, 10))
        ttk.Label(selection, text="FAList entry (1-based):").pack(side="left", padx=(0, 8))
        self.fa_entry_number = tk.StringVar(self.root, "1")
        ttk.Spinbox(selection, from_=1, to=10000, width=6, textvariable=self.fa_entry_number).pack(side="left")
        ttk.Label(selection, text="Choose the entry before opening an FAList. Not used for a standalone PSdZ FA.", wraplength=650).pack(side="left", padx=(12, 0))
        fields = ttk.LabelFrame(frame, text="Vehicle order (FA)", padding=12)
        fields.pack(fill="x")
        labels = (("series", "Development series"), ("version", "FA version"), ("type", "Type key"), ("timeCriterion", "Time criterion"), ("paint", "Paint code"), ("upholstery", "Upholstery code"), ("vin", "VIN"))
        for index, (key, label) in enumerate(labels):
            row, column = divmod(index, 2)
            column *= 2
            var = tk.StringVar(self.root)
            self.fa_fields[key] = var
            ttk.Label(fields, text=label).grid(row=row, column=column, sticky="w", padx=(0, 8), pady=5)
            ttk.Entry(fields, textvariable=var, state="readonly", width=25).grid(row=row, column=column + 1, sticky="ew", padx=(0, 20), pady=5)
        fields.columnconfigure(1, weight=1)
        fields.columnconfigure(3, weight=1)
        options = ttk.Frame(frame)
        options.pack(fill="both", expand=True, pady=(12, 0))
        for index, (key, label) in enumerate((("salapa", "SALAPA elements"), ("eWords", "E-Words"), ("hoWords", "HO-Words"))):
            group = ttk.LabelFrame(options, text=label, padding=6)
            group.grid(row=0, column=index, sticky="nsew", padx=(0, 8 if index < 2 else 0))
            table = DataTable(group, (("code", "Code", 130),))
            table.pack(fill="both", expand=True)
            self.fa_options[key] = table
            options.columnconfigure(index, weight=1)
        options.rowconfigure(0, weight=1)

    def _build_svt(self, frame: ttk.Frame) -> None:
        self._document_header(frame, "SVT Viewer", "Inspect a saved SVT document. Its source file determines whether it represents actual or target equipment.")
        self.svt_summary = tk.StringVar(self.root)
        ttk.Label(frame, textvariable=self.svt_summary).pack(anchor="w", pady=(0, 8))
        pane = ttk.Panedwindow(frame, orient="vertical")
        pane.pack(fill="both", expand=True)
        self.ecu_table = DataTable(pane, (("address", "Diagnostic address", 125), ("base", "Base variant", 180), ("variant", "Variant", 180), ("bus", "Bus", 120)))
        pane.add(self.ecu_table, weight=1)
        software_group = ttk.LabelFrame(pane, text="Selected ECU software (SGBM)", padding=6)
        self.software_table = DataTable(software_group, (("class", "Process class", 130), ("name", "Name", 240), ("id", "ID", 130), ("version", "Version", 150)))
        self.software_table.pack(fill="both", expand=True)
        pane.add(software_group, weight=1)
        self.ecu_table.tree.bind("<<TreeviewSelect>>", self._select_ecu)

    def _build_fp(self, frame: ttk.Frame) -> None:
        self._document_header(frame, "FP Viewer", "Inspect a saved vehicle profile and check its VPC checksum against a matching FA.")
        self.fp_summary = tk.StringVar(self.root)
        ttk.Label(frame, textvariable=self.fp_summary, wraplength=950).pack(anchor="w", pady=(0, 8))
        controls = ttk.Frame(frame)
        controls.pack(fill="x", pady=(0, 8))
        ttk.Label(controls, text="Matching FAList entry (1-based):").pack(side="left", padx=(0, 8))
        self.fp_fa_entry_number = tk.StringVar(self.root, "1")
        ttk.Spinbox(controls, from_=1, to=10000, width=6, textvariable=self.fp_fa_entry_number).pack(side="left")
        self.fp_vpc_button = ttk.Button(controls, text="Check VPC against FA…", command=self.check_fp_vpc, state="disabled")
        self.fp_vpc_button.pack(side="left", padx=(14, 0))
        self.work_buttons.append(self.fp_vpc_button)
        self.fp_checksum = tk.StringVar(self.root)
        self.fp_checksum_label = ttk.Label(frame, textvariable=self.fp_checksum, wraplength=950, font=("Segoe UI", 10, "bold"))
        self.fp_checksum_label.pack(anchor="w", pady=(0, 6))
        self.fp_checksums = tk.StringVar(self.root)
        ttk.Label(frame, textvariable=self.fp_checksums, wraplength=950).pack(anchor="w", pady=(0, 6))
        self.fp_matching_fa = tk.StringVar(self.root)
        ttk.Label(frame, textvariable=self.fp_matching_fa, wraplength=950).pack(anchor="w", pady=(0, 8))
        self.fp_table = DataTable(frame, (("categoryId", "Category ID", 110), ("category", "Category", 240), ("value", "Criterion value", 120), ("name", "Criterion", 350)))
        self.fp_table.pack(fill="both", expand=True)

    def _update_fp_vpc_button(self) -> None:
        self.fp_vpc_button.configure(state="disabled" if self.busy or self.fp_document_xml is None else "normal")

    def _build_tal(self, frame: ttk.Frame) -> None:
        self._document_header(frame, "TAL Viewer", "Inspect saved TAL work items and statuses. Loading a TAL does not execute it.")
        self.tal_summary = tk.StringVar(self.root)
        ttk.Label(frame, textvariable=self.tal_summary).pack(anchor="w", pady=(0, 8))
        self.tal_table = DataTable(frame, (("id", "Line", 60), ("ecu", "ECU", 150), ("address", "Address", 80), ("category", "Category", 160), ("action", "Technical action", 160), ("software", "SGBM", 220), ("lineStatus", "Stored line status", 160), ("actionStatus", "Stored action status", 160)))
        self.tal_table.pack(fill="both", expand=True)

    def _build_istep(self, frame: ttk.Frame) -> None:
        ttk.Label(frame, text="I-Step", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text="Parse and compare I-Step identifiers in Python. This does not establish installed or vehicle-compatible I-Steps.", wraplength=950).pack(anchor="w", pady=(5, 16))
        group = ttk.LabelFrame(frame, text="I-Step identifier", padding=12)
        group.pack(fill="x")
        self.istep_value = tk.StringVar(self.root)
        self.istep_other = tk.StringVar(self.root)
        self.istep_result = tk.StringVar(self.root)
        ttk.Label(group, text="I-Step").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=5)
        ttk.Entry(group, textvariable=self.istep_value, width=34).grid(row=0, column=1, sticky="ew", pady=5)
        button = ttk.Button(group, text="Parse", command=self.parse_istep)
        button.grid(row=0, column=2, padx=(12, 0), pady=5)
        self.work_buttons.append(button)
        ttk.Label(group, text="Compare with").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=5)
        ttk.Entry(group, textvariable=self.istep_other, width=34).grid(row=1, column=1, sticky="ew", pady=5)
        button = ttk.Button(group, text="Compare", command=self.compare_isteps)
        button.grid(row=1, column=2, padx=(12, 0), pady=5)
        self.work_buttons.append(button)
        group.columnconfigure(1, weight=1)
        ttk.Label(frame, textvariable=self.istep_result, wraplength=950, justify="left").pack(anchor="w", pady=16)

    def _build_system(self, frame: ttk.Frame) -> None:
        ttk.Label(frame, text="System & Data", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text="BMGARAGE runs in Python. Choose your PSdZDATA folder in Options; saved-file viewers work without it.", wraplength=950).pack(anchor="w", pady=(5, 12))
        controls = ttk.Frame(frame)
        controls.pack(fill="x", pady=(0, 12))
        button = ttk.Button(controls, text="Refresh", command=self.refresh_system)
        button.pack(side="left")
        self.work_buttons.append(button)
        button = ttk.Button(controls, text="Select PSdZDATA…", command=self.show_settings)
        button.pack(side="left", padx=(10, 0))
        self.work_buttons.append(button)
        self.system_table = DataTable(frame, (("name", "Component", 220), ("value", "Observed value", 600)))
        self.system_table.pack(fill="both", expand=True)

    def _build_capabilities(self, frame: ttk.Frame) -> None:
        ttk.Label(frame, text="Capabilities and dependencies", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frame, text="This build implements native Python saved-file inspection and data-folder inventory. The remaining workflows need native implementations and validation.", wraplength=950).pack(anchor="w", pady=(5, 12))
        table = DataTable(frame, (("workflow", "Workflow", 220), ("status", "Current scope", 230), ("needs", "Required next", 430)))
        table.pack(fill="both", expand=True)
        for row in (
            ("FA to FP", "Native calculation not implemented", "FA2FP rules, matching data and reference-result validation"),
            ("Installed / compatible I-Steps", "Identifier parsing and comparison only", "Matching PSdZ data and FA"),
            ("VCM / SVT Actual", "Saved SVT inspection only", "Native transport, vehicle connection and authorized diagnostics"),
            ("SVT Target / TAL calculation", "Native calculation not implemented", "Native planning algorithms, matching data and reference-result validation"),
            ("TAL processing", "Execution unavailable", "Native execution engine, validated vehicle integration and required authorization"),
            ("Coding / FSC", "Operations unavailable", "Native coding/FSC implementation, valid data and required authorization"),
            ("SFA / KDS / LCS", "Operations unavailable", "Native protocols, authorized BMW access and applicable certificates/tokens"),
            ("Diagnostics", "Vehicle operations unavailable", "Native transport and applicable diagnostic authorization"),
        ):
            table.add(row)
        ttk.Label(frame, text="No security checks, certificate validation or authorization requirements are bypassed.", wraplength=950).pack(anchor="w", pady=(12, 0))

    def select_module(self, name: str) -> None:
        self.active_module.set(name)
        self.frames[name].tkraise()

    def _ensure_engine(self) -> Engine:
        if self.engine is None:
            self.engine = Engine(data_home=self.data_home or None, state_dir=self.state_dir)
        return self.engine

    def _submit(self, description: str, work: Callable, success: Callable, failure: Callable | None = None) -> None:
        if self.busy or self.closed:
            return
        self.busy = True
        self.status.set(description)
        for button in self.work_buttons:
            button.configure(state="disabled")
        for index in range(len(FILE_OPERATIONS)):
            self.file_menu.entryconfigure(index, state="disabled")

        def execute() -> None:
            try:
                result = work()
                self.events.put((success, result, False))
            except Exception as error:
                self.events.put((failure, error, True))

        self.executor.submit(execute)

    def _poll_events(self) -> None:
        if self.closed:
            return
        try:
            while True:
                callback, payload, failed = self.events.get_nowait()
                self.busy = False
                for button in self.work_buttons:
                    button.configure(state="normal")
                for index in range(len(FILE_OPERATIONS)):
                    self.file_menu.entryconfigure(index, state="normal")
                if failed:
                    if callback is not None:
                        callback(payload)
                    self.status.set(f"Operation failed: {payload}")
                    messagebox.showerror("Operation failed", str(payload), parent=self.root)
                else:
                    callback(payload)
        except queue.Empty:
            pass
        self._update_fp_vpc_button()
        self._poll_after = self.root.after(50, self._poll_events)

    def _clear_document(self, module: str) -> None:
        self.module_notes[module].set("No document result available.")
        if module == "FA Viewer":
            for var in self.fa_fields.values():
                var.set("")
            for table in self.fa_options.values():
                table.clear()
        elif module == "SVT Viewer":
            self.svt_summary.set("")
            self.svt_data = []
            self.ecu_table.clear()
            self.software_table.clear()
        elif module == "FP Viewer":
            self.fp_document_xml = None
            self.fp_data = None
            self.fp_summary.set("")
            self.fp_checksum.set("")
            self.fp_checksums.set("")
            self.fp_matching_fa.set("")
            self.fp_table.clear()
            self._update_fp_vpc_button()
        else:
            self.tal_summary.set("")
            self.tal_table.clear()

    def open_document(self, module: str) -> None:
        if self.busy:
            return
        filename = filedialog.askopenfilename(parent=self.root, title=f"Open {module.split()[0]} document", filetypes=(("XML documents", "*.xml"), ("All files", "*.*")))
        if not filename:
            return
        self.load_document(module, filename)

    def load_document(self, module: str, filename: Path | str) -> None:
        """Load a selected document through the same worker flow as the picker."""
        if self.busy:
            return
        if module not in FILE_OPERATIONS:
            raise ValueError(f"Unknown document module: {module}")
        self.select_module(module)
        self.file_names[module].set(str(filename))
        self._clear_document(module)
        self.module_notes[module].set("Reading document in Python…")
        selected_entry = self.fa_entry_number.get().strip() if module == "FA Viewer" else None
        loaded_xml: list[str] = []

        def work() -> dict:
            with Path(filename).open("rb") as source:
                data = source.read(MAX_DOCUMENT_BYTES + 1)
            if len(data) > MAX_DOCUMENT_BYTES:
                raise ValueError("Document exceeds the 8 MiB viewer limit.")
            xml = data.decode("utf-8-sig")
            args = {"xml": xml}
            if selected_entry is not None:
                try:
                    entry_number = int(selected_entry)
                except ValueError:
                    raise ValueError("FAList entry must be a positive whole number.") from None
                if entry_number < 1:
                    raise ValueError("FAList entry must be a positive whole number.")
                args["entryIndex"] = entry_number - 1
            result = self._ensure_engine().call(FILE_OPERATIONS[module], args)
            if module == "FP Viewer":
                loaded_xml.append(xml)
            return result

        def success(data: dict) -> None:
            if module == "FP Viewer":
                self.fp_document_xml = loaded_xml[0]
            {"FA Viewer": self._render_fa, "FP Viewer": self._render_fp, "SVT Viewer": self._render_svt, "TAL Viewer": self._render_tal}[module](data)
            self.status.set(f"{module.split()[0]} saved contents inspected in Python. No vehicle operation performed.")

        def failed(_error: Exception) -> None:
            self._clear_document(module)
            self.module_notes[module].set("Document inspection failed. No result is displayed.")

        self._submit(f"Reading {module.split()[0]} document…", work, success, failed)

    def check_fp_vpc(self) -> None:
        if self.busy or self.fp_document_xml is None:
            return
        filename = filedialog.askopenfilename(parent=self.root, title="Select matching FA for VPC check", filetypes=(("FA XML documents", "*.xml"), ("All files", "*.*")))
        if filename:
            self.verify_fp_vpc(filename)

    def verify_fp_vpc(self, filename: Path | str) -> None:
        """Check the loaded FP checksum using the user's selected FA document."""
        if self.busy or self.fp_document_xml is None:
            return
        fp_xml = self.fp_document_xml
        selected_entry = self.fp_fa_entry_number.get().strip()
        self.fp_checksum.set("Checking VPC against selected FA…")
        self.fp_checksum_label.configure(foreground="#705300")
        self.fp_checksums.set("Stored VPC: " + (_text((self.fp_data or {}).get("storedVpc")) or "Not present"))
        self.fp_matching_fa.set(str(filename))

        def work() -> dict:
            with Path(filename).open("rb") as source:
                data = source.read(MAX_DOCUMENT_BYTES + 1)
            if len(data) > MAX_DOCUMENT_BYTES:
                raise ValueError("Matching FA exceeds the 8 MiB viewer limit.")
            try:
                entry_number = int(selected_entry)
            except ValueError:
                raise ValueError("Matching FAList entry must be a positive whole number.") from None
            if entry_number < 1:
                raise ValueError("Matching FAList entry must be a positive whole number.")
            return self._ensure_engine().call("fp.inspect", {"xml": fp_xml, "faXml": data.decode("utf-8-sig"), "entryIndex": entry_number - 1})

        def success(data: dict) -> None:
            self._render_fp(data)
            self.status.set(self.fp_checksum.get() + ". No FA-to-FP calculation performed.")

        def failed(_error: Exception) -> None:
            self.fp_checksum.set("VPC check failed — checksum is not verified")
            self.fp_checksum_label.configure(foreground="#a21515")
            self.module_notes["FP Viewer"].set("The saved FP remains displayed. The selected FA could not be used for the VPC check.")

        self._submit("Checking FP VPC against matching FA…", work, success, failed)

    def _render_fa(self, data: dict) -> None:
        for key, var in self.fa_fields.items():
            var.set(_text(data.get(key)))
        for key, table in self.fa_options.items():
            table.clear()
            for code in data.get(key, []):
                table.add((code,))
        source = _text(data.get("format", "PSdZ FA"))
        if data.get("entryCount") is not None:
            source += f" — entry {data['entryIndex'] + 1} of {data['entryCount']}"
            if data.get("entryName"):
                source += f" ({data['entryName']})"
        note = source + "; structural checks passed. Vehicle compatibility is unverified. FP has not been calculated."
        if data.get("warnings"):
            note += " " + " ".join(data["warnings"])
        self.module_notes["FA Viewer"].set(note)

    def _render_svt(self, data: dict) -> None:
        self.svt_data = data["ecus"]
        self.ecu_table.clear()
        self.software_table.clear()
        for index, ecu in enumerate(self.svt_data):
            self.ecu_table.add((ecu.get("diagnosticAddress"), ecu.get("baseVariant"), ecu.get("variant"), ecu.get("bus")), iid=str(index))
        self.svt_summary.set(f"SVT version: {data.get('version')}    VIN: {_text(data.get('vin'))}    ECUs: {len(self.svt_data)}")
        self.module_notes["SVT Viewer"].set("Saved SVT inspected in Python. No actual or target SVT was requested from a vehicle or calculated.")
        if self.svt_data:
            self.ecu_table.tree.selection_set("0")
            self._select_ecu()

    def _render_fp(self, data: dict) -> None:
        self.fp_data = data
        self.fp_table.clear()
        for category in data.get("categories", []):
            criteria = category.get("criteria") or [None]
            for criterion in criteria:
                self.fp_table.add((category.get("id"), category.get("nameEN") or category.get("name"), criterion.get("value") if criterion else "", (criterion.get("nameEN") or criterion.get("name") or criterion.get("text")) if criterion else ""))
        self.fp_summary.set(f"FP version: {_text(data.get('version'))}    Series: {_text(data.get('series'))}    Main series: {_text(data.get('mainSeries'))}    VIN: {_text(data.get('vin'))}")
        status = data.get("checksumStatus")
        if status == "match" and data.get("checksumMatches") is True:
            text, colour = "VPC matches selected FA — checksum only", "#176c35"
        elif status == "mismatch" or data.get("checksumMatches") is False:
            text, colour = "VPC mismatch — stored checksum differs from selected FA", "#a21515"
        elif status == "not_present":
            text, colour = "VPC is not present in the saved FP", "#705300"
        else:
            text, colour = "VPC not checked — select a matching FA", "#705300"
        self.fp_checksum.set(text)
        self.fp_checksum_label.configure(foreground=colour)
        self.fp_checksums.set("Stored VPC: " + (_text(data.get("storedVpc")) or "Not present") + "    Calculated VPC: " + (_text(data.get("calculatedVpc")) or "Not checked"))
        note = "Saved FP inspected. VPC checks do not verify profile compatibility or authenticity. No FA-to-FP calculation performed."
        if data.get("warnings"):
            note += " " + " ".join(data["warnings"])
        self.module_notes["FP Viewer"].set(note)
        self._update_fp_vpc_button()

    def _select_ecu(self, _event=None) -> None:
        selection = self.ecu_table.tree.selection()
        self.software_table.clear()
        if not selection:
            return
        index = int(selection[0])
        if index >= len(self.svt_data):
            return
        ecu = self.svt_data[index]
        for software in ecu.get("sgbm", []):
            self.software_table.add((software.get("processClass"), software.get("name"), software.get("id"), software.get("version")))

    def _render_tal(self, data: dict) -> None:
        self.tal_table.clear()
        for line in data["lines"]:
            actions = line.get("actions") or [None]
            for action in actions:
                self.tal_table.add((line.get("id"), line.get("ecu"), line.get("diagnosticAddress"), line.get("category"), action.get("category") if action else "", action.get("sgbm") if action else "", line.get("status"), action.get("status") if action else ""))
        identity = f"TAL ID: {data['id']}    " if data.get("id") is not None else ""
        self.tal_summary.set(identity + f"Schema: {_text(data.get('schemaVersion'))}    Stored status: {_text(data.get('status'))}    Lines: {len(data['lines'])}")
        note = "Saved TAL inspected in Python. Status values are stored document values; no TAL has been executed."
        if data.get("uninspectedSections"):
            note += " Sections not inspected: " + ", ".join(data["uninspectedSections"]) + "."
        self.module_notes["TAL Viewer"].set(note)

    def parse_istep(self) -> None:
        value = self.istep_value.get().strip()
        self.istep_result.set("")

        def success(data: dict) -> None:
            self.istep_result.set(f"I-Step: {data['canonical']}\nMain series: {data['mainSeries']}\nYear: {data['year']}    Month: {data['month']}    Number: {data['number']}")
            self.status.set("I-Step identifier parsed in Python. Vehicle compatibility has not been checked.")

        self._submit("Parsing I-Step…", lambda: self._ensure_engine().call("istep.parse", {"value": value}), success)

    def compare_isteps(self) -> None:
        left, right = self.istep_value.get().strip(), self.istep_other.get().strip()
        self.istep_result.set("")

        def success(data: dict) -> None:
            symbol = {-1: "<", 0: "=", 1: ">"}[data["comparison"]]
            self.istep_result.set(f"{data['left']}  {symbol}  {data['right']}")
            self.status.set("I-Step identifiers compared in Python. Vehicle compatibility has not been checked.")

        self._submit("Comparing I-Steps…", lambda: self._ensure_engine().call("istep.compare", {"left": left, "right": right}), success)

    def _render_system(self, info: dict, data: dict) -> None:
        self.system_table.clear()
        for key, label in (("application", "Application"), ("version", "Version"), ("engine", "Engine"), ("python", "Python"), ("os", "Operating system")):
            self.system_table.add((label, info.get(key)))
        self.system_table.add(("Java required", "Yes" if info.get("javaRequired") else "No"))
        self.system_table.add(("PSdZDATA folder", data.get("path") or "Not selected"))
        self.system_table.add(("Folder exists", "Yes" if data.get("exists") else "No"))
        self.system_table.add(("Series mapping present", "Yes" if data.get("mappingPresent") else "No"))
        self.system_table.add(("Series mapping readable", "Yes" if data.get("mappingReadable") else "No"))
        self.system_table.add(("Mapping entries", data.get("seriesCount")))
        self.system_table.add(("FA-to-FP / target planning", "Not implemented"))
        self.system_table.add(("Vehicle connection", "Not connected"))
        for error in data.get("errors", []):
            self.system_table.add(("Data-folder issue", error))

    def refresh_system(self) -> None:
        if self.busy:
            return
        self.system_table.clear()

        def work() -> tuple[dict, dict]:
            engine = self._ensure_engine()
            return engine.call("system.info"), engine.call("data.status")

        def success(result: tuple[dict, dict]) -> None:
            info, data = result
            self._render_system(info, data)
            self.status.set("Python engine available. " + ("PSdZDATA folder inspected." if data.get("usableForInventory") else "Select PSdZDATA when needed; saved-file tools are available."))

        self._submit("Inspecting application and data folder…", work, success, lambda _error: self.system_table.clear())

    def select_data_path(self, value: str, on_saved: Callable | None = None) -> None:
        """Apply a user-selected folder, save it, and show its actual inventory."""
        selected = value.strip()

        def work() -> tuple[dict, dict]:
            engine = self._ensure_engine()
            previous_path = engine.call("data.status").get("path")
            data = engine.call("data.select", {"path": selected})
            preferences = {"data_home": data.get("path") if data.get("selected") else None}
            try:
                self.state_dir.mkdir(parents=True, exist_ok=True)
                temporary = self.settings_file.with_suffix(".tmp")
                temporary.write_text(json.dumps(preferences, indent=2) + "\n", encoding="utf-8")
                temporary.replace(self.settings_file)
            except OSError:
                engine.call("data.select", {"path": previous_path or ""})
                raise
            return engine.call("system.info"), data

        def success(result: tuple[dict, dict]) -> None:
            info, data = result
            self.data_home = _text(data.get("path"))
            self.preferences = {"data_home": self.data_home or None}
            self._render_system(info, data)
            self.select_module("System & Data")
            if data.get("errors"):
                self.status.set("PSdZDATA selection saved; inspect the reported data-folder issues.")
            else:
                self.status.set("PSdZDATA selection saved. Native calculations remain under development.")
            if on_saved is not None:
                on_saved()

        self._submit("Saving PSdZDATA selection…", work, success)

    def show_settings(self) -> None:
        if self.busy:
            messagebox.showinfo("Application busy", "Wait for the current operation before changing PSdZDATA settings.", parent=self.root)
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("PSdZDATA settings")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(True, False)
        area = ttk.Frame(dialog, padding=16)
        area.pack(fill="both", expand=True)
        data_home = tk.StringVar(dialog, self.data_home)
        ttk.Label(area, text="PSdZDATA folder or its parent directory").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Entry(area, textvariable=data_home, width=65).grid(row=1, column=0, sticky="ew", pady=(4, 12))

        def browse() -> None:
            value = filedialog.askdirectory(parent=dialog, title="Select PSdZDATA folder")
            if value:
                data_home.set(value)

        ttk.Button(area, text="Browse…", command=browse).grid(row=1, column=1, padx=(8, 0), pady=(4, 12))
        ttk.Label(area, text="Leave blank to use saved-file tools without a dataset. Folder inspection does not establish calculation or vehicle readiness.", wraplength=600).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 12))
        controls = ttk.Frame(area)
        controls.grid(row=3, column=0, columnspan=2, sticky="e")
        ttk.Button(controls, text="Cancel", command=dialog.destroy).pack(side="left", padx=(0, 8))
        ttk.Button(controls, text="Save and inspect", command=lambda: self.select_data_path(data_home.get(), lambda: dialog.destroy() if dialog.winfo_exists() else None)).pack(side="left")
        area.columnconfigure(0, weight=1)
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

    def show_about(self) -> None:
        messagebox.showinfo("About BMGARAGE", "BMGARAGE — Python standalone\n\nRuns directly in Python with no E-Sys installation, Java engine or Java runtime.\n\nThis build implements saved-document readers, I-Step utilities and manual PSdZDATA selection. Native calculation and vehicle workflows remain under development.", parent=self.root)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        for callback in (self._poll_after, self._startup_after):
            self.root.after_cancel(callback)
        if self.engine is not None:
            threading.Thread(target=self.engine.close, daemon=True).start()
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def run_gui(data_home=None, state_dir=None) -> None:
    root = tk.Tk()
    GarageApp(root, data_home=data_home, state_dir=state_dir)
    root.mainloop()


def main() -> None:
    parser = argparse.ArgumentParser(description="BMGARAGE Python standalone application")
    parser.add_argument("--psdzdata", "--data-home", dest="data_home", type=Path, help="Optional PSdZDATA directory or its parent")
    parser.add_argument("--state-dir", type=Path, help="Application-owned local settings directory")
    args = parser.parse_args()
    run_gui(data_home=args.data_home, state_dir=args.state_dir)


if __name__ == "__main__":
    main()

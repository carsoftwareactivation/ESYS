"""Exercise real Tk widgets, native Python operations and persisted data selection.

Run under a display (for example Xvfb). No engine results or widgets are mocked.
Synthetic saved documents and mapping metadata do not verify vehicle operations.
"""

from __future__ import annotations

from pathlib import Path
import sys
import json
import tempfile
import time
import tkinter as tk
import traceback

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PROCESS_LAUNCHES = []


def audit_processes(event, args):
    if event == "subprocess.Popen":
        PROCESS_LAUNCHES.append(args[0])


sys.addaudithook(audit_processes)

from bmgarage.gui import GarageApp


FIXTURES = Path(__file__).parent / "fixtures"


def main() -> None:
    callback_errors: list[str] = []
    checks: list[str] = []
    with tempfile.TemporaryDirectory(prefix="bmgarage-gui-") as temporary:
        root = tk.Tk()
        app = GarageApp(root, state_dir=Path(temporary))

        def callback_exception(kind, value, tb) -> None:
            callback_errors.append("".join(traceback.format_exception(kind, value, tb)))

        root.report_callback_exception = callback_exception
        # The hard watchdog also exits any unexpected nested modal dialog.
        timed_out = []

        def watchdog() -> None:
            timed_out.append(True)
            root.destroy()

        root.after(120000, watchdog)

        def wait_for(predicate, label: str, timeout: float = 35) -> None:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                root.update()
                if timed_out:
                    raise AssertionError(f"GUI watchdog expired during {label}")
                if callback_errors:
                    raise AssertionError("Tk callback failed:\n" + "\n".join(callback_errors))
                if predicate():
                    return
                time.sleep(0.01)
            raise AssertionError(f"GUI operation did not complete: {label}; status={app.status.get()}")

        def rows(table) -> list[tuple[str, ...]]:
            return [tuple(map(str, table.tree.item(item, "values"))) for item in table.tree.get_children()]

        def load(module: str, filename: Path) -> None:
            app.load_document(module, filename)
            assert app.busy, f"{module} did not enter its worker flow"
            wait_for(lambda: not app.busy, module)
            assert "failed" not in app.status.get().lower(), app.status.get()

        try:
            wait_for(lambda: not app.busy and bool(app.system_table.tree.get_children()), "automatic native engine inspection")
            system = dict(rows(app.system_table))
            assert system["Application"] == "BMGARAGE", system
            assert system["Engine"] == "Native Python", system
            assert system["Java required"] == "No", system
            assert system["PSdZDATA folder"] == "Not selected", system
            assert system["FA-to-FP / target planning"] == "Not implemented", system
            assert system["Vehicle connection"] == "Not connected", system
            checks.append("native Python launch without Java, E-Sys or a dataset")

            # Minimal XML for inventory tests only; this is not a validated BMW
            # dataset and cannot make calculations or vehicle operations work.
            data_home = Path(temporary) / "dataset" / "psdzdata"
            (data_home / "mapping").mkdir(parents=True)
            (data_home / "mapping" / "brref.xml").write_text(
                '<brRef xmlns="http://bmw.com/2005/psdz.data.brref" version="01.02.00">'
                '<mainSeries name="F020" fa2fpId="00000001"><series>F030</series>'
                '<series>F031</series></mainSeries></brRef>', encoding="utf-8")
            app.select_data_path(str(data_home.parent))
            wait_for(lambda: not app.busy, "manual PSdZDATA parent selection")
            system = dict(rows(app.system_table))
            assert system["PSdZDATA folder"] == str(data_home.resolve()), system
            assert system["Series mapping readable"] == "Yes", system
            assert system["Mapping entries"] == "2", system
            assert system["FA-to-FP / target planning"] == "Not implemented", system
            preferences = json.loads(app.settings_file.read_text(encoding="utf-8"))
            assert preferences == {"data_home": str(data_home.resolve())}, preferences
            checks.append("manual PSdZDATA selection, honest inventory status and saved settings")

            app.select_data_path("")
            wait_for(lambda: not app.busy, "clearing PSdZDATA selection")
            assert dict(rows(app.system_table))["PSdZDATA folder"] == "Not selected"
            app.select_data_path(str(data_home))
            wait_for(lambda: not app.busy, "manual direct PSdZDATA selection")
            assert dict(rows(app.system_table))["PSdZDATA folder"] == str(data_home.resolve())
            checks.append("clearing selection and choosing PSdZDATA directly")

            load("FA Viewer", FIXTURES / "fa.xml")
            assert app.fa_fields["series"].get() == "F030"
            assert app.fa_fields["type"].get() == "3A51"
            assert app.fa_fields["timeCriterion"].get() == "0714"
            assert rows(app.fa_options["salapa"]) == [("205",), ("249",)]
            assert "FP has not been calculated" in app.module_notes["FA Viewer"].get()
            checks.append("standalone FA semantic fields and SALAPA")

            app.fa_entry_number.set("1")
            load("FA Viewer", FIXTURES / "falist.xml")
            note = app.module_notes["FA Viewer"].get()
            assert "E-Sys FAList" in note and "entry 1 of 1" in note and "0001" in note, note
            checks.append("original E-Sys FAList metadata")

            xml = (FIXTURES / "falist.xml").read_text(encoding="utf-8")
            entry = xml[xml.index("<id "):xml.index("</id>") + len("</id>")]
            entry = entry.replace('name="0001"', 'name="0002"').replace('typeKey="3A51"', 'typeKey="3A52"')
            multiple = Path(temporary) / "multiple-fa.xml"
            multiple.write_text(xml.replace("</faList>", entry + "</faList>"), encoding="utf-8")
            app.fa_entry_number.set("2")
            load("FA Viewer", multiple)
            note = app.module_notes["FA Viewer"].get()
            assert "entry 2 of 2" in note and "0002" in note, note
            assert app.fa_fields["type"].get() == "3A52"
            checks.append("explicit selection of the second FAList vehicle order")

            load("FA Viewer", FIXTURES / "fa.xml")
            assert app.fa_fields["type"].get() == "3A51"
            checks.append("standalone FA opens after selecting a different FAList entry")

            outside_version = Path(temporary) / "fa-version.xml"
            outside_version.write_text((FIXTURES / "fa.xml").read_text().replace('faVersion="3"', 'faVersion="5"'))
            load("FA Viewer", outside_version)
            assert "outside the analyzed versions" in app.module_notes["FA Viewer"].get()
            checks.append("limited FA version coverage disclosed in the viewer")

            assert str(app.fp_vpc_button["state"]) == "disabled"
            load("FP Viewer", FIXTURES / "fp.xml")
            assert rows(app.fp_table) == [
                ("2", "Synthetic category two", "513", "Synthetic criterion"),
                ("1", "Synthetic category one", "256", ""),
                ("1", "Synthetic category one", "2", ""),
            ], rows(app.fp_table)
            assert app.fp_data["checksumMatches"] is None
            assert "VPC not checked" in app.fp_checksum.get()
            assert str(app.fp_vpc_button["state"]) == "normal"
            checks.append("saved FP categories and unchecked stored VPC")

            app.verify_fp_vpc(FIXTURES / "fa.xml")
            wait_for(lambda: not app.busy, "native VPC verification")
            assert app.fp_data["storedVpc"] == "005B2113", app.fp_data
            assert app.fp_data["calculatedVpc"] == "005B2113", app.fp_data
            assert app.fp_data["checksumMatches"] is True
            assert "checksum only" in app.fp_checksum.get()
            assert "No FA-to-FP calculation performed" in app.module_notes["FP Viewer"].get()
            checks.append("native VPC checksum check against matching FA")

            different_paint = Path(temporary) / "fa-other-paint.xml"
            different_paint.write_text((FIXTURES / "fa.xml").read_text().replace('colourCode="0300"', 'colourCode="0301"'))
            app.verify_fp_vpc(different_paint)
            wait_for(lambda: not app.busy, "native VPC mismatch")
            assert app.fp_data["checksumMatches"] is False
            assert "VPC mismatch" in app.fp_checksum.get()
            assert str(app.fp_checksum_label.cget("foreground")) == "#a21515"
            checks.append("VPC mismatch is displayed without success or compatibility claims")

            second_fa = entry.replace('colourCode="0300"', 'colourCode="0301"')
            checksum_falist = Path(temporary) / "fp-check-falist.xml"
            checksum_falist.write_text(xml.replace("</faList>", second_fa + "</faList>"))
            app.fp_fa_entry_number.set("2")
            app.verify_fp_vpc(checksum_falist)
            wait_for(lambda: not app.busy, "explicit VPC FAList selection")
            assert app.fp_data["checksumMatches"] is False
            app.fp_fa_entry_number.set("1")
            app.verify_fp_vpc(checksum_falist)
            wait_for(lambda: not app.busy, "first VPC FAList selection")
            assert app.fp_data["checksumMatches"] is True
            checks.append("VPC check uses the explicitly selected FAList entry")

            load("FP Viewer", FIXTURES / "fp.xml")
            assert app.fp_data["checksumMatches"] is None
            assert "VPC not checked" in app.fp_checksum.get()
            assert app.fp_matching_fa.get() == ""
            checks.append("opening an FP clears previous checksum-verification state")

            load("SVT Viewer", FIXTURES / "svt.xml")
            assert rows(app.ecu_table) == [("10", "DME", "DME_TEST", "")], rows(app.ecu_table)
            software = rows(app.software_table)
            assert len(software) == 1 and software[0][0] == "BTLD" and software[0][3] == "001_002_003", software
            checks.append("SVT ECU selection and original SGBM values")

            load("TAL Viewer", FIXTURES / "tal.xml")
            lines = rows(app.tal_table)
            assert len(lines) == 1 and lines[0][1] == "DME", lines
            assert lines[0][3:5] == ("cdDeploy", "cdDeployTA"), lines
            assert lines[0][6:] == ("Executable", "Executable"), lines
            assert "Stored status: Executable" in app.tal_summary.get()
            assert "no TAL has been executed" in app.module_notes["TAL Viewer"].get()
            checks.append("TAL action plan and separately labelled stored statuses")

            context_plan = Path(temporary) / "tal-context.xml"
            context_plan.write_text((FIXTURES / "tal.xml").read_text().replace("</tal>", "<TaskDependencies/></tal>"))
            load("TAL Viewer", context_plan)
            assert "Sections not inspected: TaskDependencies" in app.module_notes["TAL Viewer"].get()
            checks.append("uninspected TAL context disclosed in the viewer")

            app.select_module("I-Step")
            app.istep_value.set("F020-24-07-500")
            app.parse_istep()
            wait_for(lambda: not app.busy, "I-Step parser")
            assert "F020-24-07-500" in app.istep_result.get() and "Number: 500" in app.istep_result.get()
            checks.append("native I-Step parser displayed through Tk")

            app.istep_other.set("F020-24-11-500")
            app.compare_isteps()
            wait_for(lambda: not app.busy, "I-Step comparison")
            assert app.istep_result.get() == "F020-24-07-500  <  F020-24-11-500"
            checks.append("native I-Step comparison displayed through Tk")
            assert not callback_errors
            assert "Python standalone" in root.title()
            checks.append("no Java or other subprocess launched")
            assert not PROCESS_LAUNCHES, PROCESS_LAUNCHES
        finally:
            if app.engine is not None:
                app.engine.close()
            try:
                app.close()
            except tk.TclError:
                if not timed_out:
                    raise
        checks.append("clean native GUI shutdown")
        # Reopen from application-owned preferences without constructor path
        # arguments. This checks persistence, not merely an in-memory selection.
        root = tk.Tk()
        app = GarageApp(root, state_dir=Path(temporary))
        root.report_callback_exception = callback_exception
        root.after(120000, watchdog)
        try:
            wait_for(lambda: not app.busy and bool(app.system_table.tree.get_children()), "reopened persisted selection")
            assert dict(rows(app.system_table))["PSdZDATA folder"] == str(data_home.resolve())
            assert app.data_home == str(data_home.resolve())
            assert not PROCESS_LAUNCHES, PROCESS_LAUNCHES
            checks.append("PSdZDATA selection restored in a new application instance")
        finally:
            if app.engine is not None:
                app.engine.close()
            app.close()
    print(f"GUI smoke: {len(checks)} checks passed")
    for check in checks:
        print(f"  PASS {check}")


if __name__ == "__main__":
    main()

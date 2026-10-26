"""Native application integration tests; no vendor installation is needed."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from bmgarage.engine import Engine, EngineError
from bmgarage.settings import load_preferences


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


class NativeEngineTests(unittest.TestCase):
    def test_application_information_is_native(self):
        with Engine() as engine:
            info = engine.call("system.info")
            self.assertEqual(info["application"], "BMGARAGE")
            self.assertEqual(info["engine"], "Native Python")
            self.assertFalse(info["javaRequired"])
            self.assertFalse(info["esysInstallationRequired"])

    def test_saved_documents_work_without_psdzdata(self):
        with Engine() as engine:
            self.assertFalse(engine.call("data.status")["selected"])
            order = engine.call("fa.inspect", {"xml": (FIXTURES / "fa.xml").read_text()})
            self.assertEqual(order["series"], "F030")
            self.assertTrue(order["structurallyValid"])
            self.assertNotIn("fp", order)
            svt = engine.call("svt.inspect", {"xml": (FIXTURES / "svt.xml").read_text()})
            self.assertEqual(svt["ecus"][0]["baseVariant"], "DME")
            tal = engine.call("tal.inspect", {"xml": (FIXTURES / "tal.xml").read_text()})
            self.assertEqual(tal["lines"][0]["category"], "cdDeploy")
            self.assertEqual(tal["status"], "Executable")

    def test_manual_selection_does_not_enable_unimplemented_calculations(self):
        with tempfile.TemporaryDirectory() as temporary, Engine() as engine:
            dataset = Path(temporary) / "psdzdata"
            dataset.mkdir()
            selected = engine.call("data.select", {"path": temporary})
            self.assertEqual(selected["path"], str(dataset.resolve()))
            self.assertTrue(selected["exists"])
            self.assertFalse(selected["mappingPresent"])
            self.assertFalse(selected["calculationsAvailable"])
            self.assertEqual(engine.call("data.status")["path"], str(dataset.resolve()))
            with self.assertRaises(EngineError) as error:
                engine.call("fa.to_fp", {})
            self.assertEqual(error.exception.code, "unsupported_operation")

    def test_native_saved_fp_checksum_operation(self):
        with Engine() as engine:
            result = engine.call("fp.inspect", {"xml": (FIXTURES / "fp.xml").read_text(),
                                                 "faXml": (FIXTURES / "fa.xml").read_text()})
            self.assertTrue(result["checksumMatches"])
            self.assertEqual(result["calculatedVpc"], "005B2113")
            self.assertFalse(result["faToFpCalculationPerformed"])
            self.assertFalse(result["faConsistencyVerified"])

    def test_resource_discovery_reports_missing_selected_data(self):
        with Engine() as engine:
            with self.assertRaises(EngineError) as failure:
                engine.call("fp.resources", {"series": "F030"})
            self.assertIn("Select a PSdZDATA directory", str(failure.exception))

    def test_missing_selection_can_be_cleared_without_blocking_file_tools(self):
        with Engine() as engine:
            result = engine.call("data.select", {"path": "/this/path/does/not/exist/psdzdata"})
            self.assertTrue(result["selected"])
            self.assertTrue(result["errors"])
            self.assertEqual(engine.call("istep.parse", {"value": "F020-24-07-500"})["number"], 500)
            self.assertFalse(engine.call("data.select", {"path": ""})["selected"])

    def test_old_java_operations_are_not_available(self):
        with Engine() as engine:
            for op in ["services", "versions", "tal.execute", "vcm.read", "coding.write"]:
                with self.subTest(operation=op), self.assertRaises(EngineError) as error:
                    engine.call(op)
                self.assertEqual(error.exception.code, "unsupported_operation")

    def test_invalid_input_preserves_functional_recovery(self):
        with Engine() as engine:
            with self.assertRaises(EngineError) as error:
                engine.call("istep.parse", {"value": "غير صالح"})
            self.assertEqual(error.exception.code, "invalid_input")
            self.assertEqual(engine.call("system.info")["engine"], "Native Python")

    def test_closed_engine_rejects_new_work(self):
        engine = Engine()
        engine.close()
        with self.assertRaises(EngineError) as error:
            engine.call("system.info")
        self.assertEqual(error.exception.code, "closed")

    def test_legacy_installation_settings_are_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            (path / "gui-settings.json").write_text(json.dumps({"esys_home": "missing-vendor", "java": "missing-java"}))
            self.assertEqual(load_preferences(path), {"data_home": None})

    def test_cli_works_without_site_packages_java_or_vendor_path(self):
        environment = os.environ.copy()
        environment["PATH"] = ""
        environment["BMGARAGE_ESYS_HOME"] = "/missing-vendor-installation"
        environment["BMGARAGE_JAVA"] = "/missing-java"
        with tempfile.TemporaryDirectory() as temporary:
            result = subprocess.run([sys.executable, "-S", "-m", "bmgarage", "--state-dir", temporary, "info"],
                                    cwd=ROOT, env=environment, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        info = json.loads(result.stdout)
        self.assertEqual(info["engine"], "Native Python")
        self.assertFalse(info["javaRequired"])


if __name__ == "__main__":
    unittest.main()

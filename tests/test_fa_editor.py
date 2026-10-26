"""FA editing tests exercise real file-format transformations, never a vehicle."""

from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from bmgarage.fa_editor import create_fa, update_fa
from bmgarage.models import DocumentError, FA_NS, inspect_fa


FIXTURES = Path(__file__).parent / "fixtures"
FIELDS = {"series": "F030", "type": "3A51", "timeCriterion": "0714",
          "paint": "0300", "upholstery": "LCSW", "salapa": ["205", "249"]}


class NativeFaEditorTests(unittest.TestCase):
    def test_create_semantic_document_roundtrip(self):
        result = create_fa(FIELDS)
        summary = inspect_fa(result["xml"])
        self.assertEqual(summary["series"], "F030")
        self.assertEqual(summary["version"], 3)
        self.assertEqual(summary["salapa"], ["205", "249"])
        self.assertIsNone(summary["vin"])
        self.assertFalse(result["vehicleWritten"])
        self.assertFalse(result["fpCalculated"])

    def test_save_created_document_and_reopen(self):
        result = create_fa(FIELDS)
        with tempfile.TemporaryDirectory() as temporary:
            file = Path(temporary) / "FA.xml"
            file.write_text(result["xml"], encoding="utf-8")
            self.assertEqual(inspect_fa(file.read_text(encoding="utf-8"))["type"], "3A51")

    def test_edit_fields_and_option_lists_without_changing_original_input(self):
        xml = (FIXTURES / "fa.xml").read_text()
        result = update_fa(xml, {"type": "3A52", "salapa": ["205"], "eWords": ["AB12"], "hoWords": ["CD34"]})
        self.assertEqual(result["summary"]["type"], "3A52")
        self.assertEqual(result["summary"]["salapa"], ["205"])
        self.assertEqual(result["summary"]["eWords"], ["AB12"])
        self.assertEqual(result["summary"]["hoWords"], ["CD34"])
        self.assertEqual(inspect_fa(xml)["type"], "3A51")

    def test_edit_one_falist_entry_preserves_other_entry_and_metadata(self):
        xml = (FIXTURES / "falist.xml").read_text()
        entry = xml[xml.index("<id "):xml.index("</id>") + len("</id>")]
        xml = xml.replace("</faList>", entry.replace('name="0001"', 'name="0002"') + "</faList>")
        original = ET.fromstring(xml)
        original_other = ET.tostring(original.findall("id")[0])
        result = update_fa(xml, {"paint": "0301"}, entry_index=1)
        changed = ET.fromstring(result["xml"])
        self.assertEqual(ET.tostring(changed.findall("id")[0]), original_other)
        self.assertEqual(inspect_fa(result["xml"], 1)["paint"], "0301")
        self.assertEqual(inspect_fa(result["xml"], 0)["paint"], "0300")
        self.assertEqual(changed.findall("id")[1].get("name"), "0002")

    def test_vin_can_be_removed_without_inventing_replacement(self):
        xml = (FIXTURES / "fa.xml").read_text()
        self.assertIsNone(update_fa(xml, {"vin": None})["summary"]["vin"])

    def test_invalid_and_duplicate_option_edits_rejected(self):
        xml = (FIXTURES / "fa.xml").read_text()
        for changes in [{"type": "!"}, {"salapa": ["205", "205"]}, {"eWords": ["123"]},
                        {"vin": "invalid"}, {"version": True}, {"salapa": "205"}, {"unknown": 1}]:
            with self.subTest(changes=changes), self.assertRaises(DocumentError):
                update_fa(xml, changes)

    def test_create_requires_supported_fields_and_types(self):
        for fields in [{}, {**FIELDS, "version": "3"}, {**FIELDS, "paint": "???"}]:
            with self.subTest(fields=fields), self.assertRaises(DocumentError):
                create_fa(fields)

    def test_editor_preserves_existing_header_attributes(self):
        xml = (FIXTURES / "fa.xml").read_text()
        before = ET.fromstring(xml).find("{" + FA_NS + "}header").attrib.copy()
        result = update_fa(xml, {"type": "3A52"})
        after = ET.fromstring(result["xml"]).find("{" + FA_NS + "}header").attrib
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()

"""Native dataset inventory tests; fixtures do not represent BMW-ready data."""

from pathlib import Path
import tempfile
import unittest

from bmgarage.data import (DataSelectionError, MAX_MAPPING_BYTES,
                           inspect_data, normalize_data_home)


# Synthetic structure follows the supplied brref.xsd. This is not a real BMW
# mapping file, engine-initialization fixture or PSdZ dataset.
INVENTORY_XML = b'''<?xml version="1.0" encoding="UTF-8"?>
<brRef xmlns="http://bmw.com/2005/psdz.data.brref" version="01.02.00">
<mainSeries name="F020" fa2fpId="00000001"><series>F030</series>
<series>F031</series><series>F030</series></mainSeries></brRef>'''


class DatasetInventoryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bmgarage-data-")
        self.parent = Path(self.temporary.name)
        self.data = self.parent / "psdzdata"
        self.data.mkdir()

    def tearDown(self):
        self.temporary.cleanup()

    def write_mapping(self, content=INVENTORY_XML):
        mapping = self.data / "mapping"
        mapping.mkdir(exist_ok=True)
        file = mapping / "brref.xml"
        file.write_bytes(content)
        return file

    def test_no_selection_is_distinct_from_missing_data(self):
        status = inspect_data()
        self.assertFalse(status["selected"])
        self.assertIsNone(status["path"])
        self.assertEqual(status["errors"], [])
        self.assertFalse(status["calculationsAvailable"])

    def test_accepts_data_directory_or_parent_without_writing(self):
        self.assertEqual(normalize_data_home(self.data), self.data.resolve())
        self.assertEqual(normalize_data_home(self.parent), self.data.resolve())
        status = inspect_data(self.parent)
        self.assertEqual(status["path"], str(self.data.resolve()))
        self.assertFalse(status["mappingPresent"])
        self.assertFalse(status["usableForInventory"])
        self.assertEqual(list(self.data.iterdir()), [])

    def test_missing_or_unrelated_directory_is_reported(self):
        missing = self.parent / "absent"
        with self.assertRaises(DataSelectionError):
            normalize_data_home(missing)
        status = inspect_data(missing)
        self.assertTrue(status["selected"])
        self.assertFalse(status["exists"])
        self.assertTrue(status["errors"])
        unrelated = self.parent / "other"
        unrelated.mkdir()
        self.assertTrue(inspect_data(unrelated)["errors"])

    def test_case_insensitive_psdzdata_name(self):
        self.data.rmdir()
        selected = self.parent / "PSDZDATA"
        selected.mkdir()
        self.assertEqual(normalize_data_home(self.parent), selected.resolve())

    def test_custom_named_data_directory_requires_mapping_directory(self):
        selected = self.parent / "selected-data"
        selected.mkdir()
        with self.assertRaises(DataSelectionError):
            normalize_data_home(selected)
        (selected / "mapping").mkdir()
        self.assertEqual(normalize_data_home(selected), selected.resolve())

    def test_inventory_counts_named_series_without_claiming_calculations(self):
        file = self.write_mapping()
        before = file.read_bytes()
        status = inspect_data(self.data)
        self.assertTrue(status["mappingPresent"])
        self.assertTrue(status["mappingReadable"])
        self.assertTrue(status["usableForInventory"])
        self.assertEqual(status["seriesCount"], 2)
        self.assertEqual(status["mainSeriesCount"], 1)
        self.assertTrue(status["inventoryOnly"])
        self.assertFalse(status["calculationsAvailable"])
        self.assertEqual(status["errors"], [])
        self.assertEqual(file.read_bytes(), before)

    def test_well_formed_unrelated_xml_is_not_usable_inventory(self):
        self.write_mapping(b"<not-a-mapping><anything/></not-a-mapping>")
        status = inspect_data(self.data)
        self.assertTrue(status["mappingReadable"])
        self.assertEqual(status["seriesCount"], 0)
        self.assertFalse(status["usableForInventory"])
        self.assertTrue(status["errors"])

    def test_old_attribute_only_series_is_not_misreported_as_real_data(self):
        self.write_mapping(b'<brRef><mainSeries name="F020"><series name="F030"/></mainSeries></brRef>')
        status = inspect_data(self.data)
        self.assertEqual(status["seriesCount"], 0)
        self.assertFalse(status["usableForInventory"])

    def test_unqualified_legacy_series_text_can_be_inventoried(self):
        self.write_mapping(b'<brRef><mainSeries name="F020"><series>F030</series></mainSeries></brRef>')
        status = inspect_data(self.data)
        self.assertEqual(status["seriesCount"], 1)
        self.assertTrue(status["usableForInventory"])

    def test_named_series_in_an_unrelated_document_is_not_a_mapping(self):
        self.write_mapping(b'<unrelated><mainSeries name="F020"><series>F030</series></mainSeries></unrelated>')
        status = inspect_data(self.data)
        self.assertTrue(status["mappingReadable"])
        self.assertFalse(status["usableForInventory"])

    def test_malformed_xml_reports_error(self):
        self.write_mapping(b"<mainSeries>")
        status = inspect_data(self.data)
        self.assertFalse(status["mappingReadable"])
        self.assertFalse(status["usableForInventory"])
        self.assertTrue(status["errors"])

    def test_dtd_entities_rejected_in_utf8_and_utf16(self):
        document = '''<?xml version="1.0"?><!DOCTYPE x [
<!ENTITY external SYSTEM "file:///must-not-be-read">]>
<x><series name="F030">&external;</series></x>'''
        for encoding in ("utf-8", "utf-16"):
            with self.subTest(encoding=encoding):
                self.write_mapping(document.encode(encoding))
                status = inspect_data(self.data)
                self.assertFalse(status["mappingReadable"])
                self.assertTrue(any("DTD" in error for error in status["errors"]))

    def test_xml_include_is_rejected(self):
        self.write_mapping(b'<x xmlns:xi="http://www.w3.org/2001/XInclude"><xi:include href="file:///must-not-be-read"/></x>')
        status = inspect_data(self.data)
        self.assertFalse(status["mappingReadable"])
        self.assertTrue(any("includes" in error for error in status["errors"]))

    def test_oversized_mapping_is_rejected(self):
        self.write_mapping(b" " * (MAX_MAPPING_BYTES + 1))
        status = inspect_data(self.data)
        self.assertTrue(status["mappingPresent"])
        self.assertFalse(status["mappingReadable"])
        self.assertTrue(any("limit" in error for error in status["errors"]))


if __name__ == "__main__":
    unittest.main()

"""Resource discovery uses synthetic filesystem fixtures, not a BMW-ready dataset."""

from pathlib import Path
import tempfile
import unittest

from bmgarage.resources import FpResourceError, find_fafp_resources


MAPPING = '''<brRef xmlns="http://bmw.com/2005/psdz.data.brref" version="01.02.00">
<mainSeries name="F020" fa2fpId="00000001"><series>F030</series>
<series fa2fpId="00000002">F031</series></mainSeries></brRef>'''


class NativeFpResourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bmgarage-fap-")
        self.data = Path(self.temporary.name) / "psdzdata"
        (self.data / "mapping").mkdir(parents=True)
        self.mapping = self.data / "mapping" / "brref.xml"
        self.mapping.write_text(MAPPING)

    def tearDown(self):
        self.temporary.cleanup()

    def artifact(self, name, location="swe/fafp"):
        path = self.data / location / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"resource-discovery fixture; not an authenticated FAP")
        return path

    def test_inherits_mapping_id_from_main_series(self):
        result = find_fafp_resources(self.data.parent, "F030")
        self.assertEqual((result["mainSeries"], result["fa2fpId"]), ("F020", "00000001"))
        self.assertFalse(result["fapPresent"])
        self.assertTrue(result["missing"])
        self.assertFalse(result["calculationAvailable"])

    def test_series_override_selects_only_its_own_file(self):
        self.artifact("fafp_00000001.fap.999_000_000")
        selected = self.artifact("fafp_00000002.fap.001_002_003")
        result = find_fafp_resources(self.data, "F031")
        self.assertEqual(result["fa2fpId"], "00000002")
        self.assertEqual(result["preferredCandidate"]["path"], str(selected))
        self.assertFalse(result["authenticated"])
        self.assertFalse(result["calculationAvailable"])

    def test_empty_series_override_inherits_the_parent_mapping(self):
        self.mapping.write_text(MAPPING.replace('fa2fpId="00000002"', 'fa2fpId=""'))
        result = find_fafp_resources(self.data, "F031")
        self.assertEqual(result["fa2fpId"], "00000001")

    def test_legacy_short_hex_identifier_is_normalized(self):
        self.mapping.write_text(MAPPING.replace('fa2fpId="00000001"', 'fa2fpId="aB"'))
        candidate = self.artifact("fafp_000000ab.fap.001_002_003")
        result = find_fafp_resources(self.data, "F030")
        self.assertEqual(result["fa2fpId"], "000000AB")
        self.assertEqual(result["preferredCandidate"]["path"], str(candidate))

    def test_uses_actual_file_naming_and_highest_matching_version(self):
        self.artifact("fafp_00000001-099_099_099.fap")
        self.artifact("fafp_00000001.fap.001_009_002")
        selected = self.artifact("fafp_00000001.fap.001_010_001")
        result = find_fafp_resources(self.data, "F030")
        self.assertEqual(len(result["candidates"]), 2)
        self.assertEqual(result["preferredCandidate"]["path"], str(selected))

    def test_legacy_discovery_does_not_claim_current_retrieval(self):
        legacy = self.artifact("fafp_00000001.fap.009_000_000", "mainseries/F020/mapping")
        result = find_fafp_resources(self.data, "F030")
        self.assertEqual(result["candidates"][0]["path"], str(legacy))
        self.assertIsNone(result["preferredCandidate"])
        self.assertFalse(result["fapPresent"])
        self.assertEqual(result["legacyFilesFound"], 1)
        self.assertFalse(result["legacyRetrievalVerified"])
        current = self.artifact("fafp_00000001.fap.001_000_000")
        self.assertEqual(find_fafp_resources(self.data, "F030")["preferredCandidate"]["path"], str(current))

    def test_missing_unknown_duplicate_or_invalid_mapping_rejected(self):
        with self.assertRaises(FpResourceError):
            find_fafp_resources(None, "F030")
        with self.assertRaises(FpResourceError):
            find_fafp_resources(self.data, "UNKNOWN")
        for bad in [MAPPING.replace("<series>F030</series>", "<series>F030</series><series>F030</series>"),
                    MAPPING.replace('fa2fpId="00000001"', 'fa2fpId="../bad"'),
                    MAPPING.replace('<series fa2fpId="00000002">', '<series fa2fpId="NOTHEX">')]:
            self.mapping.write_text(bad)
            with self.subTest(mapping=bad), self.assertRaises(FpResourceError):
                find_fafp_resources(self.data, "F031" if 'fa2fpId="NOTHEX"' in bad else "F030")

    def test_symlink_cannot_escape_dataset(self):
        outside = Path(self.temporary.name) / "outside"
        outside.write_bytes(b"not-a-resource")
        folder = self.data / "swe" / "fafp"
        folder.mkdir(parents=True)
        try:
            (folder / "fafp_00000001.fap.001_000_000").symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable on this platform.")
        with self.assertRaises(FpResourceError):
            find_fafp_resources(self.data, "F030")


if __name__ == "__main__":
    unittest.main()

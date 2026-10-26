"""Native FP serialization/checksum checks, not vehicle or FA->FP generation.

The FP fixture is synthetic. Its VPC is a fixed bitwise-reference value over
the independently specified byte layout, not an expected real vehicle profile.
"""

from pathlib import Path
import unittest

from bmgarage.fp import (bmw_crc32_autosar, calculate_vpc, crc32_autosar,
                         inspect_fp, serialize_categories)
from bmgarage.models import DocumentError


FIXTURES = Path(__file__).parent / "fixtures"


class NativeFpAlgorithmTests(unittest.TestCase):
    def test_autosar_standard_check_vector(self):
        self.assertEqual(crc32_autosar(b"123456789"), 0x1697D06A)
        self.assertEqual(crc32_autosar(b""), 0)
        self.assertEqual(crc32_autosar(bytes(4)), 0x6FB32240)

    def test_bmw_reserved_crc_value_substitution(self):
        self.assertEqual(crc32_autosar(b"\xff" * 4), 0xFFFFFFFF)
        self.assertEqual(bmw_crc32_autosar(b"\xff" * 4), 0xFFFFFFFE)

    def test_version_two_sorted_binary_layout(self):
        values = {2: [513], 1: [256, 2]}
        self.assertEqual(serialize_categories(values, 2).hex(), "02010002000201000200010201")
        self.assertEqual(serialize_categories(values, 2, True).hex(), "0202010002000201000200010201")

    def test_legacy_count_layout_and_newer_count_width(self):
        self.assertEqual(serialize_categories({1: [256, 2]}, 1).hex(), "01010200020100")
        self.assertEqual(serialize_categories({1: [256, 2]}, 3).hex(), "0101000200020100")
        self.assertEqual(serialize_categories({}, 2), b"\x00")

    def test_duplicate_criterion_values_are_preserved(self):
        self.assertEqual(serialize_categories({1: [2, 2]}, 2).hex(), "0101000200020002")

    def test_count_ranges_and_unsigned_values_are_enforced(self):
        invalid = [({True: [1]}, 2), ({256: [1]}, 2), ({1: [-1]}, 2),
                   ({1: [65536]}, 2), ({1: []}, 2), ({1: [1]}, 4),
                   ({1: [1] * 256}, 1), ({1: [1] * 65536}, 2),
                   ({i: [1] for i in range(256)}, 2)]
        for categories, version in invalid:
            with self.subTest(version=version), self.assertRaises((DocumentError, TypeError)):
                serialize_categories(categories, version)

    def test_maximum_unsigned_values_and_version_count_boundaries(self):
        legacy = serialize_categories({255: [65535] * 255}, 1)
        self.assertEqual(legacy[:3], b"\x01\xff\xff")
        self.assertEqual(len(legacy), 513)
        self.assertEqual(legacy[-2:], b"\xff\xff")
        current = serialize_categories({255: [65535] * 65535}, 2)
        self.assertEqual(current[:4], b"\x01\xff\xff\xff")
        self.assertEqual(len(current), 131074)
        self.assertEqual(serialize_categories({i: [65535] for i in range(255)}, 2)[0], 255)

    def test_vpc_uses_ascii_paint_upholstery_and_excludes_version_byte(self):
        self.assertEqual(calculate_vpc({2: [513], 1: [256, 2]}, 2, "0300", "LCSW"), "005B2113")
        self.assertNotEqual(calculate_vpc({2: [513], 1: [256, 2]}, 2, "0301", "LCSW"), "005B2113")
        with self.assertRaises(DocumentError):
            calculate_vpc({1: [2]}, 2, "0300", "???")

    def test_saved_fp_semantics_and_required_fa_for_checksum(self):
        result = inspect_fp((FIXTURES / "fp.xml").read_text())
        self.assertEqual(result["version"], 2)
        self.assertEqual(result["categoryCount"], 2)
        self.assertEqual(result["criterionCount"], 3)
        self.assertEqual(result["categories"][0]["id"], 2)
        self.assertEqual(result["storedVpc"], "005B2113")
        self.assertEqual(result["checksumStatus"], "requires_fa")
        self.assertIsNone(result["checksumMatches"])
        self.assertFalse(result["faToFpCalculationPerformed"])

    def test_actual_saved_vpc_comparison_match_and_mismatch(self):
        fp, fa = (FIXTURES / "fp.xml").read_text(), (FIXTURES / "fa.xml").read_text()
        result = inspect_fp(fp, fa)
        self.assertEqual(result["checksumStatus"], "match")
        self.assertTrue(result["checksumMatches"])
        self.assertEqual(result["calculatedVpc"], "005B2113")
        self.assertFalse(result["faConsistencyVerified"])
        result = inspect_fp(fp.replace('vpc="005B2113"', 'vpc="00000000"'), fa)
        self.assertEqual(result["checksumStatus"], "mismatch")
        self.assertFalse(result["checksumMatches"])

    def test_falist_selection_can_supply_matching_checksum_inputs(self):
        result = inspect_fp((FIXTURES / "fp.xml").read_text(),
                            (FIXTURES / "falist.xml").read_text(), entry_index=0)
        self.assertTrue(result["checksumMatches"])

    def test_no_stored_checksum_does_not_become_a_match(self):
        xml = (FIXTURES / "fp.xml").read_text().replace(' vpc="005B2113"', "")
        result = inspect_fp(xml, (FIXTURES / "fa.xml").read_text())
        self.assertEqual(result["checksumStatus"], "not_present")
        self.assertIsNone(result["checksumMatches"])
        self.assertEqual(result["calculatedVpc"], "005B2113")

    def test_conflicting_vehicle_identity_rejects_checksum_comparison(self):
        fp, fa = (FIXTURES / "fp.xml").read_text(), (FIXTURES / "fa.xml").read_text()
        for bad in [fp.replace('series="F030"', 'series="F031"'),
                    fp.replace('vinLong="WBA00000200000000"', 'vinLong="WBA00000300000000"')]:
            with self.assertRaises(DocumentError):
                inspect_fp(bad, fa)

    def test_malformed_unsupported_or_ambiguous_fp_is_rejected(self):
        original = (FIXTURES / "fp.xml").read_text()
        cases = [original.replace('fpVersion="2"', 'fpVersion="4"'),
                 original.replace('vpc="005B2113"', 'vpc="xyz"'),
                 original.replace('<cat val="2"', '<cat val="1"'),
                 original.replace('val="513"', 'val="65536"'),
                 original.replace('psdz.data.fp', 'psdz.data.notfp'),
                 original.replace('</standardFP>', '<unknown/></standardFP>'),
                 original.replace('<standardFP fpVersion="2">', '<standardFP fpVersion="2"><cat val="9"/>')]
        for xml in cases:
            with self.subTest(prefix=xml[:50]), self.assertRaises(DocumentError):
                inspect_fp(xml)

    def test_external_xml_content_is_rejected(self):
        xml = (FIXTURES / "fp.xml").read_text()
        end = xml.index("?>") + 2
        dtd = '<!DOCTYPE fp [<!ENTITY xxe SYSTEM "file:///must-not-read">]>'
        with self.assertRaises(DocumentError):
            inspect_fp(xml[:end] + dtd + xml[end:])


if __name__ == "__main__":
    unittest.main()

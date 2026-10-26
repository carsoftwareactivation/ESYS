"""Native FAFP algorithm tests over synthetic, explicitly UNTRUSTED mappings.

The fixtures below are not real BMW mapping data, signed/decrypted artifacts,
expected vehicle profiles or successful programming/authentication responses.
"""

from dataclasses import FrozenInstanceError
from pathlib import Path
from xml.sax.saxutils import quoteattr
import unittest

from bmgarage.fap import (FapAuthenticationRequired, FapError,
                         evaluate_untrusted_mapping, lookup_elements,
                         parse_untrusted_fap, require_production_mapping,
                         verify_untrusted_consistency)


FIXTURES = Path(__file__).parent / "fixtures"
FA = (FIXTURES / "fa.xml").read_text()


def rule(selector, code, pairs, bounds=""):
    elements = "".join(f'<fpElement categoryVal="{category}" criteriaVal="{criterion}">'
                       '<criteriaName>Test criterion</criteriaName><criteriaNameEN>Test criterion</criteriaNameEN>'
                       '<categoryName>Test category</categoryName><categoryNameEN>Test category</categoryNameEN>'
                       '</fpElement>' for category, criterion in pairs)
    return f'<fa2fpMapping {bounds}><faElement selector={quoteattr(selector)} code={quoteattr(code)}/>{elements}</fa2fpMapping>'


def document(rules=None, signature=""):
    if rules is None:
        rules = [rule("T", "3A51", [(1, 10)]), rule("A", "0714", [(2, 20)]),
                 rule("W", "205", [(3, 30)]), rule("W", "249", [(3, 31)])]
    return ('<fa2fp xmlns="http://bmw.com/2005/psdz.data.fa2fp" isEncrypted="false">'
            '<sweHeader mainSeries="F020" date="2024-06-01" time="12:00:00Z" createdBy="synthetic-algorithm-test">'
            '<sweIdent><processClass>FAFP</processClass><id>00000001</id>'
            '<mainVersion>001</mainVersion><subVersion>002</subVersion><patchVersion>003</patchVersion></sweIdent>'
            + signature + '</sweHeader><data><fa2fpMappings>' + "".join(rules) +
            '</fa2fpMappings></data></fa2fp>')


class NativeFapParsingTests(unittest.TestCase):
    def test_identity_is_complete_and_explicitly_untrusted(self):
        mapping = parse_untrusted_fap(document(), "fafp_00000001-001_002_003")
        self.assertEqual(mapping.identity.sgbmid, "fafp_00000001-001_002_003")
        self.assertEqual(mapping.identity.main_series, "F020")
        self.assertFalse(mapping.authenticated)
        self.assertEqual(len(mapping.rules), 4)
        with self.assertRaises(FrozenInstanceError):
            mapping.authenticated = True

    def test_each_identity_component_must_match_expected_resource(self):
        for expected in ("fafp_00000002-001_002_003", "fafp_00000001-001_002_004",
                         "swfl_00000001-001_002_003", 1):
            with self.subTest(expected=expected), self.assertRaises(FapError):
                parse_untrusted_fap(document(), expected)

    def test_signature_presence_never_becomes_trust(self):
        signature = '<ds:Signature xmlns:ds="http://www.w3.org/2000/09/xmldsig#"/>'
        mapping = parse_untrusted_fap(document(signature=signature))
        self.assertTrue(mapping.signature_present)
        self.assertFalse(mapping.authenticated)
        with self.assertRaises(FapAuthenticationRequired):
            require_production_mapping(mapping)

    def test_unsigned_mapping_cannot_enter_production(self):
        with self.assertRaises(FapAuthenticationRequired):
            require_production_mapping(parse_untrusted_fap(document()))

    def test_encrypted_content_is_not_treated_as_plaintext(self):
        for value in ("true", "1"):
            with self.subTest(value=value), self.assertRaises(FapAuthenticationRequired):
                parse_untrusted_fap(document().replace('isEncrypted="false"', f'isEncrypted="{value}"'))

    def test_malformed_headers_mappings_and_numeric_fields_rejected(self):
        sample = document()
        cases = [sample.replace('isEncrypted="false"', 'isEncrypted="invalid"'),
                 sample.replace('<processClass>FAFP</processClass>', '<processClass>SWFL</processClass>'),
                 sample.replace('mainSeries="F020"', 'mainSeries="../x"'),
                 sample.replace('date="2024-06-01"', 'date="invalid"'),
                 sample.replace('<id>00000001</id>', '<id>../bad</id>'),
                 sample.replace('selector="T"', 'selector="X"'),
                 sample.replace('categoryVal="1"', 'categoryVal="256"'),
                 sample.replace('criteriaVal="10"', 'criteriaVal="65536"'),
                 sample.replace('criteriaVal="10"', 'criteriaVal="-1"'),
                 sample.replace('</data>', '<unknown/></data>')]
        for case in cases:
            with self.subTest(xml=case[:150]), self.assertRaises(FapError):
                parse_untrusted_fap(case)

    def test_dtd_entities_and_wrong_namespace_rejected(self):
        with self.assertRaises(ValueError):
            parse_untrusted_fap('<!DOCTYPE fa2fp [<!ENTITY x SYSTEM "file:///must-not-read">]>' + document())
        with self.assertRaises(FapError):
            parse_untrusted_fap(document().replace("psdz.data.fa2fp", "not-the-fap-namespace"))

    def test_empty_mapping_or_duplicate_source_node_rejected(self):
        with self.assertRaises(FapError):
            parse_untrusted_fap(document([]))
        with self.assertRaises(FapError):
            parse_untrusted_fap(document().replace('<faElement selector="T" code="3A51"/>',
                                                 '<faElement selector="T" code="3A51"/><faElement selector="T" code="3A51"/>'))


class NativeFapRuleTests(unittest.TestCase):
    def test_type_time_and_options_are_mapped_in_original_order(self):
        result = evaluate_untrusted_mapping(parse_untrusted_fap(document()), FA)
        self.assertEqual(result.categories, ((1, (10,)), (2, (20,)), (3, (30, 31))))
        self.assertEqual(result.matched_rule_count, 4)
        self.assertEqual(result.missing_mappings, ())
        self.assertTrue(result.as_dict()["mappingCoverageComplete"])
        self.assertFalse(result.as_dict()["authenticated"])
        self.assertFalse(result.as_dict()["faToFpCalculationPerformed"])

    def test_lower_boundary_inclusive_and_upper_boundary_exclusive(self):
        mapping = parse_untrusted_fap(document([
            rule("T", "3A51", [(1, 10)], 'from="0714" to="0715"'),
            rule("T", "3A51", [(1, 11)], 'to="0714"')]))
        self.assertEqual([x.criterion for x in lookup_elements(mapping, "T", "3A51", "0714")], [10])
        self.assertEqual(lookup_elements(mapping, "T", "3A51", "0715"), ())

    def test_ranges_compare_year_before_month_not_raw_mmYY_integer(self):
        mapping = parse_untrusted_fap(document([rule("T", "3A51", [(1, 10)], 'from="1213" to="0115"')]))
        self.assertEqual(len(lookup_elements(mapping, "T", "3A51", "0714")), 1)
        self.assertEqual(lookup_elements(mapping, "T", "3A51", "1113"), ())
        self.assertEqual(lookup_elements(mapping, "T", "3A51", "0115"), ())

    def test_missing_empty_and_minus_one_bounds_are_unbounded(self):
        for bounds in ("", 'from="" to=""', 'from="-1" to="-1"'):
            with self.subTest(bounds=bounds):
                mapping = parse_untrusted_fap(document([rule("T", "3A51", [(1, 10)], bounds)]))
                self.assertEqual(len(lookup_elements(mapping, "T", "3A51", "0000")), 1)
                self.assertEqual(len(lookup_elements(mapping, "T", "3A51", "9999")), 1)

    def test_multiple_active_rules_and_duplicate_criteria_are_preserved(self):
        mapping = parse_untrusted_fap(document([rule("T", "3A51", [(1, 10), (1, 10)]),
                                               rule("T", "3A51", [(1, 11)])]))
        result = evaluate_untrusted_mapping(mapping, FA)
        self.assertEqual(result.categories, ((1, (10, 10, 11)),))
        self.assertIn(("A", "0714"), result.missing_mappings)
        self.assertIn(("W", "205"), result.missing_mappings)

    def test_paint_and_upholstery_mappings_are_optional(self):
        mapping = parse_untrusted_fap(document())
        self.assertEqual(evaluate_untrusted_mapping(mapping, FA).missing_mappings, ())
        extra = document([rule("T", "3A51", [(1, 10)]), rule("A", "0714", [(2, 20)]),
                          rule("L", "0300", [(4, 40)]), rule("P", "LCSW", [(5, 50)]),
                          rule("W", "205", [(3, 30)]), rule("W", "249", [(3, 31)])])
        self.assertEqual(evaluate_untrusted_mapping(parse_untrusted_fap(extra), FA).categories,
                         ((1, (10,)), (2, (20,)), (4, (40,)), (5, (50,)), (3, (30, 31))))

    def test_ewords_use_H_and_howords_use_K_without_guessing_aliases(self):
        fa = FA.replace("<eCodes/>", "<eCodes><eCode>TEST</eCode></eCodes>").replace(
            "<hoCodes/>", "<hoCodes><hoCode>ABCD</hoCode></hoCodes>")
        mapping = parse_untrusted_fap(document([rule("H", "TEST", [(6, 60)]), rule("K", "ABCD", [(7, 70)]),
                                               rule("E", "TEST", [(8, 80)]), rule("Z", "0714", [(9, 90)])]))
        result = evaluate_untrusted_mapping(mapping, fa)
        self.assertEqual(result.categories, ((6, (60,)), (7, (70,))))
        self.assertIn(("A", "0714"), result.missing_mappings)

    def test_invalid_time_bound_does_not_become_an_unbounded_rule(self):
        with self.assertRaises(FapError):
            parse_untrusted_fap(document([rule("T", "3A51", [(1, 10)], 'from="unknown"')]))


class NativeFapIndependentValidationTests(unittest.TestCase):
    def setUp(self):
        self.mapping = parse_untrusted_fap(document())
        self.values = {1: [10], 2: [20], 3: [30, 31]}

    def verify(self, values=None, **kwargs):
        return verify_untrusted_consistency(self.mapping, FA, self.values if values is None else values,
                                            kwargs.get("series", "F030"))

    def test_valid_algorithm_vector_passes_without_becoming_trusted(self):
        result = self.verify()
        self.assertTrue(result["algorithmChecksPassed"])
        self.assertEqual(result["possibleTypeKeys"], ["3A51"])
        self.assertFalse(result["productionValidated"])

    def test_reverse_check_rejects_unmapped_fp_pair_and_foreign_option(self):
        result = self.verify({**self.values, 99: [999]})
        self.assertIn("unmapped_fp_pair", {x["code"] for x in result["issues"]})
        foreign = parse_untrusted_fap(document([rule("W", "999", [(3, 30)]),
                                                *[rule("T", "3A51", [(1, 10)]), rule("A", "0714", [(2, 20)]),
                                                  rule("W", "205", [(3, 30)]), rule("W", "249", [(3, 31)])]]))
        result = verify_untrusted_consistency(foreign, FA, self.values, "F030")
        self.assertIn("fp_element_absent_from_fa", {x["code"] for x in result["issues"]})

    def test_forward_check_detects_omitted_fa_option_mapping_pair(self):
        result = self.verify({1: [10], 2: [20], 3: [30]})
        self.assertFalse(result["algorithmChecksPassed"])
        self.assertIn("missing_fp_pair_for_fa", {x["code"] for x in result["issues"]})

    def test_series_and_type_key_are_checked_independently(self):
        self.assertIn("series_mismatch", {x["code"] for x in self.verify(series="F031")["issues"]})
        self.assertIn("type_key_mismatch", {x["code"] for x in self.verify({2: [20], 3: [30, 31]})["issues"]})

    def test_forward_validator_retains_first_code_and_any_pair_semantics(self):
        mappings = parse_untrusted_fap(document([rule("T", "3A51", [(1, 10)]),
                                                 rule("A", "0714", [(2, 20), (2, 21)]),
                                                 rule("W", "205", [(3, 30)]), rule("W", "249", [(3, 31)])]))
        # The traced independent validator requires at least one corresponding
        # pair here. Recomputing an exact FP would give a different answer.
        result = verify_untrusted_consistency(mappings, FA, self.values, "F030")
        self.assertTrue(result["algorithmChecksPassed"])


if __name__ == "__main__":
    unittest.main()

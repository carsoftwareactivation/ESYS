"""Native model checks use real saved-document shapes, never a Java process."""

from pathlib import Path
import unittest

from bmgarage.models import (DocumentError, FA_NS, MAX_XML_DEPTH, SVT_NS, TAL_NS,
                             compare_isteps, inspect_fa, inspect_svt, inspect_tal,
                             parse_document, parse_istep)


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


class NativeDocumentTests(unittest.TestCase):
    def test_falist_selector_does_not_block_a_standalone_fa(self):
        result = inspect_fa(fixture("fa.xml"), entry_index=1)
        self.assertEqual(result["format"], "PSdZ FA")
        self.assertEqual(result["entryIndex"], 0)
        self.assertEqual(result["entryCount"], 1)

    def test_fa_semantic_fields_and_explicit_validation_scope(self):
        result = inspect_fa(fixture("fa.xml"))
        self.assertEqual((result["series"], result["type"], result["timeCriterion"]), ("F030", "3A51", "0714"))
        self.assertEqual(result["paint"], "0300")
        self.assertEqual(result["upholstery"], "LCSW")
        self.assertEqual(result["salapa"], ["205", "249"])
        self.assertTrue(result["structurallyValid"])
        self.assertFalse(result["vehicleCompatibilityVerified"])
        self.assertNotIn("valid", result)
        self.assertNotIn("standardValid", result)
        self.assertNotIn("fp", result)

    def test_original_falist_entry_metadata(self):
        result = inspect_fa(fixture("falist.xml"))
        self.assertEqual(result["format"], "E-Sys FAList")
        self.assertEqual((result["entryCount"], result["entryIndex"], result["entryName"]), (1, 0, "0001"))

    def test_multiple_falist_entries_select_explicit_distinct_vehicle_order(self):
        xml = fixture("falist.xml")
        entry = xml[xml.index("<id "):xml.index("</id>") + 5]
        extra = entry.replace('name="0001"', 'name="0002"').replace('typeKey="3A51"', 'typeKey="3A52"')
        xml = xml.replace("</faList>", extra + "</faList>")
        with self.assertRaises(DocumentError):
            inspect_fa(xml)
        result = inspect_fa(xml, entry_index=1)
        self.assertEqual(result["type"], "3A52")
        self.assertEqual(result["entryName"], "0002")
        for index in (-1, 2, True, "1"):
            with self.subTest(index=index), self.assertRaises(DocumentError):
                inspect_fa(xml, entry_index=index)

    def test_fa_missing_and_invalid_required_fields_rejected(self):
        xml = fixture("fa.xml")
        for bad in (xml.replace('typeKey="3A51"', ''),
                    xml.replace('typeKey="3A51"', 'typeKey="!"'),
                    xml.replace('timeCriteria="0714"', 'timeCriteria="ABCD"'),
                    xml.replace('colourCode="0300"', 'colourCode="300"')):
            with self.subTest(xml=bad[:70]), self.assertRaises(DocumentError):
                inspect_fa(bad)

    def test_fa_duplicate_standard_and_invalid_option_do_not_disappear(self):
        xml = fixture("fa.xml")
        for bad in (xml.replace("<saCode>205</saCode>", "<saCode>!!!</saCode>"),
                    xml.replace("<saCode>249</saCode>", "<saCode>205</saCode>"),
                    xml.replace("</fa>", '<standardFA/></fa>')):
            with self.assertRaises(DocumentError):
                inspect_fa(bad)

    def test_fa_namespace_and_unqualified_list_rules(self):
        for bad in (fixture("fa.xml").replace(FA_NS, "urn:wrong"),
                    fixture("falist.xml").replace("<faList>", '<faList xmlns="urn:wrong">'),
                    fixture("fa.xml").replace("<saCode>", '<saCode xmlns="urn:wrong">')):
            with self.assertRaises(DocumentError):
                inspect_fa(bad)

    def test_optional_fa_vin_does_not_invent_a_vehicle_identity(self):
        result = inspect_fa(fixture("fa.xml").replace('vinLong="WBA00000200000000"', ''))
        self.assertIsNone(result["vin"])
        with self.assertRaises(DocumentError):
            inspect_fa(fixture("fa.xml").replace('vinLong="WBA00000200000000"', 'vinLong="short"'))

    def test_fa_series_schema_supports_ncar_without_guessing_compatibility(self):
        result = inspect_fa(fixture("fa.xml").replace('series="F030"', 'series="NA5_"'))
        self.assertEqual(result["series"], "NA5_")
        self.assertFalse(result["vehicleCompatibilityVerified"])

    def test_svt_ecu_software_and_stored_source_metadata(self):
        result = inspect_svt(fixture("svt.xml"))
        self.assertEqual(result["version"], 5)
        self.assertEqual(len(result["ecus"]), 1)
        ecu = result["ecus"][0]
        self.assertEqual((ecu["baseVariant"], ecu["variant"], ecu["diagnosticAddress"]), ("DME", "DME_TEST", "10"))
        self.assertEqual(ecu["sgbm"][0], {"name": "btld_00000001-001_002_003", "processClass": "BTLD",
                                          "id": "00000001", "version": "001_002_003"})
        self.assertIsNone(ecu["bus"])
        self.assertFalse(result["vehicleCompatibilityVerified"])

    def test_svt_preserves_multiple_diagnostic_addresses(self):
        xml = fixture("svt.xml").replace("</diagnosticAddresses>", '<diagnosticAddress physicalOffset="17" physicalOffsetAsHex="11"/></diagnosticAddresses>')
        self.assertEqual(inspect_svt(xml)["ecus"][0]["diagnosticAddresses"], ["10", "11"])

    def test_svt_rejects_inconsistent_duplicate_and_missing_addresses(self):
        xml = fixture("svt.xml")
        for bad in (xml.replace('physicalOffsetAsHex="10"', 'physicalOffsetAsHex="11"'),
                    xml.replace("</diagnosticAddresses>", '<diagnosticAddress physicalOffset="16"/></diagnosticAddresses>'),
                    xml.replace('<diagnosticAddress physicalOffset="16" physicalOffsetAsHex="10"/>', ''),
                    xml.replace('physicalOffset="16"', 'physicalOffset="999"')):
            with self.assertRaises(DocumentError):
                inspect_svt(bad)

    def test_svt_duplicate_ecu_identity_is_not_silently_overwritten(self):
        xml = fixture("svt.xml")
        ecu = xml[xml.index("<ecu "):xml.index("</ecu>") + 6]
        with self.assertRaises(DocumentError):
            inspect_svt(xml.replace("</standardSVT>", ecu + "</standardSVT>"))

    def test_svt_invalid_software_identifier_and_wrong_nested_namespace(self):
        xml = fixture("svt.xml")
        for bad in (xml.replace("<id>00000001</id>", "<id>not-hex</id>"),
                    xml.replace("<mainVersion>001</mainVersion>", "<mainVersion>bad</mainVersion>"),
                    xml.replace("<ecu baseVariant", '<ecu xmlns="urn:wrong" baseVariant')):
            with self.assertRaises(DocumentError):
                inspect_svt(bad)

    def test_tal_saved_status_and_actions_are_not_execution(self):
        result = inspect_tal(fixture("tal.xml"))
        self.assertEqual(result["schemaVersion"], "24.6.0")
        self.assertEqual(result["status"], "Executable")
        self.assertFalse(result["executionPerformed"])
        line = result["lines"][0]
        self.assertEqual((line["id"], line["documentId"], line["ecu"], line["diagnosticAddress"]), (1, "tl_1", "DME", "10"))
        self.assertEqual(line["category"], "cdDeploy")
        self.assertEqual(line["actions"][0], {"category": "cdDeployTA", "sgbm": "cafd_00000001-001_002_003", "status": "Executable"})

    def test_tal_preserves_multiple_actions_and_lines(self):
        xml = fixture("tal.xml")
        action = xml[xml.index("<cdDeployTA "):xml.index("</cdDeployTA>") + len("</cdDeployTA>")]
        xml = xml.replace("</cdDeploy>", action.replace("00000001", "00000002") + "</cdDeploy>")
        line = xml[xml.index("<talLine "):xml.index("</talLine>") + len("</talLine>")]
        xml = xml.replace("</tal>", line.replace('id="tl_1"', 'id="tl_2"').replace('baseVariant="DME"', 'baseVariant="BDC"') + "</tal>")
        result = inspect_tal(xml)
        self.assertEqual(len(result["lines"]), 2)
        self.assertEqual([len(row["actions"]) for row in result["lines"]], [2, 2])
        self.assertEqual(result["lines"][1]["ecu"], "BDC")

    def test_tal_duplicate_line_missing_category_or_status_rejected(self):
        xml = fixture("tal.xml")
        line = xml[xml.index("<talLine "):xml.index("</talLine>") + len("</talLine>")]
        bad_inputs = [xml.replace("</tal>", line + "</tal>"),
                      xml.replace('id="tl_1" status="Executable"', 'id="tl_1"'),
                      xml.replace("<cdDeploy ", "<unknownDeploy ").replace("</cdDeploy>", "</unknownDeploy>"),
                      xml.replace('status="Executable"', 'status="simulated-success"')]
        for bad in bad_inputs:
            with self.assertRaises(DocumentError):
                inspect_tal(bad)

    def test_tal_additional_context_is_reported_as_uninspected(self):
        xml = fixture("tal.xml").replace("</tal>", "<TaskDependencies/></tal>")
        self.assertEqual(inspect_tal(xml)["uninspectedSections"], ["TaskDependencies"])

    def test_tal_unknown_action_and_invalid_category_status_are_rejected(self):
        xml = fixture("tal.xml")
        for bad in (xml.replace("cdDeployTA", "unknownTA"),
                    xml.replace('<cdDeploy status="Executable">', '<cdDeploy status="invented-success">')):
            with self.assertRaises(DocumentError):
                inspect_tal(bad)

    def test_empty_stored_tal_is_not_a_successful_programming_run(self):
        result = inspect_tal(f'<tal xmlns="{TAL_NS}" schemaVersion="24.6.0"/>')
        self.assertEqual(result["lines"], [])
        self.assertIsNone(result["status"])
        self.assertFalse(result["executionPerformed"])

    def test_external_content_is_rejected_for_all_document_readers(self):
        for kind, reader in [("fa", inspect_fa), ("svt", inspect_svt), ("tal", inspect_tal)]:
            xml = fixture(kind + ".xml")
            end = xml.index("?>") + 2
            dtd = '<!DOCTYPE ' + kind + ' [<!ENTITY xxe SYSTEM "file:///must-not-read">]>'
            with self.subTest(kind=kind), self.assertRaises(DocumentError):
                reader(xml[:end] + dtd + xml[end:])
        with self.assertRaises(DocumentError):
            inspect_tal(fixture("tal.xml").replace('refSchemaFile="tal.xsd"', 'refSchemaFile="https://example.invalid/tal.xsd"'))

    def test_include_and_schema_references_rejected(self):
        for tail in ('<xi:include xmlns:xi="http://www.w3.org/2001/XInclude" href="file:///must-not-read"/>',):
            with self.assertRaises(DocumentError):
                inspect_fa(fixture("fa.xml").replace("</fa>", tail + "</fa>"))
        bad = fixture("fa.xml").replace("<fa xmlns=", '<fa xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="urn:wrong https://example.invalid/xsd" xmlns=')
        with self.assertRaises(DocumentError):
            inspect_fa(bad)

    def test_xml_depth_size_and_malformed_limits(self):
        for xml in ("<r>" * (MAX_XML_DEPTH + 1) + "</r>" * (MAX_XML_DEPTH + 1),
                    "x" * (8 * 1024 * 1024 + 1), "<r>", "", "<r>\x00</r>"):
            with self.subTest(prefix=xml[:15]), self.assertRaises(DocumentError):
                parse_document(xml)


class NativeIStepTests(unittest.TestCase):
    def test_value_parts_and_canonical_separators(self):
        self.assertEqual(parse_istep("F020_24_07_500"), {"canonical": "F020-24-07-500", "mainSeries": "F020",
                                                        "year": 24, "month": 7, "number": 500})
        self.assertEqual(parse_istep("S18A-00_01-000")["canonical"], "S18A-00-01-000")

    def test_invalid_format_month_and_numeric_widths_rejected(self):
        for value in ("f020-24-07-500", "F020-24-00-500", "F020-24-13-500", "F020-2024-07-500",
                      "F020-24-07-1000", " F020-24-07-500", "F020-24-07-500 ", "غير صالح", None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_istep(value)

    def test_comparison_matches_traced_canonical_value_order(self):
        pairs = [("F020-24-07-500", "F020-24-11-500", -1),
                 ("F020-24-11-500", "F020-24-07-500", 1),
                 ("F020_24_07_500", "F020-24-07-500", 0),
                 ("F020-25-01-500", "S18A-24-01-500", -1)]
        for left, right, expected in pairs:
            with self.subTest(left=left, right=right):
                self.assertEqual(compare_isteps(left, right)["comparison"], expected)


if __name__ == "__main__":
    unittest.main()

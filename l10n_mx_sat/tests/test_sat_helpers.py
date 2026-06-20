# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from lxml import etree

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from ..services.sat_helpers import SAFE_XML_PARSER, sat_int, sat_str


@tagged("post_install", "-at_install")
class TestSatHelpers(TransactionCase):
    """Unit tests for SAT helper functions executed by Odoo."""

    def test_sat_str_none_returns_empty(self):
        self.assertEqual(sat_str(None), "")

    def test_sat_str_int_coerced_to_str(self):
        self.assertEqual(sat_str(5000), "5000")

    def test_sat_str_whitespace_stripped(self):
        self.assertEqual(sat_str("  5004  "), "5004")

    def test_sat_str_normal_passthrough(self):
        self.assertEqual(sat_str("abc"), "abc")

    def test_sat_int_none_returns_default(self):
        self.assertEqual(sat_int(None), 0)

    def test_sat_int_empty_returns_default(self):
        self.assertEqual(sat_int(""), 0)

    def test_sat_int_string_number(self):
        self.assertEqual(sat_int("3"), 3)

    def test_sat_int_passthrough(self):
        self.assertEqual(sat_int(3), 3)

    def test_sat_int_invalid_returns_default(self):
        self.assertEqual(sat_int("abc"), 0)

    def test_sat_int_custom_default(self):
        self.assertEqual(sat_int(None, -1), -1)

    def test_sat_int_whitespace_stripped(self):
        self.assertEqual(sat_int("  42  "), 42)

    def test_safe_xml_parser_parses_valid_xml(self):
        xml = b"<root><child>text</child></root>"
        tree = etree.fromstring(xml, SAFE_XML_PARSER)
        self.assertEqual(tree.tag, "root")

    def test_safe_xml_parser_does_not_resolve_xxe_entity(self):
        xxe = (
            b'<?xml version="1.0"?>'
            b"<!DOCTYPE foo ["
            b'  <!ENTITY xxe SYSTEM "file:///etc/passwd">'
            b"]>"
            b"<root>&xxe;</root>"
        )
        root = etree.fromstring(xxe, SAFE_XML_PARSER)
        self.assertIsNone(root.text)

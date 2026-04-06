# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from unittest import TestCase

from lxml import etree

from ..services.sat_helpers import SAFE_XML_PARSER, sat_int, sat_str


class TestSatStr(TestCase):
    """Unit tests for sat_str helper."""

    def test_none_returns_empty(self):
        self.assertEqual(sat_str(None), "")

    def test_int_coerced_to_str(self):
        self.assertEqual(sat_str(5000), "5000")

    def test_whitespace_stripped(self):
        self.assertEqual(sat_str("  5004  "), "5004")

    def test_normal_str_passthrough(self):
        self.assertEqual(sat_str("abc"), "abc")


class TestSatInt(TestCase):
    """Unit tests for sat_int helper."""

    def test_none_returns_default(self):
        self.assertEqual(sat_int(None), 0)

    def test_empty_returns_default(self):
        self.assertEqual(sat_int(""), 0)

    def test_string_number(self):
        self.assertEqual(sat_int("3"), 3)

    def test_int_passthrough(self):
        self.assertEqual(sat_int(3), 3)

    def test_invalid_returns_default(self):
        self.assertEqual(sat_int("abc"), 0)

    def test_custom_default(self):
        self.assertEqual(sat_int(None, -1), -1)

    def test_whitespace_stripped(self):
        self.assertEqual(sat_int("  42  "), 42)


class TestSafeXmlParser(TestCase):
    """Unit tests for SAFE_XML_PARSER."""

    def test_parses_valid_xml(self):
        xml = b"<root><child>text</child></root>"
        tree = etree.fromstring(xml, SAFE_XML_PARSER)
        self.assertEqual(tree.tag, "root")

    def test_xxe_entity_not_resolved(self):
        """External entities must never be expanded to prevent XXE attacks."""
        xxe = (
            b'<?xml version="1.0"?>'
            b"<!DOCTYPE foo ["
            b'  <!ENTITY xxe SYSTEM "file:///etc/passwd">'
            b"]>"
            b"<root>&xxe;</root>"
        )
        root = etree.fromstring(xxe, SAFE_XML_PARSER)
        # resolve_entities=False keeps the entity as an unresolved reference.
        # The critical assertion: text content is None (entity NOT expanded).
        self.assertIsNone(root.text)

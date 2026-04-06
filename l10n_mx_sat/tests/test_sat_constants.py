# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from unittest import TestCase

from ..services.sat_constants import (
    MX_TZ,
    SAT_CODE_NO_INFO,
    SAT_CODE_SUCCESS,
    SAT_REJECT_CODES,
)


class TestSatConstants(TestCase):
    """Verify SAT constants are properly defined."""

    def test_mx_tz_is_mexico_city(self):
        self.assertEqual(str(MX_TZ), "America/Mexico_City")

    def test_success_code(self):
        self.assertEqual(SAT_CODE_SUCCESS, "5000")

    def test_no_info_code(self):
        self.assertEqual(SAT_CODE_NO_INFO, "5004")

    def test_reject_codes_is_frozenset(self):
        self.assertIsInstance(SAT_REJECT_CODES, frozenset)

    def test_reject_codes_contains_known(self):
        for code in ("5001", "5002", "5005", "404"):
            self.assertIn(code, SAT_REJECT_CODES)

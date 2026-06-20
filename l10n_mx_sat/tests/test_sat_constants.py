# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

from odoo.addons.l10n_mx_sat.services import (
    SAT_CODE_DUPLICATE_LIFETIME,
    SAT_CODE_MAX_ELEMENTS,
    SAT_CODE_NO_INFO,
    SAT_CODE_SUCCESS,
    SAT_DEFAULT_SYNC_DAYS,
    SAT_METADATA_DEFAULT_WINDOW_DAYS,
)


@tagged("post_install", "-at_install")
class TestSatConstants(TransactionCase):
    def test_core_codes(self):
        self.assertEqual(SAT_CODE_SUCCESS, "5000")
        self.assertEqual(SAT_CODE_NO_INFO, "5004")
        self.assertEqual(SAT_CODE_MAX_ELEMENTS, "5003")
        self.assertEqual(SAT_CODE_DUPLICATE_LIFETIME, "5002")

    def test_defaults(self):
        self.assertEqual(SAT_DEFAULT_SYNC_DAYS, 30)
        self.assertEqual(SAT_METADATA_DEFAULT_WINDOW_DAYS, 7)

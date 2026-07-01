from odoo.tests.common import TransactionCase


class TestCFDISeries(TransactionCase):
    def test_create_method(self):
        # Only test the module default; standard implementation triggers
        # PostgreSQL sequence DDL that cannot be rolled back in TransactionCase.
        series = self.env["l10n_mx_cfdi.series"].create(
            {"name": "Test Series", "code": "TEST_NO_GAP"}
        )
        self.assertEqual(series.implementation, "no_gap")

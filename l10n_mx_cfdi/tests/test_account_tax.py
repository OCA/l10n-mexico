from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestAccountTax(TransactionCase):
    def setUp(self):
        super().setUp()
        self.tax_isr = self.env["account.tax"].create(
            {
                "name": "ISR Tax",
                # Add other required fields here
            }
        )
        self.tax_iva = self.env["account.tax"].create(
            {
                "name": "IVA Tax",
                # Add other required fields here
            }
        )
        self.tax_ieps = self.env["account.tax"].create(
            {
                "name": "IEPS Tax",
                # Add other required fields here
            }
        )

    def test_extract_l10n_mx_tax_code(self):
        self.assertEqual(self.tax_isr.extract_l10n_mx_tax_code(), "ISR")
        self.assertEqual(self.tax_iva.extract_l10n_mx_tax_code(), "IVA")
        self.assertEqual(self.tax_ieps.extract_l10n_mx_tax_code(), "IEPS")
        with self.assertRaises(UserError):
            self.env["account.tax"].create(
                {
                    "name": "Test Tax",
                    # Add other required fields here
                }
            ).extract_l10n_mx_tax_code()

    def test_extract_is_retention(self):
        self.assertFalse(self.tax_isr.extract_is_retention())
        self.assertFalse(self.tax_iva.extract_is_retention())
        self.assertFalse(self.tax_ieps.extract_is_retention())
        tax_retention = self.env.ref("l10n_mx.1_tax2")
        self.assertTrue(tax_retention.extract_is_retention())

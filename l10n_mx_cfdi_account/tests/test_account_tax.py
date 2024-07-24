from odoo.tests import TransactionCase


class TestAccountTax(TransactionCase):
    def setUp(self):
        super().setUp()
        self.tax_group = self.env["account.tax.group"].create(
            {
                "name": "IVA",
                "sequence": 1,
            }
        )

        self.tax_isr = self.env["account.tax"].create(
            {
                "name": "ISR Tax",
                "amount": 10.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": self.tax_group.id,
            }
        )
        self.tax_iva = self.env["account.tax"].create(
            {
                "name": "IVA Tax",
                "amount": 16.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": self.tax_group.id,
            }
        )
        self.tax_ieps = self.env["account.tax"].create(
            {
                "name": "IEPS Tax",
                "amount": 8.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": self.tax_group.id,
            }
        )

    def test_extract_l10n_mx_tax_code(self):
        self.assertEqual(self.tax_isr.extract_l10n_mx_tax_code(), "ISR")
        self.assertEqual(self.tax_iva.extract_l10n_mx_tax_code(), "IVA")
        self.assertEqual(self.tax_ieps.extract_l10n_mx_tax_code(), "IEPS")

        tax_without_code = self.env["account.tax"].create(
            {
                "name": "Test Tax",
                "amount": 5.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "tax_group_id": self.tax_group.id,
            }
        )

        tax_without_code.extract_l10n_mx_tax_code()

    def test_extract_is_retention(self):
        self.assertFalse(self.tax_isr.extract_is_retention())
        self.assertFalse(self.tax_iva.extract_is_retention())
        self.assertFalse(self.tax_ieps.extract_is_retention())

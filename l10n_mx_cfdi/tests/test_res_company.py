from odoo.tests import TransactionCase


class TestResCompany(TransactionCase):
    def test_l10n_mx_cfdi_auto_default(self):
        company = self.env["res.company"].create(
            {
                "name": "Test Company",
                # Add other required fields here
            }
        )
        self.assertTrue(company.l10n_mx_cfdi_auto)

    def test_l10n_mx_cfdi_enabled(self):
        company_mx = self.env["res.company"].create(
            {
                "name": "Test Company MX",
                "country_id": self.env.ref("base.mx").id,
                # Add other required fields here
            }
        )
        company_other = self.env["res.company"].create(
            {
                "name": "Test Company Other",
                "country_id": self.env.ref("base.us").id,
                # Add other required fields here
            }
        )
        self.assertTrue(company_mx.l10n_mx_cfdi_enabled)
        self.assertFalse(company_other.l10n_mx_cfdi_enabled)

    def test_l10n_mx_cfdi_enabled_change_country(self):
        company = self.env["res.company"].create(
            {
                "name": "Test Company",
                "country_id": self.env.ref("base.us").id,
                # Add other required fields here
            }
        )
        company.country_id = self.env.ref("base.mx").id
        self.assertTrue(company.l10n_mx_cfdi_enabled)

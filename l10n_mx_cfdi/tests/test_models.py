from odoo.tests.common import TransactionCase


class TestCFDIProductAndPartner(TransactionCase):
    def test_partner_cfdi_fields(self):
        partner = self.env["res.partner"].create({"name": "Partner with CFDI fields"})
        self.assertFalse(partner.tax_regime)
        self.assertFalse(partner.cfdi_use_id)

    def test_product_template_cfdi_fields(self):
        product = self.env["product.template"].create({"name": "CFDI Product"})
        self.assertFalse(product.l10n_mx_cfdi_product_code_id)
        self.assertFalse(product.l10n_mx_cfdi_product_measurement_unit_id)

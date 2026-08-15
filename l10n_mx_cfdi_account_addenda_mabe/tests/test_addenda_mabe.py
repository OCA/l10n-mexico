# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo.tests.common import tagged

from odoo.addons.l10n_mx_cfdi_account.tests.common import CFDIAccountTestCommon


@tagged("post_install", "-at_install")
class TestAddendaMabe(CFDIAccountTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.addenda_view = cls.env.ref(
            "l10n_mx_cfdi_account_addenda_mabe.l10n_mx_cfdi_account_addenda_mabe"
        )
        cls.customer.write(
            {
                "l10n_mx_edi_addenda": cls.addenda_view.id,
                "ref": "AMS-001",
                "street_name": "Industria",
                "street_number": "100",
                "street_number2": "B",
                "mabe_plant_code": "S001",
            }
        )

    def test_addenda_view_flag(self):
        self.assertTrue(self.addenda_view.l10n_mx_edi_addenda_flag)
        self.assertEqual(self.addenda_view.name, "Addenda Mabe")

    def test_partner_addenda_related_name(self):
        self.assertEqual(self.customer.l10n_mx_edi_addenda_name, "Addenda Mabe")

    def test_mabe_flag_compute(self):
        invoice = self._create_cfdi_invoice()
        self.assertTrue(invoice.mabe_flag)
        partner_no_addenda = self.env["res.partner"].create(
            {"name": "No Addenda", "country_id": self.env.ref("base.mx").id}
        )
        invoice.partner_id = partner_no_addenda
        self.assertFalse(invoice.mabe_flag)

    def test_render_mabe_addenda_via_framework(self):
        invoice = self._create_cfdi_invoice(
            ref="PO-77",
            mabe_ref1="R1",
            mabe_ref2="R2",
            mabe_amount_with_letter="CIEN PESOS",
            partner_shipping_id=self.customer.id,
        )
        sample = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" '
            b'Version="4.0">'
            b"</cfdi:Comprobante>"
        )
        result = invoice._l10n_mx_edi_cfdi_invoice_append_addenda(
            sample, self.addenda_view
        )
        self.assertIn(b"PO-77", result)
        self.assertIn(b"R1", result)
        self.assertIn(b"R2", result)
        self.assertIn(b"CIEN PESOS", result)
        self.assertIn(b"S001", result)
        self.assertIn(b"mabe", result)

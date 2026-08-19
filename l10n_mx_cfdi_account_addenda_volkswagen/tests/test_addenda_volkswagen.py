# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo.tests.common import tagged

from odoo.addons.l10n_mx_cfdi_account.tests.common import CFDIAccountTestCommon


@tagged("post_install", "-at_install")
class TestAddendaVolkswagen(CFDIAccountTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.addenda_view = cls.env.ref(
            "l10n_mx_cfdi_account_addenda_volkswagen.l10n_mx_cfdi_account_addenda_volkswagen"
        )
        cls.customer.write(
            {
                "l10n_mx_edi_addenda": cls.addenda_view.id,
                "ref": "VW-SUP-1",
            }
        )

    def test_addenda_view_flag(self):
        self.assertTrue(self.addenda_view.l10n_mx_edi_addenda_flag)
        self.assertEqual(self.addenda_view.name, "Addenda Volkswagen")

    def test_partner_addenda_related_name(self):
        self.assertEqual(self.customer.l10n_mx_edi_addenda_name, "Addenda Volkswagen")

    def test_vw_flag_compute(self):
        invoice = self._create_cfdi_invoice()
        self.assertTrue(invoice.vw_flag)
        partner_no_addenda = self.env["res.partner"].create(
            {"name": "No Addenda", "country_id": self.env.ref("base.mx").id}
        )
        invoice.partner_id = partner_no_addenda
        self.assertFalse(invoice.vw_flag)

    def test_render_vw_addenda_via_framework(self):
        invoice = self._create_cfdi_invoice(
            ref="PO-VW",
            vw_division="DIV1",
            vw_applicant_name="Applicant",
            vw_applicant_email="applicant@vw.test",
        )
        invoice.invoice_line_ids[0].vw_product_ref = "PART-99"
        sample = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" '
            b'Version="4.0">'
            b"</cfdi:Comprobante>"
        )
        result = invoice._l10n_mx_edi_cfdi_invoice_append_addenda(
            sample, self.addenda_view
        )
        self.assertIn(b"DIV1", result)
        self.assertIn(b"Applicant", result)
        self.assertIn(b"applicant@vw.test", result)
        self.assertIn(b"PART-99", result)
        self.assertIn(b"PO-VW", result)
        self.assertIn(b"PSV", result)

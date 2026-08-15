# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo.tests.common import tagged

from odoo.addons.l10n_mx_cfdi_account.tests.common import CFDIAccountTestCommon


@tagged("post_install", "-at_install")
class TestAddendaWhirlpool(CFDIAccountTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.addenda_view = cls.env.ref(
            "l10n_mx_cfdi_account_addenda_whirlpool.view_account_move_addenda_whirlpool"
        )
        cls.customer.write({"l10n_mx_edi_addenda": cls.addenda_view.id})

    def test_addenda_view_flag(self):
        self.assertTrue(self.addenda_view.l10n_mx_edi_addenda_flag)
        self.assertEqual(self.addenda_view.name, "Addenda Whirlpool")

    def test_partner_addenda_related_name(self):
        self.assertEqual(self.customer.l10n_mx_edi_addenda_name, "Addenda Whirlpool")

    def test_render_whirlpool_addenda_via_framework(self):
        invoice = self._create_cfdi_invoice(ref="WH-PO-1")
        sample = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" '
            b'Version="4.0">'
            b"</cfdi:Comprobante>"
        )
        result = invoice._l10n_mx_edi_cfdi_invoice_append_addenda(
            sample, self.addenda_view
        )
        self.assertIn(b"WH-PO-1", result)
        self.assertIn(b"detallista", result)

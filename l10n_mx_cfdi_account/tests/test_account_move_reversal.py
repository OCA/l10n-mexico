from odoo import fields

from .common import CFDIAccountTestCommon


class TestAccountMoveReversal(CFDIAccountTestCommon):
    def _create_reversal_wizard(self, invoice):
        return (
            self.env["account.move.reversal"]
            .with_context(
                active_model="account.move",
                active_ids=invoice.ids,
            )
            .new({"date": fields.Date.today()})
        )

    def test_prepare_default_reversal_skips_non_cfdi(self):
        invoice = self._create_cfdi_invoice(cfdi_required=False)
        invoice.action_post()
        reversal = self._create_reversal_wizard(invoice)
        res = reversal._prepare_default_reversal(invoice)
        self.assertNotIn("cfdi_required", res)

    def test_prepare_default_reversal_sets_cfdi_fields(self):
        invoice = self._create_cfdi_invoice()
        invoice.action_post()
        reversal = self._create_reversal_wizard(invoice)
        values = reversal._prepare_default_reversal(invoice)
        self.assertTrue(values["cfdi_required"])
        self.assertEqual(values["issuer_id"], self.issuer.id)
        self.assertEqual(
            values["payment_method_id"],
            self.env.ref("l10n_mx_catalogs.c_metodo_pago_PUE").id,
        )
        self.assertEqual(
            values["cfdi_use_id"],
            self.env.ref("l10n_mx_catalogs.c_uso_cfdi_G02").id,
        )

    def test_prepare_default_reversal_publico_en_general(self):
        public_partner = self.env.ref(
            "l10n_mx_cfdi.l10n_mx_cfdi_res_partner_publico_en_general"
        )
        invoice = self._create_cfdi_invoice(partner_id=public_partner.id)
        invoice.action_post()
        reversal = self._create_reversal_wizard(invoice)
        values = reversal._prepare_default_reversal(invoice)
        self.assertEqual(
            values["cfdi_use_id"],
            self.env.ref("l10n_mx_catalogs.c_uso_cfdi_S01").id,
        )

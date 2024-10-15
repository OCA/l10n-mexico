from odoo import models, fields


class AccountMoveReversal(models.TransientModel):
    _inherit = "account.move.reversal"

    def _prepare_default_reversal(self, move):
        """ Add CFDI required fields to the reversal if the original move is a CFDI """

        res = super()._prepare_default_reversal(move)

        if move.cfdi_required:
            data = {
                "cfdi_required": True,
                "payment_method_id": self.env["l10n_mx_catalogs.c_metodo_pago"]
                .search([("code", "=", "PUE")])
                .id,
                "cfdi_use_id": self.env["l10n_mx_catalogs.c_uso_cfdi"]
                .search([("code", "=", "G02")])
                .id,
                "issuer_id": move.issuer_id.id,
                "related_cert_ids": [(6, 0, [])],
            }

            # set the right cfdi use for operations with public
            if move.partner_id.vat == "XAXX010101000":
                data["cfdi_use_id"] = (
                    self.env["l10n_mx_catalogs.c_uso_cfdi"]
                    .search([("code", "=", "S01")])
                    .id
                )

            res.update(data)

        return res

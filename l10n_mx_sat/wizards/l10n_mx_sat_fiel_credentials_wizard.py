# Copyright 2026 Gray Matter Logic
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import base64

from odoo import fields, models
from odoo.exceptions import UserError

from ..services import SatClient


class L10nMxSatFielCredentialsWizard(models.TransientModel):
    _name = "l10n_mx_sat.fiel.credentials.wizard"
    _description = "SAT FIEL Credentials Wizard"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        required=True,
        readonly=True,
    )
    fiel_cer = fields.Binary(
        string="FIEL certificate (.cer)",
        attachment=False,
    )
    fiel_key = fields.Binary(
        string="FIEL private key (.key)",
        attachment=False,
    )
    fiel_password = fields.Char(
        string="FIEL password",
        default="",
    )

    def action_apply(self):
        """Store new FIEL credentials on the company."""
        for wizard in self:
            if not wizard.fiel_cer:
                raise UserError(
                    wizard.env._("Upload the FIEL certificate (.cer) first.")
                )
            if not wizard.fiel_key:
                raise UserError(
                    wizard.env._("Upload the FIEL private key (.key) first.")
                )
            if not wizard.fiel_password:
                raise UserError(wizard.env._("Enter the FIEL password first."))
            fiel_rfc = wizard._get_fiel_rfc()
            wizard.company_id.with_context(l10n_mx_sat_sync_vat_from_fiel=True).write(
                {
                    "l10n_mx_sat_fiel_cer": wizard.fiel_cer,
                    "l10n_mx_sat_fiel_key": wizard.fiel_key,
                    "l10n_mx_sat_fiel_password": wizard.fiel_password,
                    "vat": fiel_rfc,
                }
            )
        return {"type": "ir.actions.act_window_close"}

    def _get_fiel_rfc(self):
        self.ensure_one()
        try:
            cer_der = base64.b64decode(self.fiel_cer)
            key_der = base64.b64decode(self.fiel_key)
            client = SatClient(cer_der, key_der, self.fiel_password)
        except Exception as e:
            raise UserError(
                self.env._("Failed to validate FIEL credentials: %s", e)
            ) from e
        if not client.rfc:
            raise UserError(
                self.env._("Could not read the RFC from the FIEL certificate.")
            )
        return client.rfc.strip().upper()

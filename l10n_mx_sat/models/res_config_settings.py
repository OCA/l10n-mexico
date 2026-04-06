# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_mx_sat_fiel_cer = fields.Binary(
        related="company_id.l10n_mx_sat_fiel_cer",
        readonly=False,
    )
    l10n_mx_sat_fiel_key = fields.Binary(
        related="company_id.l10n_mx_sat_fiel_key",
        readonly=False,
    )
    l10n_mx_sat_fiel_password = fields.Char(
        related="company_id.l10n_mx_sat_fiel_password",
        readonly=False,
    )

    def l10n_mx_sat_test_connection(self):
        """Proxy for the 'Test connection' button in settings."""
        return self.company_id.l10n_mx_sat_test_connection()

from odoo import models, fields, api


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_mx_cfdi_auto = fields.Boolean(
        "Create CFDI on post",
        default=True,
        help="Enable to automatically sign CFDI when validating invoices.",
    )

    l10n_mx_cfdi_enabled = fields.Boolean(
        "Enable CFDI",
        compute="_compute_l10n_mx_cfdi_enabled",
        help="Enable CFDI for this company.",
    )

    def _compute_l10n_mx_cfdi_enabled(self):
        for company in self:
            company.l10n_mx_cfdi_enabled = company.country_id == self.env.ref("base.mx")

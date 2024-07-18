from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_mx_cfdi_auto = fields.Boolean(
        "Create CFDI on post",
        related="company_id.l10n_mx_cfdi_auto",
        help="Enable to automatically sign CFDI when validating invoices.",
        readonly=False,
    )

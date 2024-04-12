from odoo import fields, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    cfdi_cert_ids = fields.Many2many(
        comodel_name="l10n_mx_cfdi.document",
        string="CFDI",
        help="Send CFDI invoices",
        readonly=False,
        store=True,
    )

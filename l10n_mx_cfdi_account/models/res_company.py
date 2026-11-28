from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    l10n_mx_cfdi_sat_69b_check = fields.Boolean(
        "Check SAT list 69-B",
        help="Refuse to sign customer invoices and credit notes when the "
        "customer RFC is on SAT list 69-B (Presunto or Definitivo).",
    )

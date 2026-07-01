from odoo import api, fields, models


class CFDISeries(models.Model):
    _name = "l10n_mx_cfdi.series"
    _inherit = ["ir.sequence"]
    _description = "CFDI Series"

    code = fields.Char(copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("implementation"):
                vals["implementation"] = "no_gap"
        return super().create(vals_list)

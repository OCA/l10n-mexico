# Copyright (C) 2023 Open Source Integrators
# (https://www.opensourceintegrators.com).
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    audi_product_ref = fields.Char(string="Audi Product Reference")

    @api.onchange("product_id")
    def _onchange_product_id_audi_ref(self):
        for line in self:
            if line.product_id and line.product_id.audi_ref:
                line.audi_product_ref = line.product_id.audi_ref

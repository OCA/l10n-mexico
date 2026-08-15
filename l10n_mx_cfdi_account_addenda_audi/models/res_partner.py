# Copyright (C) 2023 Open Source Integrators
# (https://www.opensourceintegrators.com).
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    audi_supplier_email = fields.Char(string="Supplier Email")
    audi_supplier_number = fields.Char(string="Supplier Number")

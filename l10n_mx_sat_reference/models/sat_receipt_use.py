# Copyright (C) 2019 Open Source Integrators
# Copyright (C) 2019 Serpent Consulting Services
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class SatReceiptUse(models.Model):
    _name = "sat.receipt.use"
    _description = "Receipt Uses"

    name = fields.Char(string="Description", required=True)
    code = fields.Char(string="Code", required=True)
    natural = fields.Boolean(string="Apply to Natural Person")
    moral = fields.Boolean(string="Apply to Moral Person")
    date_start = fields.Datetime(string="Start Date")
    date_end = fields.Datetime(string="End Date")

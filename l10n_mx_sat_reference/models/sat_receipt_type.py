# Copyright (C) 2019 Open Source Integrators
# Copyright (C) 2019 Serpent Consulting Services
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class SatReceiptType(models.Model):
    _name = "sat.receipt.type"
    _description = "Receipt Types"

    name = fields.Char(string="Description", required=True)
    code = fields.Char(string="Code", required=True)
    date_start = fields.Datetime(string="Start Date")
    date_end = fields.Datetime(string="End Date")

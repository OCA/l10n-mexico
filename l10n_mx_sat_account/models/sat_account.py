# Copyright (C) 2019 Open Source Integrators
# Copyright (C) 2019 Serpent Consulting Services
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class SatAccount(models.Model):
    _name = "sat.account"
    _description = "SAT Account"

    name = fields.Char(string="name")
    code = fields.Char(string="Code")
    parent_id = fields.Many2one(comodel_name="sat.account", string="Parent")

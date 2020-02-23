# Copyright (C) 2019 Open Source Integrators
# Copyright (C) 2019 Serpent Consulting Services
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class AccountAccountTag(models.Model):
    _inherit = "account.account.tag"

    parent_id = fields.Many2one("account.account.tag", string="Parent")

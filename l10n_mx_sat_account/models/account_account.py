# Copyright (C) 2019 Open Source Integrators
# Copyright (C) 2019 Serpent Consulting Services
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class AccountAccountExtend(models.Model):
    _inherit = 'account.account'

    sat_account_id = fields.Many2one(
        comodel_name='sat.account',
        string='SAT Grouping Account')

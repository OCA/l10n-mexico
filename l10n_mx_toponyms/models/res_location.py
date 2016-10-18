# -*- coding: utf-8 -*-
# Copyright 2016 OpenPyme
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import fields, models


class ResLocation(models.Model):

    _name = 'res.location'

    name = fields.Char(
        size=64, required=True, select=True,
        help='Administrative divisions of a state.',
    )
    code = fields.Char(
        'Location Code', size=5, help='Location code according with SAT',
    )
    country_id = fields.Many2one(
        related='state_id.country_id',
        string='Country', readonly=True,
    )
    state_id = fields.Many2one(
        'res.country.state', 'State', required=True,
    )

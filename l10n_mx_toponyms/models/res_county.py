# -*- coding: utf-8 -*-
# Copyright 2016 OpenPyme
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import fields, models

import logging

# Get a logger to work with
_logger = logging.getLogger(__name__)


class ResPartnerCounty(models.Model):
    _description = 'County'
    _name = 'res.partner.county'
    _order = 'name'

    name = fields.Char(
        'Name', size=64, required=True, readonly=True,
        help='Administrative divisions of a state.',
    )
    state_id = fields.Many2one(
        'res.country.state', 'State', required=True,
    )
    country_id = fields.Many2one(
        related='state_id.country_id',
        string='Country', readonly=True,
    )
    code = fields.Char(
        'City Code', size=5,
        help='The city code in max. five chars.', readonly=True,
    )

# -*- coding: utf-8 -*-
# Copyright 2016 OpenPyme
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import fields, models


class ResZip(models.Model):

    _name = 'res.zip'

    name = fields.Char(string='Zip Code')
    location_id = fields.Many2one('res.location', 'Location', readonly=True)
    county_id = fields.Many2one(
        'res.partner.county', 'County', readonly=True,
    )
    state_id = fields.Many2one(
        related='county_id.state_id', string='State', readonly=True,
    )
    country_id = fields.Many2one(
        related='state_id.country_id', string='Country', readonly=True,
    )

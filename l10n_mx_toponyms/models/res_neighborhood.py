# -*- coding: utf-8 -*-
# Copyright 2016 OpenPyme
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import fields, models

import logging

# Get a logger to work with
_logger = logging.getLogger(__name__)


class ResNeighborhood(models.Model):

    _name = 'res.neighborhood'

    name = fields.Char(
        size=64, required=True, select=True, readonly=True,
        help='Administrative divisions of a state.',
    )
    zip_id = fields.Many2one(
        'res.zip', 'Zip', required=True, readonly=True,
    )
    location_id = fields.Many2one(
        related='zip_id.location_id', store=False,
        string='Location', readonly=True,
    )
    county_id = fields.Many2one(
        related='zip_id.county_id', store=False,
        string='County', readonly=True,
    )
    state_id = fields.Many2one(
        related='zip_id.state_id', store=False,
        string='State', readonly=True,
    )
    country_id = fields.Many2one(
        related='state_id.country_id', store=False,
        string='Country', readonly=True,
    )
    code = fields.Char(
        'City Code', size=5, help='The neighborhood code.', readonly=True,
    )

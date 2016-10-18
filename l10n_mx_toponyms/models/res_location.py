# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in root directory
##############################################################################

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

# -*- coding: utf-8 -*-
##############################################################################
# For copyright and license notices, see __openerp__.py file in root directory
##############################################################################

from openerp import api, fields, models


import logging

# Get a logger to work with
_logger = logging.getLogger('10n.mx.toponyms')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.one
    def _compute_l10n_mx_street3(self):
        self.l10n_mx_street3 = self.num_ext
        _logger.warn(
            'The field l10n_mx_street3 is deprecated please '
            'se instead num_ext',
        )

    @api.one
    def _compute_l10n_mx_street4(self):
        self.l10n_mx_street4 = self.num_int
        _logger.warn(
            'The field l10n_mx_street4 is deprecated please '
            'use instead num_int',
        )

    @api.one
    def _compute_street2(self):
        self.street2 = (
            self.neighborhood_id.name if
            self.neighborhood_id else False,
        )
        _logger.warn(
            'The field street2 is deprecated please '
            'use instead neighborhood_id',
        )

    @api.one
    def _compute_l10n_mx_city2(self):
        self.l10n_mx_city2 = (
            self.location_id.name if
            self.location_id else False,
        )
        _logger.warn(
            'The field l10n_mx_city2 is deprecated please '
            'use instead location_id',
        )

    @api.one
    def _compute_city(self):
        self.city = (
            self.ciudad_id.name if
            self.ciudad_id else False,
        )
        _logger.warn(
            'The field city is deprecated please '
            'use instead ciudad_id',
        )

    @api.one
    def _compute_zip(self):
        self.zip = (
            self.zip_id.name if
            self.zip_id else False,
        )
        _logger.warn(
            'The field zip is deprecated please '
            'use instead zip_id',
        )

    county_id = fields.Many2one('res.partner.county', 'County')
    location_id = fields.Many2one('res.location', 'Location')
    zip_id = fields.Many2one('res.zip', 'Zip')
    neighborhood_id = fields.Many2one('res.neighborhood', 'Neighborhood')
    num_int = fields.Char(size=10)
    num_ext = fields.Char(size=10)

    # The next files only exist to keep compatibility with deprecated modules
    l10n_mx_street3 = fields.Char(
        compute='_compute_l10n_mx_street3', store=False,
    )
    l10n_mx_street4 = fields.Char(
        compute='_compute_l10n_mx_street4', store=False,
    )
    street2 = fields.Char(compute='_compute_street2', store=False)
    l10n_mx_city2 = fields.Char(compute='_compute_l10n_mx_city2', store=False)
    city = fields.Char(compute='_compute_city', store=False)
    zip = fields.Char(compute='_compute_zip', store=False)

    # Old api use this method
    def _address_fields(self, cr, uid, context=None):
        """
        Returns the list of the address fields that synchronizes from the
        parent when the flag is set use_parent_address.
        """
        res = super(ResPartner, self)._address_fields(cr, uid, context=None)
        res.extend([
            'state_id', 'location_id', 'county_id',
            'neighborhood_id', 'num_int', 'num_ext',
        ])
        return res

    @api.onchange('zip_id')
    def onchange_zip_id(self):
        """ Fill automatically address getting data from
        the selected zip code
        """
        res_neighborhood_model = self.env['res.neighborhood']
        if not self.zip_id and not self.location_id:
            domain = {'neighborhood_id': []}
        elif not self.zip_id and self.location_id:
            domain = {
                'neighborhood_id': [('location_id', '=', self.location_id.id)],
            }
        else:
            self.location_id = self.zip_id.location_id.id
            self.county_id = self.zip_id.county_id.id
            domain = {'neighborhood_id': [('zip_id', '=', self.zip_id.id)]}
            neighborhoods = res_neighborhood_model.search(
                [('zip_id', '=', self.zip_id.id)],
            )
            if len(neighborhoods) == 1:
                self.neighborhood_id = neighborhoods.id
            else:
                if (self.neighborhood_id and
                        self.neighborhood_id.zip_id.id != self.zip_id.id):
                    # Erase value if there
                    self.neighborhood_id = False

        return {'domain': domain}

    @api.onchange('neighborhood_id')
    def onchange_neighborhood_id(self):
        if self.neighborhood_id:
            self.zip_id = self.neighborhood_id.zip_id.id
            self.location_id = self.neighborhood_id.location_id.id
            self.county_id = self.neighborhood_id.county_id.id

    @api.onchange('location_id')
    def onchange_location_id(self):
        if not self.location_id:
            domain = {
                'neighborhood_id': [],
                'zip_id': [],
            }
        else:
            self.state_id = self.location_id.state_id.id
            domain = {
                'zip_id': [('location_id', '=', self.location_id.id)],
            }
            if self.zip_id:
                domain['neighborhood_id'] = [
                    ('zip_id', '=', self.zip_id.id),
                ]
            else:
                domain['neighborhood_id'] = [
                    ('location_id', '=', self.location_id.id),
                ]

        return {'domain': domain}

    @api.v7
    def onchange_state(self, cr, uid, ids, state_id, context=None):
        context = dict(context or {})
        res = super(ResPartner, self).onchange_state(
            cr, uid, ids, state_id, context=context,
        )
        if state_id:
            res['domain'] = {
                'county_id': [('state_id', '=', state_id)],
                'location_id': [('state_id', '=', state_id)],
            }
        else:
            res['domain'] = {
                'county_id': [],
                'location_id': [],
            }
        return res

    @api.onchange('state_id')
    def onchange_state_id(self):
        if not self.state_id:
            domain = {
                'county_id': [],
                'location_id': [],
            }
        else:
            self.country_id = self.state_id.country_id.id
            domain = {
                'county_id': [('state_id', '=', self.state_id.id)],
                'location_id': [('state_id', '=', self.state_id.id)],
            }

        return {'domain': domain}

    @api.onchange('country_id')
    def onchange_country_id(self):
        if not self.country_id:
            domain = {'state_id': []}
        else:
            domain = {'state_id': [('country_id', '=', self.country_id.id)]}
        return {'domain': domain}

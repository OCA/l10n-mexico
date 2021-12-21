# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class L10nMxEdiResLocality(models.Model):
    _name = "l10n_mx_edi.res.locality"
    _description = "Locality"

    name = fields.Char(required=True, translate=True,)
    country_id = fields.Many2one(comodel_name="res.country", required=True,)
    state_id = fields.Many2one(
        comodel_name="res.country.state",
        domain="[('country_id', '=', country_id)]",
        required=True,
    )
    code = fields.Char()

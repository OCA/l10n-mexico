# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class ResCityZip(models.Model):
    _inherit = "res.city.zip"

    l10n_mx_edi_colony = fields.Char(string="Colony",)
    l10n_mx_edi_colony_code = fields.Char(string="Colony Code",)
    l10n_mx_edi_locality_id = fields.Many2one(
        comodel_name="l10n_mx_edi.res.locality", string="Locality",
    )

    _sql_constraints = [
        (
            "name_city_uniq",
            "UNIQUE(name, city_id, l10n_mx_edi_colony_code)",
            "You already have a zip with that code in the same city. "
            "The zip code must be unique within it's city",
        )
    ]

    @api.depends(
        "name",
        "city_id",
        "city_id.state_id",
        "city_id.country_id",
        "l10n_mx_edi_colony",
    )
    def _compute_new_display_name(self):
        for rec in self:
            name = [rec.name, rec.city_id.name]
            if rec.l10n_mx_edi_colony:
                name.append(rec.l10n_mx_edi_colony)
            if rec.city_id.state_id:
                name.append(rec.city_id.state_id.name)
            if rec.city_id.country_id:
                name.append(rec.city_id.country_id.name)
            rec.display_name = ", ".join(name)

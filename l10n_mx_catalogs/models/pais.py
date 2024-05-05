from odoo import api, fields, models


class Pais(models.Model):
    _name = "l10n_mx_catalogs.c_pais"
    _description = "Catálogo de Países SAT"

    code = fields.Char(string="Código", required=True)
    description = fields.Char(string="Descripción", required=True)

    @api.model
    def map_res_country(self, country_id):
        """Map a res.country to a c_pais"""
        if not country_id:
            return self

        country = self.search([("description", "like", country_id.name)], limit=1)
        return country

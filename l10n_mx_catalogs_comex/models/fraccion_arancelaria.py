from odoo import api, fields, models


class Fraccion(models.Model):
    _name = "l10n_mx_catalogs.c_fraccion"
    _description = "SAT Catalog for tariff code"
    _rec_names_search = ["code", "name"]

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Descripción", required=True)

    @api.depends("name", "code")
    def _compute_display_name(self):
        for clave in self:
            clave.display_name = (
                False
                if not clave.name
                else (
                    "{} - {}".format(
                        clave.code and "[%s] " % clave.code or "", clave.name
                    )
                )
            )

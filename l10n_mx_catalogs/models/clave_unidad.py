from odoo import api, fields, models


class ClaveUnidad(models.Model):
    _name = "l10n_mx_catalogs.c_clave_unidad"
    _description = "Catálogo SAT Clave Unidad"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Nombre", required=True)
    description = fields.Char(string="Descripción")
    symbol = fields.Char(string="Símbolo")

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

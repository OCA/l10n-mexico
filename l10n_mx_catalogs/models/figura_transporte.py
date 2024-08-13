from odoo import api, fields, models


class FiguraTransporte(models.Model):
    _name = "l10n_mx_catalogs.c_figura_transporte"
    _description = "Catálogo Figura Transporte"
    _rec_name = "description"

    code = fields.Char(string="Código", required=True)
    description = fields.Char(string="Descripción", required=True)

    @api.depends("description", "code")
    def _compute_display_name(self):
        for figura in self:
            figura.display_name = (
                False
                if not figura.description
                else (
                    "{} - {}".format(
                        figura.code and "[%s] " % figura.code or "", figura.description
                    )
                )
            )

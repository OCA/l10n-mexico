from odoo import api, fields, models


class ParteTransporte(models.Model):
    _name = "l10n_mx_catalogs.c_parte_transporte"
    _description = "Catálogo Parte Transporte"
    _rec_name = "description"

    code = fields.Char(string="Código", required=True)
    description = fields.Char(string="Descripción", required=True)

    @api.depends("description", "code")
    def _compute_display_name(self):
        for res in self:
            res.display_name = (
                False
                if not res.description
                else (
                    "{} - {}".format(
                        res.code and "[%s] " % res.code or "", res.description
                    )
                )
            )

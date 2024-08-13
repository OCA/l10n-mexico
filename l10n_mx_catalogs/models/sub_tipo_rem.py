from odoo import api, fields, models


class SubTipoRem(models.Model):
    _name = "l10n_mx_catalogs.c_sub_tipo_rem"
    _description = "Catálogo Subtipo de Remolque"
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

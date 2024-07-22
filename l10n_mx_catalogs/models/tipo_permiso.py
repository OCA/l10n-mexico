from odoo import api, fields, models


class TipoPermiso(models.Model):
    _name = "l10n_mx_catalogs.c_tipo_permiso"
    _description = "Catálogo Tipo de Permiso"
    _rec_name = "description"

    code = fields.Char(required=True)
    description = fields.Char(required=True)
    clave_transporte = fields.Char(required=True)

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

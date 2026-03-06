from odoo import api, fields, models


class ConfigAutotransporte(models.Model):
    _name = "l10n_mx_catalogs.c_config_autotransporte"
    _description = "Catálogo Configuración Autotransporte"
    _rec_name = "description"
    _rec_names_search = ["code", "description"]

    code = fields.Char("Código", required=True)
    description = fields.Char(string="Descripción", required=True)

    @api.depends("description", "code")
    def _compute_display_name(self):
        for clave in self:
            clave.display_name = (
                False
                if not clave.description
                else (
                    "{} - {}".format(
                        clave.code and f"[{clave.code}] " or "", clave.description
                    )
                )
            )

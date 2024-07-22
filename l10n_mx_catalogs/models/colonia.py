from odoo import api, fields, models


class Colonia(models.Model):
    _name = "l10n_mx_catalogs.c_colonia"
    _description = "Catálogo SAT Colonia"

    name = fields.Char(required=True)
    code = fields.Char(size=5, required=True)
    zip = fields.Char(size=5, required=True)

    @api.depends("name", "code")
    def _compute_display_name(self):
        for colonia in self:
            colonia.display_name = (
                False
                if not colonia.name
                else (
                    "{} - {}".format(
                        colonia.code and "[%s] " % colonia.code or "", colonia.name
                    )
                )
            )

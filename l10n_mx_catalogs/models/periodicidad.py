from odoo import api, fields, models


class Periodicidad(models.Model):
    _name = "l10n_mx_catalogs.c_periodicidad"
    _description = "Catalogo SAT de Periodicidad"

    code = fields.Char(string="Codigo", required=True)
    name = fields.Char(string="Nombre", required=True)

    @api.depends("name", "code")
    def _compute_display_name(self):
        for res in self:
            res.display_name = (
                False
                if not res.name
                else ("{} - {}".format(res.code and "[%s] " % res.code or "", res.name))
            )

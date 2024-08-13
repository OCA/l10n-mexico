from odoo import api, fields, models


class MetodoPago(models.Model):
    _name = "l10n_mx_catalogs.c_metodo_pago"
    _description = "Catalogo SAT de Metodos de pago"

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

from odoo import api, fields, models


class MotivoCancelacion(models.Model):
    _name = "l10n_mx_catalogs.c_motivo_cancelacion"
    _description = "Catalogo SAT de Motivos de Cancelación"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Nombre", required=True)

    @api.depends("name", "code")
    def _compute_display_name(self):
        for res in self:
            res.display_name = (
                False
                if not res.name
                else ("{} - {}".format(res.code and "[%s] " % res.code or "", res.name))
            )

from odoo import fields, models


class MotivoCancelacion(models.Model):
    _name = "l10n_mx_catalogs.c_motivo_cancelacion"
    _description = "Catalogo SAT de Motivos de Cancelación"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Nombre", required=True)

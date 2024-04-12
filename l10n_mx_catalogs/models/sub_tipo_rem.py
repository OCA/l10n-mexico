from odoo import fields, models


class SubTipoRem(models.Model):
    _name = "l10n_mx_catalogs.c_sub_tipo_rem"
    _description = "Catálogo Subtipo de Remolque"
    _rec_name = "description"

    code = fields.Char(string="Código", required=True)
    description = fields.Char(string="Descripción", required=True)

from odoo import fields, models


class TipoPermiso(models.Model):
    _name = "l10n_mx_catalogs.c_tipo_permiso"
    _description = "Catálogo Tipo de Permiso"
    _rec_name = "description"

    code = fields.Char(string="Código", required=True)
    description = fields.Char(string="Descripción", required=True)
    clave_transporte = fields.Char(string="Clave Transporte", required=True)

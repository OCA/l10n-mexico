from odoo import fields, models


class ConfigAutotransporte(models.Model):
    _name = "l10n_mx_catalogs.c_config_autotransporte"
    _description = "Catálogo Configuración Autotransporte"
    _rec_name = "description"

    code = fields.Char("Código", required=True)
    description = fields.Char(string="Descripción", required=True)

from odoo import api, fields, models


class Fraccion(models.Model):
    _name = "l10n_mx_catalogs.c_fraccion"
    _description = "SAT Catalog for tariff code"
    _rec_names_search = ["code", "name"]

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Descripción", required=True)
    active = fields.Boolean(default=True)

    @api.depends("name", "code")
    def _compute_display_name(self):
        for clave in self:
            prefix = f"[{clave.code}] " if clave.code else ""
            clave.display_name = False if not clave.name else f"{prefix}{clave.name}"

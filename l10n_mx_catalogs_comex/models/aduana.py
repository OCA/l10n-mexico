from odoo import api, fields, models


class Customs(models.Model):
    _name = "l10n_mx_catalogs.c_aduana"
    _description = "Aduana"
    _rec_name = "display_name"
    _order = "code, name"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Nombre", required=True)
    city = fields.Char(string="Ciudad")
    state = fields.Char(string="Estado")
    active = fields.Boolean(default=True)

    display_name = fields.Char(
        string="Nombre completo",
        compute="_compute_display_name",
        store=True,
    )

    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.code or ''} - {rec.name or ''}"

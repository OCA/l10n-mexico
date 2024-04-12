from odoo import api, fields, models


class Localidad(models.Model):
    _name = "l10n_mx_catalogs.c_localidad"
    _description = "Catalogo SAT Localidad"

    code = fields.Char(string="Codigo")
    name = fields.Char(string="Localidad")

    state_code = fields.Char(string="Codigo de Estado")
    state_id = fields.Many2one(
        "res.country.state", string="Estado", compute="_compute_state_id"
    )

    @api.depends("state_code")
    def _compute_state_id(self):
        for res in self:
            res.state_id = self.env["res.country.state"].search(
                [("code", "=", res.state_code)]
            )

from odoo import api, fields, models


class UsoCFDI(models.Model):
    _name = "l10n_mx_catalogs.c_uso_cfdi"
    _description = "Catalogo SAT de uso de CFDI"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Nombre", required=True)
    applies_to_natural_person = fields.Boolean(string="Aplica para persona física")
    applies_to_legal_person = fields.Boolean(string="Aplica para persona moral")

    applies_to_fiscal_regimes = fields.Char(string="Aplica para régimen fiscal")

    @api.depends("name", "code")
    def _compute_display_name(self):
        for res in self:
            res.display_name = (
                False
                if not res.name
                else ("{} - {}".format(res.code and "[%s] " % res.code or "", res.name))
            )

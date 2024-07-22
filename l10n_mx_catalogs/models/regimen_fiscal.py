from odoo import api, fields, models


class RegimenFiscal(models.Model):
    _name = "l10n_mx_catalogs.c_regimen_fiscal"
    _description = "Catálogo Regimen Fiscal"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Nombre", required=True)
    applies_to_natural_person = fields.Boolean(string="Aplica para persona física")
    applies_to_legal_person = fields.Boolean(string="Aplica para persona moral")

    @api.depends("name", "code")
    def _compute_display_name(self):
        for res in self:
            res.display_name = (
                False
                if not res.name
                else ("{} - {}".format(res.code and "[%s] " % res.code or "", res.name))
            )

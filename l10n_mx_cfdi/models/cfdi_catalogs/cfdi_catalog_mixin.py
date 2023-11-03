from odoo import fields, models, api


class CFDICatalogMixin(models.AbstractModel):
    _name = "l10n_mx_cfdi.catalog_mixin"
    _description = "CFDI Catalog Mixin"

    name = fields.Char("Name", required=False, compute="_compute_name", store=True)
    code = fields.Char("Code", required=True)
    description = fields.Char("Description", required=True)

    @api.depends("code", "description")
    def _compute_name(self):
        for record in self:
            record.name = f"{record.code} - {record.description}"

    @api.model
    def resolve_from_code(self, code):
        return self.search([("code", "=", code)], limit=1)

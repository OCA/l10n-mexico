from odoo import api, fields, models


class TipoRelacion(models.Model):
    _name = "l10n_mx_catalogs.c_tipo_relacion"
    _description = "Catálogo Tipo de Relación"
    _rec_names_search = ["code", "description"]

    code = fields.Char(string="Código", required=True)
    description = fields.Char(string="Descripción", required=True)

    name = fields.Char(compute="_compute_name", store=True)

    @api.depends("code", "description")
    def _compute_name(self):
        for record in self:
            record.name = f"{record.code} - {record.description}"

    @api.depends("name", "code")
    def _compute_display_name(self):
        for res in self:
            res.display_name = (
                False
                if not res.name
                else ("{} - {}".format(res.code and f"[{res.code}] " or "", res.name))
            )

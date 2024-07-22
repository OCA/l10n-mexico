from odoo import api, fields, models


class FormaPago(models.Model):
    _name = "l10n_mx_catalogs.c_forma_pago"
    _description = "Catalogo SAT de Formas de Pago"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Nombre", required=True)

    @api.depends("name", "code")
    def _compute_display_name(self):
        for record in self:
            record.display_name = (
                False
                if not record.name
                else (
                    "{} - {}".format(
                        record.code and "[%s] " % record.code or "", record.name
                    )
                )
            )

from odoo import api, fields, models


class ClaveProdServ(models.Model):
    _name = "l10n_mx_catalogs.c_clave_prod_serv"
    _description = "Catálogo SAT Clave Producto/Servicio"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Descripción", required=True)
    includes_iva = fields.Char(string="Incluye IVA Trasladado")
    includes_ieps = fields.Char(string="Incluye IEPS Trasladado")
    border_incentive = fields.Integer(string="Estímulo Fronterizo")
    alternative_names = fields.Char(string="Nombres Alternos")

    @api.depends("name", "code")
    def _compute_display_name(self):
        for clave in self:
            clave.display_name = (
                False
                if not clave.name
                else (
                    "{} - {}".format(
                        clave.code and "[%s] " % clave.code or "", clave.name
                    )
                )
            )

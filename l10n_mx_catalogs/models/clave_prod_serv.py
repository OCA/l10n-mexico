from odoo import models, fields


class CaveProdServ(models.Model):
    _name = "l10n_mx_catalogs.c_clave_prod_serv"
    _description = "Catálogo SAT Clave Producto/Servicio"

    code = fields.Char(string="Código", required=True)
    name = fields.Char(string="Descripción", required=True)
    includes_iva = fields.Char(string="Incluye IVA Trasladado")
    includes_ieps = fields.Char(string="Incluye IEPS Trasladado")
    border_incentive = fields.Integer(string="Estímulo Fronterizo")
    alternative_names = fields.Char(string="Nombres Alternos")

from odoo import api, fields, models


class CfdiMeasurementUnit(models.Model):
    _name = "l10n_mx_cfdi.cfdi_measurement_unit"
    _description = "CFDI Measurement Unit"
    _inherit = "l10n_mx_cfdi.catalog_mixin"
    _l10n_mx_catalog_name = "c_ClaveUnidad"

    detail = fields.Char("Detail")  # column 'Descripción'
    notes = fields.Char("Notes")  # column 'Notas'
    symbol = fields.Char("Symbol")  # column 'Símbolo'

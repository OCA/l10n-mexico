from odoo import fields, models


class CFDIVehicleTrailer(models.Model):
    _name = "l10n_mx_cfdi_waybill.vehicle_trailer"
    _description = 'Vehicle Trailer Record used in CFDI of type "Carta Porte"'
    _rec_name = "plate"

    plate = fields.Char(string="Número de Placa", required=True)
    type = fields.Many2one("l10n_mx_catalogs.c_sub_tipo_rem", string="Tipo de Trailer")

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )

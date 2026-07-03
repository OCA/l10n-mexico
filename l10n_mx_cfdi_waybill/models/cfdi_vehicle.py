from odoo import fields, models
from odoo.exceptions import ValidationError


class CFDIVehicle(models.Model):
    _name = "l10n_mx_cfdi_waybill.vehicle"
    _description = 'Vehicle Record used in CFDI of type "Carta Porte"'

    name = fields.Char(string="Nombre", required=True)
    plate = fields.Char(string="Número de Placa", required=True)
    model = fields.Char(string="Año/Modelo", required=True)
    vehicle_setup = fields.Many2one(
        "l10n_mx_catalogs.c_config_autotransporte",
        string="Configuración de Vehicular",
        required=True,
    )
    gross_vehicle_weight = fields.Float(
        string="Peso Bruto Vehicular", required=True, help="Peso Bruto Vehicular (Kg)"
    )

    permit_type = fields.Many2one(
        "l10n_mx_catalogs.c_tipo_permiso", string="Tipo de Permiso", required=True
    )
    permit_number = fields.Char(string="Número de Permiso", required=True)

    insurance_company = fields.Many2one(
        "res.partner", string="Compañía de Seguros", required=True
    )
    insurance_number = fields.Char(string="Número de Seguro", required=True)

    trailers = fields.Many2many(
        "l10n_mx_cfdi_waybill.vehicle_trailer",
        relation="l10n_mx_cfdi_waybill_vehicle_trailer_rel",
    )

    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )

    def validate(self):
        for entry in self:
            if not entry.plate:
                raise ValidationError(
                    self.env._(
                        "Debe ingresar el número de placa del vehículo: %s", entry.name
                    )
                )

            if not entry.model:
                raise ValidationError(
                    self.env._(
                        "Debe ingresar el año/modelo del vehículo: %s", entry.name
                    )
                )

            if not entry.vehicle_setup:
                raise ValidationError(
                    self.env._(
                        "Debe ingresar la configuración del vehículo: %s", entry.name
                    )
                )

            if not entry.permit_type:
                raise ValidationError(
                    self.env._(
                        "Debe seleccionar el tipo de permiso del vehículo: %s",
                        entry.name,
                    )
                )

            if not entry.permit_number:
                raise ValidationError(
                    self.env._(
                        "Debe ingresar el número de permiso del vehículo: %s",
                        entry.name,
                    )
                )

            if not entry.insurance_company:
                raise ValidationError(
                    self.env._(
                        "Debe seleccionar la compañía de seguros del vehículo: %s",
                        entry.name,
                    )
                )

            if not entry.insurance_number:
                raise ValidationError(
                    self.env._(
                        "Debe ingresar el número de seguro del vehículo: %s", entry.name
                    )
                )

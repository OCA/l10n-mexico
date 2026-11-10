# Copyright (C) 2026 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models
from odoo.exceptions import UserError


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    l10n_mx_cfdi_waybill_vehicle_id = fields.Many2one(
        "l10n_mx_cfdi_waybill.vehicle",
        string="Carta Porte vehicle",
    )
    l10n_mx_cfdi_trailer_type_id = fields.Many2one(
        "l10n_mx_catalogs.c_sub_tipo_rem",
        string="SAT trailer type",
    )
    l10n_mx_cfdi_waybill_trailer_id = fields.Many2one(
        "l10n_mx_cfdi_waybill.vehicle_trailer",
        string="Carta Porte trailer",
    )

    def _l10n_mx_cfdi_ensure_waybill_trailer(self):
        self.ensure_one()
        if self.l10n_mx_cfdi_waybill_trailer_id:
            return self.l10n_mx_cfdi_waybill_trailer_id
        if not self.license_plate:
            raise UserError(self.env._("Set the trailer plate."))
        if not self.l10n_mx_cfdi_trailer_type_id:
            raise UserError(self.env._("Set the SAT trailer type."))
        trailer = self.env["l10n_mx_cfdi_waybill.vehicle_trailer"].create(
            {
                "plate": self.license_plate,
                "type": self.l10n_mx_cfdi_trailer_type_id.id,
            }
        )
        self.l10n_mx_cfdi_waybill_trailer_id = trailer
        return trailer

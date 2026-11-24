# Copyright (C) 2026 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class TMSDriver(models.Model):
    _inherit = "tms.driver"

    l10n_mx_cfdi_waybill_transporter_id = fields.Many2one(
        "l10n_mx_cfdi_waybill.transporter",
        string="Carta Porte figure",
    )

    def _l10n_mx_cfdi_ensure_transporter(self):
        self.ensure_one()
        transporter = self.l10n_mx_cfdi_waybill_transporter_id
        if transporter:
            return transporter
        if (
            self.driver_license_number
            and not self.partner_id.l10n_mx_cfdi_waybill_driving_license
        ):
            self.partner_id.l10n_mx_cfdi_waybill_driving_license = (
                self.driver_license_number
            )
        transporter = self.env["l10n_mx_cfdi_waybill.transporter"].create(
            {
                "partner_id": self.partner_id.id,
                "type": self.env.ref("l10n_mx_catalogs.c_figura_transporte_1").id,
            }
        )
        self.l10n_mx_cfdi_waybill_transporter_id = transporter
        return transporter

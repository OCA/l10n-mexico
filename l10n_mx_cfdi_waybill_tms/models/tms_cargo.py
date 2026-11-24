# Copyright (C) 2026 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class TMSCargo(models.Model):
    _inherit = "tms.cargo"

    l10n_mx_cfdi_product_code_id = fields.Many2one(
        "l10n_mx_catalogs.c_clave_prod_serv",
        string="SAT product code",
    )
    l10n_mx_cfdi_unit_id = fields.Many2one(
        "l10n_mx_catalogs.c_clave_unidad",
        string="SAT unit",
    )
    l10n_mx_cfdi_hazardous = fields.Boolean(string="Hazardous material")
    l10n_mx_cfdi_hazardous_code = fields.Char(string="Hazardous material code")
    l10n_mx_cfdi_declared_value = fields.Float(string="Declared value")
    l10n_mx_cfdi_sat_packaging = fields.Char(string="SAT packaging")

    def _l10n_mx_cfdi_weight_kg(self):
        self.ensure_one()
        kilogram = self.env.ref("uom.product_uom_kgm", raise_if_not_found=False)
        if kilogram and self.weight_uom_id:
            return self.weight_uom_id._compute_quantity(self.weight, kilogram)
        return self.weight

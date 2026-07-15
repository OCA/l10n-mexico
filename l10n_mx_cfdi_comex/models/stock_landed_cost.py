# Copyright (C) 2024 Alexis López Zubieta (https://augetec.com).
# License GPL-3.0 or later (http://www.gnu.org/licenses/gpl).

from odoo import fields, models


class StockLandedCost(models.Model):
    _inherit = "stock.landed.cost"

    l10n_mx_cfdi_pedimento_id = fields.Many2one(
        "l10n_mx_cfdi.pedimento",
        string="Pedimento",
        help="Pedimento que se copiará a los lotes de las recepciones relacionadas.",
    )

    def _l10n_mx_cfid_apply_pedimento_to_lots(self):
        for cost in self:
            if not cost.l10n_mx_cfdi_pedimento_id:
                continue

            for picking in cost.picking_ids:
                for line in picking.move_ids.move_line_ids:
                    if not line.lot_id:
                        continue

                    line.lot_id.l10n_mx_cfdi_pedimento_id = (
                        cost.l10n_mx_cfdi_pedimento_id
                    )

    def button_validate(self):
        res = super().button_validate()
        self._l10n_mx_cfid_apply_pedimento_to_lots()
        return res

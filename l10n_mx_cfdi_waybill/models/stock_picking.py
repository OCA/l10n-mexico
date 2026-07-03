from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    waybill_ids = fields.Many2many(
        "l10n_mx_cfdi_waybill.waybill",
        string="waybill",
        relation="stock_picking_waybill_rel",
    )

    has_waybill = fields.Boolean(
        compute="_compute_has_waybill",
    )

    def _compute_has_waybill(self):
        for record in self:
            record.has_waybill = any(
                cn.state == "published" for cn in record.waybill_ids
            )

    def action_create_waybill(self):
        self.ensure_one()

        # open waybill form view
        return {
            "name": "waybill",
            "type": "ir.actions.act_window",
            "res_model": "l10n_mx_cfdi_waybill.waybill",
            "view_mode": "form",
            "view_type": "form",
            "target": "current",
            "context": {
                "default_stock_picking_id": self.id,
            },
        }

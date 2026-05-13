# -*- coding: utf-8 -*-

from odoo import fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    l10n_mx_cfdi_pedimento_id = fields.Many2one(
        "l10n_mx_cfdi.pedimento",
        string="Pedimento",
        tracking=True,
        help="Pedimento relacionado con este lote.",
    )

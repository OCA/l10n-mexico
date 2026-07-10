# Copyright (C) 2024 Alexis López Zubieta (https://augetec.com).
# License GPL-3.0 or later (http://www.gnu.org/licenses/gpl).

from odoo import fields, models


class StockLot(models.Model):
    _inherit = "stock.lot"

    l10n_mx_cfdi_pedimento_id = fields.Many2one(
        "l10n_mx_cfdi.pedimento",
        string="Pedimento",
        tracking=True,
        help="Pedimento relacionado con este lote.",
    )

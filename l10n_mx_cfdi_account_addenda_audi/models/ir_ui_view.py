# Copyright (C) 2023 Open Source Integrators
# (https://www.opensourceintegrators.com).
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class IrUiView(models.Model):
    _inherit = "ir.ui.view"

    l10n_mx_edi_addenda_flag = fields.Boolean(
        string="Is CFDI Addenda",
        help="Technical flag to mark this view as a selectable CFDI addenda.",
    )

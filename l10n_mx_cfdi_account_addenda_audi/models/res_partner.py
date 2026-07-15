# Copyright (C) 2023 Open Source Integrators
# (https://www.opensourceintegrators.com).
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    l10n_mx_edi_addenda = fields.Many2one(
        "ir.ui.view",
        string="CFDI Addenda",
        domain="[('l10n_mx_edi_addenda_flag', '=', True)]",
        help="Addenda template to include when generating CFDI for this partner.",
    )
    l10n_mx_edi_addenda_name = fields.Char(
        related="l10n_mx_edi_addenda.name",
        string="CFDI Addenda Name",
    )
    audi_supplier_email = fields.Char(string="Supplier Email")
    audi_supplier_number = fields.Char(string="Supplier Number")

# Copyright (C) 2023 Open Source Integrators
# (https://www.opensourceintegrators.com).
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    mabe_ref1 = fields.Char(string="Mabe Reference 1", default="NA")
    mabe_ref2 = fields.Char(string="Mabe Reference 2", default="NA")
    mabe_amount_with_letter = fields.Char(string="Amount with letter")
    mabe_flag = fields.Boolean(compute="_compute_mabe_flag", store=True)

    @api.depends("partner_id.l10n_mx_edi_addenda_name")
    def _compute_mabe_flag(self):
        for record in self:
            record.mabe_flag = (
                record.partner_id.l10n_mx_edi_addenda_name == "Addenda Mabe"
            )

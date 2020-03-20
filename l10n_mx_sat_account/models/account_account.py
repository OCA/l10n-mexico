# Copyright (C) 2019 Open Source Integrators
# Copyright (C) 2019 Serpent Consulting Services
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import _, api, models
from odoo.exceptions import UserError


class AccountAccountExtend(models.Model):
    _inherit = "account.account"

    @api.constrains("tag_ids")
    def check_sat(self):
        for rec in self:
            count = 0
            for tag in rec.tag_ids:
                if tag.parent_id == self.env.ref(
                    "l10n_mx_sat_account.account_account_tag_sat"
                ):
                    count += 1
                    if count >= 2:
                        raise UserError(
                            _(
                                "You cannot set more than one SAT tag on the "
                                "same account."
                            )
                        )

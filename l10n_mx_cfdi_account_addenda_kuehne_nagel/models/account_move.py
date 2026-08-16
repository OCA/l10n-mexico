# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    kn_file_type = fields.Selection(
        selection=[
            ("file", "File Number"),
            ("tracking", "Tracking Number"),
        ],
        string="KN File/Tracking Type",
    )
    kn_file_number_gl = fields.Char(string="KN File Number GL")
    kn_branch_centre = fields.Char(string="KN Branch Centre")
    kn_transport_ref = fields.Char(string="KN Transport Ref")
    kn_flag = fields.Boolean(compute="_compute_kn_flag", store=True)

    @api.depends("partner_id.l10n_mx_edi_addenda")
    def _compute_kn_flag(self):
        for record in self:
            record.kn_flag = (
                record.partner_id.l10n_mx_edi_addenda_name == "Addenda Kuehne Nagel"
            )

    def _l10n_mx_edi_kn_normalize_vals(self, vals):
        """Normalize KN-specific values before create/write."""
        vals = dict(vals)
        if vals.get("kn_branch_centre"):
            vals["kn_branch_centre"] = vals["kn_branch_centre"].strip().upper()
        if vals.get("kn_file_number_gl"):
            vals["kn_file_number_gl"] = vals["kn_file_number_gl"].strip()
        if vals.get("kn_transport_ref"):
            vals["kn_transport_ref"] = vals["kn_transport_ref"].strip()
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._l10n_mx_edi_kn_normalize_vals(vals) for vals in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        vals = self._l10n_mx_edi_kn_normalize_vals(vals)
        return super().write(vals)

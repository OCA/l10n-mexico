# Copyright (C) 2023 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    def action_upload_csf(self):
        return {
            "name": _("Import CSF File"),
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "import.csf",
            "target": "new",
        }

# Copyright (C) 2026 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    l10n_mx_cfdi_waybill_tms_require_published = fields.Boolean(
        string="Require a published Carta Porte before starting a cargo trip",
        config_parameter="l10n_mx_cfdi_waybill_tms.require_published_waybill",
    )

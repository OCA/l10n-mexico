# Copyright (C) 2023 Open Source Integrators
# (https://www.opensourceintegrators.com).
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from odoo import models
from odoo.exceptions import UserError


class CFDIService(models.Model):
    _inherit = "l10n_mx_cfdi.cfdi_service"

    def attach_addenda(self, cfdi_id, addenda_xml):
        """Attach addenda XML to an already published CFDI (Facturama api-lite)."""
        self.ensure_one()
        try:
            pac = self._get_pac()
            return pac.CfdiMultiEmisor.build_http_request(
                "put",
                f"addenda/{cfdi_id}/nu",
                addenda_xml,
            )
        except Exception as exc:
            raise UserError(
                self.env._("Failed to attach addenda to the CFDI: %s", exc)
            ) from exc

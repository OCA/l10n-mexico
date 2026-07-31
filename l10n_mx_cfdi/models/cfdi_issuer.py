import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CFDIIssuer(models.Model):
    """Holds the CFDI issuer information"""

    _name = "l10n_mx_cfdi.issuer"
    _description = "Emisor"
    _inherits = {"res.partner": "partner_id"}

    partner_id = fields.Many2one(
        "res.partner", delegate=True, ondelete="cascade", required=True
    )

    logo_url = fields.Char(string="URL del logo")
    fiscal_name = fields.Char(help="Razón Social del Emisor")
    certificate_file = fields.Binary(groups="base.group_system")
    key_file = fields.Binary(groups="base.group_system")
    key_password = fields.Char(string="Password", groups="base.group_system")
    service_id = fields.Many2one("l10n_mx_cfdi.cfdi_service")
    registered = fields.Boolean(store=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        res["country_id"] = self.env.ref("base.mx").id
        return res

    @api.model
    def _slugify(self, string):
        return string.lower().replace(" ", "_")

    def register_issuer(self):
        """Validate and activate the local CSD for stamping.

        For Facturama Multiemisor, also uploads the CSD to the PAC (required
        before ``issue()``).
        """
        self.ensure_one()
        if not self.vat:
            raise UserError(self.env._("Emitter RFC not defined.."))

        if not self.certificate_file or not self.key_file or not self.key_password:
            raise UserError(self.env._("Digital certificate not configured."))

        if not self.service_id:
            raise UserError(self.env._("Invoicing service not defined."))

        try:
            self.service_id.validate_csd(self)
            self.service_id.upload_issuer_csd(self)
            self.registered = True
        except UserError:
            self.registered = False
            raise
        except Exception as e:
            self.registered = False
            _logger.warning(e)
            raise UserError(self.env._("Cannot register the certificate.")) from e

    def unregister_issuer(self):
        """Deactivate the local CSD registration flag."""
        self.ensure_one()
        if self.service_id:
            self.service_id.delete_issuer_csd(self)
        self.registered = False

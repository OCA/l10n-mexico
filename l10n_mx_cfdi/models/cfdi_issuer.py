import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class CFDIIssuer(models.Model):
    """Holds the CFDI issuer information"""

    _name = "l10n_mx_cfdi.issuer"
    _description = "Emisor"

    # Embed partner fields
    partner_id = fields.Many2one(
        "res.partner", delegate=True, ondelete="cascade", required=True
    )

    logo_url = fields.Char(string="URL del logo")
    fiscal_name = fields.Char(help="Razón Social del Emisor")
    certificate_file = fields.Binary(groups="account.group_account_manager")
    key_file = fields.Binary(groups="account.group_account_manager")
    key_password = fields.Char(
        string="Password", groups="account.group_account_manager"
    )
    service_id = fields.Many2one("l10n_mx_cfdi.cfdi_service")
    registered = fields.Boolean(store=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)
    use_origin_document_sequence = fields.Boolean(
        string="Usar Serie de Origen",
        help="Usar serie del documento de origen para los CFDI generados",
    )

    invoice_sequence_id = fields.Many2one(
        "l10n_mx_cfdi.series",
        string="Serie Ingresos",
        default=lambda self: self._create_default_cfdi_sequence("Ingresos"),
    )
    refund_sequence_id = fields.Many2one(
        "l10n_mx_cfdi.series",
        string="Serie Egresos",
        default=lambda self: self._create_default_cfdi_sequence("Egresos"),
    )
    transfer_sequence_id = fields.Many2one(
        "l10n_mx_cfdi.series",
        string="Serie Traslados",
        default=lambda self: self._create_default_cfdi_sequence("Traslados"),
    )
    payment_sequence_id = fields.Many2one(
        "l10n_mx_cfdi.series",
        string="Serie Pagos",
        default=lambda self: self._create_default_cfdi_sequence("Pagos"),
    )

    @api.model
    def default_get(self, fields_list):
        # set country to Mexico
        res = super(CFDIIssuer, self).default_get(fields_list)
        res["country_id"] = self.env.ref("base.mx").id

        return res

    @api.model
    def _slugify(self, string):
        # slugify string
        return string.lower().replace(" ", "_")

    @api.model
    def _create_default_cfdi_sequence(self, name):
        # format a unique sequence code for the company
        sequence_code = "l10n_mx_cfdi.sequence.{}.{}".format(
            self._slugify(self.env.company.name), self._slugify(name)
        )

        existent_sequence = self.env["l10n_mx_cfdi.series"].search(
            [("code", "=", sequence_code)]
        )
        if existent_sequence:
            return existent_sequence
        else:
            return (
                self.env["l10n_mx_cfdi.series"]
                .sudo()
                .create(
                    {
                        "name": "Folios CFDI %s" % name,
                        "implementation": "no_gap",
                        "number_increment": 1,
                        "number_next_actual": 0,
                        "prefix": name[0],
                        "company_id": self.env.user.company_id.id,
                        "code": sequence_code,
                    }
                )
            )

    def register_issuer(self):
        """Registers the certificate in the SAT"""

        self.ensure_one()
        if not self.vat:
            raise UserError(_("Emitter RFC not defined.."))

        if not self.certificate_file or not self.key_file or not self.key_password:
            raise UserError(_("Digital certificate not configured."))

        if not self.service_id:
            raise UserError(_("Invoicing service not defined."))

        try:
            self.service_id.register_csd(
                self.vat, self.certificate_file, self.key_file, self.key_password
            )
            self.registered = True
        except Exception as e:
            self.registered = False
            _logger.warning(e)
            raise UserError(_("Cannot register the certificate.")) from e

    def unregister_issuer(self):
        """Unregisters the certificate in the SAT"""
        self.ensure_one()
        if not self.certificate_file or not self.key_file or not self.key_password:
            self.registered = False
            return
        if not self.service_id:
            raise UserError(_("Invoicing service not defined."))
        try:
            self.service_id.unregister_csd(self.vat)
            self.registered = False
        except Exception as e:
            _logger.warning(e)
            raise UserError(_("Cannot unregister the certificate.")) from e

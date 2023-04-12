import base64

from odoo import fields, models, api, _
from simple_cfdi import utils as cfdi_utils

from odoo.exceptions import UserError


class CFDI_4_0(models.Model):
    """
    This model represents a CFDI 4.0 document following the specifications of the SAT.
    It stores the document state, information and attachments.
    """

    _name = "l10n_mx_cfdi.document_4_0"
    _description = "CFDI Document 4.0"
    _inherit = ["mail.thread"]

    name = fields.Char(
        string="Name",
        readonly=True,
        compute="_compute_name",
    )

    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("to_post", "To Post"),
            ("posted", "Posted"),
            ("to_cancel", "To Cancel"),
            ("cancelled", "Cancelled"),
        ],
        string="State",
        readonly=True,
        copy=False,
        default="draft",
        tracking=True,
    )

    cfdi_type = fields.Many2one(
        comodel_name="l10n_mx_cfdi.cfdi_type",
        string="CFDI Type",
        readonly=True,
    )

    series = fields.Char(string="Series", readonly=True)
    folio = fields.Char(string="Folio", readonly=True)
    date = fields.Datetime(string="Date", readonly=True)
    expedition_zip_code = fields.Many2one(
        "l10n_mx_cfdi.cfdi_zip_codes",
        string="Expedition Place",
        readonly=True,
    )

    issuer_id = fields.Many2one(
        comodel_name="res.partner",
        string="Issuer",
        readonly=True,
    )

    receiver_id = fields.Many2one(
        comodel_name="res.partner",
        string="Receiver",
        readonly=True,
    )

    uuid = fields.Char(string="UUID", readonly=True, copy=False)

    @api.depends("series", "folio")
    def _compute_name(self):
        for rec in self:
            if rec.state == "draft":
                rec.name = _("Draft")
                continue

            rec.name = rec._format_name()

    def _format_name(self):
        self.ensure_one()

        if self.series:
            return f"{self.series}-{self.folio}"
        else:
            return f"{self.folio}"

    def action_post(self):
        pass

    def action_cancel(self):
        pass

    def action_draft(self):
        pass

    def action_check_status(self):
        pass

    def _check_signature(self):
        """
        Scan the XML file for the complement 'TimbreFiscalDigital' and
        extracts the UUID.
        """
        self.ensure_one()

        # get xml data from attachment
        attachment = self.env["ir.attachment"].search(
            [
                ("res_model", "=", self._name),
                ("res_id", "=", self.id),
                ("mimetype", "=", "application/xml"),
            ],
            limit=1,
        )

        if not attachment:
            raise UserError(_("CFDI document has no XML attachment"))

        xml_data = base64.b64decode(attachment.datas)

        # check signature
        document = cfdi_utils.import_xml(xml_data)
        for complemento in document.complemento.any_element:
            if (
                complemento.qname
                == "{http://www.sat.gob.mx/TimbreFiscalDigital}TimbreFiscalDigital"
            ):
                self.uuid = complemento.attributes["UUID"]

                # TODO: validate signature

                self.state = "posted"
                return True

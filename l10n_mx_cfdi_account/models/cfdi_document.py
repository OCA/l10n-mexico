import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class Document(models.Model):
    _inherit = "l10n_mx_cfdi.document"
    _description = "CFDI document"

    ###
    # Certificate fields
    ###

    related_invoice_id = fields.Many2one(
        "account.move", string="Factura relacionada", readonly=True
    )
    related_payment_id = fields.Many2one(
        "account.payment", string="Pago relacionado", readonly=True
    )

    ###
    # Computed fields generation functions
    ###

    @api.depends("tracking_id")
    def _compute_download_files_if_needed(self):
        for entry in self:
            if entry.tracking_id:
                entry._download_pdf_file_if_needed()
                entry._download_xml_file_if_needed()
                entry.files_in_cache = True
            else:
                entry.files_in_cache = False

    def _resolve_report(self):
        """Returns the report and resource IDs for generating the PDF file."""
        self.ensure_one()
        report = None
        resource_ids = []

        if self.type in ("I", "E") and self.related_invoice_id:
            report = self.env.ref("account.account_invoices")
            resource_ids = [self.related_invoice_id.id]
        elif self.type == "P" and self.related_payment_id:
            report = self.env.ref("account.action_report_payment_receipt")
            resource_ids = [self.related_payment_id.id]

        return report, resource_ids

    ###
    # Model methods
    ###

    def create(self, vals_list):
        # Set values to serie and folio from sequence if not provided

        # check if vals_list is a list of dictionaries
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        for vals in vals_list:
            if "serie" not in vals or "folio" not in vals:
                issuer = self._resolve_issuer_on_create(vals)
                if (
                    issuer.use_origin_document_sequence
                    and vals.get("type", False) != "T"
                    and vals.get("is_global_note", False) is False
                ):
                    self._set_serie_and_folio_from_document_sequence(vals)
                else:
                    self._set_serie_and_folio_from_cfdi_sequence(vals)

        # Create certificate
        return super().create(vals_list)

    def _set_serie_and_folio_from_document_sequence(self, vals):
        serie = ""
        folio = ""
        document_name = ""

        if "related_invoice_id" in vals:
            invoice = self.env["account.move"].browse(vals["related_invoice_id"])
            document_name = invoice.name

        if "related_payment_id" in vals:
            payment = self.env["account.payment"].browse(vals["related_payment_id"])
            document_name = payment.name

        if not document_name:
            raise UserError(_("Unable to determine the origin document name."))

        # extract numeric postfix from invoice name using regex
        match = re.search(r"\d+$", document_name)
        if match:
            folio = match.group()
            serie = document_name[: -len(match.group())]
        else:
            raise UserError(_("Invoice name does not contain a numeric postfix."))

        # remove non-alphanumeric characters from serie
        serie = re.sub(r"\W+", "", serie)

        vals["serie"] = serie
        vals["folio"] = folio

    def action_check_status(self):
        self.ensure_one()

        service = self.issuer_id.service_id.sudo()
        amount_total = 0
        if self.related_invoice_id:
            amount_total = self.related_invoice_id.amount_total

        if self.related_payment_id:
            amount_total = self.related_payment_id.amount

        status = service.check_cfdi_status(
            self.uuid, self.issuer_id.vat, self.receiver_id.vat, amount_total
        )

        if self.state != status:
            self.state = status

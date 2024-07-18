import base64
import io
import zipfile

from odoo import api, fields, models


class DownloadCFDIFilesWizard(models.TransientModel):
    _name = "l10n_mx_cfdi.download_cfdi_files_wizard"
    _description = "Create ZIP file containing selected invoices CFDI"

    invoice_ids = fields.Many2many("account.move", string="Facturas", required=True)
    cfdi_document_ids = fields.Many2many(
        "l10n_mx_cfdi.document",
        string="CFDI Documents",
        required=True,
        relation="l10n_mx_cfdi_download_cfdi_files_wizard_rel",
    )

    zip_file = fields.Many2one("ir.attachment", readonly=True, ondelete="cascade")

    @api.model
    def default_get(self, field_names):
        defaults_dict = super().default_get(field_names)
        context = self.env.context

        if context["active_model"] == "account.move":
            related_invoice_objs = self.env["account.move"].browse(
                context["active_ids"]
            )
            defaults_dict.update(
                {
                    "invoice_ids": related_invoice_objs,
                    "cfdi_document_ids": related_invoice_objs.mapped(
                        "cfdi_document_id"
                    ),
                }
            )

        return defaults_dict

    def _create_zip_file(self):
        # prepare zip file
        stream = io.BytesIO()
        zip_archive = zipfile.ZipFile(stream, "w")

        # add docs to zip file
        for cfdi_doc in self.cfdi_document_ids:
            if cfdi_doc:
                cfdi_doc.download_files_if_needed()

                zip_archive.writestr(
                    cfdi_doc.pdf_filename, base64.b64decode(cfdi_doc.pdf_file)
                )
                zip_archive.writestr(
                    cfdi_doc.xml_filename, base64.b64decode(cfdi_doc.xml_file)
                )

        zip_archive.close()

        bytes_of_zipfile = stream.getvalue()

        # create attachment
        self.zip_file = self.env["ir.attachment"].create(
            {
                "name": "cfdis.zip",
                "datas": base64.b64encode(bytes_of_zipfile),
                "type": "binary",
            }
        )

    def action_download_zip(self):
        self._create_zip_file()

        return {
            "type": "ir.actions.act_url",
            "url": "/web/content/%s?download=true" % self.zip_file.id,
            "target": "self",
        }

# -*- coding: utf-8 -*-

from odoo import models


class MailTemplate(models.Model):
    _inherit = "mail.template"

    def generate_email(self, res_ids, fields):
        """ Override to add the CFDI attachment to the email. """

        res = super().generate_email(res_ids, fields)

        multi_mode = True
        if isinstance(res_ids, int):
            res_ids = [res_ids]
            multi_mode = False

        if self.model not in ["account.move", "account.payment"]:
            return res

        records = self.env[self.model].browse(res_ids)
        for record in records:
            record_data = res[record.id] if multi_mode else res
            related_cfdi_documents = record.related_cert_ids

            # existent documents will be replaced by their cfdi counterpart
            if related_cfdi_documents:
                record_data["attachments"] = []

            for doc in related_cfdi_documents:
                if doc.state == "published":
                    doc.download_files_if_needed()

                    record_data["attachments"].append(
                        (
                            doc.pdf_filename,
                            doc.pdf_file,
                        )
                    )

                    record_data["attachments"].append(
                        (
                            doc.xml_filename,
                            doc.xml_file,
                        )
                    )

        return res

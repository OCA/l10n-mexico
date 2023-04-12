import base64
from base64 import b64decode
from datetime import datetime

import pytz
from simple_cfdi import utils as cfdi_utils

from odoo import models, fields


class CFDIDocumentImportWizard(models.TransientModel):
    _name = "l10n_mx_cfdi.cfdi_document_import_wizard"
    _description = "CFDI Document Import Wizard"

    xml_file = fields.Binary(
        string="XML File",
        required=True,
    )

    def action_import_cfdi(self):
        # decode xml_file from base64
        xml_data = b64decode(self.xml_file)

        # import Comprobante class into l10n_mx_cfdi.document_4_0 model

        rec = self._import_xml(xml_data)
        return {
            "type": "ir.actions.act_window",
            "name": "CFDI Documents",
            "res_model": "l10n_mx_cfdi.document_4_0",
            "view_mode": "tree,form",
            "domain": [("id", "in", rec.ids)],
        }

    def _import_xml(self, xml_data):
        """
        Import CFDI document from XML data

        :param xml_data: CFDI document in XML format
        :type xml_data: bytes
        :return: CFDI document record
        :rtype: l10n_mx_cfdi.document_4_0
        """

        document = cfdi_utils.import_xml(xml_data)

        cfdi_type = self.env["l10n_mx_cfdi.cfdi_type"].resolve_from_code(
            document.tipo_de_comprobante
        )

        issuer = self._get_or_create_partner(
            name=document.emisor.nombre,
            rfc=document.emisor.rfc,
        )

        receiver = self._get_or_create_partner(
            name=document.receptor.nombre,
            rfc=document.receptor.rfc,
        )

        expedition_zip_code = self.env["l10n_mx_cfdi.cfdi_zip_codes"].resolve_from_code(
            document.lugar_expedicion
        )

        document_date = datetime.strptime(document.fecha, "%Y-%m-%dT%H:%M:%S")
        # set timezone to document date
        if expedition_zip_code:
            zip_code_tz = expedition_zip_code.timezone()
        else:
            # fallback to Mexico City timezone if expedition zip code
            # is not set or not found
            zip_code_tz = pytz.timezone("America/Mexico_City")
        document_date = document_date.replace(tzinfo=zip_code_tz)

        # convert document date to UTC
        document_date_utc = document_date.astimezone(pytz.UTC)

        document_model = self.env["l10n_mx_cfdi.document_4_0"]
        cfdi = document_model.create(
            {
                "cfdi_type": cfdi_type.id,
                "series": document.serie,
                "folio": document.folio,
                "date": document_date_utc.strftime("%Y-%m-%d %H:%M:%S"),
                "issuer_id": issuer.id,
                "receiver_id": receiver.id,
                "expedition_zip_code": expedition_zip_code.id,
            }
        )

        # attach xml to the CFDI
        attachment_data = base64.b64encode(xml_data)
        self.env["ir.attachment"].create(
            {
                "name": f"{cfdi._format_name()}.xml",
                "type": "binary",
                "datas": attachment_data,
                "res_model": "l10n_mx_cfdi.document_4_0",
                "res_id": cfdi.id,
                "mimetype": "application/xml",
            }
        )

        cfdi._check_signature()

        return cfdi

    def _get_or_create_partner(self, name, rfc):
        partner = self.env["res.partner"].search(
            [
                ("vat", "=", rfc),
            ]
        )

        if not partner:
            partner = self.env["res.partner"].create(
                {
                    "name": name,
                    "vat": rfc,
                }
            )

        return partner

# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import VendorBillTestCommon


@tagged("post_install", "-at_install")
class TestSatDocumentVendorBillHook(VendorBillTestCommon):
    """Cover l10n_mx_sat.document._upsert_from_xml vendor bill linking."""

    def test_upsert_links_vendor_bill_for_received_cfdi_xml(self):
        uuid = "HOOK-LINK-1111-2222-3333-444455556666"
        xml_bytes = self._cfdi_xml(uuid=uuid, folio="H1")
        tree = self._parse(xml_bytes)
        document = self.env["l10n_mx_sat.document"]._upsert_from_xml(
            tree, xml_bytes, self.company, self.request
        )
        self.assertTrue(document)
        self.assertTrue(document.vendor_bill_id)
        self.assertEqual(document.vendor_bill_id.l10n_mx_cfdi_uuid, uuid)
        self.assertEqual(
            document.vendor_bill_id.l10n_mx_sat_download_request_id,
            self.request,
        )

    def test_upsert_skips_bill_for_issued_direction(self):
        request = self.env["l10n_mx_sat.download.request"].create(
            {
                "company_id": self.company.id,
                "document_kind": "cfdi",
                "direction": "issued",
                "request_type": "xml",
                "date_from": "2026-02-01 00:00:00",
                "date_to": "2026-02-28 23:59:59",
                "state": "downloading",
            }
        )
        # Issued validation requires Emisor RFC == company VAT
        xml_bytes = self._cfdi_xml(
            uuid="HOOK-ISSUED-1111-2222-3333-444455556666",
            folio="H2",
            emisor_rfc=self.company.vat,
            emisor_nombre="EMPRESA LOCAL",
        )
        document = self.env["l10n_mx_sat.document"]._upsert_from_xml(
            self._parse(xml_bytes), xml_bytes, self.company, request
        )
        self.assertTrue(document)
        self.assertFalse(document.vendor_bill_id)

    def test_upsert_skips_bill_for_metadata_request(self):
        request = self.env["l10n_mx_sat.download.request"].create(
            {
                "company_id": self.company.id,
                "document_kind": "cfdi",
                "direction": "received",
                "request_type": "metadata",
                "date_from": "2026-02-01 00:00:00",
                "date_to": "2026-02-28 23:59:59",
                "state": "downloading",
            }
        )
        xml_bytes = self._cfdi_xml(
            uuid="HOOK-META-1111-2222-3333-444455556666", folio="H3"
        )
        document = self.env["l10n_mx_sat.document"]._upsert_from_xml(
            self._parse(xml_bytes), xml_bytes, self.company, request
        )
        self.assertTrue(document)
        self.assertFalse(document.vendor_bill_id)

    def test_upsert_skips_bill_for_retention(self):
        request = self.env["l10n_mx_sat.download.request"].create(
            {
                "company_id": self.company.id,
                "document_kind": "retention",
                "direction": "received",
                "request_type": "xml",
                "date_from": "2026-02-01 00:00:00",
                "date_to": "2026-02-28 23:59:59",
                "state": "downloading",
            }
        )
        uuid = "HOOK-RET-1111-2222-3333-444455556666"
        xml_bytes = (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b"<retenciones:Retenciones xmlns:retenciones="
            b'"http://www.sat.gob.mx/esquemas/retencionpago/2" '
            b'xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital" '
            b'Version="2.0" FechaExp="2026-02-26T16:57:09">'
            b'<retenciones:Emisor RfcE="AAA010101AAA" '
            b'NomDenRazSocE="Emisor Retencion"/>'
            b'<retenciones:Receptor NacionalidadR="Nacional">'
            b'<retenciones:Nacional RfcR="EKU9003173C9"/>'
            b"</retenciones:Receptor>"
            b'<retenciones:Totales MontoTotOperacion="100.00"/>'
            b"<retenciones:Complemento>"
            b'<tfd:TimbreFiscalDigital UUID="' + uuid.encode() + b'"/>'
            b"</retenciones:Complemento></retenciones:Retenciones>"
        )
        document = self.env["l10n_mx_sat.document"]._upsert_from_xml(
            self._parse(xml_bytes), xml_bytes, self.company, request
        )
        self.assertTrue(document)
        self.assertFalse(document.vendor_bill_id)

    @mute_logger("odoo.addons.l10n_mx_sat_vendor_bill.models.account_move")
    def test_upsert_no_bill_link_when_payment_cfdi(self):
        xml_bytes = self._cfdi_xml(
            uuid="HOOK-PAY-1111-2222-3333-444455556666",
            tipo="P",
            folio="H4",
            moneda="XXX",
        )
        document = self.env["l10n_mx_sat.document"]._upsert_from_xml(
            self._parse(xml_bytes), xml_bytes, self.company, self.request
        )
        self.assertTrue(document)
        self.assertFalse(document.vendor_bill_id)

    @mute_logger("odoo.addons.l10n_mx_sat.models.l10n_mx_sat_document")
    def test_upsert_returns_empty_when_super_skips(self):
        xml_bytes = self._cfdi_xml(
            uuid="HOOK-SKIP-1111-2222-3333-444455556666",
            folio="H5",
        )
        # Break company match by changing receptor through a rebuilt XML
        bad_xml = xml_bytes.replace(b"EKU9003173C9", b"AAA010101AAA")
        document = self.env["l10n_mx_sat.document"]._upsert_from_xml(
            self._parse(bad_xml), bad_xml, self.company, self.request
        )
        self.assertFalse(document)

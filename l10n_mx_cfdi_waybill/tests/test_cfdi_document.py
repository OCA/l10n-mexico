from .common import WaybillTestCommon


class TestCFDIDocumentWaybill(WaybillTestCommon):
    def test_resolve_report_for_transfer(self):
        waybill = self._create_waybill()
        report_type, report, resource_ids = waybill.cfdi_id._resolve_report()
        self.assertEqual(report_type, "l10n_mx_cfdi_waybill.action_waybill_report")
        self.assertEqual(resource_ids, waybill.ids)

    def test_set_serie_and_folio_for_transfer(self):
        vals = {"type": "T"}
        waybill = self._create_waybill()
        waybill.cfdi_id._set_serie_and_folio_from_document_sequence(vals)
        self.assertEqual(vals["serie"], "CP")
        self.assertEqual(vals["folio"], "(Borrador)")

    def test_resolve_report_non_transfer(self):
        document = self._create_document(type="I")
        report_type, _report, _resource_ids = document._resolve_report()
        self.assertNotEqual(report_type, "l10n_mx_cfdi_waybill.action_waybill_report")

    def test_set_serie_and_folio_non_transfer(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        vals = {"type": "I", "related_invoice_id": invoice.id}
        self.env["l10n_mx_cfdi.document"]._set_serie_and_folio_from_document_sequence(
            vals
        )
        self.assertNotEqual(vals.get("serie"), "CP")

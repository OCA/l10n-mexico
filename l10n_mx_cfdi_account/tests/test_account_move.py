import base64
from datetime import timedelta
from unittest.mock import PropertyMock, patch

from lxml import etree

from odoo import fields
from odoo.exceptions import UserError, ValidationError

from .common import ACTIVE_CFDI_RESPONSE, SAMPLE_CFDI_XML, CFDIAccountTestCommon


class TestAccountMove(CFDIAccountTestCommon):
    def test_onchange_partner_updates_receiver_and_cfdi_fields(self):
        invoice = self.env["account.move"].new(
            {
                "move_type": "out_invoice",
                "partner_id": self.customer.id,
            }
        )
        invoice._update_receiver()
        self.assertEqual(invoice.receiver_id, self.customer)
        self.assertEqual(invoice.cfdi_use_id, self.customer.cfdi_use_id)
        self.assertEqual(invoice.payment_method_id, self.customer.payment_method_id)
        self.assertEqual(invoice.payment_form_id, self.customer.payment_form_id)

    def test_onchange_receiver_updates_cfdi_data(self):
        invoice = self.env["account.move"].new(
            {
                "move_type": "out_invoice",
                "receiver_id": self.customer.id,
            }
        )
        invoice._update_cfdi_data()
        self.assertEqual(invoice.cfdi_use_id, self.customer.cfdi_use_id)

    def test_cfdi_posted_when_document_is_published(self):
        invoice = self._create_cfdi_invoice()
        self.assertFalse(invoice.cfdi_posted)
        self._create_published_invoice_cfdi(invoice)
        self.assertTrue(invoice.cfdi_posted)
        self.assertEqual(invoice.cfdi_document_id.type, "I")

    def test_compute_cfdi_document_out_refund(self):
        invoice = self._create_cfdi_invoice(move_type="out_refund")
        document = self._create_document(
            type="E",
            state="published",
            related_invoice_id=invoice.id,
            receiver_id=self.customer.id,
        )
        invoice.related_cert_ids = [(4, document.id)]
        self.assertEqual(invoice.cfdi_document_id, document)

    def test_cfdi_data_in_attachments(self):
        invoice = self._create_cfdi_invoice()
        self.env["ir.attachment"].create(
            {
                "name": "invoice.xml",
                "res_model": "account.move",
                "res_id": invoice.id,
                "mimetype": "application/xml",
                "datas": base64.b64encode(b"<cfdi:Comprobante></cfdi:Comprobante>"),
            }
        )
        invoice._compute_cfdi_data_in_attachments()
        self.assertTrue(invoice.cfdi_data_in_attachments)

    def test_validate_invoice_cfdi_required_fields(self):
        invoice = self._create_cfdi_invoice(issuer_id=False, receiver_id=False)
        with self.assertRaises(ValidationError):
            invoice._validate_invoice_cfdi_required_fields()

    def test_validate_invoice_cfdi_required_field_messages(self):
        invoice = self._create_cfdi_invoice()
        incomplete = self.env["res.partner"].create(
            {
                "name": "Incomplete Receiver",
                "country_id": self.env.ref("base.mx").id,
            }
        )
        invoice.write(
            {
                "issuer_id": False,
                "receiver_id": incomplete.id,
                "cfdi_use_id": False,
                "payment_method_id": False,
                "payment_form_id": False,
            }
        )
        with self.assertRaises(ValidationError) as err:
            invoice._validate_invoice_cfdi_required_fields()
        message = str(err.exception)
        self.assertIn("emisor", message)
        self.assertIn("RFC del receptor", message)
        self.assertIn("régimen fiscal", message)
        self.assertIn("código postal", message)
        self.assertIn("uso del CFDI", message)
        self.assertIn("método de pago", message)
        self.assertIn("forma de pago", message)

    def test_exportacion_complemento_hook_default(self):
        invoice = self._create_cfdi_invoice()
        exportacion, complemento = (
            invoice._l10n_mx_cfdi_invoice_exportacion_complemento()
        )
        self.assertEqual(exportacion, "01")
        self.assertIsNone(complemento)
        cfdi = invoice._gather_invoice_cfdi_data()
        self.assertEqual(cfdi.get("Exportacion"), "01")

    def test_prepare_invoice_cfdi_total_taxes_aggregates_same_code(self):
        self.cfdi_product.taxes_id = [(6, 0, [self._iva_tax().id])]
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        tax_lines = invoice.line_ids.filtered("tax_line_id")
        self.assertTrue(tax_lines)
        first = tax_lines[0]
        base_before = invoice.prepare_invoice_cfdi_total_taxes()[0]["Base"]
        # Second tax line with same SAT code triggers the aggregation branch
        clone = first.copy(
            {
                "name": "Clone tax line",
                "tax_base_amount": 25.0,
            }
        )
        clone.tax_base_amount = 25.0
        totals = invoice.prepare_invoice_cfdi_total_taxes()
        self.assertAlmostEqual(totals[0]["Base"], base_before + 25.0, places=2)

    def test_validate_invoice_items_for_cfdi_generation(self):
        product = self.env["product.product"].create(
            {
                "name": "Incomplete Product",
                "list_price": 50.0,
            }
        )
        invoice = self._create_cfdi_invoice(
            invoice_line_ids=[
                (0, 0, {"product_id": product.id, "quantity": 1, "price_unit": 50.0})
            ]
        )
        err_msg = invoice.validate_invoice_items_for_cfdi_generation()
        self.assertIn("Incomplete Product", err_msg)

    def test_default_get_sets_single_issuer(self):
        defaults = (
            self.env["account.move"]
            .with_company(self.company)
            .default_get(["issuer_id", "receiver_id"])
        )
        self.assertEqual(defaults["issuer_id"], self.issuer.id)

    def test_default_get_skips_issuer_when_multiple_registered(self):
        other = self._create_cfdi_issuer(self.service)
        other.write({"registered": True, "zip": "06000"})
        defaults = (
            self.env["account.move"]
            .with_company(self.company)
            .default_get(["issuer_id"])
        )
        self.assertNotIn("issuer_id", defaults)

    def test_gather_invoice_cfdi_items_data(self):
        invoice = self._create_cfdi_invoice()
        items = invoice.gather_invoice_cfdi_items_data()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["ProductCode"], "01010101")

    def test_gater_invoice_cfdi_item_data(self):
        invoice = self._create_cfdi_invoice()
        line = invoice.invoice_line_ids[0]
        item = invoice.gater_invoice_cfdi_item_data(line)
        self.assertEqual(item["Quantity"], 1)

    def test_gather_invoice_cfdi_item_taxes_data(self):
        invoice = self._create_cfdi_invoice()
        line = invoice.invoice_line_ids[0]
        taxes = self.env["account.move"]._gather_invoice_cfdi_item_taxes_data(line, 0)
        self.assertTrue(taxes)

    def test_prepare_invoice_cfdi_total_taxes(self):
        self.cfdi_product.taxes_id = [(6, 0, [self._iva_tax().id])]
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        taxes = invoice.prepare_invoice_cfdi_total_taxes()
        self.assertTrue(taxes)

    def test_create_refund_cfdi(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        self._create_published_invoice_cfdi(invoice)
        refund = self._create_cfdi_invoice(move_type="out_refund")
        refund.reversed_entry_id = invoice
        refund.action_post()
        with self._mock_cfdi_publish():
            refund.create_refund_cfdi()
        self.assertTrue(
            refund.related_cert_ids.filtered_domain(
                [("type", "=", "E"), ("state", "=", "published")]
            )
        )

    def test_format_cfdi_date_str_old_invoice(self):
        invoice = self._create_cfdi_invoice(
            invoice_date=fields.Date.today() - timedelta(days=5)
        )
        date_str = invoice._format_cfdi_date_str(invoice.invoice_date)
        self.assertIn("T", date_str)
        # Stale invoice dates must not keep a Fecha outside the 72h stamp window.
        self.assertTrue(date_str.startswith(fields.Date.today().isoformat()))

    def test_gather_invoice_cfdi_data_global_information(self):
        public_partner = self.env.ref(
            "l10n_mx_cfdi.l10n_mx_cfdi_res_partner_publico_en_general"
        )
        # Público en general invoices must use UsoCFDI S01 (SAT rule).
        public_partner.cfdi_use_id = self.env.ref("l10n_mx_catalogs.c_uso_cfdi_S01")
        self.issuer.fiscal_name = "ESCUELA KEMPER URGATE"
        self.cfdi_product.taxes_id = [(6, 0, [self._iva_tax().id])]
        invoice = self._create_cfdi_invoice(
            partner_id=public_partner.id,
            receiver_id=public_partner.id,
            cfdi_use_id=public_partner.cfdi_use_id.id,
        )
        cfdi = invoice._gather_invoice_cfdi_data()
        self.assertTrue(cfdi.get("InformacionGlobal"))
        self.assertEqual(cfdi["Receptor"]["RegimenFiscalReceptor"], "616")
        self.assertEqual(cfdi["Receptor"]["UsoCFDI"], "S01")
        self.assertEqual(cfdi["Receptor"]["DomicilioFiscalReceptor"], self.issuer.zip)
        self.assertEqual(cfdi["Receptor"]["Nombre"], "PUBLICO EN GENERAL")
        self.assertEqual(cfdi["Emisor"]["Nombre"], "ESCUELA KEMPER URGATE")
        xml = cfdi.xml_bytes().decode()
        self.assertIn('TasaOCuota="0.160000"', xml)
        # Reject short rates that SW/SAT treat as invalid catalog values.
        self.assertNotRegex(xml, r'TasaOCuota="0\.16"')

    def test_create_invoice_cfdi_success(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        with self._mock_cfdi_publish():
            invoice.create_invoice_cfdi()
        self.assertTrue(invoice.related_cert_ids)
        self.assertEqual(invoice.cfdi_document_id.state, "published")

    def test_create_invoice_cfdi_posts_chatter_attachments(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        response = dict(ACTIVE_CFDI_RESPONSE)
        response["pdf"] = b"%PDF-1.4"
        with patch.object(type(self.service), "create_cfdi", return_value=response):
            invoice.create_invoice_cfdi()
        attachments = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", invoice.id),
            ]
        )
        names = attachments.mapped("name")
        self.assertTrue(any(name.endswith(".xml") for name in names))
        self.assertTrue(any(name.endswith(".pdf") for name in names))

    def test_post_document_attachments_recovers_pdf_and_xml(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        document = self._create_published_invoice_cfdi(invoice)
        document.write(
            {
                "pdf_file": False,
                "xml_file": False,
                "pdf_filename": False,
                "xml_filename": False,
                "tracking_id": "track-recover",
            }
        )
        with (
            patch.object(
                type(self.service),
                "get_cfdi_pdf",
                return_value={"Content": base64.b64encode(b"%PDF-1.4")},
            ),
            patch.object(
                type(self.service),
                "get_cfdi_xml",
                return_value={"Content": "<cfdi/>"},
            ),
        ):
            invoice._l10n_mx_cfdi_post_document_attachments(document)
        self.assertTrue(document.pdf_file)
        self.assertTrue(document.xml_file)
        attachments = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", invoice.id),
            ]
        )
        names = attachments.mapped("name")
        self.assertTrue(any(name.endswith(".xml") for name in names))
        self.assertTrue(any(name.endswith(".pdf") for name in names))

    def test_post_document_attachments_soft_fails_and_empty_return(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        document = self._create_published_invoice_cfdi(invoice)
        document.write(
            {
                "pdf_file": False,
                "xml_file": False,
                "tracking_id": "track-empty",
            }
        )
        before = self.env["ir.attachment"].search_count(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", invoice.id),
            ]
        )
        with (
            patch.object(
                type(self.service),
                "get_cfdi_pdf",
                side_effect=AttributeError("'dict' object has no attribute 'pdf'"),
            ),
            patch.object(
                type(self.service),
                "get_cfdi_xml",
                side_effect=AttributeError("'dict' object has no attribute 'xml'"),
            ),
        ):
            invoice._l10n_mx_cfdi_post_document_attachments(document)
        after = self.env["ir.attachment"].search_count(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", invoice.id),
            ]
        )
        self.assertEqual(before, after)

    def test_create_invoice_cfdi_failure_unlinks_document(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        with (
            patch.object(
                type(self.service),
                "create_cfdi",
                side_effect=UserError("publish failed"),
            ),
            self.assertRaises(UserError),
        ):
            invoice.create_invoice_cfdi()
        self.assertFalse(invoice.related_cert_ids)

    def test_action_post_auto_cfdi(self):
        self.company.l10n_mx_cfdi_auto = True
        invoice = self._create_cfdi_invoice()
        with self._mock_cfdi_publish():
            invoice.action_post()
        self.assertTrue(invoice.cfdi_posted)

    def test_button_draft_with_published_cfdi(self):
        self.company.l10n_mx_cfdi_auto = True
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        self._create_published_invoice_cfdi(invoice)
        action = invoice.button_draft()
        self.assertEqual(
            action.get("res_model"),
            "l10n_mx_cfdi_account.document_cancel",
        )

    def test_get_name_invoice_report_mx(self):
        invoice = self._create_cfdi_invoice()
        invoice.company_id.account_fiscal_country_id = self.env.ref("base.mx")
        self.assertEqual(
            invoice._get_name_invoice_report(),
            "l10n_mx_cfdi_account.report_invoice_document",
        )

    def test_get_name_invoice_report_non_mx(self):
        invoice = self._create_cfdi_invoice()
        invoice.company_id.country_id = self.env.ref("base.us")
        self.assertNotEqual(
            invoice._get_name_invoice_report(),
            "l10n_mx_cfdi_account.report_invoice_document",
        )

    def test_action_load_from_attachment(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        self.env["ir.attachment"].create(
            {
                "name": "invoice.xml",
                "res_model": "account.move",
                "res_id": invoice.id,
                "mimetype": "application/xml",
                "datas": base64.b64encode(SAMPLE_CFDI_XML),
            }
        )
        invoice.action_load_from_attachment()
        self.assertTrue(invoice.related_cert_ids)
        self.assertTrue(invoice.cfdi_required)

    def test_parse_cfdi_xml_creates_issuer_from_partner(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        partner = self.env["res.partner"].create(
            {
                "name": "New Issuer Partner",
                "vat": "NEWISSUER1",
            }
        )
        xml = SAMPLE_CFDI_XML.replace(b"RFC123456", partner.vat.encode())
        document = invoice._parse_cfdi_xml(xml)
        self.assertTrue(document.issuer_id)
        self.assertEqual(document.issuer_id.partner_id, partner)

    def test_resolve_receiver_data_from_xml_missing_partner(self):
        invoice = self._create_cfdi_invoice()
        xml = SAMPLE_CFDI_XML.replace(b"XAXX010101010", b"MISSINGRFC1")
        root = etree.fromstring(xml)
        with self.assertRaises(UserError):
            invoice._resolve_receiver_data_from_xml(root.nsmap, root)

    def test_resolve_issuer_from_xml_missing_partner(self):
        invoice = self._create_cfdi_invoice()
        xml = SAMPLE_CFDI_XML.replace(b"RFC123456", b"MISSINGRFC2")
        root = etree.fromstring(xml)
        with self.assertRaises(UserError):
            invoice._resolve_issuer_from_xml(root.nsmap, root)

    def test_action_load_from_attachment_missing_xml(self):
        invoice = self._create_cfdi_invoice()
        with self.assertRaises(UserError):
            invoice.action_load_from_attachment()

    def test_action_generate_cfdi_already_published(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        self._create_published_invoice_cfdi(invoice)
        with self.assertRaises(UserError):
            invoice.action_generate_cfdi()

    def test_action_generate_cfdi_out_invoice(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        with self._mock_cfdi_publish():
            invoice.action_generate_cfdi()
        self.assertTrue(invoice.cfdi_document_id)

    def test_action_generate_cfdi_refund_with_residual(self):
        invoice = self._create_cfdi_invoice(move_type="out_refund")
        invoice.action_post()
        with self.assertRaises(UserError):
            invoice.action_generate_cfdi()

    def test_action_generate_cfdi_refund_success(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        self._create_published_invoice_cfdi(invoice)
        refund = self._create_cfdi_invoice(move_type="out_refund")
        # Odoo 19 auto-reconciles when reversed_entry_id is set on post.
        refund.reversed_entry_id = invoice
        refund.action_post()
        self.assertEqual(refund.amount_residual, 0)
        with self._mock_cfdi_publish():
            refund.action_generate_cfdi()
        self.assertTrue(refund.related_cert_ids)

    def test_action_generate_cfdi_refund_requires_posted(self):
        refund = self._create_cfdi_invoice(move_type="out_refund")
        with self.assertRaises(UserError) as err:
            refund.action_generate_cfdi()
        self.assertIn("Confirm the credit note", str(err.exception))

    def test_create_refund_cfdi_requires_relations(self):
        refund = self._post_cfdi_invoice(
            self._create_cfdi_invoice(move_type="out_refund")
        )
        with self.assertRaises(UserError) as err:
            refund.create_refund_cfdi()
        self.assertIn("related income CFDIs", str(err.exception))

    def test_compute_cfdi_document_in_payment(self):
        move = self.env["account.move"].new({"move_type": "in_payment"})
        document = self._create_document(
            type="P",
            state="published",
            receiver_id=self.customer.id,
        )
        move.related_cert_ids = document
        move._compute_cfdi_document_id()
        self.assertEqual(move.cfdi_document_id.type, "P")
        self.assertEqual(move.cfdi_document_id.state, "published")

    def test_cfdi_data_in_attachments_without_comprobante(self):
        invoice = self._create_cfdi_invoice()
        self.env["ir.attachment"].create(
            {
                "name": "other.xml",
                "res_model": "account.move",
                "res_id": invoice.id,
                "mimetype": "application/xml",
                "datas": base64.b64encode(b"<root></root>"),
            }
        )
        invoice._compute_cfdi_data_in_attachments()
        self.assertFalse(invoice.cfdi_data_in_attachments)

    def test_parse_cfdi_xml_updates_existing_document(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        existing = self.env["l10n_mx_cfdi.document"].create(
            {
                "type": "I",
                "uuid": "11111111-1111-1111-1111-111111111111",
                "state": "draft",
                "issuer_id": self.issuer.id,
                "receiver_id": self.customer.id,
                "serie": "INV",
                "folio": "1",
            }
        )
        document = invoice._parse_cfdi_xml(SAMPLE_CFDI_XML)
        self.assertEqual(document.id, existing.id)
        self.assertEqual(document.state, "published")

    def test_button_draft_in_invoice_skips_dialog(self):
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(move_type="in_invoice")
        )
        self._create_published_invoice_cfdi(invoice)
        self.company.l10n_mx_cfdi_auto = True
        result = invoice.button_draft()
        self.assertNotIsInstance(result, dict)

    def test_add_global_information_to_cfdi_if_required(self):
        public_partner = self.env.ref(
            "l10n_mx_cfdi.l10n_mx_cfdi_res_partner_publico_en_general"
        )
        invoice = self._create_cfdi_invoice(
            partner_id=public_partner.id, receiver_id=public_partner.id
        )
        cfdi_data = {"Receiver": {"TaxZipCode": "99999", "FiscalRegime": "601"}}
        invoice._add_global_information_to_cfdi_if_required(cfdi_data)
        self.assertIn("GlobalInformation", cfdi_data)
        self.assertEqual(cfdi_data["Receiver"]["FiscalRegime"], "616")
        self.assertEqual(cfdi_data["Receiver"]["TaxZipCode"], self.issuer.zip)

        normal = self._create_cfdi_invoice()
        plain = {"Receiver": {"TaxZipCode": "06000", "FiscalRegime": "601"}}
        normal._add_global_information_to_cfdi_if_required(plain)
        self.assertNotIn("GlobalInformation", plain)

    def test_create_refund_cfdi_failure_unlinks_document(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        self._create_published_invoice_cfdi(invoice)
        refund = self._create_cfdi_invoice(move_type="out_refund")
        refund.reversed_entry_id = invoice
        refund = self._post_cfdi_invoice(refund)
        before = self.env["l10n_mx_cfdi.document"].search_count([])
        with (
            patch.object(
                type(self.service),
                "create_cfdi",
                side_effect=ValidationError("stamp failed"),
            ),
            self.assertRaises(ValidationError),
        ):
            refund.create_refund_cfdi()
        after = self.env["l10n_mx_cfdi.document"].search_count([])
        self.assertEqual(before, after)

    def test_create_refund_cfdi_with_manual_relations(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        related = self._create_document(
            type="I",
            state="published",
            uuid="11111111-1111-1111-1111-111111111111",
            related_invoice_id=invoice.id,
            receiver_id=invoice.receiver_id.id,
        )
        invoice.related_cert_ids = [(4, related.id)]
        refund = self._post_cfdi_invoice(
            self._create_cfdi_invoice(move_type="out_refund")
        )
        refund.cfdi_document_relation_type = self.env.ref(
            "l10n_mx_catalogs.c_tipo_relacion_1"
        )
        refund.cfdi_document_relations = related
        with self._mock_cfdi_publish():
            refund.create_refund_cfdi()
        self.assertTrue(refund.related_cert_ids)
        egreso = refund.related_cert_ids.filtered(lambda d: d.type == "E")
        self.assertTrue(egreso)
        self.assertTrue(egreso.related_document_ids)

    def test_create_refund_cfdi_auto_relations_from_reconcile(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        related = self._create_document(
            type="I",
            state="published",
            uuid="11111111-1111-1111-1111-111111111111",
            related_invoice_id=invoice.id,
            receiver_id=invoice.receiver_id.id,
        )
        invoice.related_cert_ids = [(4, related.id)]
        refund = self._post_cfdi_invoice(
            self._create_cfdi_invoice(move_type="out_refund")
        )
        (
            invoice.line_ids.filtered(
                lambda line: line.account_id.account_type == "asset_receivable"
            )
            + refund.line_ids.filtered(
                lambda line: line.account_id.account_type == "asset_receivable"
            )
        ).reconcile()
        with self._mock_cfdi_publish():
            refund.create_refund_cfdi()
        egreso = refund.related_cert_ids.filtered(lambda doc: doc.type == "E")
        self.assertTrue(egreso)
        self.assertTrue(egreso.related_document_ids)
        self.assertEqual(
            egreso.related_document_ids.relation_type_id,
            self.env.ref("l10n_mx_catalogs.c_tipo_relacion_1"),
        )
        self.assertIn(egreso, invoice.related_cert_ids)

    def test_create_refund_cfdi_publico_en_general(self):
        public = self.env.ref(
            "l10n_mx_cfdi.l10n_mx_cfdi_res_partner_publico_en_general"
        )
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(partner_id=public.id, receiver_id=public.id)
        )
        related = self._create_document(
            type="I",
            state="published",
            uuid="11111111-1111-1111-1111-111111111111",
            related_invoice_id=invoice.id,
            receiver_id=public.id,
        )
        invoice.related_cert_ids = [(4, related.id)]
        refund = self._create_cfdi_invoice(
            move_type="out_refund", partner_id=public.id, receiver_id=public.id
        )
        refund.reversed_entry_id = invoice
        refund = self._post_cfdi_invoice(refund)
        captured = {}

        def _capture(cfdi, issuer=None):
            captured["cfdi"] = cfdi
            return ACTIVE_CFDI_RESPONSE

        with patch.object(type(self.service), "create_cfdi", side_effect=_capture):
            refund.create_refund_cfdi()
        self.assertTrue(captured["cfdi"].get("InformacionGlobal"))
        self.assertEqual(captured["cfdi"]["Receptor"]["RegimenFiscalReceptor"], "616")
        self.assertTrue(captured["cfdi"].get("CfdiRelacionados"))

    def test_create_refund_cfdi_relations_from_reversed_entry(self):
        """When not reconciled, use reversed_entry_id related income CFDIs."""
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        related = self._create_document(
            type="I",
            state="published",
            uuid="22222222-2222-2222-2222-222222222222",
            related_invoice_id=invoice.id,
            receiver_id=invoice.receiver_id.id,
        )
        invoice.related_cert_ids = [(4, related.id)]
        refund = self._create_cfdi_invoice(move_type="out_refund")
        refund.reversed_entry_id = invoice
        refund = self._post_cfdi_invoice(refund)
        empty = self.env["account.partial.reconcile"]
        with (
            patch.object(
                type(self.env["account.partial.reconcile"]),
                "search",
                return_value=empty,
            ),
            patch.object(
                type(refund.line_ids),
                "matched_debit_ids",
                new_callable=PropertyMock,
                return_value=empty,
            ),
            patch.object(
                type(refund.line_ids),
                "matched_credit_ids",
                new_callable=PropertyMock,
                return_value=empty,
            ),
            self._mock_cfdi_publish(),
        ):
            refund.create_refund_cfdi()
        egreso = refund.related_cert_ids.filtered(lambda d: d.type == "E")
        self.assertTrue(egreso)
        self.assertIn(
            related.uuid, egreso.related_document_ids.mapped("target_id.uuid")
        )

    def test_prepare_invoice_cfdi_total_taxes_missing_code(self):
        self.cfdi_product.taxes_id = [(6, 0, [self._iva_tax().id])]
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        tax_line = invoice.line_ids.filtered("tax_line_id")[:1]
        self.assertTrue(tax_line, "Expected a tax line after posting with IVA")
        with (
            patch.object(
                type(tax_line.tax_line_id),
                "extract_l10n_mx_tax_code",
                return_value=False,
            ),
            self.assertRaises(UserError),
        ):
            invoice.prepare_invoice_cfdi_total_taxes()


class TestAccountMoveCFDIRelations(CFDIAccountTestCommon):
    """CFDI relationship fields (ported from OCA PR #77 / issue #76)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.relation_type = cls.env.ref("l10n_mx_catalogs.c_tipo_relacion_4")
        cls.related_cfdi = cls._create_document(
            type="I",
            uuid="11111111-1111-1111-1111-111111111111",
            state="published",
            issuer_id=cls.issuer.id,
            receiver_id=cls.customer.id,
        )

    def test_add_related_cfdis_data_if_needed(self):
        move = self.env["account.move"].new({})
        move.cfdi_document_relation_type = self.relation_type
        move.cfdi_document_relations = self.related_cfdi
        cfdi_data = {}
        move._add_related_cfdis_data_if_needed(cfdi_data)
        self.assertEqual(cfdi_data["Relations"]["Type"], self.relation_type.code)
        self.assertEqual(
            cfdi_data["Relations"]["Cfdis"],
            [{"Uuid": self.related_cfdi.uuid}],
        )

    def test_add_related_cfdis_data_if_needed_without_relations(self):
        move = self.env["account.move"].new({})
        move.cfdi_document_relation_type = self.relation_type
        with self.assertRaises(ValidationError):
            move._add_related_cfdis_data_if_needed({})

    def test_add_related_cfdis_data_if_needed_without_relation_type(self):
        move = self.env["account.move"].new({})
        move.cfdi_document_relations = self.related_cfdi
        cfdi_data = {}
        move._add_related_cfdis_data_if_needed(cfdi_data)
        self.assertNotIn("Relations", cfdi_data)

    def test_get_cfdi_relacionados_builds_satcfdi_node(self):
        move = self.env["account.move"].new({})
        move.cfdi_document_relation_type = self.relation_type
        move.cfdi_document_relations = self.related_cfdi
        related = move._get_cfdi_relacionados()
        self.assertEqual(related["TipoRelacion"], self.relation_type.code)
        self.assertEqual(related["CfdiRelacionado"], [self.related_cfdi.uuid])

    def test_validate_cfdi_relation_fields_requires_both(self):
        invoice = self._create_cfdi_invoice()
        invoice.cfdi_document_relations = self.related_cfdi
        with self.assertRaises(ValidationError):
            invoice._validate_cfdi_relation_fields()
        invoice.cfdi_document_relation_type = self.relation_type
        invoice.cfdi_document_relations = False
        with self.assertRaises(ValidationError):
            invoice._validate_cfdi_relation_fields()

    def test_create_invoice_cfdi_registers_related_documents(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        invoice.cfdi_document_relation_type = self.relation_type
        invoice.cfdi_document_relations = self.related_cfdi
        with patch.object(
            type(self.service),
            "create_cfdi",
            return_value=ACTIVE_CFDI_RESPONSE,
        ):
            invoice.create_invoice_cfdi()
        document = invoice.cfdi_document_id
        self.assertTrue(document)
        self.assertEqual(len(document.related_document_ids), 1)
        self.assertEqual(document.related_document_ids.target_id, self.related_cfdi)
        self.assertEqual(
            document.related_document_ids.relation_type_id, self.relation_type
        )
        self.assertEqual(document.pac_provider, self.service.provider)

    def test_get_cfdi_relacionados_rejects_missing_uuid(self):
        draft = self._create_document(
            type="I",
            state="draft",
            uuid=False,
            issuer_id=self.issuer.id,
            receiver_id=self.customer.id,
        )
        move = self.env["account.move"].new({})
        move.cfdi_document_relation_type = self.relation_type
        move.cfdi_document_relations = draft
        with self.assertRaises(ValidationError):
            move._get_cfdi_relacionados()

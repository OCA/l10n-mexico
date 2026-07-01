import base64
from datetime import timedelta
from unittest.mock import patch

from lxml import etree

from odoo import fields
from odoo.exceptions import UserError, ValidationError

from .common import SAMPLE_CFDI_XML, CFDIAccountTestCommon


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

    def test_gather_invoice_cfdi_data_global_information(self):
        public_partner = self.env.ref(
            "l10n_mx_cfdi.l10n_mx_cfdi_res_partner_publico_en_general"
        )
        invoice = self._create_cfdi_invoice(
            partner_id=public_partner.id,
            receiver_id=public_partner.id,
        )
        cfdi_data = invoice._gather_invoice_cfdi_data()
        self.assertIn("GlobalInformation", cfdi_data)
        self.assertEqual(cfdi_data["Receiver"]["FiscalRegime"], "616")

    def test_create_invoice_cfdi_success(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        with self._mock_cfdi_publish():
            invoice.create_invoice_cfdi()
        self.assertTrue(invoice.related_cert_ids)
        self.assertEqual(invoice.cfdi_document_id.state, "published")

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
        refund.action_post()
        register = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=refund.ids)
            .create(
                {
                    "amount": refund.amount_residual,
                    "payment_form_id": self.env.ref(
                        "l10n_mx_catalogs.c_forma_pago_03"
                    ).id,
                }
            )
        )
        register._create_payments()
        with self._mock_cfdi_publish():
            refund.action_generate_cfdi()
        self.assertTrue(refund.related_cert_ids)

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

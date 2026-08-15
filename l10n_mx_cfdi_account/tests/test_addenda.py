import base64
from unittest.mock import patch

from lxml import etree

from odoo.tests import tagged

from .common import ACTIVE_CFDI_RESPONSE, SAMPLE_CFDI_XML, CFDIAccountTestCommon


@tagged("post_install", "-at_install")
class TestCFDIAddenda(CFDIAccountTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Use unprefixed tags: QWeb drops custom prefixes on programmatic
        # views, which broke namespaced assertions in CI.
        cls.addenda_view = cls.env["ir.ui.view"].create(
            {
                "name": "Addenda Test",
                "type": "qweb",
                "mode": "primary",
                "l10n_mx_edi_addenda_flag": True,
                "arch": """
                    <AddendaTest>
                        <Value t-out="record.name"/>
                    </AddendaTest>
                """,
            }
        )
        cls.customer.country_id = cls.env.ref("base.mx")
        cls.customer.l10n_mx_edi_addenda = cls.addenda_view
        # ACTIVE_CFDI_RESPONSE may omit Version; addenda append needs it.
        xml = ACTIVE_CFDI_RESPONSE["xml"]
        if b'Version="' not in xml:
            xml = xml.replace(
                b"<cfdi:Comprobante ",
                b'<cfdi:Comprobante Version="4.0" ',
                1,
            )
        cls._addenda_cfdi_response = {**ACTIVE_CFDI_RESPONSE, "xml": xml}

    def _mock_cfdi_publish(self):
        return patch.object(
            type(self.service),
            "create_cfdi",
            return_value=self._addenda_cfdi_response,
        )

    def test_partner_addenda_domain_lists_flagged_views_only(self):
        other = self.env["ir.ui.view"].create(
            {
                "name": "Not an addenda",
                "type": "qweb",
                "mode": "primary",
                "l10n_mx_edi_addenda_flag": False,
                "arch": "<data><span/></data>",
            }
        )
        field = self.env["res.partner"]._fields["l10n_mx_edi_addenda"]
        domain = field.domain
        matching = self.env["ir.ui.view"].search(domain)
        self.assertIn(self.addenda_view, matching)
        self.assertNotIn(other, matching)

    def test_append_addenda_wraps_content_in_cfdi_addenda(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        result = invoice._l10n_mx_edi_cfdi_invoice_append_addenda(
            SAMPLE_CFDI_XML, self.addenda_view
        )
        root = etree.fromstring(result)
        ns = {"cfdi": "http://www.sat.gob.mx/cfd/4"}
        addenda = root.find("cfdi:Addenda", namespaces=ns)
        self.assertIsNotNone(addenda)
        addenda_test = addenda.find("AddendaTest")
        self.assertIsNotNone(addenda_test)
        self.assertEqual(addenda_test.findtext("Value"), invoice.name)

    def test_create_invoice_cfdi_stores_addenda_in_xml(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        with self._mock_cfdi_publish():
            invoice.create_invoice_cfdi()
        document = invoice.cfdi_document_id
        self.assertTrue(document.xml_file)
        xml = base64.b64decode(document.xml_file)
        self.assertIn(b"Addenda", xml)
        self.assertIn(b"AddendaTest", xml)
        self.assertIn(invoice.name.encode(), xml)

    def test_create_refund_cfdi_stores_addenda_in_xml(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        self._create_published_invoice_cfdi(invoice)
        refund = self._create_cfdi_invoice(move_type="out_refund")
        refund.reversed_entry_id = invoice
        refund.action_post()
        with self._mock_cfdi_publish():
            refund.create_refund_cfdi()
        document = refund.related_cert_ids.filtered(
            lambda d: d.type == "E" and d.state == "published"
        )[:1]
        self.assertTrue(document)
        xml = base64.b64decode(document.xml_file)
        self.assertIn(b"Addenda", xml)
        self.assertIn(b"AddendaTest", xml)

    def test_append_addenda_empty_qweb_returns_unchanged_cfdi(self):
        empty_view = self.env["ir.ui.view"].create(
            {
                "name": "Empty Addenda",
                "type": "qweb",
                "mode": "primary",
                "l10n_mx_edi_addenda_flag": True,
                "arch": '<t t-if="False"><AddendaTest/></t>',
            }
        )
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        result = invoice._l10n_mx_edi_cfdi_invoice_append_addenda(
            SAMPLE_CFDI_XML, empty_view
        )
        self.assertEqual(result, SAMPLE_CFDI_XML)

    def test_append_addenda_accepts_str_cfdi(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        result = invoice._l10n_mx_edi_cfdi_invoice_append_addenda(
            SAMPLE_CFDI_XML.decode("utf-8"), self.addenda_view
        )
        self.assertIsInstance(result, bytes)
        root = etree.fromstring(result)
        ns = {"cfdi": "http://www.sat.gob.mx/cfd/4"}
        self.assertIsNotNone(root.find("cfdi:Addenda", namespaces=ns))

    def test_append_addenda_does_not_double_wrap_namespaced_addenda_root(self):
        view = self.env["ir.ui.view"].create(
            {
                "name": "Namespaced Addenda",
                "type": "qweb",
                "mode": "primary",
                "l10n_mx_edi_addenda_flag": True,
                "arch": """
                    <Addenda xmlns="http://www.sat.gob.mx/cfd/4">
                        <AddendaTest>
                            <Value t-out="record.name"/>
                        </AddendaTest>
                    </Addenda>
                """,
            }
        )
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        result = invoice._l10n_mx_edi_cfdi_invoice_append_addenda(SAMPLE_CFDI_XML, view)
        root = etree.fromstring(result)
        ns = {"cfdi": "http://www.sat.gob.mx/cfd/4"}
        addendas = root.findall("cfdi:Addenda", namespaces=ns)
        self.assertEqual(len(addendas), 1)
        # Default xmlns from the QWeb root also scopes child elements.
        self.assertIsNotNone(
            addendas[0].find("{http://www.sat.gob.mx/cfd/4}AddendaTest")
        )
        self.assertIsNone(addendas[0].find("cfdi:Addenda", namespaces=ns))

    def test_append_addenda_defaults_version_namespace_when_missing(self):
        xml = SAMPLE_CFDI_XML.replace(b' Version="4.0"', b"")
        self.assertNotIn(b"Version=", xml)
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        result = invoice._l10n_mx_edi_cfdi_invoice_append_addenda(
            xml, self.addenda_view
        )
        root = etree.fromstring(result)
        addenda = root.find("{http://www.sat.gob.mx/cfd/4}Addenda")
        self.assertIsNotNone(addenda)

    def test_apply_partner_addenda_noop_without_addenda(self):
        self.customer.l10n_mx_edi_addenda = False
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        document = self._create_document(
            type="I",
            state="published",
            related_invoice_id=invoice.id,
            receiver_id=invoice.receiver_id.id,
        )
        document.xml_file = base64.b64encode(SAMPLE_CFDI_XML)
        original = document.xml_file
        invoice._l10n_mx_edi_cfdi_apply_partner_addenda(document)
        self.assertEqual(document.xml_file, original)
        self.assertNotIn(b"Addenda", base64.b64decode(document.xml_file))

    def test_apply_partner_addenda_noop_without_xml_file(self):
        invoice = self._post_cfdi_invoice(self._create_cfdi_invoice())
        document = self._create_document(
            type="I",
            state="published",
            related_invoice_id=invoice.id,
            receiver_id=invoice.receiver_id.id,
        )
        document.xml_file = False
        invoice._l10n_mx_edi_cfdi_apply_partner_addenda(document)
        self.assertFalse(document.xml_file)

    def test_apply_partner_addenda_uses_commercial_partner_fallback(self):
        parent = self.customer
        child = self.env["res.partner"].create(
            {
                "name": "Child Contact",
                "parent_id": parent.id,
                "type": "invoice",
                "country_id": self.env.ref("base.mx").id,
            }
        )
        self.assertFalse(child.l10n_mx_edi_addenda)
        self.assertTrue(child.commercial_partner_id.l10n_mx_edi_addenda)
        invoice = self._post_cfdi_invoice(
            self._create_cfdi_invoice(partner_id=child.id, receiver_id=parent.id)
        )
        document = self._create_document(
            type="I",
            state="published",
            related_invoice_id=invoice.id,
            receiver_id=parent.id,
        )
        document.xml_file = base64.b64encode(SAMPLE_CFDI_XML)
        invoice._l10n_mx_edi_cfdi_apply_partner_addenda(document)
        xml = base64.b64decode(document.xml_file)
        self.assertIn(b"Addenda", xml)
        self.assertIn(b"AddendaTest", xml)

    def test_compute_l10n_mx_edi_addenda_is_readonly_false_with_view_read(self):
        self.assertFalse(self.customer.l10n_mx_edi_addenda_is_readonly)
        self.assertEqual(self.customer.l10n_mx_edi_addenda_name, self.addenda_view.name)

    def test_compute_l10n_mx_edi_addenda_is_readonly_when_no_view_access(self):
        with patch.object(
            type(self.env["ir.ui.view"]), "has_access", return_value=False
        ):
            self.customer.invalidate_recordset(["l10n_mx_edi_addenda_is_readonly"])
            self.assertTrue(self.customer.l10n_mx_edi_addenda_is_readonly)

    def test_ir_ui_view_addenda_flag_defaults_false(self):
        view = self.env["ir.ui.view"].create(
            {
                "name": "No Flag View",
                "type": "qweb",
                "mode": "primary",
                "arch": "<span/>",
            }
        )
        self.assertFalse(view.l10n_mx_edi_addenda_flag)

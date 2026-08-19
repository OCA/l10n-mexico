# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

from lxml import etree

from odoo.tests import tagged

from odoo.addons.l10n_mx_cfdi_account.tests.common import CFDIAccountTestCommon


@tagged("post_install", "-at_install")
class TestAddendaKuehneNagel(CFDIAccountTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.addenda_view = cls.env.ref(
            "l10n_mx_cfdi_account_addenda_kuehne_nagel."
            "l10n_mx_cfdi_account_addenda_kuehne_nagel"
        )
        cls.customer.write({"l10n_mx_edi_addenda": cls.addenda_view.id})

    # -- flag / partner wiring --

    def test_addenda_view_flag(self):
        self.assertTrue(self.addenda_view.l10n_mx_edi_addenda_flag)
        self.assertEqual(self.addenda_view.name, "Addenda Kuehne Nagel")

    def test_partner_addenda_related_name(self):
        self.assertEqual(self.customer.l10n_mx_edi_addenda_name, "Addenda Kuehne Nagel")

    def test_kn_flag_on_partner_with_addenda(self):
        invoice = self._create_cfdi_invoice()
        self.assertTrue(invoice.kn_flag)

    def test_kn_flag_false_for_other_partner(self):
        partner_other = self.env["res.partner"].create(
            {"name": "Other Customer", "country_id": self.env.ref("base.mx").id}
        )
        invoice = self._create_cfdi_invoice(partner_id=partner_other.id)
        self.assertFalse(invoice.kn_flag)

    # -- normalization --

    def test_normalize_branch_centre_uppercase(self):
        invoice = self._create_cfdi_invoice(
            kn_file_type="file",
            kn_file_number_gl="7310880180505405",
            kn_branch_centre="10dwt",
            kn_transport_ref="2886541",
        )
        self.assertEqual(invoice.kn_branch_centre, "10DWT")

    def test_normalize_strips_whitespace(self):
        invoice = self._create_cfdi_invoice(
            kn_file_number_gl="  12345  ",
            kn_transport_ref="  2886541  ",
        )
        self.assertEqual(invoice.kn_file_number_gl, "12345")
        self.assertEqual(invoice.kn_transport_ref, "2886541")

    def test_write_normalizes_branch_centre(self):
        invoice = self._create_cfdi_invoice()
        invoice.write({"kn_branch_centre": "  abc  "})
        self.assertEqual(invoice.kn_branch_centre, "ABC")

    # -- ref preservation --

    def test_ref_is_preserved_for_kn(self):
        invoice = self._create_cfdi_invoice(ref="Customer PO/abc-123")
        self.assertEqual(invoice.ref, "Customer PO/abc-123")

    def test_any_purchase_order_format_is_allowed(self):
        invoice = self._create_cfdi_invoice()
        invoice.write({"ref": "INVALID-PO"})
        self.assertEqual(invoice.ref, "INVALID-PO")

    def test_arbitrary_kn_field_formats_are_allowed(self):
        invoice = self._create_cfdi_invoice()
        invoice.write(
            {
                "kn_file_type": "file",
                "kn_file_number_gl": "12345",
                "kn_branch_centre": "AB",
                "kn_transport_ref": "123",
            }
        )
        self.assertEqual(invoice.kn_file_number_gl, "12345")
        self.assertEqual(invoice.kn_branch_centre, "AB")
        self.assertEqual(invoice.kn_transport_ref, "123")

    def test_valid_tracking_number(self):
        invoice = self._create_cfdi_invoice(
            kn_file_type="tracking",
            kn_file_number_gl="1023950106-1815",
            kn_branch_centre="10WP",
            kn_transport_ref="2886541",
        )
        self.assertEqual(invoice.kn_file_number_gl, "1023950106-1815")

    # -- QWeb rendering via framework --

    def _sample_cfdi(self):
        return (
            b'<?xml version="1.0" encoding="UTF-8"?>'
            b'<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" '
            b'Version="4.0">'
            b"</cfdi:Comprobante>"
        )

    def test_render_kn_addenda_via_framework(self):
        invoice = self._create_cfdi_invoice(
            ref="Customer PO/abc-123",
            kn_file_type="file",
            kn_file_number_gl="7310880180505405",
            kn_branch_centre="10DWT",
            kn_transport_ref="2886541",
        )
        result = invoice._l10n_mx_edi_cfdi_invoice_append_addenda(
            self._sample_cfdi(), self.addenda_view
        )
        self.assertIn(b"KNRECEPCION", result)
        self.assertIn(b"FacturasKN", result)
        self.assertIn(b"7310880180505405", result)
        self.assertIn(b"10DWT", result)
        self.assertIn(b"2886541", result)
        self.assertIn(b"Customer PO/abc-123", result)
        self.assertIn(b"Addenda", result)

    def test_render_kn_addenda_empty_optional_fields(self):
        invoice = self._create_cfdi_invoice(ref=False)
        result = invoice._l10n_mx_edi_cfdi_invoice_append_addenda(
            self._sample_cfdi(), self.addenda_view
        )
        root = etree.fromstring(result)
        ns = {"kn": "http://www.w3.org/2001/XMLSchema"}
        for field_name in (
            "Purchase_Order",
            "FileNumber_GL",
            "Branch_Centre",
            "TransportRef",
        ):
            element = root.find(f".//kn:{field_name}", namespaces=ns)
            self.assertIsNotNone(element)
            self.assertFalse((element.text or "").strip())

    def test_render_kn_addenda_wraps_in_cfdi_addenda(self):
        invoice = self._create_cfdi_invoice(
            ref="PO-1",
            kn_file_number_gl="F-1",
            kn_branch_centre="BC-1",
            kn_transport_ref="TR-1",
        )
        result = invoice._l10n_mx_edi_cfdi_invoice_append_addenda(
            self._sample_cfdi(), self.addenda_view
        )
        root = etree.fromstring(result)
        ns = {
            "cfdi": "http://www.sat.gob.mx/cfd/4",
            "kn": "http://www.w3.org/2001/XMLSchema",
        }
        addenda = root.find("cfdi:Addenda", namespaces=ns)
        self.assertIsNotNone(addenda)
        kn = addenda.find("kn:KNRECEPCION", namespaces=ns)
        self.assertIsNotNone(kn)
        self.assertEqual(kn.findtext(".//kn:Purchase_Order", namespaces=ns), "PO-1")
        self.assertEqual(kn.findtext(".//kn:FileNumber_GL", namespaces=ns), "F-1")
        self.assertEqual(kn.findtext(".//kn:Branch_Centre", namespaces=ns), "BC-1")
        self.assertEqual(kn.findtext(".//kn:TransportRef", namespaces=ns), "TR-1")

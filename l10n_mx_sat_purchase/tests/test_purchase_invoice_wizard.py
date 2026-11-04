# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from lxml import etree

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# Fictitious RFCs: the SAT test RFC for the company and a made-up one for the vendor.
COMPANY_RFC = "EKU9003173C9"
VENDOR_RFC = "XIA190128J61"
OTHER_RFC = "XOT190128J61"


@tagged("post_install", "-at_install")
class TestPurchaseInvoiceWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.company.write({"vat": COMPANY_RFC, "country_id": cls.env.ref("base.mx").id})
        cls.mxn = cls.env.ref("base.MXN")
        cls.mxn.active = True
        cls.vendor = cls.env["res.partner"].create(
            {
                "name": "Soluciones Demo",
                "vat": VENDOR_RFC,
                "country_id": cls.env.ref("base.mx").id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {"name": "Service", "type": "service", "purchase_method": "purchase"}
        )
        cls.request = cls.env["l10n_mx_sat.download.request"].create(
            {
                "company_id": cls.company.id,
                "document_kind": "cfdi",
                "direction": "received",
                "request_type": "xml",
                "date_from": "2026-02-01 00:00:00",
                "date_to": "2026-02-28 23:59:59",
                "state": "downloading",
            }
        )
        cls.document = cls._create_document("AAAAAAAA-0000-0000-0000-000000000001")
        cls.order = cls._create_order()

    @classmethod
    def _create_document(
        cls, uuid, issuer_rfc=VENDOR_RFC, total="1650.00", moneda="MXN"
    ):
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Version="4.0"
    Serie="A" Folio="1"
    Fecha="2026-02-10T10:00:00" SubTotal="1422.41" Moneda="{moneda}" Total="{total}"
    TipoDeComprobante="I" MetodoPago="PUE" LugarExpedicion="06600">
    <cfdi:Emisor Rfc="{issuer_rfc}" Nombre="SOLUCIONES DEMO" RegimenFiscal="601"/>
    <cfdi:Receptor Rfc="{COMPANY_RFC}" Nombre="ESCUELA KEMPER URGATE"
        DomicilioFiscalReceptor="06600" RegimenFiscalReceptor="603" UsoCFDI="G03"/>
    <cfdi:Conceptos>
        <cfdi:Concepto ClaveProdServ="01010101" Cantidad="1" ClaveUnidad="E48"
            Descripcion="Service" ValorUnitario="1422.41" Importe="1422.41"
            ObjetoImp="02"/>
    </cfdi:Conceptos>
    <cfdi:Complemento>
        <tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
            Version="1.1" UUID="{uuid}" FechaTimbrado="2026-02-10T10:05:00"/>
    </cfdi:Complemento>
</cfdi:Comprobante>""".encode()
        document = cls.env["l10n_mx_sat.document"]._upsert_from_xml(
            etree.fromstring(xml), xml, cls.company, cls.request
        )
        if document.vendor_bill_id:
            # l10n_mx_sat_vendor_bill, when installed, bills every received CFDI
            document.vendor_bill_id.unlink()
            document._sat_write({"vendor_bill_id": False})
        return document

    @classmethod
    def _create_order(cls, partner=None):
        order = cls.env["purchase.order"].create(
            {
                "partner_id": (partner or cls.vendor).id,
                "currency_id": cls.mxn.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": cls.product.id,
                            "product_qty": 1,
                            "price_unit": 1650.0,
                            "tax_ids": [Command.clear()],
                        }
                    )
                ],
            }
        )
        order.button_confirm()
        return order

    def _open_wizard(self, orders=None, select=True):
        action = (orders or self.order).action_l10n_mx_sat_select_document()
        wizard = (
            self.env[action["res_model"]].with_context(**action["context"]).create({})
        )
        if select:
            wizard.line_ids.selected = False
            wizard.line_ids.filtered(
                lambda line: line.document_id == self.document
            ).selected = True
        return wizard

    def test_available_documents(self):
        other_vendor = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000002", OTHER_RFC
        )
        other_currency = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000003", moneda="USD"
        )
        billed = self._create_document("AAAAAAAA-0000-0000-0000-000000000004")
        billed._sat_write(
            {
                "vendor_bill_id": self.env["account.move"]
                .create({"move_type": "in_invoice"})
                .id
            }
        )
        cancelled = self._create_document("AAAAAAAA-0000-0000-0000-000000000005")
        cancelled._sat_write({"sat_status": "cancelled"})
        wizard = self._open_wizard(select=False)
        self.assertEqual(wizard.partner_id, self.vendor)
        self.assertEqual(wizard.l10n_mx_sat_available_document_ids, self.document)
        self.assertEqual(wizard.line_ids.document_id, self.document)
        self.assertEqual(wizard.line_ids.total, 1650.0)
        # The only CFDI matching the orders total comes pre-selected
        self.assertTrue(wizard.line_ids.selected)
        self.assertEqual(wizard.l10n_mx_sat_document_id, self.document)
        for document in (other_vendor, other_currency, billed, cancelled):
            self.assertNotIn(document, wizard.l10n_mx_sat_available_document_ids)

    def test_selection(self):
        second = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000006", total="1650.00"
        )
        wizard = self._open_wizard(select=False)
        self.assertEqual(len(wizard.line_ids), 2)
        # Two CFDIs match the total: none is pre-selected
        self.assertFalse(wizard.line_ids.filtered("selected"))
        self.assertRejected(wizard.action_create_invoice())
        wizard.line_ids.selected = True
        self.assertRejected(wizard.action_create_invoice())
        wizard.line_ids.filtered(
            lambda line: line.document_id == second
        ).selected = False
        self.assertEqual(wizard.l10n_mx_sat_document_id, self.document)
        wizard.action_create_invoice()
        self.assertEqual(self.document.vendor_bill_id, self.order.invoice_ids)
        self.assertEqual(
            self._open_wizard(self._create_order(), select=False).line_ids.document_id,
            second,
        )

    def test_display_name(self):
        self.assertEqual(
            self.document.display_name,
            f"A-1 | SOLUCIONES DEMO | 1,650.00 MXN | {self.document.uuid}",
        )

    def test_create_bill(self):
        wizard = self._open_wizard()
        self.assertFalse(wizard.total_mismatch)
        action = wizard.action_create_invoice()
        move = self.order.invoice_ids
        self.assertEqual(len(move), 1)
        self.assertEqual(action["res_id"], move.id)
        self.assertEqual(self.document.vendor_bill_id, move)
        self.assertEqual(move.partner_id, self.vendor)
        self.assertEqual(move.invoice_line_ids.product_id, self.product)
        xml = move.attachment_ids.filtered(lambda a: a.mimetype == "application/xml")
        self.assertEqual(len(xml), 1)
        self.assertEqual(xml.raw, self.document.attachment_id.raw)
        self.assertNotIn(
            self.document, self._open_wizard().l10n_mx_sat_available_document_ids
        )

    def test_total_mismatch_warning(self):
        self.order.order_line.price_unit = 1000.0
        wizard = self._open_wizard()
        self.assertTrue(wizard.total_mismatch)
        wizard.action_create_invoice()
        self.assertEqual(self.document.vendor_bill_id, self.order.invoice_ids)

    def assertRejected(self, action):
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(action["params"]["type"], "danger")
        self.assertFalse(self.order.invoice_ids)

    def test_document_already_linked(self):
        wizard = self._open_wizard()
        self.document._sat_write(
            {
                "vendor_bill_id": self.env["account.move"]
                .create({"move_type": "in_invoice"})
                .id
            }
        )
        self.assertRejected(wizard.action_create_invoice())

    def test_orders_of_different_vendors(self):
        other = self._create_order(
            self.env["res.partner"].create({"name": "Other", "vat": OTHER_RFC})
        )
        with self.assertRaises(ValidationError):
            self._open_wizard(self.order | other)

    def test_orders_of_different_currencies(self):
        usd = self.env.ref("base.USD")
        usd.active = True
        other = self.env["purchase.order"].create(
            {"partner_id": self.vendor.id, "currency_id": usd.id}
        )
        with self.assertRaises(ValidationError):
            self._open_wizard(self.order | other)

    def test_no_orders_nor_document(self):
        wizard = self.env["l10n_mx_sat.purchase.invoice.wizard"].new({})
        self.assertFalse(wizard.l10n_mx_sat_available_document_ids)
        self.assertFalse(wizard.line_ids)
        self.assertTrue(wizard._l10n_mx_sat_check_document())

    def test_not_confirmed_order(self):
        order = self.env["purchase.order"].create(
            {"partner_id": self.vendor.id, "currency_id": self.mxn.id}
        )
        with self.assertRaises(UserError):
            self._open_wizard(order).action_create_invoice()

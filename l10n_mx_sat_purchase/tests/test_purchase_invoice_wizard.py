# Copyright 2026 Jarsa
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from unittest.mock import patch

from lxml import etree

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger

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
        cls.tax = cls.env["account.tax"].create(
            {
                "name": "IVA 16% (test)",
                "amount": 16,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "company_id": cls.company.id,
            }
        )
        cls.product = cls._create_product("Service", default_code="SRV-001")
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
    def _create_product(cls, name, default_code=None, vendor_code=None):
        vals = {"name": name, "type": "service", "purchase_method": "purchase"}
        if default_code:
            vals["default_code"] = default_code
        if vendor_code:
            vals["seller_ids"] = [
                Command.create(
                    {"partner_id": cls.vendor.id, "product_code": vendor_code}
                )
            ]
        return cls.env["product.product"].create(vals)

    @classmethod
    def _create_document(
        cls,
        uuid,
        issuer_rfc=VENDOR_RFC,
        total=None,
        moneda="MXN",
        concepts=None,
        series="A",
        folio="1",
    ):
        """Create a received CFDI with ``concepts``: dicts with ``description``,
        ``quantity``, ``price_unit`` and optionally ``code``
        (NoIdentificacion), ``unit`` (ClaveUnidad), ``discount`` and ``tax``
        (False for a concept without IVA)."""
        concepts = concepts or [
            {"description": "Service", "quantity": 1, "price_unit": 1422.41}
        ]
        subtotal = discount = taxes = 0.0
        nodes = []
        for concept in concepts:
            amount = round(concept["quantity"] * concept["price_unit"], 2)
            concept_discount = concept.get("discount", 0.0)
            base = amount - concept_discount
            subtotal += amount
            discount += concept_discount
            attributes = {
                "ClaveProdServ": "01010101",
                "Cantidad": concept["quantity"],
                "ClaveUnidad": concept.get("unit", "E48"),
                "Descripcion": concept["description"],
                "ValorUnitario": concept["price_unit"],
                "Importe": f"{amount:.2f}",
                "NoIdentificacion": concept.get("code"),
                "Descuento": f"{concept_discount:.2f}" if concept_discount else None,
                "ObjetoImp": "02",
            }
            node = "<cfdi:Concepto " + " ".join(
                f'{name}="{value}"'
                for name, value in attributes.items()
                if value is not None
            )
            if concept.get("tax", True):
                tax = round(base * 0.16, 2)
                taxes += tax
                node += (
                    "><cfdi:Impuestos><cfdi:Traslados><cfdi:Traslado "
                    f'Base="{base:.2f}" Impuesto="002" TipoFactor="Tasa" '
                    f'TasaOCuota="0.160000" Importe="{tax:.2f}"/>'
                    "</cfdi:Traslados></cfdi:Impuestos></cfdi:Concepto>"
                )
            else:
                node += "/>"
            nodes.append(node)
        total = total or f"{subtotal - discount + taxes:.2f}"
        xml = f"""<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4" Version="4.0"
    Serie="{series}" Folio="{folio}"
    Fecha="2026-02-10T10:00:00" SubTotal="{subtotal:.2f}" Moneda="{moneda}"
    {f'Descuento="{discount:.2f}"' if discount else ""} Total="{total}"
    TipoDeComprobante="I" MetodoPago="PUE" LugarExpedicion="06600">
    <cfdi:Emisor Rfc="{issuer_rfc}" Nombre="SOLUCIONES DEMO" RegimenFiscal="601"/>
    <cfdi:Receptor Rfc="{COMPANY_RFC}" Nombre="ESCUELA KEMPER URGATE"
        DomicilioFiscalReceptor="06600" RegimenFiscalReceptor="603" UsoCFDI="G03"/>
    <cfdi:Conceptos>{"".join(nodes)}</cfdi:Conceptos>
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
    def _create_order(cls, partner=None, lines=None, tax=True):
        """Confirmed order with ``lines``: (product, quantity, price) tuples."""
        lines = lines or [(cls.product, 1, 1422.41)]
        order = cls.env["purchase.order"].create(
            {
                "partner_id": (partner or cls.vendor).id,
                "currency_id": cls.mxn.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_qty": quantity,
                            "price_unit": price,
                            "tax_ids": [Command.set(cls.tax.ids)]
                            if tax
                            else [Command.clear()],
                        }
                    )
                    for product, quantity, price in lines
                ],
            }
        )
        order.button_confirm()
        return order

    def _open_wizard(self, orders=None, select=True, document=None, mode="line"):
        """Open the wizard of ``orders`` in ``mode``. ``select`` sets ``document``
        (the default one of the tests) instead of the CFDI the wizard proposes."""
        action = (orders or self.order).action_l10n_mx_sat_select_document()
        context = dict(action["context"], default_match_mode=mode)
        if not mode:
            del context["default_match_mode"]
        wizard = self.env[action["res_model"]].with_context(**context).create({})
        if select:
            wizard.l10n_mx_sat_document_id = document or self.document
        return wizard

    def assertRejected(self, action):
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(action["params"]["type"], "danger")
        self.assertFalse(self.order.invoice_ids)

    # ------------------------------------------------------------------
    # CFDI selection
    # ------------------------------------------------------------------

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
        # The only CFDI matching the orders total comes pre-selected
        self.assertEqual(wizard.l10n_mx_sat_document_id, self.document)
        for document in (other_vendor, other_currency, billed, cancelled):
            self.assertNotIn(document, wizard.l10n_mx_sat_available_document_ids)

    def test_default_document(self):
        second = self._create_document("AAAAAAAA-0000-0000-0000-000000000006")
        wizard = self._open_wizard(select=False)
        # Two CFDIs match the total: none is pre-selected, no concepts yet
        self.assertFalse(wizard.l10n_mx_sat_document_id)
        self.assertFalse(wizard.concept_ids)
        self.assertRejected(wizard.action_create_invoice())
        wizard.l10n_mx_sat_document_id = self.document
        self.assertEqual(wizard.concept_document_id, self.document)
        self.assertEqual(len(wizard.concept_ids), 1)
        wizard.action_create_invoice()
        self.assertEqual(self.document.vendor_bill_id, self.order.invoice_ids)
        self.assertEqual(
            self._open_wizard(
                self._create_order(), select=False
            ).l10n_mx_sat_document_id,
            second,
        )

    def test_default_document_within_tolerance(self):
        order = self._create_order(lines=[(self.product, 1, 1422.0)])
        self.assertEqual(order.amount_total, 1649.52)
        wizard = self._open_wizard(order, select=False, mode="document")
        self.assertEqual(wizard.l10n_mx_sat_document_id, self.document)
        self.assertTrue(wizard.total_mismatch)
        self.company.l10n_mx_sat_purchase_total_tolerance = 0.1
        wizard = self._open_wizard(order, select=False)
        self.assertFalse(wizard.l10n_mx_sat_document_id)

    def test_match_mode(self):
        self.assertEqual(self._open_wizard(mode=None).match_mode, "document")
        self.company.l10n_mx_sat_purchase_match_mode = "line"
        self.assertEqual(self._open_wizard(mode=None).match_mode, "line")
        self.vendor.l10n_mx_sat_purchase_match_mode = "document"
        wizard = self._open_wizard(mode=None)
        self.assertEqual(wizard.match_mode, "document")
        # Adding an order keeps the mode chosen by the user
        wizard.match_mode = "line"
        wizard.purchase_order_ids = [Command.link(self._create_order().id)]
        self.assertEqual(wizard.match_mode, "line")

    def test_company_without_rfc(self):
        wizard = self._open_wizard()
        self.company.vat = False
        Document = self.env["l10n_mx_sat.document"]
        self.assertFalse(Document.search(Document._get_selectable_domain(self.company)))
        self.assertRejected(wizard.action_create_invoice())
        with self.assertRaises(UserError):
            self.order.action_l10n_mx_sat_select_document()

    def test_document_access(self):
        # An issued CFDI (e.g. a customer invoice) is none of the buyer's business
        issued = self.env["l10n_mx_sat.document"]._sat_create(
            [
                {
                    "company_id": self.company.id,
                    "uuid": "AAAAAAAA-0000-0000-0000-000000000007",
                    "document_kind": "cfdi",
                    "direction": "issued",
                    "voucher_type": "I",
                }
            ]
        )
        documents = self.document | issued
        user = self.env["res.users"].create(
            {
                "name": "Buyer",
                "login": "l10n_mx_sat_buyer",
                "group_ids": [
                    Command.set(self.env.ref("purchase.group_purchase_user").ids)
                ],
            }
        )
        domain = [("id", "in", documents.ids)]
        Document = self.env["l10n_mx_sat.document"].with_user(user)
        self.assertEqual(Document.search(domain), self.document)
        wizard = self._open_wizard().with_user(user)
        self.assertEqual(wizard.l10n_mx_sat_document_id, self.document)
        self.assertEqual(wizard.concept_ids.description, "Service")
        user.group_ids = [Command.link(self.env.ref("l10n_mx_sat.group_sat_user").id)]
        self.assertEqual(Document.search(domain), documents)

    def test_display_name(self):
        self.assertEqual(
            self.document.display_name,
            f"A-1 | SOLUCIONES DEMO | 1,650.00 MXN | {self.document.uuid}",
        )

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
        self.assertFalse(wizard._find_default_document())
        self.assertFalse(wizard.available_purchase_line_ids)
        self.assertFalse(wizard.total_mismatch)
        self.assertTrue(wizard._l10n_mx_sat_check_document())

    def test_not_confirmed_order(self):
        order = self.env["purchase.order"].create(
            {"partner_id": self.vendor.id, "currency_id": self.mxn.id}
        )
        with self.assertRaises(UserError):
            self._open_wizard(order).action_create_invoice()

    # ------------------------------------------------------------------
    # Concepts and mapping proposal
    # ------------------------------------------------------------------

    def test_concepts_parsed(self):
        document = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000010",
            concepts=[
                {
                    "description": "Tornillo 1/4",
                    "quantity": 10,
                    "price_unit": 2.5,
                    "code": "TOR-14",
                    "unit": "H87",
                    "discount": 5,
                },
                {
                    "description": "Flete",
                    "quantity": 1,
                    "price_unit": 100,
                    "tax": False,
                },
            ],
        )
        concepts = document._get_cfdi_concepts()
        self.assertEqual(len(concepts), 2)
        self.assertEqual(
            concepts[0],
            {
                "sequence": 1,
                "no_identificacion": "TOR-14",
                "description": "Tornillo 1/4",
                "product_service_code": "01010101",
                "quantity": 10.0,
                "unit_code": "H87",
                "price_unit": 2.5,
                "amount": 25.0,
                "discount_amount": 5.0,
                "tax_amount": 3.2,
                "tax_summary": "IVA 16%",
            },
        )
        self.assertEqual(concepts[1]["tax_amount"], 0.0)
        self.assertEqual(concepts[1]["tax_summary"], "")
        self.assertFalse(concepts[1]["no_identificacion"])
        self.assertEqual(
            document._get_cfdi_amounts(),
            {"subtotal": 125.0, "discount": 5.0, "total": 123.2},
        )
        wizard = self._open_wizard(document=document)
        concept = wizard.concept_ids[0]
        self.assertEqual(concept.description, "Tornillo 1/4")
        self.assertEqual(concept.tax_summary, "IVA 16%")
        self.assertEqual(wizard.cfdi_amount_untaxed, 120.0)

    @mute_logger("odoo.addons.l10n_mx_sat_purchase.models.l10n_mx_sat_document")
    def test_concepts_of_document_without_xml(self):
        self.document.attachment_id.write({"raw": b"<broken"})
        self.assertIsNone(self.document._get_cfdi_tree())
        self.assertEqual(self.document._get_cfdi_concepts(), [])
        self.assertEqual(self.document._get_cfdi_amounts()["total"], 1650.0)
        wizard = self._open_wizard()
        self.assertFalse(wizard.concept_ids)
        with self.assertRaises(UserError):
            wizard.action_create_invoice()

    def test_mapping_by_internal_code(self):
        bolt = self._create_product("Bolt", default_code="BLT-01")
        nut = self._create_product("Nut", default_code="NUT-01")
        order = self._create_order(lines=[(bolt, 10, 3.0), (nut, 10, 1.0)])
        document = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000011",
            concepts=[
                {
                    "description": "TUERCA",
                    "quantity": 4,
                    "price_unit": 1.0,
                    "code": "nut-01",
                },
                {
                    "description": "TORNILLO",
                    "quantity": 5,
                    "price_unit": 3.0,
                    "code": "BLT-01",
                },
            ],
        )
        wizard = self._open_wizard(order, document=document)
        self.assertEqual(
            wizard.concept_ids.mapped("purchase_line_id.product_id"), nut | bolt
        )
        self.assertEqual(wizard.concept_ids.mapped("qty_to_invoice"), [4.0, 5.0])
        self.assertEqual(wizard.concept_ids.mapped("product_id"), nut | bolt)

    def test_mapping_by_vendor_code(self):
        bolt = self._create_product("Bolt", vendor_code="V-BOLT")
        nut = self._create_product("Nut", vendor_code="V-NUT")
        order = self._create_order(lines=[(bolt, 10, 3.0), (nut, 10, 1.0)])
        document = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000012",
            concepts=[
                {
                    "description": "Pieza",
                    "quantity": 4,
                    "price_unit": 1.0,
                    "code": "V-NUT",
                },
                {
                    "description": "Pieza",
                    "quantity": 5,
                    "price_unit": 3.0,
                    "code": "V-BOLT",
                },
            ],
        )
        wizard = self._open_wizard(order, document=document)
        self.assertEqual(
            wizard.concept_ids.mapped("purchase_line_id.product_id"), nut | bolt
        )

    def test_mapping_by_description(self):
        gear = self._create_product("Engrane de transmisión")
        shaft = self._create_product("Eje")
        shaft.seller_ids = [
            Command.create(
                {"partner_id": self.vendor.id, "product_name": "Flecha de acero"}
            )
        ]
        order = self._create_order(lines=[(gear, 2, 500.0), (shaft, 3, 200.0)])
        document = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000013",
            concepts=[
                {"description": "FLECHA DE  ACERO", "quantity": 1, "price_unit": 200.0},
                {
                    "description": "[X] engrane de transmision",
                    "quantity": 2,
                    "price_unit": 450.0,
                },
                {
                    "description": "Servicio no pedido",
                    "quantity": 1,
                    "price_unit": 999.0,
                },
            ],
        )
        wizard = self._open_wizard(order, document=document)
        self.assertEqual(wizard.concept_ids[0].purchase_line_id.product_id, shaft)
        self.assertEqual(wizard.concept_ids[1].purchase_line_id.product_id, gear)
        self.assertFalse(wizard.concept_ids[2].purchase_line_id)
        self.assertFalse(wizard.concept_ids[2].product_id)

    def test_mapping_by_product_and_price(self):
        # Same product ordered twice at different prices: the price decides
        order = self._create_order(
            lines=[(self.product, 1, 1000.0), (self.product, 1, 1422.41)]
        )
        wizard = self._open_wizard(order)
        self.assertEqual(wizard.concept_ids.purchase_line_id, order.order_line[1])
        # No line with the CFDI price: the oldest line with pending quantity
        document = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000014",
            concepts=[{"description": "Service", "quantity": 1, "price_unit": 1200.0}],
        )
        wizard = self._open_wizard(order, document=document)
        self.assertEqual(wizard.concept_ids.purchase_line_id, order.order_line[0])

    def test_mapping_by_unique_price(self):
        other = self._create_product("Other")
        order = self._create_order(lines=[(other, 1, 50.0), (self.product, 1, 70.0)])
        document = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000015",
            concepts=[
                {"description": "Unknown", "quantity": 1, "price_unit": 70.0},
                {"description": "Unknown too", "quantity": 1, "price_unit": 123.0},
            ],
        )
        wizard = self._open_wizard(order, document=document)
        self.assertEqual(wizard.concept_ids[0].purchase_line_id, order.order_line[1])
        self.assertFalse(wizard.concept_ids[1].purchase_line_id)
        # Two lines with the same price: no proposal
        order.order_line[0].price_unit = 70.0
        wizard = self._open_wizard(order, document=document)
        self.assertFalse(wizard.concept_ids.purchase_line_id)

    def test_mapping_prefers_oldest_pending_order(self):
        old_order = self._create_order(lines=[(self.product, 2, 100.0)])
        new_order = self._create_order(lines=[(self.product, 2, 100.0)])
        old_order.date_approve = "2026-01-01 10:00:00"
        new_order.date_approve = "2026-01-02 10:00:00"
        document = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000016",
            concepts=[
                {"description": "Service", "quantity": 2, "price_unit": 100.0},
                {"description": "Service", "quantity": 1, "price_unit": 100.0},
                {"description": "Service", "quantity": 1, "price_unit": 100.0},
                {"description": "Service", "quantity": 1, "price_unit": 100.0},
            ],
        )
        wizard = self._open_wizard(new_order | old_order, document=document)
        self.assertEqual(
            wizard.concept_ids.mapped("purchase_line_id.order_id"),
            old_order | new_order,
        )
        # 2 + 1 + 1 = 4 units pending: the fifth unit has no line
        self.assertEqual(wizard.concept_ids[0].purchase_line_id.order_id, old_order)
        self.assertEqual(wizard.concept_ids[1].purchase_line_id.order_id, new_order)
        self.assertEqual(wizard.concept_ids[2].purchase_line_id.order_id, new_order)
        self.assertFalse(wizard.concept_ids[3].purchase_line_id)

    def test_add_order_keeps_mapping(self):
        second = self._create_order(lines=[(self.product, 1, 1422.41)])
        document = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000017",
            concepts=[
                {"description": "Service", "quantity": 1, "price_unit": 1422.41},
                {"description": "Service", "quantity": 1, "price_unit": 1422.41},
            ],
        )
        wizard = self._open_wizard(document=document)
        self.assertEqual(wizard.concept_ids[0].purchase_line_id, self.order.order_line)
        self.assertFalse(wizard.concept_ids[1].purchase_line_id)
        wizard.purchase_order_ids = [Command.link(second.id)]
        self.assertEqual(
            wizard.available_purchase_line_ids, (self.order | second).order_line
        )
        # Only the pending concept is proposed, on the order just added
        self.assertEqual(wizard.concept_ids[0].purchase_line_id, self.order.order_line)
        self.assertEqual(wizard.concept_ids[1].purchase_line_id, second.order_line)
        # The quantities and lines set by the user survive adding an order
        third = self._create_order(lines=[(self.product, 1, 1422.41)])
        wizard.concept_ids[0].qty_to_invoice = 0.5
        wizard.concept_ids[1].purchase_line_id = False
        wizard.purchase_order_ids = [Command.link(third.id)]
        self.assertEqual(wizard.concept_ids[0].qty_to_invoice, 0.5)
        # The first line still has 0.5 pending, so it is preferred to the new order
        self.assertEqual(wizard.concept_ids[1].purchase_line_id, self.order.order_line)

    def test_uom_conversion(self):
        unit = self.env.ref("uom.product_uom_unit")
        dozen = self.env.ref("uom.product_uom_dozen")
        product = self._create_product("Eggs", default_code="EGG")
        product.uom_id = unit
        order = self._create_order(lines=[(product, 24, 10.0)])
        document = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000018",
            concepts=[
                {
                    "description": "Eggs",
                    "quantity": 1,
                    "price_unit": 120.0,
                    "code": "EGG",
                    "unit": "DZN",
                },
            ],
        )
        Concept = self.registry["l10n_mx_sat.purchase.invoice.wizard.concept"]
        with patch.object(Concept, "_get_uom_from_unit_code", lambda concept: dozen):
            wizard = self._open_wizard(order, document=document)
            concept = wizard.concept_ids
            self.assertEqual(concept.purchase_line_id, order.order_line)
            self.assertEqual(concept.qty_to_invoice, 12.0)
            self.assertEqual(concept._get_invoice_quantity_and_price(), (12.0, 10.0))
            self.assertFalse(wizard.total_mismatch)
            wizard.action_create_invoice()
        line = order.invoice_ids.invoice_line_ids
        self.assertEqual(
            (line.quantity, line.price_unit, line.product_uom_id), (12.0, 10.0, unit)
        )
        self.assertEqual(order.order_line.qty_invoiced, 12.0)
        # Without product_unspsc (or an unknown unit) the CFDI values are kept
        self.assertEqual(concept._get_invoice_quantity_and_price(), (1.0, 120.0))

    # ------------------------------------------------------------------
    # Bill creation
    # ------------------------------------------------------------------

    def test_create_bill(self):
        self.order.order_line.product_qty = 5
        wizard = self._open_wizard()
        self.assertFalse(wizard.total_mismatch)
        self.assertEqual(wizard.cfdi_amount_untaxed, 1422.41)
        self.assertEqual(wizard.mapped_amount_untaxed, 1422.41)
        action = wizard.action_create_invoice()
        move = self.order.invoice_ids
        self.assertEqual(len(move), 1)
        self.assertEqual(action["res_id"], move.id)
        self.assertEqual(self.document.vendor_bill_id, move)
        self.assertEqual(move.partner_id, self.vendor)
        self.assertEqual(move.ref, "A-1")
        self.assertEqual(move.invoice_origin, self.order.name)
        self.assertEqual(str(move.invoice_date), "2026-02-10")
        line = move.invoice_line_ids
        self.assertEqual(line.product_id, self.product)
        self.assertEqual(line.purchase_line_id, self.order.order_line)
        # The quantity comes from the CFDI, not from the pending quantity
        self.assertEqual(line.quantity, 1.0)
        self.assertEqual(line.price_unit, 1422.41)
        self.assertEqual(line.tax_ids, self.tax)
        self.assertEqual(move.amount_total, 1650.0)
        self.assertEqual(self.order.order_line.qty_to_invoice, 4.0)
        xml = move.attachment_ids.filtered(lambda a: a.mimetype == "application/xml")
        self.assertEqual(len(xml), 1)
        self.assertEqual(xml.raw, self.document.attachment_id.raw)
        if "l10n_mx_cfdi_uuid" in move._fields:
            self.assertEqual(move.l10n_mx_cfdi_uuid, self.document.uuid)
        if "l10n_mx_edi_invoice_document_ids" in move._fields:
            # l10n_mx_edi processed the attached XML as the received CFDI
            document = move.l10n_mx_edi_invoice_document_ids
            self.assertEqual(document.state, "invoice_received")
            self.assertEqual(document.attachment_id, xml)
        self.assertFalse(
            move.message_ids.filtered(lambda m: "differs" in (m.body or ""))
        )
        self.assertNotIn(
            self.document, self._open_wizard().l10n_mx_sat_available_document_ids
        )

    def test_create_bill_partial_two_orders(self):
        bolt = self._create_product("Bolt", default_code="BLT-01")
        nut = self._create_product("Nut", default_code="NUT-01")
        first = self._create_order(lines=[(bolt, 10, 3.0), (nut, 10, 1.0)])
        second = self._create_order(lines=[(bolt, 20, 3.0)])
        document = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000020",
            concepts=[
                {
                    "description": "Bolt",
                    "quantity": 10,
                    "price_unit": 3.0,
                    "code": "BLT-01",
                },
                {
                    "description": "Bolt",
                    "quantity": 5,
                    "price_unit": 3.0,
                    "code": "BLT-01",
                },
                {
                    "description": "Nut",
                    "quantity": 4,
                    "price_unit": 1.0,
                    "code": "NUT-01",
                    "discount": 1.0,
                },
            ],
        )
        wizard = self._open_wizard(first | second, document=document)
        concepts = wizard.concept_ids
        self.assertEqual(concepts[0].purchase_line_id, first.order_line[0])
        self.assertEqual(concepts[1].purchase_line_id, second.order_line)
        self.assertEqual(concepts[2].purchase_line_id, first.order_line[1])
        self.assertFalse(wizard.total_mismatch)
        self.assertEqual(wizard.mapped_amount_untaxed, 48.0)
        wizard.action_create_invoice()
        move = first.invoice_ids
        self.assertEqual(move, second.invoice_ids)
        self.assertEqual(move.invoice_origin, f"{first.name}, {second.name}")
        self.assertEqual(move.invoice_line_ids.mapped("quantity"), [10.0, 5.0, 4.0])
        self.assertEqual(move.invoice_line_ids[2].discount, 25.0)
        self.assertEqual(move.amount_untaxed, 48.0)
        self.assertEqual(move.amount_total, 55.68)
        self.assertEqual(first.order_line.mapped("qty_to_invoice"), [0.0, 6.0])
        self.assertEqual(second.order_line.qty_to_invoice, 15.0)
        self.assertEqual(document.vendor_bill_id, move)

    def test_unmapped_concept(self):
        document = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000021",
            concepts=[
                {"description": "Service", "quantity": 1, "price_unit": 1422.41},
                {"description": "Envío", "quantity": 1, "price_unit": 150.0},
                {"description": "Seguro", "quantity": 1, "price_unit": 50.0},
            ],
        )
        wizard = self._open_wizard(document=document)
        self.assertFalse(wizard.concept_ids[1:].purchase_line_id)
        shipping = self._create_product("Shipping")
        wizard.concept_ids[1].product_id = shipping
        wizard.action_create_invoice()
        move = self.order.invoice_ids
        lines = move.invoice_line_ids
        # The concepts without order line are billed without one
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[1].product_id, shipping)
        self.assertEqual(lines.mapped("name")[1:], ["Envío", "Seguro"])
        self.assertFalse(lines[1:].purchase_line_id)
        self.assertFalse(lines[2].product_id)
        self.assertEqual((lines[1].quantity, lines[1].price_unit), (1.0, 150.0))
        self.assertEqual(move.invoice_origin, self.order.name)

    def test_whole_document(self):
        self.order.order_line.product_qty = 2
        wizard = self._open_wizard(mode="document")
        self.assertTrue(wizard.total_mismatch)
        action = wizard.action_create_invoice()
        move = self.order.invoice_ids
        self.assertEqual(action["res_id"], move.id)
        self.assertEqual(self.document.vendor_bill_id, move)
        # Everything pending in the order is billed, whatever the CFDI says
        self.assertEqual(move.invoice_line_ids.quantity, 2.0)
        xml = move.attachment_ids.filtered(lambda a: a.mimetype == "application/xml")
        self.assertEqual(xml.raw, self.document.attachment_id.raw)

    def test_contacts_of_the_same_vendor(self):
        contact = self.env["res.partner"].create(
            {"name": "Branch", "parent_id": self.vendor.id}
        )
        orders = self.order | self._create_order(contact)
        document = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000024",
            concepts=[{"description": "Service", "quantity": 2, "price_unit": 1422.41}],
        )
        wizard = self._open_wizard(orders, document=document, mode="document")
        with self.assertRaisesRegex(UserError, "different contacts"):
            wizard.action_create_invoice()
        wizard.match_mode = "line"
        wizard.action_create_invoice()
        self.assertEqual(document.vendor_bill_id, orders.invoice_ids)
        self.assertEqual(orders.order_line.mapped("qty_invoiced"), [1.0, 1.0])

    def test_match_purchase_orders_from_document(self):
        action = self.document.action_l10n_mx_sat_match_purchase_orders()
        context = action["context"]
        self.assertEqual(context["default_purchase_order_ids"], self.order.ids)
        wizard = self.env[action["res_model"]].with_context(**context).create({})
        self.assertEqual(wizard.match_mode, "line")
        self.assertEqual(wizard.l10n_mx_sat_document_id, self.document)
        self.assertEqual(wizard.concept_ids.purchase_line_id, self.order.order_line)
        other = self._create_document("AAAAAAAA-0000-0000-0000-000000000025", OTHER_RFC)
        with self.assertRaises(UserError):
            other.action_l10n_mx_sat_match_purchase_orders()

    def test_split_concept(self):
        bolt = self._create_product("Bolt", default_code="BLT-01")
        orders = self.env["purchase.order"]
        for _number in range(3):
            orders |= self._create_order(lines=[(bolt, 10, 3.0)])
        document = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000026",
            concepts=[
                {
                    "description": "Bolt",
                    "quantity": 12,
                    "price_unit": 3.0,
                    "code": "BLT-01",
                    "discount": 6.0,
                },
            ],
        )
        wizard = self._open_wizard(orders, document=document)
        first, second = wizard.concept_ids
        # The oldest order takes what it has pending and the next one the rest
        self.assertEqual(
            wizard.concept_ids.mapped(
                lambda c: (c.purchase_line_id, c.quantity, c.qty_to_invoice)
            ),
            [(orders[0].order_line, 10.0, 10.0), (orders[1].order_line, 2.0, 2.0)],
        )
        self.assertEqual(wizard.concept_ids.mapped("amount"), [30.0, 6.0])
        self.assertEqual(wizard.concept_ids.mapped("discount_amount"), [5.0, 1.0])
        self.assertFalse(wizard.total_mismatch)
        with self.assertRaisesRegex(UserError, "Lower the quantity"):
            first.action_split()
        first.qty_to_invoice = 4
        action = first.action_split()
        self.assertEqual(action["res_id"], wizard.id)
        third = wizard.concept_ids - first - second
        self.assertEqual((first.quantity, third.quantity), (4.0, 6.0))
        self.assertFalse(third.purchase_line_id)
        third.purchase_line_id = orders[2].order_line
        self.assertFalse(wizard.total_mismatch)
        wizard.action_create_invoice()
        self.assertEqual(orders.order_line.mapped("qty_invoiced"), [4.0, 2.0, 6.0])
        self.assertEqual(document.vendor_bill_id.amount_untaxed, 30.0)

    def test_price_source_and_mismatch(self):
        self.order.order_line.price_unit = 1400.0
        wizard = self._open_wizard()
        concept = wizard.concept_ids
        self.assertEqual(concept.purchase_price_unit, 1400.0)
        self.assertTrue(concept.price_mismatch)
        self.company.l10n_mx_sat_purchase_price_tolerance = 5
        concept.invalidate_recordset(["price_mismatch"])
        self.assertFalse(concept.price_mismatch)
        self.company.l10n_mx_sat_purchase_price_source = "order"
        wizard.action_create_invoice()
        move = self.order.invoice_ids
        self.assertEqual(move.invoice_line_ids.price_unit, 1400.0)
        self.assertTrue(
            move.message_ids.filtered(lambda m: "differs" in (m.body or ""))
        )

    def test_learn_vendor_code(self):
        bolt = self._create_product("Bolt", default_code="BLT-01")
        order = self._create_order(lines=[(bolt, 10, 3.0)])
        concepts = [
            {"description": "Tornillo", "quantity": 2, "price_unit": 5.0, "code": "T-9"}
        ]
        document = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000027", concepts=concepts
        )
        wizard = self._open_wizard(order, document=document)
        self.assertFalse(wizard.concept_ids.purchase_line_id)
        wizard.concept_ids.purchase_line_id = order.order_line
        self.company.l10n_mx_sat_purchase_learn_vendor_code = False
        wizard.action_create_invoice()
        # Confirming the order added the vendor pricelist of the product
        seller = bolt.seller_ids
        self.assertFalse(seller.product_code)
        self.company.l10n_mx_sat_purchase_learn_vendor_code = True
        second = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000028", concepts=concepts
        )
        wizard = self._open_wizard(order, document=second)
        wizard.concept_ids.purchase_line_id = order.order_line
        wizard.action_create_invoice()
        self.assertEqual(seller.product_code, "T-9")
        # The next CFDI with that code is mapped alone
        third = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000029", concepts=concepts
        )
        wizard = self._open_wizard(order, document=third)
        self.assertEqual(wizard.concept_ids.purchase_line_id, order.order_line)
        # Without vendor pricelist, one is added for the code
        seller.unlink()
        wizard.action_create_invoice()
        self.assertEqual(
            bolt.seller_ids.mapped(lambda s: (s.partner_id, s.product_code, s.price)),
            [(self.vendor, "T-9", 3.0)],
        )

    def test_wizard_form(self):
        action = self.order.action_l10n_mx_sat_select_document()
        form = Form(self.env[action["res_model"]].with_context(**action["context"]))
        self.assertEqual(form.l10n_mx_sat_document_id, self.document)
        self.assertEqual(form.match_mode, "document")
        form.match_mode = "line"
        self.assertEqual(len(form.concept_ids), 1)
        wizard = form.save()
        concept = wizard.concept_ids
        # The values of the CFDI, read-only in the view, are saved
        self.assertEqual(
            (concept.description, concept.quantity, concept.price_unit, concept.amount),
            ("Service", 1.0, 1422.41, 1422.41),
        )
        self.assertEqual(concept.purchase_line_id, self.order.order_line)
        wizard.action_create_invoice()
        self.assertEqual(self.order.invoice_ids.amount_total, 1650.0)

    def test_quantity_exceeds_pending(self):
        document = self._create_document(
            "AAAAAAAA-0000-0000-0000-000000000022",
            concepts=[{"description": "Service", "quantity": 3, "price_unit": 1422.41}],
        )
        wizard = self._open_wizard(document=document)
        concept = wizard.concept_ids
        self.assertEqual(concept.purchase_line_id, self.order.order_line)
        self.assertEqual(concept.qty_to_invoice, 3.0)
        with self.assertRaisesRegex(UserError, "exceeds its pending quantity"):
            wizard.action_create_invoice()
        concept.qty_to_invoice = 0
        with self.assertRaisesRegex(UserError, "must be positive"):
            wizard.action_create_invoice()
        concept.qty_to_invoice = 1
        self.assertTrue(wizard.total_mismatch)
        wizard.action_create_invoice()
        move = self.order.invoice_ids
        self.assertEqual(move.invoice_line_ids.quantity, 1.0)
        self.assertTrue(
            move.message_ids.filtered(lambda m: "differs" in (m.body or ""))
        )

    def test_line_without_pending_quantity(self):
        second = self._create_document("AAAAAAAA-0000-0000-0000-000000000023")
        wizard = self._open_wizard(document=second)
        concept = wizard.concept_ids
        self.assertEqual(concept.purchase_line_id, self.order.order_line)
        # Meanwhile the order is billed from another CFDI
        self._open_wizard().action_create_invoice()
        self.assertEqual(self.order.order_line.qty_to_invoice, 0.0)
        self.assertFalse(wizard._get_available_lines())
        with self.assertRaisesRegex(UserError, "nothing left to bill"):
            wizard.action_create_invoice()
        self.assertEqual(concept.purchase_line_id, self.order.order_line)

    def test_total_mismatch_warning(self):
        self.order.order_line.price_unit = 1000.0
        wizard = self._open_wizard()
        self.assertFalse(wizard.total_mismatch)
        self.assertEqual(wizard.amount_total, 1160.0)
        wizard.action_create_invoice()
        move = self.order.invoice_ids
        self.assertEqual(self.document.vendor_bill_id, move)
        # The CFDI price prevails over the order price
        self.assertEqual(move.invoice_line_ids.price_unit, 1422.41)
        self.assertEqual(move.amount_total, 1650.0)

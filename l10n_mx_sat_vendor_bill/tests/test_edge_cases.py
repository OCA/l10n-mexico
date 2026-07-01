# Copyright (C) 2026 Gray Matter Logic (<https://www.graymatterlogic.com>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import EMISOR_NAME, RFC_FOREIGN, RFC_PUBLIC, VendorBillTestCommon


@tagged("post_install", "-at_install")
class TestCfdiParserEdgeCases(VendorBillTestCommon):
    """Cover edge branches of bill creation and tax helpers."""

    @mute_logger("odoo.addons.l10n_mx_sat_vendor_bill.models.account_move")
    def test_missing_timbre_skipped(self):
        move = self._create_bill(self._cfdi_xml(include_tfd=False, uuid="no-tfd-uuid"))
        self.assertFalse(move)

    @mute_logger("odoo.addons.l10n_mx_sat_vendor_bill.models.account_move")
    def test_missing_uuid_on_timbre_skipped(self):
        move = self._create_bill(
            self._cfdi_xml(uuid="ignored", tfd_uuid="", folio="2001")
        )
        self.assertFalse(move)

    @mute_logger("odoo.addons.l10n_mx_sat_vendor_bill.models.account_move")
    def test_missing_emisor_skipped(self):
        move = self._create_bill(
            self._cfdi_xml(include_emisor=False, uuid="no-emisor-1111-2222-3333-4444")
        )
        self.assertFalse(move)

    @mute_logger("odoo.addons.l10n_mx_sat_vendor_bill.models.account_move")
    def test_no_purchase_journal_skipped(self):
        journals = self.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", self.company.id)]
        )
        journals.write({"active": False})
        try:
            move = self._create_bill(
                self._cfdi_xml(uuid="no-journal-1111-2222-3333-444455556666")
            )
            self.assertFalse(move)
        finally:
            journals.write({"active": True})

    def test_foreign_partner_skips_vat_and_mx_country(self):
        # Exercise the create path (demo/base data may already have generic RFCs).
        self.env["res.partner"].search([("vat", "=", RFC_FOREIGN)]).unlink()
        move = self._create_bill(
            self._cfdi_xml(
                uuid="foreign-1111-2222-3333-444455556666",
                emisor_rfc=RFC_FOREIGN,
                emisor_nombre="PROVEEDOR EXTRANJERO",
                folio="F1",
            )
        )
        self.assertTrue(move)
        self.assertEqual(move.partner_id.name, "PROVEEDOR EXTRANJERO")
        self.assertFalse(move.partner_id.vat)
        self.assertFalse(move.partner_id.country_id)

    def test_public_partner_skips_vat_keeps_mx(self):
        # Exercise the create path (demo/base data may already have XAXX partners).
        self.env["res.partner"].search([("vat", "=", RFC_PUBLIC)]).unlink()
        move = self._create_bill(
            self._cfdi_xml(
                uuid="public-1111-2222-3333-444455556666",
                emisor_rfc=RFC_PUBLIC,
                emisor_nombre="PUBLICO EN GENERAL",
                folio="P1",
            )
        )
        self.assertTrue(move)
        self.assertEqual(move.partner_id.name, "PUBLICO EN GENERAL")
        self.assertFalse(move.partner_id.vat)
        self.assertEqual(move.partner_id.country_id, self.env.ref("base.mx"))

    def test_unknown_currency_falls_back_to_company(self):
        move = self._create_bill(
            self._cfdi_xml(
                uuid="currency-1111-2222-3333-444455556666",
                moneda="ZZZ",
                folio="C1",
            )
        )
        self.assertTrue(move)
        self.assertEqual(move.currency_id, self.company.currency_id)

    def test_invoice_date_from_emision_when_no_timbrado(self):
        move = self._create_bill(
            self._cfdi_xml(
                uuid="emision-1111-2222-3333-444455556666",
                fecha="2026-01-15T08:30:00",
                fecha_timbrado=None,
                folio="E1",
            )
        )
        self.assertTrue(move)
        self.assertEqual(str(move.invoice_date), "2026-01-15")

    def test_ref_falls_back_to_uuid_prefix(self):
        move = self._create_bill(
            self._cfdi_xml(
                uuid="abcdefgh-1111-2222-3333-444455556666",
                folio=None,
                serie=None,
            )
        )
        self.assertTrue(move)
        self.assertEqual(move.ref, "abcdefgh")

    def test_existing_partner_reused(self):
        partner = self.env["res.partner"].create(
            {
                "name": EMISOR_NAME,
                "vat": "XIA190128J61",
                "country_id": self.env.ref("base.mx").id,
            }
        )
        move = self._create_bill(
            self._cfdi_xml(uuid="reuse-1111-2222-3333-444455556666", folio="R1")
        )
        self.assertTrue(move)
        self.assertEqual(move.partner_id, partner)

    def test_discount_percent_applied(self):
        conceptos = """
        <cfdi:Concepto ClaveProdServ="01010101" Cantidad="2"
            ClaveUnidad="E48" Descripcion="Producto con descuento"
            ValorUnitario="100.00" Importe="200.00"
            Descuento="20.00" ObjetoImp="01"/>"""
        move = self._create_bill(
            self._cfdi_xml(
                uuid="discount-1111-2222-3333-444455556666",
                folio="D1",
                conceptos=conceptos,
            )
        )
        self.assertTrue(move)
        line = move.invoice_line_ids.filtered(
            lambda rec: rec.display_type == "product"
        )[0]
        self.assertAlmostEqual(line.discount, 10.0)
        self.assertAlmostEqual(line.quantity, 2.0)
        self.assertAlmostEqual(line.price_unit, 100.0)

    def test_concepto_without_clave_uses_description_only(self):
        conceptos = """
        <cfdi:Concepto Cantidad="1" ClaveUnidad="E48"
            Descripcion="Sin clave" ValorUnitario="50.00"
            Importe="50.00" ObjetoImp="01"/>"""
        move = self._create_bill(
            self._cfdi_xml(
                uuid="noclave-1111-2222-3333-444455556666",
                folio="N1",
                conceptos=conceptos,
            )
        )
        line = move.invoice_line_ids.filtered(
            lambda rec: rec.display_type == "product"
        )[0]
        self.assertEqual(line.name, "Sin clave")

    @mute_logger("odoo.addons.l10n_mx_sat_vendor_bill.models.account_move")
    def test_invalid_concepto_numbers_skipped(self):
        conceptos = """
        <cfdi:Concepto ClaveProdServ="01010101" Cantidad="abc"
            ClaveUnidad="E48" Descripcion="Invalid nums"
            ValorUnitario="x" Importe="y" ObjetoImp="01"/>"""
        move = self._create_bill(
            self._cfdi_xml(
                uuid="badnums-1111-2222-3333-444455556666",
                folio="B1",
                conceptos=conceptos,
            )
        )
        self.assertTrue(move)
        product_lines = move.invoice_line_ids.filtered(
            lambda rec: rec.display_type == "product" and rec.name
        )
        self.assertFalse(product_lines)

    def test_attachment_and_request_linked(self):
        uuid = "attach-1111-2222-3333-444455556666"
        xml_bytes = self._cfdi_xml(uuid=uuid, folio="A1")
        move = self._create_bill(xml_bytes)
        self.assertEqual(move.l10n_mx_sat_download_request_id, self.request)
        attachment = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "account.move"),
                ("res_id", "=", move.id),
                ("name", "=", f"{uuid}.xml"),
            ],
            limit=1,
        )
        self.assertTrue(attachment)
        self.assertEqual(attachment.raw, xml_bytes)

    def test_tax_without_rate_not_exento_skipped(self):
        move, line = self._draft_bill_line()
        node = self._tax_node(Impuesto="002", TipoFactor="Tasa")
        tax = move._l10n_mx_sat_get_tax_from_cfdi_node(node, line)
        self.assertFalse(tax)

    @mute_logger("odoo.addons.l10n_mx_sat_vendor_bill.models.account_move")
    def test_tax_invalid_rate_skipped(self):
        move, line = self._draft_bill_line()
        node = self._tax_node(
            Impuesto="002", TipoFactor="Tasa", TasaOCuota="not-a-number"
        )
        tax = move._l10n_mx_sat_get_tax_from_cfdi_node(node, line)
        self.assertFalse(tax)

    def test_tax_exento_matched(self):
        move, line = self._draft_bill_line()
        TaxGroup = self.env["account.tax.group"]
        tax_group = self.env.ref(
            f"account.{self.company.id}_tax_group_exe_0",
            raise_if_not_found=False,
        )
        if not tax_group:
            tax_group = TaxGroup.create(
                {
                    "name": "Exe 0",
                    "company_id": self.company.id,
                }
            )
            self.env["ir.model.data"].create(
                {
                    "name": f"{self.company.id}_tax_group_exe_0",
                    "module": "account",
                    "model": "account.tax.group",
                    "res_id": tax_group.id,
                    "noupdate": True,
                }
            )
        Tax = self.env["account.tax"]
        domain = [
            *Tax._check_company_domain(self.company),
            ("amount", "=", 0.0),
            ("type_tax_use", "=", "purchase"),
            ("amount_type", "=", "percent"),
            ("tax_group_id", "=", tax_group.id),
        ]
        if "l10n_mx_tax_type" in Tax._fields:
            domain.append(("l10n_mx_tax_type", "=", "iva"))
        tax = Tax.search(domain, limit=1)
        if not tax:
            vals = {
                "name": "IVA Exento purchase",
                "amount": 0.0,
                "amount_type": "percent",
                "type_tax_use": "purchase",
                "company_id": self.company.id,
                "tax_group_id": tax_group.id,
            }
            if "l10n_mx_tax_type" in Tax._fields:
                vals["l10n_mx_tax_type"] = "iva"
            tax = Tax.create(vals)
        node = self._tax_node(Impuesto="002", TipoFactor="Exento")
        matched = move._l10n_mx_sat_get_tax_from_cfdi_node(node, line)
        self.assertEqual(matched, tax)

    def test_traslado_tax_appended_to_line(self):
        expected = self._ensure_purchase_tax(16.0, tax_type="iva", name="IVA 16 purch")
        conceptos = """
        <cfdi:Concepto ClaveProdServ="01010101" Cantidad="1"
            ClaveUnidad="E48" Descripcion="Con IVA"
            ValorUnitario="100.00" Importe="100.00" ObjetoImp="02">
            <cfdi:Impuestos>
                <cfdi:Traslados>
                    <cfdi:Traslado Base="100.00" Impuesto="002"
                        TipoFactor="Tasa" TasaOCuota="0.160000"
                        Importe="16.00"/>
                </cfdi:Traslados>
            </cfdi:Impuestos>
        </cfdi:Concepto>"""
        move = self._create_bill(
            self._cfdi_xml(
                uuid="iva-line-1111-2222-3333-444455556666",
                folio="IVA1",
                conceptos=conceptos,
            )
        )
        line = move.invoice_line_ids.filtered(
            lambda rec: rec.display_type == "product"
        )[0]
        self.assertIn(expected, line.tax_ids)

    def test_tax_unknown_code_skips_tax_type_filter(self):
        move, line = self._draft_bill_line()
        expected = self._ensure_purchase_tax(
            16.0, tax_type=False, name="Purchase 16 no type"
        )
        node = self._tax_node(Impuesto="999", TipoFactor="Tasa", TasaOCuota="0.160000")
        matched = move._l10n_mx_sat_get_tax_from_cfdi_node(node, line)
        self.assertEqual(matched, expected)

    def test_invoice_date_false_when_dates_absent(self):
        move = self._create_bill(
            self._cfdi_xml(
                uuid="nodate-1111-2222-3333-444455556666",
                folio="ND1",
                fecha="",
                fecha_timbrado=None,
            )
        )
        self.assertTrue(move)
        self.assertFalse(move.invoice_date)

    def test_retencion_not_found_still_keeps_traslado(self):
        iva = self._ensure_purchase_tax(16.0, tax_type="iva", name="IVA 16 keep")
        conceptos = """
        <cfdi:Concepto ClaveProdServ="01010101" Cantidad="1"
            ClaveUnidad="E48" Descripcion="IVA y retencion faltante"
            ValorUnitario="100.00" Importe="100.00" ObjetoImp="02">
            <cfdi:Impuestos>
                <cfdi:Traslados>
                    <cfdi:Traslado Base="100.00" Impuesto="002"
                        TipoFactor="Tasa" TasaOCuota="0.160000"
                        Importe="16.00"/>
                </cfdi:Traslados>
                <cfdi:Retenciones>
                    <cfdi:Retencion Base="100.00" Impuesto="001"
                        TipoFactor="Tasa" TasaOCuota="0.990000"
                        Importe="99.00"/>
                </cfdi:Retenciones>
            </cfdi:Impuestos>
        </cfdi:Concepto>"""
        move = self._create_bill(
            self._cfdi_xml(
                uuid="mix-tax-1111-2222-3333-444455556666",
                folio="MIX1",
                conceptos=conceptos,
            )
        )
        line = move.invoice_line_ids.filtered(
            lambda rec: rec.display_type == "product"
        )[0]
        self.assertIn(iva, line.tax_ids)

    def test_tax_withholding_matched(self):
        move, line = self._draft_bill_line()
        rate = "0.106667"
        amount = float(rate) * -100
        expected = self._ensure_purchase_tax(amount, tax_type="isr", name="ISR Ret")
        node = self._tax_node(
            tag="Retencion",
            Impuesto="001",
            TipoFactor="Tasa",
            TasaOCuota=rate,
        )
        matched = move._l10n_mx_sat_get_tax_from_cfdi_node(
            node, line, is_withholding=True
        )
        self.assertEqual(matched, expected)

    def test_tax_not_found_posts_message(self):
        move, line = self._draft_bill_line()
        node = self._tax_node(Impuesto="002", TipoFactor="Tasa", TasaOCuota="0.990000")
        matched = move._l10n_mx_sat_get_tax_from_cfdi_node(node, line)
        self.assertFalse(matched)
        self.assertTrue(
            any("Could not find" in (msg.body or "") for msg in move.message_ids)
        )

    def test_withholding_tax_not_found_posts_message(self):
        move, line = self._draft_bill_line()
        node = self._tax_node(
            tag="Retencion",
            Impuesto="001",
            TipoFactor="Tasa",
            TasaOCuota="0.990000",
        )
        matched = move._l10n_mx_sat_get_tax_from_cfdi_node(
            node, line, is_withholding=True
        )
        self.assertFalse(matched)
        self.assertTrue(
            any("withholding" in (msg.body or "").lower() for msg in move.message_ids)
        )

    def test_fill_line_applies_withholding_tax(self):
        rate = "0.106667"
        amount = float(rate) * -100
        expected = self._ensure_purchase_tax(amount, tax_type="isr", name="ISR Ret2")
        conceptos = f"""
        <cfdi:Concepto ClaveProdServ="01010101" Cantidad="1"
            ClaveUnidad="E48" Descripcion="Con retencion"
            ValorUnitario="1000.00" Importe="1000.00" ObjetoImp="02">
            <cfdi:Impuestos>
                <cfdi:Retenciones>
                    <cfdi:Retencion Base="1000.00" Impuesto="001"
                        TipoFactor="Tasa" TasaOCuota="{rate}"
                        Importe="106.67"/>
                </cfdi:Retenciones>
            </cfdi:Impuestos>
        </cfdi:Concepto>"""
        move = self._create_bill(
            self._cfdi_xml(
                uuid="retencion-1111-2222-3333-444455556666",
                folio="RET1",
                conceptos=conceptos,
            )
        )
        line = move.invoice_line_ids.filtered(
            lambda rec: rec.display_type == "product"
        )[0]
        self.assertIn(expected, line.tax_ids)

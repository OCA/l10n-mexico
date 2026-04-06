# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

# Fictitious RFCs and data — never use real taxpayer information in tests.
RECEPTOR_RFC = "EKU9003173C9"  # SAT's official test RFC
EMISOR_RFC = "XIA190128J61"  # Fictitious
EMISOR_NAME = "SOLUCIONES DEMO SA DE CV"


@tagged("post_install", "-at_install")
class TestCfdiParser(TransactionCase):
    """Test CFDI XML parsing and bill creation logic."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("base.main_company")
        cls.company.write(
            {
                "vat": RECEPTOR_RFC,
                "country_id": cls.env.ref("base.mx").id,
            }
        )
        # Ensure purchase journal exists
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "purchase"), ("company_id", "=", cls.company.id)],
            limit=1,
        )
        if not cls.journal:
            cls.journal = cls.env["account.journal"].create(
                {
                    "name": "Vendor Bills",
                    "code": "BILL",
                    "type": "purchase",
                    "company_id": cls.company.id,
                }
            )
        # Create a mock download request
        cls.request = cls.env["l10n_mx_sat.download.request"].create(
            {
                "company_id": cls.company.id,
                "fecha_inicial": "2026-02-01 00:00:00",
                "fecha_final": "2026-02-28 23:59:59",
                "state": "downloading",
            }
        )

    def _get_iva_16_xml(self):
        """Return a sample CFDI XML with IVA 16%."""
        return b"""<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    Version="4.0" Folio="1001"
    Fecha="2026-02-26T16:57:09"
    FormaPago="04" SubTotal="1422.41" Descuento="0.00"
    Moneda="MXN" Total="1650.00" TipoDeComprobante="I"
    MetodoPago="PUE" Exportacion="01" LugarExpedicion="06600">
    <cfdi:Emisor Rfc="XIA190128J61"
        Nombre="SOLUCIONES DEMO SA DE CV" RegimenFiscal="601"/>
    <cfdi:Receptor Rfc="EKU9003173C9"
        Nombre="ESCUELA KEMPER URGATE"
        DomicilioFiscalReceptor="06600"
        RegimenFiscalReceptor="603" UsoCFDI="G03"/>
    <cfdi:Conceptos>
        <cfdi:Concepto ClaveProdServ="43232400" Cantidad="1"
            ClaveUnidad="E48" Unidad="Unidad de servicio"
            Descripcion="Servicio de consultoria mensual"
            ValorUnitario="1422.41" Importe="1422.41"
            Descuento="0.00" ObjetoImp="02">
            <cfdi:Impuestos>
                <cfdi:Traslados>
                    <cfdi:Traslado Base="1422.41" Impuesto="002"
                        TipoFactor="Tasa" TasaOCuota="0.160000"
                        Importe="227.59"/>
                </cfdi:Traslados>
            </cfdi:Impuestos>
        </cfdi:Concepto>
    </cfdi:Conceptos>
    <cfdi:Complemento>
        <tfd:TimbreFiscalDigital
            xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
            Version="1.1"
            UUID="aabbccdd-1111-2222-3333-444455556666"
            FechaTimbrado="2026-02-26T16:57:10"
            RfcProvCertif="SPR190613I52"/>
    </cfdi:Complemento>
</cfdi:Comprobante>"""

    def _get_no_tax_xml(self):
        """Return a sample CFDI XML without taxes (ObjetoImp=01)."""
        return b"""<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    Version="4.0" Serie="I" Folio="7"
    Fecha="2026-02-05T15:29:03"
    FormaPago="03" SubTotal="500.00" Descuento="0"
    Moneda="MXN" Total="500.00" TipoDeComprobante="I"
    MetodoPago="PUE" Exportacion="01" LugarExpedicion="06600">
    <cfdi:Emisor Rfc="URE180429TM6"
        Nombre="UNIVERSIDAD ROBOTICA ESPANOLA"
        RegimenFiscal="601"/>
    <cfdi:Receptor Rfc="EKU9003173C9"
        Nombre="ESCUELA KEMPER URGATE" UsoCFDI="G03"
        DomicilioFiscalReceptor="06600"
        RegimenFiscalReceptor="603"/>
    <cfdi:Conceptos>
        <cfdi:Concepto ClaveProdServ="01010101" Cantidad="1"
            ClaveUnidad="E48"
            Descripcion="Servicio de membresia anual"
            ValorUnitario="500.0" Importe="500.0"
            Descuento="0.0" ObjetoImp="01"/>
    </cfdi:Conceptos>
    <cfdi:Complemento>
        <tfd:TimbreFiscalDigital
            xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
            Version="1.1"
            UUID="eeff0011-aabb-ccdd-eeff-001122334455"
            FechaTimbrado="2026-02-05T15:29:03"/>
    </cfdi:Complemento>
</cfdi:Comprobante>"""

    def _get_credit_note_xml(self):
        """Return a sample CFDI XML with TipoDeComprobante=E (credit note)."""
        return b"""<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    Version="4.0" Folio="100"
    Fecha="2026-03-01T10:00:00"
    FormaPago="03" SubTotal="100.00"
    Moneda="MXN" Total="116.00" TipoDeComprobante="E"
    MetodoPago="PUE" LugarExpedicion="06600">
    <cfdi:Emisor Rfc="XIA190128J61"
        Nombre="SOLUCIONES DEMO SA DE CV" RegimenFiscal="601"/>
    <cfdi:Receptor Rfc="EKU9003173C9"
        Nombre="ESCUELA KEMPER URGATE" UsoCFDI="G03"
        DomicilioFiscalReceptor="06600"
        RegimenFiscalReceptor="603"/>
    <cfdi:Conceptos>
        <cfdi:Concepto ClaveProdServ="43232400" Cantidad="1"
            ClaveUnidad="E48" Descripcion="Nota de credito"
            ValorUnitario="100.00" Importe="100.00" ObjetoImp="02">
            <cfdi:Impuestos>
                <cfdi:Traslados>
                    <cfdi:Traslado Base="100.00" Impuesto="002"
                        TipoFactor="Tasa" TasaOCuota="0.160000"
                        Importe="16.00"/>
                </cfdi:Traslados>
            </cfdi:Impuestos>
        </cfdi:Concepto>
    </cfdi:Conceptos>
    <cfdi:Complemento>
        <tfd:TimbreFiscalDigital
            xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
            Version="1.1"
            UUID="cc111111-2222-3333-4444-555555555555"
            FechaTimbrado="2026-03-01T10:00:01"/>
    </cfdi:Complemento>
</cfdi:Comprobante>"""

    def _get_payment_xml(self):
        """Return a sample CFDI with TipoDeComprobante=P (payment)."""
        return b"""<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    Version="4.0" Fecha="2026-03-01T10:00:00"
    SubTotal="0" Total="0" TipoDeComprobante="P"
    Moneda="XXX" LugarExpedicion="06600">
    <cfdi:Emisor Rfc="XIA190128J61" Nombre="SOLUCIONES DEMO SA DE CV"
        RegimenFiscal="601"/>
    <cfdi:Receptor Rfc="EKU9003173C9" Nombre="ESCUELA KEMPER URGATE"
        UsoCFDI="CP01" DomicilioFiscalReceptor="06600"
        RegimenFiscalReceptor="603"/>
    <cfdi:Conceptos>
        <cfdi:Concepto ClaveProdServ="84111506" Cantidad="1"
            ClaveUnidad="ACT" Descripcion="Pago"
            ValorUnitario="0" Importe="0" ObjetoImp="01"/>
    </cfdi:Conceptos>
    <cfdi:Complemento>
        <tfd:TimbreFiscalDigital
            xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
            Version="1.1"
            UUID="dd111111-2222-3333-4444-555555555555"
            FechaTimbrado="2026-03-01T10:00:01"/>
    </cfdi:Complemento>
</cfdi:Comprobante>"""

    def test_iva_16_creates_bill(self):
        """Test that a CFDI with IVA 16% creates a vendor bill."""
        from lxml import etree

        xml_bytes = self._get_iva_16_xml()
        tree = etree.fromstring(xml_bytes)

        move = self.env["account.move"]._l10n_mx_sat_create_bill_from_cfdi(
            tree, xml_bytes, self.request
        )

        self.assertTrue(move, "Should create a vendor bill")
        self.assertEqual(move.move_type, "in_invoice")
        self.assertEqual(
            move.l10n_mx_cfdi_uuid,
            "aabbccdd-1111-2222-3333-444455556666",
        )
        self.assertEqual(move.ref, "1001")
        self.assertTrue(move.partner_id, "Should have a partner")
        self.assertEqual(move.partner_id.vat, EMISOR_RFC)
        self.assertEqual(str(move.invoice_date), "2026-02-26")
        self.assertTrue(len(move.invoice_line_ids) >= 1)

        # Check line
        line = move.invoice_line_ids.filtered(lambda rec: rec.display_type == "product")
        self.assertTrue(line, "Should have at least one product line")
        line = line[0]
        self.assertIn("43232400", line.name)
        self.assertIn("Servicio de consultoria mensual", line.name)
        self.assertAlmostEqual(line.price_unit, 1422.41)
        self.assertEqual(line.quantity, 1.0)

    def test_no_tax_creates_bill(self):
        """Test that a CFDI without taxes creates a bill correctly."""
        from lxml import etree

        xml_bytes = self._get_no_tax_xml()
        tree = etree.fromstring(xml_bytes)

        move = self.env["account.move"]._l10n_mx_sat_create_bill_from_cfdi(
            tree, xml_bytes, self.request
        )

        self.assertTrue(move)
        self.assertEqual(move.move_type, "in_invoice")
        self.assertEqual(
            move.l10n_mx_cfdi_uuid,
            "eeff0011-aabb-ccdd-eeff-001122334455",
        )
        # Serie + Folio
        self.assertEqual(move.ref, "I-7")

    def test_credit_note_creates_refund(self):
        """TipoDeComprobante=E should create in_refund."""
        from lxml import etree

        xml_bytes = self._get_credit_note_xml()
        tree = etree.fromstring(xml_bytes)

        move = self.env["account.move"]._l10n_mx_sat_create_bill_from_cfdi(
            tree, xml_bytes, self.request
        )

        self.assertTrue(move)
        self.assertEqual(move.move_type, "in_refund")

    def test_payment_skipped(self):
        """TipoDeComprobante=P should be skipped."""
        from lxml import etree

        xml_bytes = self._get_payment_xml()
        tree = etree.fromstring(xml_bytes)

        move = self.env["account.move"]._l10n_mx_sat_create_bill_from_cfdi(
            tree, xml_bytes, self.request
        )

        self.assertFalse(move, "Payment CFDIs should be skipped")

    def test_duplicate_uuid_skipped(self):
        """Duplicate UUID should not create a second bill."""
        from lxml import etree

        xml_bytes = self._get_iva_16_xml()
        tree = etree.fromstring(xml_bytes)

        # First import
        move1 = self.env["account.move"]._l10n_mx_sat_create_bill_from_cfdi(
            tree, xml_bytes, self.request
        )
        self.assertTrue(move1)

        # Second import with same UUID
        tree2 = etree.fromstring(xml_bytes)
        move2 = self.env["account.move"]._l10n_mx_sat_create_bill_from_cfdi(
            tree2, xml_bytes, self.request
        )
        self.assertFalse(move2, "Duplicate UUID should be skipped")

    def test_serie_absent_uses_folio_only(self):
        """When Serie is absent, ref should be just the Folio."""
        from lxml import etree

        xml_bytes = self._get_iva_16_xml()
        tree = etree.fromstring(xml_bytes)

        move = self.env["account.move"]._l10n_mx_sat_create_bill_from_cfdi(
            tree, xml_bytes, self.request
        )

        # The IVA 16 XML has no Serie, only Folio="1001"
        self.assertEqual(move.ref, "1001")

    def test_partner_auto_created(self):
        """Partner should be auto-created if not found by RFC."""
        from lxml import etree

        # Ensure no partner with this RFC exists
        self.env["res.partner"].search([("vat", "=", EMISOR_RFC)]).unlink()

        xml_bytes = self._get_iva_16_xml()
        tree = etree.fromstring(xml_bytes)

        move = self.env["account.move"]._l10n_mx_sat_create_bill_from_cfdi(
            tree, xml_bytes, self.request
        )

        self.assertTrue(move.partner_id)
        self.assertEqual(move.partner_id.vat, EMISOR_RFC)
        self.assertEqual(move.partner_id.name, EMISOR_NAME)
        self.assertEqual(move.partner_id.country_id, self.env.ref("base.mx"))

    def test_product_not_created(self):
        """Products should NOT be auto-created. Lines should have no product."""
        from lxml import etree

        xml_bytes = self._get_iva_16_xml()
        tree = etree.fromstring(xml_bytes)

        move = self.env["account.move"]._l10n_mx_sat_create_bill_from_cfdi(
            tree, xml_bytes, self.request
        )

        product_lines = move.invoice_line_ids.filtered(
            lambda rec: rec.display_type == "product"
        )
        for line in product_lines:
            self.assertFalse(
                line.product_id, "Product should NOT be set on imported lines"
            )

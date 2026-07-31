from datetime import datetime
from types import SimpleNamespace

from odoo.tests.common import TransactionCase

from odoo.addons.l10n_mx_cfdi.services import cfdi_builder


class TestCFDIBuilder(TransactionCase):
    def test_tax_code_from_name_mapping(self):
        self.assertEqual(cfdi_builder.tax_code_from_name("ISR"), "001")
        self.assertEqual(cfdi_builder.tax_code_from_name("IVA"), "002")
        self.assertEqual(cfdi_builder.tax_code_from_name("IEPS"), "003")
        self.assertEqual(cfdi_builder.tax_code_from_name("OTHER"), "OTHER")
        self.assertEqual(cfdi_builder.tax_code_from_name(None), "002")

    def test_build_concepto_impuestos_empty(self):
        self.assertIsNone(cfdi_builder.build_concepto_impuestos(None))
        self.assertIsNone(cfdi_builder.build_concepto_impuestos([]))

    def test_build_concepto_impuestos_traslado_and_retencion(self):
        taxes = [
            {
                "Name": "IVA",
                "Rate": 0.16,
                "Base": 100,
                "Total": 16,
                "IsRetention": False,
            },
            {
                "Name": "ISR",
                "Rate": 0.1,
                "Base": 100,
                "Total": 10,
                "IsRetention": True,
            },
        ]
        impuestos = cfdi_builder.build_concepto_impuestos(taxes)
        self.assertIsNotNone(impuestos)
        traslados = impuestos.get("Traslados") if hasattr(impuestos, "get") else None
        retenciones = (
            impuestos.get("Retenciones") if hasattr(impuestos, "get") else None
        )
        if traslados is None:
            traslados = getattr(impuestos, "traslados", None)
        if retenciones is None:
            retenciones = getattr(impuestos, "retenciones", None)
        self.assertTrue(traslados)
        self.assertTrue(retenciones)

    def test_build_concepto_impuestos_getattr_fallback(self):
        """Exercise getattr fallback when impuestos has no mapping API."""
        taxes = [
            {
                "Name": "IVA",
                "Rate": 0.16,
                "Base": 100,
                "Total": 16,
                "IsRetention": False,
            },
            {
                "Name": "ISR",
                "Rate": 0.1,
                "Base": 100,
                "Total": 10,
                "IsRetention": True,
            },
        ]
        impuestos = cfdi_builder.build_concepto_impuestos(taxes)
        # Simulate a non-mapping object that only exposes attributes.
        attr_only = SimpleNamespace(
            traslados=getattr(impuestos, "traslados", None)
            or (impuestos.get("Traslados") if hasattr(impuestos, "get") else None),
            retenciones=getattr(impuestos, "retenciones", None)
            or (impuestos.get("Retenciones") if hasattr(impuestos, "get") else None),
        )
        traslados = attr_only.get("Traslados") if hasattr(attr_only, "get") else None
        retenciones = (
            attr_only.get("Retenciones") if hasattr(attr_only, "get") else None
        )
        if traslados is None:
            traslados = getattr(attr_only, "traslados", None)
        if retenciones is None:
            retenciones = getattr(attr_only, "retenciones", None)
        self.assertTrue(traslados)
        self.assertTrue(retenciones)

    def test_build_concepto_impuestos_tasa_o_cuota_six_decimals(self):
        """SAT/SW reject TasaOCuota='0.16'; must emit 0.160000 (Cristhian)."""
        from decimal import Decimal

        impuestos = cfdi_builder.build_concepto_impuestos(
            [
                {
                    "Name": "IVA",
                    "Rate": 0.16,
                    "Base": 100,
                    "Total": 16,
                    "IsRetention": False,
                }
            ]
        )
        traslado = impuestos.get("Traslados")[0]
        tasa = traslado.get("TasaOCuota")
        self.assertEqual(tasa, Decimal("0.160000"))
        self.assertEqual(format(tasa, "f"), "0.160000")

        # XML serialization must keep six decimals (satcfdi preserves Decimal).
        issuer = SimpleNamespace(
            vat="EKU9003173C9",
            fiscal_name="ESCUELA KEMPER URGATE",
            name="Issuer",
            tax_regime=SimpleNamespace(code="601"),
        )
        cfdi = cfdi_builder.build_comprobante(
            issuer=issuer,
            receiver={
                "Rfc": "XAXX010101000",
                "Name": "PUBLICO EN GENERAL",
                "TaxZipCode": "42501",
                "FiscalRegime": "616",
                "CfdiUse": "S01",
            },
            conceptos=[
                {
                    "ProductCode": "01010101",
                    "Quantity": 1,
                    "UnitCode": "H87",
                    "Description": "Demo",
                    "UnitPrice": 100,
                    "TaxObject": "02",
                    "Taxes": [
                        {
                            "Name": "IVA",
                            "Rate": 0.16,
                            "Base": 100,
                            "Total": 16,
                        }
                    ],
                }
            ],
            tipo_de_comprobante="I",
            lugar_expedicion="42501",
            forma_pago="03",
            metodo_pago="PUE",
            fecha="2026-07-27T16:23:00",
            informacion_global={
                "Periodicity": "01",
                "Months": "07",
                "Year": 2026,
            },
        )
        xml = cfdi.xml_bytes().decode()
        self.assertIn('TasaOCuota="0.160000"', xml)
        self.assertNotIn('TasaOCuota="0.16"', xml)
        self.assertIn('Nombre="PUBLICO EN GENERAL"', xml)
        self.assertIn('Nombre="ESCUELA KEMPER URGATE"', xml)
        self.assertIn("InformacionGlobal", xml)

    def test_build_concepto_from_item_optional_fields(self):
        item = {
            "ProductCode": "01010101",
            "Quantity": 1,
            "UnitCode": "H87",
            "Description": "Widget",
            "UnitPrice": 100,
            "TaxObject": "02",
            "IdentificationNumber": "SKU-1",
            "Discount": 5,
            "NumerosPedimento": ["19  48  3807  0001234"],
            "Taxes": [
                {
                    "Name": "IVA",
                    "Rate": 0.16,
                    "Base": 95,
                    "Total": 15.2,
                }
            ],
        }
        concepto = cfdi_builder.build_concepto_from_item(item)
        self.assertEqual(concepto.get("NoIdentificacion"), "SKU-1")
        self.assertTrue(concepto.get("Descuento"))
        self.assertTrue(concepto.get("InformacionAduanera"))
        self.assertTrue(concepto.get("Impuestos"))

    def test_build_concepto_from_item_without_taxes(self):
        item = {
            "ProductCode": "01010101",
            "Quantity": 1,
            "UnitCode": "H87",
            "Description": "Widget",
            "UnitPrice": 10,
        }
        concepto = cfdi_builder.build_concepto_from_item(item)
        self.assertFalse(concepto.get("Impuestos"))

    def test_parse_fecha_formats(self):
        self.assertIsNone(cfdi_builder._parse_fecha(None))
        now = datetime(2024, 1, 1, 12, 0, 0)
        self.assertEqual(cfdi_builder._parse_fecha(now), now)
        self.assertEqual(
            cfdi_builder._parse_fecha("2024-01-01T12:00:00"),
            datetime(2024, 1, 1, 12, 0, 0),
        )
        self.assertEqual(
            cfdi_builder._parse_fecha("2024-01-01 12:00:00"),
            datetime(2024, 1, 1, 12, 0, 0),
        )
        self.assertEqual(
            cfdi_builder._parse_fecha("2024-01-01"),
            datetime(2024, 1, 1),
        )
        self.assertIsNone(cfdi_builder._parse_fecha("not-a-date"))

    def test_build_informacion_global_none(self):
        self.assertIsNone(cfdi_builder.build_informacion_global(None))
        self.assertIsNone(cfdi_builder.build_informacion_global({}))

    def test_build_comprobante_emisor_receptor(self):
        issuer = SimpleNamespace(
            vat="EKU9003173C9",
            fiscal_name="Issuer SA",
            name="Issuer",
            tax_regime=SimpleNamespace(code="601"),
        )
        receiver = {
            "Rfc": "XAXX010101000",
            "Name": "Publico",
            "TaxZipCode": "06000",
            "FiscalRegime": "616",
            "CfdiUse": "S01",
        }
        conceptos = [
            {
                "ProductCode": "01010101",
                "Quantity": 1,
                "UnitCode": "H87",
                "Description": "Item",
                "UnitPrice": 100,
            }
        ]
        cfdi = cfdi_builder.build_comprobante(
            issuer=issuer,
            receiver=receiver,
            conceptos=conceptos,
            tipo_de_comprobante="I",
            lugar_expedicion="06000",
            forma_pago="03",
            metodo_pago="PUE",
            fecha="2024-01-01T12:00:00",
            informacion_global={
                "Periodicity": "01",
                "Months": "01",
                "Year": 2024,
            },
        )
        self.assertEqual(cfdi.get("Emisor").get("Rfc"), "EKU9003173C9")
        self.assertEqual(cfdi.get("Receptor").get("Rfc"), "XAXX010101000")
        self.assertEqual(cfdi.get("TipoDeComprobante"), "I")
        self.assertTrue(cfdi.get("InformacionGlobal"))
        self.assertEqual(cfdi.get("Exportacion"), "01")

    def test_build_comprobante_omits_exportacion_when_none(self):
        issuer = SimpleNamespace(
            vat="EKU9003173C9",
            fiscal_name="Issuer SA",
            name="Issuer",
            tax_regime=SimpleNamespace(code="601"),
        )
        receiver = {
            "Rfc": "XAXX010101000",
            "Name": "Publico",
            "TaxZipCode": "06000",
            "FiscalRegime": "616",
            "CfdiUse": "CP01",
        }
        conceptos = [
            {
                "ProductCode": "84111506",
                "Quantity": 1,
                "UnitCode": "ACT",
                "Description": "Pago",
                "UnitPrice": 0,
            }
        ]
        cfdi = cfdi_builder.build_comprobante(
            issuer=issuer,
            receiver=receiver,
            conceptos=conceptos,
            tipo_de_comprobante="P",
            lugar_expedicion="06000",
            moneda="XXX",
            exportacion=None,
        )
        self.assertFalse(cfdi.get("Exportacion"))

    def test_dec_none_is_zero(self):
        self.assertEqual(str(cfdi_builder._dec(None)), "0")
        self.assertEqual(str(cfdi_builder._dec(1.5)), "1.5")

    def test_build_concepto_skips_zero_discount(self):
        concepto = cfdi_builder.build_concepto_from_item(
            {
                "ProductCode": "01010101",
                "Quantity": 1,
                "UnitCode": "H87",
                "Description": "",
                "UnitPrice": 100,
                "Discount": 0,
            }
        )
        self.assertFalse(concepto.get("Descuento"))
        self.assertEqual(concepto.get("ObjetoImp") or concepto.get("objeto_imp"), "01")

    def test_build_concepto_with_pedimentos(self):
        concepto = cfdi_builder.build_concepto_from_item(
            {
                "ProductCode": "01010101",
                "Quantity": 1,
                "UnitCode": "H87",
                "Description": "Item",
                "UnitPrice": 100,
                "NumerosPedimento": ["12  34  5678  9012345"],
            }
        )
        self.assertTrue(
            concepto.get("InformacionAduanera") or concepto.get("informacion_aduanera")
        )

    def test_build_concepto_discount_string_zero(self):
        concepto = cfdi_builder.build_concepto_from_item(
            {
                "ProductCode": "01010101",
                "Quantity": 1,
                "UnitCode": "H87",
                "Description": "x",
                "UnitPrice": 10,
                "Discount": "0",
            }
        )
        self.assertFalse(concepto.get("Descuento"))

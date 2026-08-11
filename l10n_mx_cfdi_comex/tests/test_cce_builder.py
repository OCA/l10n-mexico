# Copyright (C) 2026 Open Source Integrators
# License GPL-3.0 or later (http://www.gnu.org/licenses/gpl).

from decimal import Decimal

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_mx_cfdi_comex.services import cce_builder


@tagged("post_install", "-at_install")
class TestCceBuilder(TransactionCase):
    def test_build_comercio_exterior_structure(self):
        cce = cce_builder.build_comercio_exterior(
            {
                "ClaveDePedimento": "A1",
                "CertificadoOrigen": 0,
                "TipoCambioUSD": "17.123456",
                "TotalUSD": "100.00",
                "Incoterm": "FOB",
                "Observaciones": "Export sample",
                "Emisor": {
                    "Domicilio": {
                        "Calle": "Av Reforma",
                        "NumeroExterior": "100",
                        "Estado": "CMX",
                        "Pais": "MEX",
                        "CodigoPostal": "06600",
                    }
                },
                "Receptor": {
                    "NumRegIdTrib": "123456789",
                    "Domicilio": {
                        "Calle": "Main St",
                        "NumeroExterior": "10",
                        "Estado": "CA",
                        "Pais": "USA",
                        "CodigoPostal": "90210",
                    },
                },
                "Destinatario": {
                    "Nombre": "Warehouse LLC",
                    "Domicilio": {
                        "Calle": "Dock Rd",
                        "Estado": "TX",
                        "Pais": "USA",
                        "CodigoPostal": "75001",
                    },
                },
                "Mercancias": [
                    {
                        "NoIdentificacion": "SKU-1",
                        "ValorDolares": "100.00",
                        "FraccionArancelaria": "96091001",
                        "CantidadAduana": "1",
                        "UnidadAduana": "01",
                        "ValorUnitarioAduana": "100.000000",
                    }
                ],
            }
        )
        self.assertEqual(cce.get("Version"), "2.0")
        self.assertEqual(cce.get("ClaveDePedimento"), "A1")
        self.assertEqual(cce.get("CertificadoOrigen"), 0)
        self.assertEqual(cce.get("Incoterm"), "FOB")
        self.assertEqual(cce.get("Observaciones"), "Export sample")
        self.assertEqual(cce.get("TipoCambioUSD"), Decimal("17.123456"))
        self.assertEqual(cce.get("TotalUSD"), Decimal("100.00"))

        emisor = cce.get("Emisor")
        self.assertTrue(emisor)
        self.assertEqual(emisor["Domicilio"]["Pais"], "MEX")
        self.assertEqual(emisor["Domicilio"]["Calle"], "Av Reforma")

        receptor = cce.get("Receptor")
        self.assertEqual(receptor.get("NumRegIdTrib"), "123456789")
        self.assertEqual(receptor["Domicilio"]["Pais"], "USA")

        destinatario = cce.get("Destinatario")
        self.assertEqual(destinatario.get("Nombre"), "Warehouse LLC")
        self.assertEqual(destinatario["Domicilio"]["Estado"], "TX")

        mercancias = cce.get("Mercancias")
        self.assertTrue(mercancias)
        from satcfdi.utils import iterate

        first = list(iterate(mercancias))[0]
        self.assertEqual(first.get("NoIdentificacion"), "SKU-1")
        self.assertEqual(first.get("FraccionArancelaria"), "96091001")
        self.assertEqual(first.get("UnidadAduana"), "01")
        self.assertEqual(first.get("ValorDolares"), Decimal("100.00"))

    def test_build_domicilio_requires_core_fields(self):
        self.assertIsNone(cce_builder.build_domicilio({"Calle": "X"}))
        dom = cce_builder.build_domicilio(
            {
                "Calle": "Street",
                "Estado": "CMX",
                "Pais": "MEX",
                "CodigoPostal": "06600",
            }
        )
        self.assertEqual(dom.get("Calle"), "Street")
        self.assertEqual(dom.get("Pais"), "MEX")

    def test_build_mercancia_list(self):
        items = cce_builder.build_mercancia(
            [
                {
                    "NoIdentificacion": "A",
                    "ValorDolares": 10,
                    "FraccionArancelaria": "12345678",
                },
                {
                    "NoIdentificacion": "B",
                    "ValorDolares": 20,
                    "CantidadAduana": 2,
                    "UnidadAduana": "06",
                    "ValorUnitarioAduana": 10,
                },
            ]
        )
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].get("NoIdentificacion"), "A")
        self.assertEqual(items[1].get("UnidadAduana"), "06")

    def test_build_comercio_exterior_edge_cases(self):
        self.assertEqual(cce_builder._dec(None), Decimal("0"))
        self.assertIsNone(cce_builder.build_domicilio(None))
        cce = cce_builder.build_comercio_exterior(
            {
                "clave_de_pedimento": "A1",
                "certificado_origen": 0,
                "tipo_cambio_usd": 17,
                "total_usd": 10,
                "mercancias": {
                    "NoIdentificacion": "X",
                    "ValorDolares": 10,
                },
                "emisor": {"Curp": "AAAA"},  # no domicilio -> omitted
                "receptor": {
                    "num_reg_id_trib": "99",
                    "domicilio": {
                        "calle": "S",
                        "estado": "CA",
                        "pais": "USA",
                        "codigo_postal": "90001",
                    },
                },
            }
        )
        self.assertEqual(cce.get("ClaveDePedimento"), "A1")
        self.assertFalse(cce.get("Emisor"))
        self.assertTrue(cce.get("Receptor"))

        # No emisor / receptor / destinatario without domicilio
        bare = cce_builder.build_comercio_exterior(
            {
                "ClaveDePedimento": "A1",
                "CertificadoOrigen": 0,
                "TipoCambioUSD": 17,
                "TotalUSD": 5,
                "Mercancias": [{"NoIdentificacion": "Y", "ValorDolares": 5}],
                "Destinatario": {"Nombre": "Only Name"},
            }
        )
        self.assertFalse(bare.get("Emisor"))
        self.assertFalse(bare.get("Receptor"))
        self.assertFalse(bare.get("Destinatario"))

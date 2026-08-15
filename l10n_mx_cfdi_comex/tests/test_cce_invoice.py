# Copyright (C) 2026 Open Source Integrators
# License GPL-3.0 or later (http://www.gnu.org/licenses/gpl).

from unittest.mock import patch

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests.common import tagged

from odoo.addons.l10n_mx_cfdi_comex.services import cce_builder

from .common import CFDIComexTestCommon


@tagged("post_install", "-at_install")
class TestCceInvoice(CFDIComexTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.incoterm = cls.env["account.incoterms"].search(
            [("code", "=", "FOB")], limit=1
        )
        if not cls.incoterm:
            cls.incoterm = cls.env["account.incoterms"].create(
                {"code": "FOB", "name": "Free On Board"}
            )
        us_state = cls.env["res.country.state"].search(
            [("country_id.code", "=", "US")], limit=1
        )
        cls.export_customer = cls.env["res.partner"].create(
            {
                "name": "US Export Customer",
                "vat": "123456789",
                "street": "Main Street",
                "street2": "Suite 1",
                "city": "Los Angeles",
                "zip": "90001",
                "country_id": cls.env.ref("base.us").id,
                "state_id": us_state.id if us_state else False,
                "tax_regime": cls.env.ref("l10n_mx_catalogs.c_regimen_fiscal_616").id,
                "cfdi_use_id": cls.env.ref("l10n_mx_catalogs.c_uso_cfdi_G03").id,
                "payment_method_id": cls.env.ref(
                    "l10n_mx_catalogs.c_metodo_pago_PUE"
                ).id,
                "payment_form_id": cls.env.ref("l10n_mx_catalogs.c_forma_pago_03").id,
            }
        )
        mx_state = cls.env["res.country.state"].search(
            [
                ("country_id", "=", cls.env.ref("base.mx").id),
                ("code", "in", ("CDMX", "DF", "CMX")),
            ],
            limit=1,
        )
        cls.issuer.partner_id.write(
            {
                "street": "Av Reforma",
                "zip": "06600",
                "city": "Ciudad de Mexico",
                "country_id": cls.env.ref("base.mx").id,
                "state_id": mx_state.id if mx_state else False,
            }
        )
        CodigoPostal = cls.env["l10n_mx_catalogs.c_codigo_postal"]
        if not CodigoPostal.search([("code", "=", "06600")], limit=1):
            CodigoPostal.create(
                {
                    "code": "06600",
                    "state_code": "CMX",
                    "municipality_code": "015",
                    "locality_code": "01",
                }
            )
        cls.comex_product.write({"default_code": "EXP-SKU-1"})

    def _create_cce_invoice(self, **extra):
        vals = {
            "move_type": "out_invoice",
            "partner_id": self.export_customer.id,
            "invoice_date": fields.Date.today(),
            "cfdi_required": True,
            "issuer_id": self.issuer.id,
            "receiver_id": self.export_customer.id,
            "cfdi_use_id": self.export_customer.cfdi_use_id.id,
            "payment_method_id": self.export_customer.payment_method_id.id,
            "payment_form_id": self.export_customer.payment_form_id.id,
            "invoice_incoterm_id": self.incoterm.id,
            "l10n_mx_cfdi_cce_enabled": True,
            "l10n_mx_cfdi_cce_clave_pedimento": "A1",
            "l10n_mx_cfdi_cce_tipo_cambio_usd": 17.25,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": self.comex_product.id,
                        "quantity": 2,
                        "price_unit": 50.0,
                        "l10n_mx_cfdi_cce_valor_dolares": 100.0,
                        "l10n_mx_cfdi_cce_cantidad_aduana": 2,
                        "l10n_mx_cfdi_cce_unidad_aduana": "01",
                        "l10n_mx_cfdi_cce_valor_unitario_aduana": 50.0,
                    },
                )
            ],
        }
        vals.update(extra)
        return self.env["account.move"].create(vals)

    def _extract_cce(self, cfdi):
        complemento = cfdi.get("Complemento")
        if not complemento:
            return None
        if hasattr(complemento, "get") and complemento.get("ComercioExterior"):
            return complemento.get("ComercioExterior")
        from satcfdi.utils import iterate

        for node in iterate(complemento):
            tag = str(getattr(node, "tag", "") or "")
            name = type(node).__name__
            if "ComercioExterior" in tag or "ComercioExterior" in name:
                return node
        if "ComercioExterior" in type(complemento).__name__:
            return complemento
        return None

    def test_gather_invoice_sets_exportacion_02_and_cce_complement(self):
        invoice = self._create_cce_invoice()
        cfdi = invoice._gather_invoice_cfdi_data()
        self.assertEqual(cfdi.get("Exportacion"), "02")
        cce = self._extract_cce(cfdi)
        self.assertTrue(cce, "Expected ComercioExterior in Complemento")
        self.assertEqual(cce.get("Version"), "2.0")
        self.assertEqual(cce.get("ClaveDePedimento"), "A1")
        self.assertEqual(cce.get("Incoterm"), "FOB")
        self.assertTrue(cce.get("Emisor"))
        self.assertTrue(cce.get("Receptor"))
        self.assertTrue(cce.get("Mercancias"))

    def test_cce_uses_invoice_incoterm_id(self):
        invoice = self._create_cce_invoice()
        data = invoice._l10n_mx_cfdi_cce_gather_data()
        self.assertEqual(data["Incoterm"], self.incoterm.code)
        self.assertEqual(data["Incoterm"], "FOB")

    def test_cce_validation_missing_required_fields(self):
        invoice = self._create_cce_invoice(
            invoice_incoterm_id=False,
            l10n_mx_cfdi_cce_tipo_cambio_usd=0,
        )
        with self.assertRaises(UserError) as err:
            invoice._l10n_mx_cfdi_cce_validate()
        message = str(err.exception)
        self.assertIn("Incoterm", message)
        self.assertIn("Tipo cambio USD", message)

    def test_cce_validation_missing_line_valor_dolares(self):
        invoice = self._create_cce_invoice()
        invoice.invoice_line_ids.filtered("product_id").write(
            {"l10n_mx_cfdi_cce_valor_dolares": 0}
        )
        with self.assertRaises(UserError) as err:
            invoice._l10n_mx_cfdi_cce_validate()
        self.assertIn("Valor dólares", str(err.exception))

    def test_pedimentos_still_work_without_cce(self):
        """Import pedimentos path remains independent of CCE export."""
        pedimento = self._create_pedimento()
        invoice, _lot = self._create_sale_invoice_with_lot(pedimento)
        line = invoice.invoice_line_ids.filtered("product_id")[:1]
        self.assertFalse(invoice.l10n_mx_cfdi_cce_enabled)
        item = line._gater_cfdi_item_data()
        self.assertIn("NumerosPedimento", item)
        cfdi = invoice._gather_invoice_cfdi_data()
        self.assertEqual(cfdi.get("Exportacion"), "01")
        self.assertIsNone(self._extract_cce(cfdi))

    def test_create_invoice_cfdi_publishes_with_cce(self):
        invoice = self._create_cce_invoice()
        invoice.action_post()
        published = {}

        def _fake_publish(doc_self, cfdi):
            published["cfdi"] = cfdi
            doc_self.write(
                {
                    "state": "published",
                    "uuid": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                }
            )
            return True

        with patch(
            "odoo.addons.l10n_mx_cfdi.models.cfdi_document.Document.publish",
            _fake_publish,
        ):
            invoice.create_invoice_cfdi()
        self.assertIn("cfdi", published)
        self.assertEqual(published["cfdi"].get("Exportacion"), "02")
        self.assertTrue(self._extract_cce(published["cfdi"]))

    def test_cce_disabled_exportacion_hook(self):
        invoice = self._create_cce_invoice(l10n_mx_cfdi_cce_enabled=False)
        exportacion, complemento = (
            invoice._l10n_mx_cfdi_invoice_exportacion_complemento()
        )
        self.assertEqual(exportacion, "01")
        self.assertIsNone(complemento)
        self.assertEqual(invoice.l10n_mx_cfdi_cce_total_usd, 0.0)

    def test_cce_validation_issuer_and_receptor_address(self):
        invoice = self._create_cce_invoice()
        self.issuer.partner_id.write({"street": False, "street2": False})
        with self.assertRaises(UserError) as err:
            invoice._l10n_mx_cfdi_cce_validate()
        self.assertIn("Issuer CCE address", str(err.exception))

        self.issuer.partner_id.write({"street": "Av Reforma"})
        self.export_customer.write({"zip": False})
        with self.assertRaises(UserError) as err:
            invoice._l10n_mx_cfdi_cce_validate()
        self.assertIn("Receptor CCE address", str(err.exception))

    def test_cce_validation_product_identification_and_fraccion(self):
        invoice = self._create_cce_invoice()
        product = self.comex_product
        product.write({"default_code": False})
        invoice.invoice_line_ids.filtered("product_id").write(
            {"l10n_mx_cfdi_cce_no_identificacion": False}
        )
        with self.assertRaises(UserError) as err:
            invoice._l10n_mx_cfdi_cce_validate()
        self.assertIn("Internal Reference", str(err.exception))

        product.write({"default_code": "EXP-SKU-1", "l10n_mx_cfdi_tariff_code": False})
        with self.assertRaises(UserError) as err:
            invoice._l10n_mx_cfdi_cce_validate()
        self.assertIn("tariff code", str(err.exception))

    def test_cce_validation_certificado_origen_and_clave(self):
        invoice = self._create_cce_invoice(
            l10n_mx_cfdi_cce_clave_pedimento=False,
            l10n_mx_cfdi_cce_certificado_origen="1",
            l10n_mx_cfdi_cce_num_certificado_origen=False,
        )
        with self.assertRaises(UserError) as err:
            invoice._l10n_mx_cfdi_cce_validate()
        message = str(err.exception)
        self.assertIn("Clave de pedimento", message)
        self.assertIn("Número certificado de origen", message)

    def test_cce_gather_with_destinatario(self):
        dest = self.env["res.partner"].create(
            {
                "name": "Dest Warehouse",
                "vat": "998877665",
                "street": "Dock Road",
                "city": "Houston",
                "zip": "77001",
                "country_id": self.env.ref("base.us").id,
                "state_id": self.export_customer.state_id.id,
            }
        )
        invoice = self._create_cce_invoice(
            l10n_mx_cfdi_cce_destinatario_id=dest.id,
            l10n_mx_cfdi_cce_observaciones="Note",
            l10n_mx_cfdi_cce_motivo_traslado="01",
        )
        data = invoice._l10n_mx_cfdi_cce_gather_data()
        self.assertEqual(data["Destinatario"]["Nombre"], "Dest Warehouse")
        self.assertEqual(data["Observaciones"], "Note")
        self.assertEqual(data["MotivoTraslado"], "01")
        cce = cce_builder.build_comercio_exterior_from_invoice(invoice)
        self.assertEqual(cce.get("Destinatario").get("Nombre"), "Dest Warehouse")

    def test_cce_map_country_helpers(self):
        invoice = self._create_cce_invoice()
        mx = invoice._l10n_mx_cfdi_cce_map_country(self.env.ref("base.mx"))
        self.assertEqual(mx.code, "MEX")
        us = invoice._l10n_mx_cfdi_cce_map_country(self.env.ref("base.us"))
        self.assertEqual(us.code, "USA")
        self.assertFalse(invoice._l10n_mx_cfdi_cce_map_country(False))

    def test_cce_validation_missing_issuer_receptor_and_lines(self):
        invoice = self._create_cce_invoice()
        invoice.write({"issuer_id": False, "receiver_id": False, "partner_id": False})
        invoice.invoice_line_ids.unlink()
        with self.assertRaises(UserError) as err:
            invoice._l10n_mx_cfdi_cce_validate()
        message = str(err.exception)
        self.assertIn("Issuer is required", message)
        self.assertIn("Receptor is required", message)
        self.assertIn("product line", message)

    def test_cce_map_country_fallbacks(self):
        invoice = self._create_cce_invoice()
        Pais = self.env["l10n_mx_catalogs.c_pais"]
        mx_country = self.env.ref("base.mx")
        # Force code search miss so MX xmlid path runs
        with patch.object(type(Pais), "search", return_value=Pais):
            mapped = invoice._l10n_mx_cfdi_cce_map_country(mx_country)
            self.assertEqual(mapped.code, "MEX")

        # Unknown ISO → map_res_country hit
        obscure = self.env["res.country"].create(
            {"name": "Testlandia CCE", "code": "ZL"}
        )
        fake_pais = Pais.sudo().create(
            {"code": "ZLX", "description": "Testlandia CCE Extra"}
        )
        with patch.object(type(Pais), "search", return_value=Pais):
            with patch.object(type(Pais), "map_res_country", return_value=fake_pais):
                found = invoice._l10n_mx_cfdi_cce_map_country(obscure)
        self.assertEqual(found, fake_pais)

        # map_res_country miss → ilike description
        with patch.object(type(Pais), "map_res_country", return_value=Pais):
            found_ilike = invoice._l10n_mx_cfdi_cce_map_country(obscure)
        self.assertEqual(found_ilike, fake_pais)

    def test_cce_partner_address_errors(self):
        invoice = self._create_cce_invoice()
        partner = self.env["res.partner"].create(
            {
                "name": "No Country Partner",
                "street": "Somewhere",
                "zip": "99999",
                "country_id": False,
            }
        )
        with self.assertRaises(UserError) as err:
            invoice._l10n_mx_cfdi_cce_partner_address(partner)
        self.assertIn("No SAT country code", str(err.exception))

        partner.write(
            {
                "country_id": self.env.ref("base.us").id,
                "state_id": False,
                "city": False,
            }
        )
        with self.assertRaises(UserError) as err:
            invoice._l10n_mx_cfdi_cce_partner_address(partner)
        self.assertIn("State (Estado)", str(err.exception))

    def test_cce_gather_mercancias_optional_aduana_fields(self):
        invoice = self._create_cce_invoice()
        line = invoice.invoice_line_ids.filtered("product_id")[:1]
        line.write(
            {
                "l10n_mx_cfdi_cce_unidad_aduana": False,
                "l10n_mx_cfdi_cce_valor_unitario_aduana": 0,
                "l10n_mx_cfdi_cce_cantidad_aduana": 0,
                "quantity": 0,
            }
        )
        items = invoice._l10n_mx_cfdi_cce_gather_mercancias()
        self.assertEqual(len(items), 1)
        self.assertNotIn("UnidadAduana", items[0])
        self.assertNotIn("ValorUnitarioAduana", items[0])
        self.assertNotIn("CantidadAduana", items[0])

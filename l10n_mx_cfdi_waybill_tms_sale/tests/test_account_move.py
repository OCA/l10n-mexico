# Copyright (C) 2026 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.addons.l10n_mx_cfdi_waybill.tests.common import WaybillTestCommon


class TestInvoiceCartaPorte(WaybillTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mexico = cls.env.ref("base.mx")
        brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Invoice Brand"})
        model = cls.env["fleet.vehicle.model"].create(
            {"name": "Invoice Model", "brand_id": brand.id}
        )
        cls.fleet_vehicle = cls.env["fleet.vehicle"].create(
            {
                "model_id": model.id,
                "operation": "cargo",
                "l10n_mx_cfdi_waybill_vehicle_id": cls.vehicle.id,
            }
        )
        cls.driver = cls.env["tms.driver"].create(
            {
                "name": "Invoice Operador",
                "vat": "XEXX010101000",
                "driver_license_number": "LICINV",
            }
        )
        cls.origin = cls.env["res.partner"].create(
            {
                "name": "Invoice Origin",
                "tms_location": True,
                "street": "Calle 1",
                "zip": "06000",
                "country_id": cls.mexico.id,
            }
        )
        cls.destination = cls.env["res.partner"].create(
            {
                "name": "Invoice Destination",
                "tms_location": True,
                "street": "Calle 2",
                "zip": "44100",
                "country_id": cls.mexico.id,
            }
        )
        cls.product_code = cls.env.ref("l10n_mx_catalogs.c_clave_prod_serv_01010101")
        cls.unit = cls.env.ref("l10n_mx_catalogs.c_clave_unidad_KGM")

    def _trip_with_waybill(self):
        trip = self.env["tms.order"].create(
            {
                "origin_id": self.origin.id,
                "destination_id": self.destination.id,
                "vehicle_id": self.fleet_vehicle.id,
                "driver_id": self.driver.id,
            }
        )
        self.env["tms.cargo"].create(
            {
                "order_id": trip.id,
                "name": "Freight",
                "quantity": 1.0,
                "weight": 100.0,
                "weight_uom_id": self.env.ref("uom.product_uom_kgm").id,
                "l10n_mx_cfdi_product_code_id": self.product_code.id,
                "l10n_mx_cfdi_unit_id": self.unit.id,
            }
        )
        waybill = self.env["l10n_mx_cfdi_waybill.waybill"].browse(
            trip.action_create_waybill()["res_id"]
        )
        return trip, waybill

    def _sale_line_for_trip(self, trip):
        product = self.env["product.product"].create(
            {"name": "Invoice freight", "type": "service", "list_price": 1000.0}
        )
        sale = self.env["sale.order"].create({"partner_id": self.customer.id})
        line = self.env["sale.order.line"].create(
            {
                "order_id": sale.id,
                "product_id": product.id,
                "product_uom_qty": 1,
            }
        )
        trip.write({"sale_id": sale.id, "sale_line_id": line.id})
        return line

    def _invoice_for_line(self, line):
        return self._create_cfdi_invoice(
            invoice_line_ids=[
                (
                    0,
                    0,
                    {
                        "product_id": line.product_id.id,
                        "quantity": 1,
                        "price_unit": 1000.0,
                        "sale_line_ids": [(6, 0, line.ids)],
                    },
                )
            ]
        )

    def test_invoice_without_a_waybill_keeps_the_default_complement(self):
        invoice = self._create_cfdi_invoice()
        exportacion, complemento = (
            invoice._l10n_mx_cfdi_invoice_exportacion_complemento()
        )
        self.assertEqual(exportacion, "01")
        self.assertFalse(invoice.l10n_mx_cfdi_tms_waybill_id)
        self.assertIsNone(complemento)

    def test_invoice_picks_the_waybill_of_the_sale_trip(self):
        trip, waybill = self._trip_with_waybill()
        line = self._sale_line_for_trip(trip)
        invoice = self._invoice_for_line(line)
        self.assertEqual(invoice.l10n_mx_cfdi_tms_waybill_id, waybill)
        exportacion, complemento = (
            invoice._l10n_mx_cfdi_invoice_exportacion_complemento()
        )
        self.assertEqual(exportacion, "01")
        self.assertIsNotNone(complemento)

    def test_canceled_waybill_is_not_used(self):
        trip, waybill = self._trip_with_waybill()
        line = self._sale_line_for_trip(trip)
        waybill.state = "canceled"
        invoice = self._invoice_for_line(line)
        self.assertFalse(invoice.l10n_mx_cfdi_tms_waybill_id)

    def test_existing_complement_is_kept_with_carta_porte(self):
        trip, _waybill = self._trip_with_waybill()
        line = self._sale_line_for_trip(trip)
        invoice = self._invoice_for_line(line)
        comercio = object()
        parent = type(invoice).mro()[1]
        with patch.object(
            parent,
            "_l10n_mx_cfdi_invoice_exportacion_complemento",
            lambda self: ("02", comercio),
        ):
            exportacion, complemento = (
                invoice._l10n_mx_cfdi_invoice_exportacion_complemento()
            )
        self.assertEqual(exportacion, "02")
        self.assertEqual(complemento[0], comercio)
        self.assertIsNotNone(complemento[1])

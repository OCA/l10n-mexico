# Copyright (C) 2026 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError

from odoo.addons.l10n_mx_cfdi_waybill.tests.common import WaybillTestCommon


class TestWaybillTMS(WaybillTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product_code = cls.env.ref("l10n_mx_catalogs.c_clave_prod_serv_01010101")
        cls.unit = cls.env.ref("l10n_mx_catalogs.c_clave_unidad_KGM")
        cls.mexico = cls.env.ref("base.mx")
        brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Waybill Brand"})
        model = cls.env["fleet.vehicle.model"].create(
            {"name": "Waybill Model", "brand_id": brand.id}
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
                "name": "Operador",
                "vat": "XEXX010101000",
                "driver_license_number": "LIC999",
            }
        )
        cls.origin = cls.env["res.partner"].create(
            {
                "name": "Origen",
                "tms_location": True,
                "street": "Calle 1",
                "zip": "06000",
                "country_id": cls.mexico.id,
            }
        )
        cls.destination = cls.env["res.partner"].create(
            {
                "name": "Destino",
                "tms_location": True,
                "street": "Calle 2",
                "zip": "44100",
                "country_id": cls.mexico.id,
            }
        )

    def _cargo_values(self, **extra):
        values = {
            "name": "Steel coils",
            "quantity": 2.0,
            "weight": 800.0,
            "weight_uom_id": self.env.ref("uom.product_uom_kgm").id,
            "l10n_mx_cfdi_product_code_id": self.product_code.id,
            "l10n_mx_cfdi_unit_id": self.unit.id,
        }
        values.update(extra)
        return values

    def _create_trip(self, cargos=None, **extra):
        values = {
            "origin_id": self.origin.id,
            "destination_id": self.destination.id,
            "vehicle_id": self.fleet_vehicle.id,
            "driver_id": self.driver.id,
        }
        values.update(extra)
        trip = self.env["tms.order"].create(values)
        for cargo_values in cargos or [self._cargo_values()]:
            cargo_values = dict(cargo_values, order_id=trip.id)
            self.env["tms.cargo"].create(cargo_values)
        return trip

    def test_trip_creates_one_waybill_per_truck(self):
        trip = self._create_trip(
            cargos=[
                self._cargo_values(name="Steel coils", weight=800.0),
                self._cargo_values(
                    name="Spare parts",
                    weight=400.0,
                    l10n_mx_cfdi_hazardous=True,
                    l10n_mx_cfdi_hazardous_code="UN1203",
                    l10n_mx_cfdi_sat_packaging="4G",
                    l10n_mx_cfdi_declared_value=1500.0,
                ),
            ]
        )
        stage = trip.stage_id
        action = trip.action_create_waybill()
        waybill = self.env["l10n_mx_cfdi_waybill.waybill"].browse(action["res_id"])
        self.assertEqual(waybill.tms_order_id, trip)
        self.assertEqual(waybill.vehicle_id, self.vehicle)
        self.assertEqual(waybill.type, "T")
        self.assertEqual(len(waybill.entry_ids), 2)
        self.assertEqual(trip.stage_id, stage)
        self.assertEqual(trip.waybill_count, 1)
        self.assertEqual(
            self.driver.partner_id.l10n_mx_cfdi_waybill_driving_license, "LIC999"
        )
        goods, _locations = waybill._format_goods_and_locations_data()
        by_name = {item["Descripcion"]: item for item in goods}
        self.assertEqual(by_name["Steel coils"]["PesoEnKg"], "800.000")
        self.assertEqual(by_name["Spare parts"]["MaterialPeligroso"], "Sí")
        self.assertEqual(by_name["Spare parts"]["CveMaterialPeligroso"], "UN1203")
        self.assertEqual(by_name["Spare parts"]["Embalaje"], "4G")
        self.assertEqual(by_name["Spare parts"]["ValorMercancia"], "1500.00")
        again = trip.action_create_waybill()
        self.assertEqual(again["res_id"], waybill.id)

    def test_two_trips_create_two_waybills(self):
        first = self._create_trip()
        second = self._create_trip(cargos=[self._cargo_values(name="Second load")])
        first_waybill = self.env["l10n_mx_cfdi_waybill.waybill"].browse(
            first.action_create_waybill()["res_id"]
        )
        second_waybill = self.env["l10n_mx_cfdi_waybill.waybill"].browse(
            second.action_create_waybill()["res_id"]
        )
        self.assertNotEqual(first_waybill, second_waybill)
        self.assertEqual(first_waybill.entry_ids.cargo_id, first.cargo_ids)
        self.assertEqual(second_waybill.entry_ids.cargo_id.name, "Second load")

    def test_truck_without_carta_porte_vehicle_is_refused(self):
        self.fleet_vehicle.l10n_mx_cfdi_waybill_vehicle_id = False
        trip = self._create_trip()
        with self.assertRaises(UserError):
            trip.action_create_waybill()
        self.assertFalse(trip.waybill_ids)

    def test_published_waybill_can_be_required_before_start(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "l10n_mx_cfdi_waybill_tms.require_published_waybill", "True"
        )
        trip = self._create_trip(cargos=[self._cargo_values(volume=1.0)])
        trip.stage_id = self.env.ref("tms.tms_stage_order_confirmed")
        trip.cargo_ids.state = "loaded"
        with self.assertRaises(UserError):
            trip.button_start_order()
        self.assertFalse(trip.start_trip)
        waybill = self.env["l10n_mx_cfdi_waybill.waybill"].browse(
            trip.action_create_waybill()["res_id"]
        )
        waybill.state = "published"
        trip.button_start_order()
        self.assertTrue(trip.start_trip)

    def test_passenger_trip_starts_without_a_waybill(self):
        self.env["ir.config_parameter"].sudo().set_param(
            "l10n_mx_cfdi_waybill_tms.require_published_waybill", "True"
        )
        passenger = self.fleet_vehicle.copy({"operation": "passenger"})
        trip = self.env["tms.order"].create(
            {
                "origin_id": self.origin.id,
                "destination_id": self.destination.id,
                "vehicle_id": passenger.id,
            }
        )
        trip.button_start_order()
        self.assertTrue(trip.start_trip)

    def test_stock_entry_keeps_the_product_description(self):
        waybill = self._create_waybill()
        entry = self._create_waybill_entry(waybill)
        item = waybill._format_invoice_item_data(entry)
        self.assertEqual(item["Description"], self.stock_product.name)
        self.assertFalse(entry.cargo_id)

    def test_trip_trailers_are_copied_onto_the_waybill_vehicle(self):
        subtype = self.env.ref("l10n_mx_catalogs.c_sub_tipo_rem_CTR004")
        trailer = self.fleet_vehicle.copy(
            {
                "license_plate": "REM001",
                "tms_equipment_type": "trailer",
                "operation": False,
                "l10n_mx_cfdi_waybill_vehicle_id": False,
                "l10n_mx_cfdi_trailer_type_id": subtype.id,
            }
        )
        trip = self._create_trip()
        self.env["tms.order.equipment"].create(
            {"order_id": trip.id, "vehicle_id": trailer.id}
        )
        trip.action_create_waybill()
        plates = trip.waybill_ids.vehicle_id.trailers.mapped("plate")
        self.assertEqual(plates, ["REM001"])
        data = {"Complemento": {"CartaPorte31": {"Mercancias": {}}}}
        trip.waybill_ids._add_autotransporte_data(data)
        remolques = data["Complemento"]["CartaPorte31"]["Mercancias"]["Autotransporte"][
            "Remolques"
        ]
        self.assertEqual(remolques, [{"SubTipoRem": "CTR004", "Placa": "REM001"}])

    def test_dropped_trailer_and_dolly_are_left_off_the_waybill(self):
        subtype = self.env.ref("l10n_mx_catalogs.c_sub_tipo_rem_CTR004")
        model = self.fleet_vehicle.model_id
        dropped = self.env["fleet.vehicle"].create(
            {
                "model_id": model.id,
                "license_plate": "REM-DROP",
                "tms_equipment_type": "trailer",
                "l10n_mx_cfdi_trailer_type_id": subtype.id,
            }
        )
        dolly = self.env["fleet.vehicle"].create(
            {
                "model_id": model.id,
                "license_plate": "DOL-1",
                "tms_equipment_type": "dolly",
            }
        )
        trip = self._create_trip()
        dropped_line = self.env["tms.order.equipment"].create(
            {"order_id": trip.id, "vehicle_id": dropped.id}
        )
        dropped_line.action_drop()
        self.env["tms.order.equipment"].create(
            {"order_id": trip.id, "vehicle_id": dolly.id}
        )
        trip.action_create_waybill()
        plates = trip.waybill_ids.vehicle_id.trailers.mapped("plate")
        self.assertNotIn("REM-DROP", plates)
        self.assertNotIn("DOL-1", plates)

    def test_trailer_without_a_sat_type_is_refused(self):
        without_type = self.env["fleet.vehicle"].create(
            {
                "model_id": self.fleet_vehicle.model_id.id,
                "license_plate": "REM-NOTYPE",
                "tms_equipment_type": "trailer",
            }
        )
        trip = self._create_trip()
        self.env["tms.order.equipment"].create(
            {"order_id": trip.id, "vehicle_id": without_type.id}
        )
        with self.assertRaises(UserError):
            trip.action_create_waybill()
        self.assertFalse(trip.waybill_ids)

    def test_trailer_without_a_plate_is_refused(self):
        without_plate = self.env["fleet.vehicle"].create(
            {
                "model_id": self.fleet_vehicle.model_id.id,
                "tms_equipment_type": "trailer",
                "l10n_mx_cfdi_trailer_type_id": self.env.ref(
                    "l10n_mx_catalogs.c_sub_tipo_rem_CTR004"
                ).id,
            }
        )
        trip = self._create_trip()
        self.env["tms.order.equipment"].create(
            {"order_id": trip.id, "vehicle_id": without_plate.id}
        )
        with self.assertRaises(UserError):
            trip.action_create_waybill()
        self.assertFalse(trip.waybill_ids)

from base64 import b64encode
from datetime import datetime
from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError

from .common import WaybillTestCommon


class TestWaybill(WaybillTestCommon):
    def test_default_get_from_picking(self):
        picking = self._create_picking()
        defaults = (
            self.env["l10n_mx_cfdi_waybill.waybill"]
            .with_context(active_model="stock.picking", active_ids=picking.ids)
            .default_get(["type", "receiver_id", "picking_ids"])
        )
        self.assertEqual(defaults["type"], "T")
        self.assertEqual(defaults["picking_ids"].ids, picking.ids)

    def test_default_get_without_picking(self):
        defaults = self.env["l10n_mx_cfdi_waybill.waybill"].default_get(
            ["type", "receiver_id", "name"]
        )
        self.assertEqual(defaults["type"], "T")
        self.assertEqual(defaults["name"], "(Borrador)")
        self.assertEqual(defaults["receiver_id"], self.env.company.partner_id.id)

    def test_default_get_outgoing_picking_receiver(self):
        picking = self._create_picking()
        defaults = (
            self.env["l10n_mx_cfdi_waybill.waybill"]
            .with_context(active_model="stock.picking", active_ids=picking.ids)
            .default_get(["receiver_id"])
        )
        self.assertEqual(defaults["receiver_id"], picking.partner_id.id)

    def test_default_get_incoming_picking_receiver(self):
        picking = self._create_picking(
            picking_type_id=self.warehouse.in_type_id.id,
            location_id=self.env.ref("stock.stock_location_suppliers").id,
            location_dest_id=self.warehouse.lot_stock_id.id,
        )
        defaults = (
            self.env["l10n_mx_cfdi_waybill.waybill"]
            .with_context(active_model="stock.picking", active_ids=picking.ids)
            .default_get(["receiver_id"])
        )
        self.assertEqual(defaults["receiver_id"], self.issuer.partner_id.id)

    def test_onchange_picking_ids_creates_entries(self):
        picking = self._create_picking()
        waybill = self._create_waybill(picking_ids=[(6, 0, picking.ids)])
        waybill._onchange_picking_ids()
        self.assertTrue(waybill.entry_ids)

    def test_onchange_picking_ids_empty(self):
        waybill = self._create_waybill()
        waybill._onchange_picking_ids()
        self.assertFalse(waybill.entry_ids)

    def test_onchange_picking_ids_idempotent(self):
        picking = self._create_picking()
        waybill = self._create_waybill(picking_ids=[(6, 0, picking.ids)])
        waybill._onchange_picking_ids()
        count = len(waybill.entry_ids)
        waybill._onchange_picking_ids()
        self.assertEqual(len(waybill.entry_ids), count)

    def test_onchange_picking_ids_mixed_types(self):
        picking_a = self._create_picking()
        picking_b = self._create_picking(
            picking_type_id=self.warehouse.in_type_id.id,
            location_id=self.env.ref("stock.stock_location_suppliers").id,
            location_dest_id=self.warehouse.lot_stock_id.id,
        )
        waybill = self._create_waybill()
        waybill.picking_ids = [(6, 0, (picking_a | picking_b).ids)]
        with self.assertRaises(ValidationError):
            waybill._onchange_picking_ids()

    def test_format_data(self):
        waybill = self._create_waybill()
        self._create_waybill_entry(waybill)
        data = waybill._format_data()
        self.assertEqual(data["CfdiType"], "T")
        self.assertIn("CartaPorte31", data["Complemento"])
        self.assertIn(
            "Autotransporte", data["Complemento"]["CartaPorte31"]["Mercancias"]
        )

    def test_format_data_without_highway(self):
        waybill = self._create_waybill(federal_highway_use=False)
        self._create_waybill_entry(waybill)
        data = waybill._format_data()
        self.assertNotIn(
            "Autotransporte",
            data["Complemento"]["CartaPorte31"]["Mercancias"],
        )

    @patch(
        "odoo.addons.l10n_mx_catalogs.models.pais.Pais.map_res_country",
        autospec=True,
    )
    def test_format_address_mexico(self, mock_map_country):
        mock_map_country.return_value = self.env.ref("l10n_mx_catalogs.c_pais_MEX")
        waybill = self._create_waybill()
        partner = self.env["res.partner"].create(
            {
                "name": "MX Address",
                "country_id": self.env.ref("base.mx").id,
                "zip": "06000",
                "street_name": "Reforma",
                "street_number": "100",
            }
        )
        address = waybill._format_address(partner)
        self.assertEqual(address["Pais"], "MEX")
        self.assertEqual(address["CodigoPostal"], "06000")

    def test_format_address_mexico_country_fallback(self):
        waybill = self._create_waybill()
        partner = self.env["res.partner"].create(
            {
                "name": "MX Address",
                "country_id": self.env.ref("base.mx").id,
                "zip": "06000",
                "street": "Reforma 100",
            }
        )
        with patch(
            "odoo.addons.l10n_mx_catalogs.models.pais.Pais.map_res_country",
            return_value=self.env["l10n_mx_catalogs.c_pais"],
        ):
            address = waybill._format_address(partner)
        self.assertEqual(address["Pais"], "MEX")
        self.assertEqual(address["Calle"], "Reforma")
        self.assertEqual(address["NumeroExterior"], "100")

    @patch(
        "odoo.addons.l10n_mx_catalogs.models.pais.Pais.map_res_country",
        autospec=True,
    )
    def test_format_address_foreign(self, mock_map_country):
        mock_map_country.return_value = self.env.ref("l10n_mx_catalogs.c_pais_USA")
        waybill = self._create_waybill()
        partner = self.env["res.partner"].create(
            {
                "name": "US Address",
                "country_id": self.env.ref("base.us").id,
                "zip": "90210",
                "street": "Sunset Blvd",
                "city": "Los Angeles",
            }
        )
        address = waybill._format_address(partner)
        self.assertEqual(address["Pais"], "USA")

    @patch(
        "odoo.addons.l10n_mx_catalogs.models.pais.Pais.map_res_country",
        autospec=True,
    )
    def test_format_address_strips_empty_values(self, mock_map_country):
        mock_map_country.return_value = self.env.ref("l10n_mx_catalogs.c_pais_MEX")
        waybill = self._create_waybill()
        partner = self.env["res.partner"].create(
            {
                "name": "MX Address",
                "country_id": self.env.ref("base.mx").id,
                "zip": "06000",
                "street_name": "Reforma",
            }
        )
        address = waybill._format_address(partner)
        self.assertNotIn("NumeroExterior", address)
        self.assertNotIn("NumeroInterior", address)

    def test_format_goods_dedup_locations(self):
        waybill = self._create_waybill()
        self._create_waybill_entry(waybill)
        self._create_waybill_entry(waybill)
        _goods, locations = waybill._format_goods_and_locations_data()
        origins = [loc for loc in locations if loc["TipoUbicacion"] == "Origen"]
        destinations = [loc for loc in locations if loc["TipoUbicacion"] == "Destino"]
        self.assertEqual(len(origins), 1)
        self.assertEqual(len(destinations), 1)

    def test_add_autotransporte_field_values(self):
        waybill = self._create_waybill()
        self._create_waybill_entry(waybill)
        data = waybill._format_data()
        autotransporte = data["Complemento"]["CartaPorte31"]["Mercancias"][
            "Autotransporte"
        ]
        self.assertEqual(autotransporte["PermSCT"], self.vehicle.permit_type.code)
        self.assertEqual(autotransporte["NumPermisoSCT"], self.vehicle.permit_number)
        self.assertEqual(
            autotransporte["IdentificacionVehicular"]["PlacaVM"], self.vehicle.plate
        )

    def test_validate_required_fields_missing_vehicle(self):
        waybill = self._create_waybill(vehicle_id=False)
        with self.assertRaises(ValidationError):
            waybill._validate_required_fields()

    def test_validate_required_fields_missing_transporter(self):
        waybill = self._create_waybill(transporter_ids=[(5, 0, 0)])
        with self.assertRaises(ValidationError):
            waybill._validate_required_fields()

    def test_validate_required_fields_missing_operator(self):
        owner_type = self.env.ref("l10n_mx_catalogs.c_figura_transporte_2")
        transporter = self.env["l10n_mx_cfdi_waybill.transporter"].create(
            {
                "partner_id": self.transporter_partner.id,
                "type": owner_type.id,
            }
        )
        waybill = self._create_waybill(transporter_ids=[(6, 0, transporter.ids)])
        with self.assertRaises(ValidationError):
            waybill._validate_required_fields()

    def test_validate_required_fields_missing_transporter_vat(self):
        self.transporter_partner.vat = False
        waybill = self._create_waybill()
        with self.assertRaises(ValidationError):
            waybill._validate_required_fields()

    def test_validate_without_highway_skips_vehicle(self):
        waybill = self._create_waybill(
            federal_highway_use=False, vehicle_id=False, transporter_ids=[(5, 0, 0)]
        )
        self._create_waybill_entry(waybill)
        waybill._validate_required_fields()

    def test_validate_missing_transporter_type(self):
        # Keep one Operador so the type-missing check is reachable per transporter
        bare_partner = self.env["res.partner"].create(
            {
                "name": "Bare Driver",
                "vat": "XAXX010101099",
                "l10n_mx_cfdi_waybill_driving_license": "LIC999",
            }
        )
        bare = self.env["l10n_mx_cfdi_waybill.transporter"].create(
            {"partner_id": bare_partner.id, "type": False}
        )
        waybill = self._create_waybill(
            transporter_ids=[(6, 0, (self.transporter | bare).ids)]
        )
        self._create_waybill_entry(waybill)
        with self.assertRaises(ValidationError) as err:
            waybill._validate_required_fields()
        self.assertIn("tipo de contacto", str(err.exception))

    def test_validate_missing_driving_license(self):
        self.transporter_partner.l10n_mx_cfdi_waybill_driving_license = False
        waybill = self._create_waybill()
        self._create_waybill_entry(waybill)
        with self.assertRaises(ValidationError):
            waybill._validate_required_fields()

    def test_validate_mixed_picking_types(self):
        picking_a = self._create_picking()
        picking_b = self._create_picking(
            picking_type_id=self.warehouse.in_type_id.id,
            location_id=self.env.ref("stock.stock_location_suppliers").id,
            location_dest_id=self.warehouse.lot_stock_id.id,
        )
        waybill = self._create_waybill()
        self._create_waybill_entry(waybill)
        waybill.picking_ids = [(6, 0, (picking_a | picking_b).ids)]
        with self.assertRaises(ValidationError):
            waybill._validate_required_fields()

    def test_action_cancel(self):
        waybill = self._create_waybill()
        action = waybill.action_cancel()
        self.assertEqual(action["res_model"], "l10n_mx_cfdi_account.document_cancel")

    def test_action_draft_removes_attachments(self):
        waybill = self._create_waybill()
        self.env["ir.attachment"].create(
            {
                "name": "waybill.pdf",
                "datas": b64encode(b"PDF").decode(),
                "res_model": "l10n_mx_cfdi_waybill.waybill",
                "res_id": waybill.id,
            }
        )
        waybill.action_draft()
        attachments = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "l10n_mx_cfdi_waybill.waybill"),
                ("res_id", "=", waybill.id),
            ]
        )
        self.assertFalse(attachments)

    def test_action_print_with_attachment(self):
        waybill = self._create_waybill()
        waybill.cfdi_id.pdf_filename = "waybill.pdf"
        self.env["ir.attachment"].create(
            {
                "name": "waybill.pdf",
                "datas": b64encode(b"PDF").decode(),
                "res_model": "l10n_mx_cfdi_waybill.waybill",
                "res_id": waybill.id,
            }
        )
        action = waybill.action_print()
        self.assertEqual(action["type"], "ir.actions.act_url")

    def test_action_print_no_attachment(self):
        waybill = self._create_waybill()
        waybill.cfdi_id.pdf_filename = "waybill.pdf"
        self.assertFalse(waybill.action_print())

    def test_format_address_for_report(self):
        waybill = self._create_waybill()
        rendered = waybill.format_address_for_report(
            {
                "Calle": "Main",
                "NumeroExterior": "1",
                "NumeroInterior": "2",
                "Estado": "CDMX",
                "Pais": "MEX",
                "CodigoPostal": "06000",
            }
        )
        self.assertIn("Main", rendered)
        self.assertIn("06000", rendered)
        self.assertIn("2", rendered)

    def test_format_peso_bruto_total(self):
        waybill = self._create_waybill()
        total = waybill.format_peso_bruto_total(
            [{"PesoEnKg": "10.500"}, {"PesoEnKg": "5.250"}]
        )
        self.assertEqual(total, "15.750")

    def test_assign_serial_number(self):
        waybill = self._create_waybill()
        waybill._assign_serial_number()
        self.assertTrue(waybill.cfdi_id.serie)
        self.assertTrue(waybill.cfdi_id.folio)

    def test_assign_serial_number_creates_sequence(self):
        self.env["ir.sequence"].search(
            [("code", "=", "l10n_mx_cfdi_waybill.sequence")]
        ).unlink()
        waybill = self._create_waybill()
        waybill._assign_serial_number()
        sequence = self.env["ir.sequence"].search(
            [("code", "=", "l10n_mx_cfdi_waybill.sequence")]
        )
        self.assertTrue(sequence)
        self.assertTrue(waybill.cfdi_id.serie)

    @patch(
        "odoo.addons.l10n_mx_cfdi.models.cfdi_document.Document.publish",
        autospec=True,
    )
    def test_action_post(self, mock_publish):
        waybill = self._create_waybill()
        self._create_waybill_entry(waybill)
        picking = self._create_picking()
        waybill.picking_ids = [(6, 0, picking.ids)]
        waybill.cfdi_id.write(
            {
                "pdf_filename": "waybill.pdf",
                "pdf_file": b64encode(b"PDF").decode(),
                "xml_filename": "waybill.xml",
                "xml_file": b64encode(b"<xml/>").decode(),
            }
        )
        waybill.action_post()
        mock_publish.assert_called_once()
        self.assertIn(waybill, picking.waybill_ids)
        self.assertTrue(waybill.message_ids)
        attachments = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "l10n_mx_cfdi_waybill.waybill"),
                ("res_id", "=", waybill.id),
            ]
        )
        self.assertEqual(len(attachments), 2)

    @patch(
        "odoo.addons.l10n_mx_cfdi.models.cfdi_document.Document.publish",
        autospec=True,
        side_effect=UserError("publish failed"),
    )
    def test_action_post_error(self, mock_publish):
        waybill = self._create_waybill()
        self._create_waybill_entry(waybill)
        self.transporter.driving_license = "LIC123"
        with self.assertRaises(UserError):
            waybill.action_post()
        mock_publish.assert_called_once()

    @patch(
        "odoo.addons.l10n_mx_cfdi.models.cfdi_document.Document.publish",
        autospec=True,
    )
    def test_action_post_facturama_publishes_comprobante(self, mock_publish):
        """Facturama Multiemisor supports Carta Porte 3.1 via satcfdi Comprobante."""
        self.service.provider = "facturama"
        waybill = self._create_waybill()
        self._create_waybill_entry(waybill)
        self.transporter.driving_license = "LIC123"
        waybill.cfdi_id.write(
            {
                "pdf_filename": "waybill.pdf",
                "pdf_file": b64encode(b"PDF").decode(),
                "xml_filename": "waybill.xml",
                "xml_file": b64encode(b"<xml/>").decode(),
            }
        )
        waybill.action_post()
        mock_publish.assert_called_once()
        published = mock_publish.call_args.args[1]
        self.assertEqual(published.get("TipoDeComprobante"), "T")
        self.assertTrue(published.get("Complemento"))

    def test_build_waybill_comprobante_from_format_data(self):
        from ..services import waybill_builder

        waybill = self._create_waybill()
        self._create_waybill_entry(waybill)
        self.transporter.driving_license = "LIC123"
        data = waybill._format_data()
        cfdi = waybill_builder.build_waybill_comprobante(waybill.issuer_id, data)
        self.assertEqual(cfdi.get("TipoDeComprobante"), "T")
        complemento = cfdi.get("Complemento")
        self.assertTrue(complemento)
        carta = (
            complemento.get("CartaPorte")
            if hasattr(complemento, "get") and complemento.get("CartaPorte")
            else complemento
        )
        self.assertEqual(str(carta.get("Version")), "3.1")
        self.assertTrue(carta.get("IdCCP"))
        # Fecha must be stamp-time (Mexico), not an old create date (SAT 72h).
        # Never ahead of America/Mexico_City now (Runboat/UTC host skew).
        fecha = cfdi.get("Fecha")
        self.assertIsNotNone(fecha)
        self.assertIsInstance(fecha, datetime)
        now_mx = waybill_builder._mexico_city_now_naive()
        self.assertLessEqual(fecha, now_mx)
        self.assertLess(abs((fecha - now_mx).total_seconds()), 3600)

    def test_build_waybill_comprobante_publico_adds_informacion_global(self):
        from ..services import waybill_builder

        waybill = self._create_waybill()
        self._create_waybill_entry(waybill)
        data = waybill._format_data()
        data["Receiver"] = {
            "Name": "PUBLICO EN GENERAL",
            "Rfc": "XAXX010101000",
            "CfdiUse": "S01",
            "FiscalRegime": "601",
            "TaxZipCode": "99999",
        }
        cfdi = waybill_builder.build_waybill_comprobante(waybill.issuer_id, data)
        self.assertTrue(cfdi.get("InformacionGlobal"))
        self.assertEqual(cfdi["Receptor"]["RegimenFiscalReceptor"], "616")
        self.assertEqual(
            cfdi["Receptor"]["DomicilioFiscalReceptor"], data["ExpeditionPlace"]
        )

    def test_waybill_builder_helpers(self):
        from decimal import Decimal

        from ..services import waybill_builder

        self.assertEqual(waybill_builder._dec(None), Decimal("0"))
        self.assertEqual(waybill_builder._dec("1.5"), Decimal("1.5"))
        now = datetime(2026, 1, 2, 3, 4, 5)
        self.assertEqual(waybill_builder._parse_dt(now), now)
        self.assertEqual(
            waybill_builder._parse_dt("2026-07-01 12:30:00"),
            datetime(2026, 7, 1, 12, 30, 0),
        )
        parsed = waybill_builder._parse_dt("not-a-date")
        self.assertIsInstance(parsed, datetime)
        self.assertIsNone(waybill_builder._build_domicilio(None))
        self.assertIsNone(waybill_builder._build_autotransporte(None))
        self.assertIsNone(waybill_builder._build_figura_transporte(None))
        self.assertIsNone(waybill_builder._build_figura_transporte([]))
        figuras = waybill_builder._build_figura_transporte(
            [
                {
                    "TipoFigura": "01",
                    "RFCFigura": "XAXX010101000",
                    "NombreFigura": "Operator",
                    "NumLicencia": "LIC1",
                    "PartesTransporte": [{"ParteTransporte": "PT01"}],
                }
            ]
        )
        self.assertEqual(len(figuras), 1)
        mercancias = waybill_builder._build_mercancia(
            [
                {
                    "BienesTransp": "50181900",
                    "Descripcion": "Goods",
                    "Cantidad": "1",
                    "ClaveUnidad": "H87",
                    "PesoEnKg": "10",
                    "CantidadTransporta": [
                        {
                            "Cantidad": "1",
                            "IDOrigen": "OR000001",
                            "IDDestino": "DE000001",
                        }
                    ],
                }
            ]
        )
        self.assertEqual(len(mercancias), 1)

    def test_build_carta_porte_accepts_single_mercancia_dict(self):
        from ..services import waybill_builder

        waybill = self._create_waybill()
        self._create_waybill_entry(waybill)
        data = waybill._format_data()
        cp_data = data["Complemento"]["CartaPorte31"]
        goods = cp_data["Mercancias"]["Mercancia"]
        if isinstance(goods, list) and goods:
            cp_data["Mercancias"]["Mercancia"] = goods[0]
        carta = waybill_builder.build_carta_porte_from_dict(cp_data)
        self.assertEqual(str(carta.get("Version")), "3.1")

    def test_stamp_fecha_mexico_tz_fallbacks(self):
        from datetime import timedelta, timezone

        from ..services import waybill_builder

        with patch(
            "zoneinfo.ZoneInfo",
            side_effect=Exception("tzdb missing"),
        ):
            fallback = waybill_builder._mexico_city_now_naive()
        self.assertIsInstance(fallback, datetime)

        mx_now = datetime(2026, 8, 10, 12, 0, 0)
        with (
            patch.object(
                waybill_builder,
                "_mexico_city_now_naive",
                return_value=mx_now,
            ),
            patch(
                "satcfdi.transform.get_timezone",
                side_effect=Exception("unknown CP"),
            ),
        ):
            stamp = waybill_builder._stamp_fecha("00000")
        self.assertEqual(stamp, mx_now - timedelta(seconds=30))

        future = datetime(2026, 8, 10, 18, 0, 0)

        class FutureDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return future.replace(tzinfo=tz) if tz is not None else future

        with (
            patch.object(
                waybill_builder,
                "_mexico_city_now_naive",
                return_value=mx_now,
            ),
            patch.object(waybill_builder, "datetime", FutureDateTime),
            patch("satcfdi.transform.get_timezone", return_value=timezone.utc),
        ):
            stamp = waybill_builder._stamp_fecha("26015")
        # Clamp future lugar stamp to Mexico now, then apply skew buffer.
        self.assertEqual(stamp, mx_now - timedelta(seconds=30))


class TestWaybillFiguraTransporte(WaybillTestCommon):
    def test_self_add_figuratransporte_operator(self):
        waybill = self._create_waybill()
        data = {"Complemento": {"CartaPorte31": {}}}
        waybill.self_add_figuratransporte_data(data)
        figura = data["Complemento"]["CartaPorte31"]["FiguraTransporte"][0]
        self.assertEqual(figura["NumLicencia"], "LIC123")
        self.assertNotIn("PartesTransporte", figura)

    def test_self_add_figuratransporte_arrendador(self):
        arrendador_type = self.env.ref("l10n_mx_catalogs.c_figura_transporte_3")
        parte = self.env.ref("l10n_mx_catalogs.c_parte_transporte_PT01")
        transporter = self.env["l10n_mx_cfdi_waybill.transporter"].create(
            {
                "partner_id": self.transporter_partner.id,
                "type": arrendador_type.id,
                "parte_transporte_ids": [(6, 0, parte.ids)],
            }
        )
        waybill = self._create_waybill(transporter_ids=[(6, 0, transporter.ids)])
        data = {"Complemento": {"CartaPorte31": {}}}
        waybill.self_add_figuratransporte_data(data)
        figura = data["Complemento"]["CartaPorte31"]["FiguraTransporte"][0]
        self.assertIn("PartesTransporte", figura)


class TestWaybillEntry(WaybillTestCommon):
    def test_get_defaults_from_picking(self):
        picking = self._create_picking()
        defaults = self.env["l10n_mx_cfdi_waybill.waybill_entry"]._get_defaults(picking)
        self.assertTrue(defaults.get("origin_address_id"))
        self.assertTrue(defaults.get("destination_address_id"))

    def test_get_defaults_without_warehouse(self):
        picking = self._create_picking(
            location_id=self.env.ref("stock.stock_location_customers").id,
            location_dest_id=self.env.ref("stock.stock_location_customers").id,
        )
        defaults = self.env["l10n_mx_cfdi_waybill.waybill_entry"]._get_defaults(picking)
        self.assertEqual(defaults["origin_address_id"], picking.partner_id.id)
        self.assertEqual(defaults["destination_address_id"], picking.partner_id.id)

    def test_get_defaults_no_scheduled_date(self):
        picking = self._create_picking()
        picking.scheduled_date = False
        defaults = self.env["l10n_mx_cfdi_waybill.waybill_entry"]._get_defaults(picking)
        self.assertNotIn("departure_datetime", defaults)

    def test_get_defaults_no_picking(self):
        defaults = self.env["l10n_mx_cfdi_waybill.waybill_entry"]._get_defaults(False)
        self.assertEqual(defaults, {})

    def test_validate_required_fields_success(self):
        waybill = self._create_waybill()
        entry = self._create_waybill_entry(waybill)
        entry._validate_required_fields()

    def test_validate_required_fields_missing_origin(self):
        waybill = self._create_waybill()
        entry = self._create_waybill_entry(waybill, origin_address_id=False)
        with self.assertRaises(ValidationError):
            entry._validate_required_fields()

    def test_validate_required_fields_missing_destination(self):
        waybill = self._create_waybill()
        entry = self._create_waybill_entry(waybill, destination_address_id=False)
        with self.assertRaises(ValidationError):
            entry._validate_required_fields()

    def test_validate_required_fields_missing_departure(self):
        waybill = self._create_waybill()
        entry = self._create_waybill_entry(waybill)
        entry.departure_datetime = False
        with self.assertRaises(ValidationError):
            entry._validate_required_fields()

    def test_validate_required_fields_missing_arrival(self):
        waybill = self._create_waybill()
        entry = self._create_waybill_entry(waybill)
        entry.arrival_datetime = False
        with self.assertRaises(ValidationError):
            entry._validate_required_fields()

    def test_validate_required_fields_missing_distance(self):
        waybill = self._create_waybill()
        entry = self._create_waybill_entry(waybill)
        entry.distance = 0
        with self.assertRaises(ValidationError):
            entry._validate_required_fields()

    def test_validate_required_fields_missing_measurement_unit(self):
        waybill = self._create_waybill()
        product = self.env["product.product"].create(
            {
                "name": "No UoM Waybill Product",
                "weight": 10.0,
                "l10n_mx_cfdi_product_code_id": self.env.ref(
                    "l10n_mx_catalogs.c_clave_prod_serv_01010101"
                ).id,
                "l10n_mx_cfdi_product_measurement_unit_id": False,
            }
        )
        entry = self._create_waybill_entry(waybill, product_id=product.id)
        with self.assertRaises(ValidationError) as err:
            entry._validate_required_fields()
        self.assertIn("unidad de medida", str(err.exception))

    def test_validate_required_fields_missing_weight(self):
        waybill = self._create_waybill()
        product = self.env["product.product"].create(
            {
                "name": "No Weight Waybill Product",
                "weight": 0.0,
                "l10n_mx_cfdi_product_code_id": self.env.ref(
                    "l10n_mx_catalogs.c_clave_prod_serv_01010101"
                ).id,
                "l10n_mx_cfdi_product_measurement_unit_id": self.env.ref(
                    "l10n_mx_catalogs.c_clave_unidad_H87"
                ).id,
            }
        )
        entry = self._create_waybill_entry(waybill, product_id=product.id)
        with self.assertRaises(ValidationError) as err:
            entry._validate_required_fields()
        self.assertIn("Peso", str(err.exception))

    def test_validate_required_fields_missing_origin_zip(self):
        waybill = self._create_waybill()
        origin = self.stock_partner.copy({"zip": False})
        entry = self._create_waybill_entry(waybill, origin_address_id=origin.id)
        with self.assertRaises(ValidationError):
            entry._validate_required_fields()

    def test_validate_required_fields_missing_destination_street(self):
        waybill = self._create_waybill()
        destination = self.partner.copy({"street": False})
        entry = self._create_waybill_entry(
            waybill, destination_address_id=destination.id
        )
        with self.assertRaises(ValidationError):
            entry._validate_required_fields()

    def test_validate_required_fields_missing_destination_zip(self):
        waybill = self._create_waybill()
        destination = self.partner.copy({"zip": False})
        entry = self._create_waybill_entry(
            waybill, destination_address_id=destination.id
        )
        with self.assertRaises(ValidationError):
            entry._validate_required_fields()

    def test_validate_required_fields_different_countries(self):
        waybill = self._create_waybill()
        foreign = self.env["res.partner"].create(
            {"name": "Foreign", "country_id": self.env.ref("base.us").id}
        )
        entry = self._create_waybill_entry(waybill, destination_address_id=foreign.id)
        with self.assertRaises(UserError):
            entry._validate_required_fields()

    def test_validate_required_fields_missing_product_code(self):
        waybill = self._create_waybill()
        product = self.stock_product.copy({"l10n_mx_cfdi_product_code_id": False})
        entry = self._create_waybill_entry(waybill, product_id=product.id)
        with self.assertRaises(ValidationError):
            entry._validate_required_fields()

    def test_validate_required_fields_duplicate_published_move(self):
        picking = self._create_picking()
        move = picking.move_ids[0]
        waybill = self._create_waybill()
        waybill.cfdi_id.state = "published"
        entry = self._create_waybill_entry(waybill, move_id=move.id)
        duplicate = self._create_waybill_entry(self._create_waybill(), move_id=move.id)
        with self.assertRaises(ValidationError):
            duplicate._validate_required_fields()
        self.assertTrue(entry)

    def test_compute_route_details(self):
        waybill = self._create_waybill()
        entry = self._create_waybill_entry(waybill)
        entry.origin_address_id.write(
            {
                "partner_latitude": 19.0,
                "partner_longitude": -99.0,
                "date_localization": datetime.now(),
            }
        )
        entry.destination_address_id.write(
            {
                "partner_latitude": 20.0,
                "partner_longitude": -98.0,
                "date_localization": datetime.now(),
            }
        )
        entry._compute_route_details()
        self.assertEqual(entry.distance, 60.0)
        self.assertEqual(entry.duration, 1.0)

    @patch(
        "odoo.addons.l10n_mx_cfdi_waybill.models.base_geocoder.GeoCoder.geo_query_route",
        return_value=None,
    )
    def test_compute_route_details_no_route(self, _mock_route):
        waybill = self._create_waybill()
        entry = self._create_waybill_entry(waybill)
        entry.origin_address_id.write(
            {
                "partner_latitude": 19.0,
                "partner_longitude": -99.0,
                "date_localization": datetime.now(),
            }
        )
        entry.destination_address_id.write(
            {
                "partner_latitude": 20.0,
                "partner_longitude": -98.0,
                "date_localization": datetime.now(),
            }
        )
        entry._compute_route_details()
        self.assertEqual(entry.distance, 60.0)
        self.assertEqual(entry.duration, 60.0)

    def test_compute_route_details_geo_localize(self):
        waybill = self._create_waybill()
        entry = self._create_waybill_entry(waybill)
        partner_model = type(entry.origin_address_id)
        with (
            patch.object(partner_model, "geo_localize", autospec=True) as mock_geo,
            patch(
                "odoo.addons.l10n_mx_cfdi_waybill.models.base_geocoder.GeoCoder.geo_query_route",
                return_value={"distance": 5000, "duration": 1800},
            ),
        ):
            entry.origin_address_id.write({"date_localization": False})
            entry.destination_address_id.write({"date_localization": False})
            entry._compute_route_details()
        self.assertEqual(mock_geo.call_count, 2)
        self.assertEqual(entry.distance, 5.0)

    def test_compute_route_details_missing_addresses(self):
        waybill = self._create_waybill()
        entry = self._create_waybill_entry(waybill, origin_address_id=False)
        entry._compute_route_details()
        self.assertEqual(entry.distance, 60.0)

    def test_compute_arrival_datetime(self):
        waybill = self._create_waybill()
        entry = self._create_waybill_entry(
            waybill,
            departure_datetime="2026-05-14 10:00:00",
            duration=2.0,
            arrival_datetime=False,
        )
        entry._compute_arrival_datetime()
        self.assertTrue(entry.arrival_datetime)

    def test_compute_arrival_datetime_cleared(self):
        waybill = self._create_waybill()
        entry = self._create_waybill_entry(
            waybill,
            departure_datetime=False,
            duration=0,
            arrival_datetime="2026-05-14 12:00:00",
        )
        entry._compute_arrival_datetime()
        self.assertFalse(entry.arrival_datetime)

    def test_create_copies_move_fields(self):
        picking = self._create_picking()
        move = picking.move_ids[0]
        waybill = self._create_waybill()
        entry = self.env["l10n_mx_cfdi_waybill.waybill_entry"].create(
            {"waybill_id": waybill.id, "move_id": move.id}
        )
        self.assertEqual(entry.product_id, move.product_id)
        self.assertEqual(entry.picking_id, picking)

    def test_self_add_figuratransporte_owner(self):
        owner_type = self.env.ref("l10n_mx_catalogs.c_figura_transporte_2")
        parte = self.env.ref("l10n_mx_catalogs.c_parte_transporte_PT01")
        transporter = self.env["l10n_mx_cfdi_waybill.transporter"].create(
            {
                "partner_id": self.transporter_partner.id,
                "type": owner_type.id,
                "parte_transporte_ids": [(6, 0, parte.ids)],
            }
        )
        waybill = self._create_waybill(transporter_ids=[(6, 0, transporter.ids)])
        data = {"Complemento": {"CartaPorte31": {}}}
        waybill.self_add_figuratransporte_data(data)
        figura = data["Complemento"]["CartaPorte31"]["FiguraTransporte"][0]
        self.assertIn("PartesTransporte", figura)

    def test_map_partner_country_ilike_and_missing(self):
        waybill = self._create_waybill()
        Pais = self.env["l10n_mx_catalogs.c_pais"]
        country = self.env["res.country"].create(
            {"name": "Waybill Testland", "code": "WQ"}
        )
        pais = Pais.sudo().create(
            {"code": "WQT", "description": "Waybill Testland Extra"}
        )
        with patch.object(type(Pais), "map_res_country", return_value=Pais):
            mapped = waybill._map_partner_country_to_c_pais(country)
        self.assertEqual(mapped, pais)

        unknown = self.env["res.country"].create(
            {"name": "Unknownia ZZ9", "code": "W9"}
        )
        with patch.object(type(Pais), "map_res_country", return_value=Pais):
            partner = self.env["res.partner"].create(
                {
                    "name": "No SAT Country",
                    "country_id": unknown.id,
                    "zip": "00000",
                    "street": "X",
                }
            )
            with self.assertRaises(ValidationError):
                waybill._format_address(partner)

    def test_entry_get_defaults_destination_from_dest_warehouse(self):
        picking = self._create_picking(
            picking_type_id=self.warehouse.in_type_id.id,
            location_id=self.env.ref("stock.stock_location_suppliers").id,
            location_dest_id=self.warehouse.lot_stock_id.id,
        )
        defaults = self.env["l10n_mx_cfdi_waybill.waybill_entry"]._get_defaults(picking)
        dest_wh_partner = picking.location_dest_id.warehouse_id.partner_id
        self.assertTrue(dest_wh_partner)
        self.assertEqual(defaults["destination_address_id"], dest_wh_partner.id)

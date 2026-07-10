from unittest.mock import patch

from odoo.addons.l10n_mx_cfdi_account.tests.common import CFDIAccountTestCommon


class WaybillTestCommon(CFDIAccountTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._geo_route_patcher = patch(
            "odoo.addons.l10n_mx_cfdi_waybill.models.base_geocoder.GeoCoder.geo_query_route",
            return_value={"distance": 60000, "duration": 3600},
        )
        cls._geo_route_patcher.start()
        cls.addClassCleanup(cls._geo_route_patcher.stop)
        cls.env.user.tz = "UTC"
        cls.partner.write({"street": "Customer Street"})

        cls.issuer.write({"registered": True, "zip": "06000"})
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.stock_partner = cls.env["res.partner"].create(
            {
                "name": "Stock Partner",
                "vat": "XAXX010101000",
                "zip": "06000",
                "street": "Main Street",
                "country_id": cls.env.ref("base.mx").id,
            }
        )
        cls.stock_product = cls.env["product.product"].create(
            {
                "name": "Waybill Product",
                "weight": 10.0,
                "default_code": "WB001",
                "l10n_mx_cfdi_product_code_id": cls.env.ref(
                    "l10n_mx_catalogs.c_clave_prod_serv_01010101"
                ).id,
                "l10n_mx_cfdi_product_measurement_unit_id": cls.env.ref(
                    "l10n_mx_catalogs.c_clave_unidad_H87"
                ).id,
            }
        )
        cls.vehicle = cls.env["l10n_mx_cfdi_waybill.vehicle"].create(
            {
                "name": "Truck 1",
                "plate": "ABC123",
                "model": "2024",
                "vehicle_setup": cls.env.ref(
                    "l10n_mx_catalogs.c_config_autotransporte_T3S2"
                ).id,
                "gross_vehicle_weight": 3500.0,
                "permit_type": cls.env.ref("l10n_mx_catalogs.c_tipo_perm_TPAF01").id,
                "permit_number": "PERM001",
                "insurance_company": cls.partner.id,
                "insurance_number": "INS001",
            }
        )
        cls.transporter_partner = cls.env["res.partner"].create(
            {
                "name": "Driver",
                "vat": "XAXX010101001",
                "l10n_mx_cfdi_waybill_driving_license": "LIC123",
            }
        )
        cls.transporter = cls.env["l10n_mx_cfdi_waybill.transporter"].create(
            {
                "partner_id": cls.transporter_partner.id,
                "type": cls.env.ref("l10n_mx_catalogs.c_figura_transporte_1").id,
            }
        )

    def _create_picking(self, **extra):
        vals = {
            "picking_type_id": self.warehouse.out_type_id.id,
            "location_id": self.warehouse.lot_stock_id.id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            "partner_id": self.stock_partner.id,
            "move_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": self.stock_product.id,
                        "product_uom_qty": 2.0,
                        "product_uom": self.stock_product.uom_id.id,
                        "location_id": self.warehouse.lot_stock_id.id,
                        "location_dest_id": self.env.ref(
                            "stock.stock_location_customers"
                        ).id,
                    },
                )
            ],
        }
        vals.update(extra)
        return self.env["stock.picking"].create(vals)

    def _create_waybill(self, **extra):
        cfdi = self.env["l10n_mx_cfdi.document"].create(
            {
                "type": "T",
                "issuer_id": self.issuer.id,
                "receiver_id": self.partner.id,
                "serie": "CP",
                "folio": "1",
            }
        )
        vals = {
            "cfdi_id": cfdi.id,
            "vehicle_id": self.vehicle.id,
            "transporter_ids": [(6, 0, self.transporter.ids)],
        }
        vals.update(extra)
        return self.env["l10n_mx_cfdi_waybill.waybill"].create(vals)

    def _create_waybill_entry(self, waybill, **extra):
        vals = {
            "waybill_id": waybill.id,
            "product_id": self.stock_product.id,
            "product_qty": 2.0,
            "origin_address_id": self.stock_partner.id,
            "destination_address_id": self.partner.id,
            "departure_datetime": "2026-05-14 10:00:00",
            "arrival_datetime": "2026-05-14 12:00:00",
            "distance": 60.0,
        }
        vals.update(extra)
        return self.env["l10n_mx_cfdi_waybill.waybill_entry"].create(vals)

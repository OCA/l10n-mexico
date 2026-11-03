# Copyright (C) 2026 Open Source Integrators
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from satcfdi.create.cfd import cartaporte31 as cp

from odoo.addons.l10n_mx_cfdi_waybill.tests.common import WaybillTestCommon

from ..services.waybill_builder import build_carta_porte_from_dict


class TestWaybillTrailers(WaybillTestCommon):
    def _waybill_with_trailer(self, trailer_values):
        trailer = self.env["l10n_mx_cfdi_waybill.vehicle_trailer"].create(
            trailer_values
        )
        self.vehicle.trailers = [(6, 0, trailer.ids)]
        waybill = self._create_waybill()
        return waybill

    def _autotransporte(self, waybill):
        data = {"Complemento": {"CartaPorte31": {"Mercancias": {}}}}
        waybill._add_autotransporte_data(data)
        return data["Complemento"]["CartaPorte31"]["Mercancias"]["Autotransporte"]

    def test_autotransporte_includes_trailer_plates(self):
        waybill = self._waybill_with_trailer(
            {
                "plate": "REM001",
                "type": self.env.ref("l10n_mx_catalogs.c_sub_tipo_rem_CTR004").id,
            }
        )
        remolques = self._autotransporte(waybill)["Remolques"]
        self.assertEqual(remolques, [{"SubTipoRem": "CTR004", "Placa": "REM001"}])

    def test_trailer_without_a_sat_type_is_omitted(self):
        waybill = self._waybill_with_trailer({"plate": "REM002"})
        self.assertNotIn("Remolques", self._autotransporte(waybill))

    def test_format_data_and_builder_keep_the_trailer_plate(self):
        waybill = self._waybill_with_trailer(
            {
                "plate": "REM001",
                "type": self.env.ref("l10n_mx_catalogs.c_sub_tipo_rem_CTR004").id,
            }
        )
        self._create_waybill_entry(waybill)
        self.transporter.driving_license = "LIC123"
        data = waybill._format_data()
        auto = data["Complemento"]["CartaPorte31"]["Mercancias"]["Autotransporte"]
        self.assertEqual(auto["Remolques"][0]["Placa"], "REM001")
        carta = build_carta_porte_from_dict(data["Complemento"]["CartaPorte31"])
        if hasattr(cp, "Remolques"):
            self.assertIn("REM001", str(carta))

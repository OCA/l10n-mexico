from odoo.exceptions import UserError

from ..services import waybill_builder
from .common import WaybillTestCommon


class TestHazardousMaterial(WaybillTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.template = cls.stock_product.product_tmpl_id
        cls.hazard_vals = {
            "l10n_mx_cfid_dangerous_material_code": "1203",
            "l10n_mx_cfid_dangerous_material_packaging": "1A1",
            "l10n_mx_cfid_dangerous_material_packaging_descripcion": "Tambor",
        }

    def _goods(self):
        waybill = self._create_waybill()
        self._create_waybill_entry(waybill)
        return waybill, waybill._format_goods_and_locations_data()[0][0]

    def test_default_is_no(self):
        self.assertEqual(self.template.l10n_mx_cfdi_dangerous_material, "no")
        self.assertFalse(self.template._l10n_mx_cfdi_is_dangerous_material())

    def test_is_dangerous_material(self):
        self.template.l10n_mx_cfdi_dangerous_material = "yes"
        self.assertTrue(self.template._l10n_mx_cfdi_is_dangerous_material())
        self.template.l10n_mx_cfdi_dangerous_material = "optional"
        self.assertFalse(self.template._l10n_mx_cfdi_is_dangerous_material())
        self.template.l10n_mx_cfid_dangerous_material_code = "1203"
        self.assertTrue(self.template._l10n_mx_cfdi_is_dangerous_material())

    def test_goods_no_sends_no_alone(self):
        _waybill, goods = self._goods()
        self.assertEqual(goods["MaterialPeligroso"], "No")
        for key in ("CveMaterialPeligroso", "Embalaje", "DescripEmbalaje"):
            self.assertNotIn(key, goods)

    def test_goods_optional_without_code_sends_no(self):
        self.template.l10n_mx_cfdi_dangerous_material = "optional"
        _waybill, goods = self._goods()
        self.assertEqual(goods["MaterialPeligroso"], "No")
        self.assertNotIn("CveMaterialPeligroso", goods)

    def test_goods_yes_sends_details(self):
        self.template.write(
            dict(self.hazard_vals, l10n_mx_cfdi_dangerous_material="yes")
        )
        _waybill, goods = self._goods()
        self.assertEqual(goods["MaterialPeligroso"], "Sí")
        self.assertEqual(goods["CveMaterialPeligroso"], "1203")
        self.assertEqual(goods["Embalaje"], "1A1")
        self.assertEqual(goods["DescripEmbalaje"], "Tambor")

    def test_goods_optional_with_code_sends_details(self):
        self.template.write(
            dict(self.hazard_vals, l10n_mx_cfdi_dangerous_material="optional")
        )
        _waybill, goods = self._goods()
        self.assertEqual(goods["MaterialPeligroso"], "Sí")
        self.assertEqual(goods["CveMaterialPeligroso"], "1203")

    def test_goods_yes_missing_data_raises(self):
        self.template.l10n_mx_cfdi_dangerous_material = "yes"
        for missing in self.hazard_vals:
            self.template.write(dict(self.hazard_vals))
            self.template.write({missing: False})
            waybill = self._create_waybill()
            self._create_waybill_entry(waybill)
            with self.assertRaises(UserError):
                waybill._format_goods_and_locations_data()

    def test_autotransporte_without_hazard_has_no_env_insurance(self):
        waybill = self._create_waybill()
        self._create_waybill_entry(waybill)
        data = waybill._format_data()
        seguros = data["Complemento"]["CartaPorte31"]["Mercancias"]["Autotransporte"][
            "Seguros"
        ]
        self.assertNotIn("AseguraMedAmbiente", seguros)
        self.assertNotIn("PolizaMedAmbiente", seguros)

    def test_autotransporte_hazard_adds_env_insurance(self):
        self.template.write(
            dict(self.hazard_vals, l10n_mx_cfdi_dangerous_material="yes")
        )
        self.vehicle.write(
            {
                "environmental_insurance_company": "Eco Seguros",
                "environmental_insurance_number": "ENV001",
            }
        )
        waybill = self._create_waybill()
        self._create_waybill_entry(waybill)
        data = waybill._format_data()
        seguros = data["Complemento"]["CartaPorte31"]["Mercancias"]["Autotransporte"][
            "Seguros"
        ]
        self.assertEqual(seguros["AseguraMedAmbiente"], "Eco Seguros")
        self.assertEqual(seguros["PolizaMedAmbiente"], "ENV001")

    def test_autotransporte_hazard_missing_env_insurance_raises(self):
        self.template.write(
            dict(self.hazard_vals, l10n_mx_cfdi_dangerous_material="yes")
        )
        waybill = self._create_waybill()
        self._create_waybill_entry(waybill)
        with self.assertRaises(UserError):
            waybill._format_data()
        self.vehicle.environmental_insurance_company = "Eco Seguros"
        with self.assertRaises(UserError):
            waybill._format_data()

    def test_builder_passes_hazard_values(self):
        self.template.write(
            dict(self.hazard_vals, l10n_mx_cfdi_dangerous_material="yes")
        )
        self.vehicle.write(
            {
                "environmental_insurance_company": "Eco Seguros",
                "environmental_insurance_number": "ENV001",
            }
        )
        waybill = self._create_waybill()
        self._create_waybill_entry(waybill)
        cp_data = waybill._format_data()["Complemento"]["CartaPorte31"]
        carta = waybill_builder.build_carta_porte_from_dict(cp_data)
        mercancia = carta["Mercancias"]["Mercancia"]
        mercancia = mercancia[0] if isinstance(mercancia, list) else mercancia
        self.assertEqual(mercancia["MaterialPeligroso"], "Sí")
        self.assertEqual(mercancia["CveMaterialPeligroso"], "1203")
        self.assertEqual(mercancia["Embalaje"], "1A1")
        seguros = carta["Mercancias"]["Autotransporte"]["Seguros"]
        self.assertEqual(seguros["AseguraMedAmbiente"], "Eco Seguros")
        self.assertEqual(seguros["PolizaMedAmbiente"], "ENV001")

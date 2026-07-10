from .common import WaybillTestCommon


class TestStockPickingWaybill(WaybillTestCommon):
    def test_action_create_waybill(self):
        picking = self._create_picking()
        action = picking.action_create_waybill()
        self.assertEqual(action["res_model"], "l10n_mx_cfdi_waybill.waybill")

    def test_compute_has_waybill(self):
        picking = self._create_picking()
        waybill = self._create_waybill()
        waybill.cfdi_id.state = "published"
        picking.waybill_ids = [(4, waybill.id)]
        picking._compute_has_waybill()
        self.assertTrue(picking.has_waybill)

    def test_compute_has_waybill_false_no_waybill(self):
        picking = self._create_picking()
        picking._compute_has_waybill()
        self.assertFalse(picking.has_waybill)

    def test_compute_has_waybill_false_draft(self):
        picking = self._create_picking()
        waybill = self._create_waybill()
        picking.waybill_ids = [(4, waybill.id)]
        picking._compute_has_waybill()
        self.assertFalse(picking.has_waybill)

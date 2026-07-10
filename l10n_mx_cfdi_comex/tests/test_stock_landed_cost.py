from unittest.mock import patch

from .common import CFDIComexTestCommon


class TestStockLandedCostComex(CFDIComexTestCommon):
    def test_apply_pedimento_to_lots(self):
        pedimento = self._create_pedimento()
        lot = self._create_lot_with_pedimento(pedimento, product=self.comex_product)
        lot.l10n_mx_cfdi_pedimento_id = False
        picking = self._create_incoming_picking_with_lot(lot)
        landed_cost_product = self._create_landed_cost_product()
        cost = (
            self.env["stock.landed.cost"]
            .sudo()
            .create(
                {
                    "target_model": "picking",
                    "picking_ids": [(6, 0, [picking.id])],
                    "cost_lines": [
                        (
                            0,
                            0,
                            {
                                "product_id": landed_cost_product.id,
                                "price_unit": 10,
                                "split_method": "equal",
                            },
                        )
                    ],
                    "l10n_mx_cfdi_pedimento_id": pedimento.id,
                }
            )
        )
        cost._l10n_mx_cfid_apply_pedimento_to_lots()
        self.assertEqual(lot.l10n_mx_cfdi_pedimento_id, pedimento)

    def test_apply_pedimento_skips_move_lines_without_lot(self):
        pedimento = self._create_pedimento()
        picking_type = self.env.ref("stock.picking_type_in")
        picking = (
            self.env["stock.picking"]
            .sudo()
            .create(
                {
                    "picking_type_id": picking_type.id,
                    "location_id": self.supplier_location.id,
                    "location_dest_id": self.stock_location.id,
                    "company_id": self.company.id,
                }
            )
        )
        move = (
            self.env["stock.move"]
            .sudo()
            .create(
                {
                    "product_id": self.comex_product.id,
                    "product_uom_qty": 1,
                    "product_uom": self.comex_product.uom_id.id,
                    "picking_id": picking.id,
                    "location_id": picking.location_id.id,
                    "location_dest_id": picking.location_dest_id.id,
                    "company_id": self.company.id,
                }
            )
        )
        self.env["stock.move.line"].sudo().create(
            {
                "move_id": move.id,
                "product_id": self.comex_product.id,
                "product_uom_id": self.comex_product.uom_id.id,
                "quantity": 1,
                "location_id": move.location_id.id,
                "location_dest_id": move.location_dest_id.id,
            }
        )
        landed_cost_product = self._create_landed_cost_product()
        cost = (
            self.env["stock.landed.cost"]
            .sudo()
            .create(
                {
                    "target_model": "picking",
                    "picking_ids": [(6, 0, [picking.id])],
                    "cost_lines": [
                        (
                            0,
                            0,
                            {
                                "product_id": landed_cost_product.id,
                                "price_unit": 10,
                                "split_method": "equal",
                            },
                        )
                    ],
                    "l10n_mx_cfdi_pedimento_id": pedimento.id,
                }
            )
        )
        cost._l10n_mx_cfid_apply_pedimento_to_lots()

    def test_apply_pedimento_skips_when_missing(self):
        lot = (
            self.env["stock.lot"]
            .sudo()
            .create(
                {
                    "name": "LC-LOT-NO-PED",
                    "product_id": self.comex_product.id,
                    "company_id": self.company.id,
                }
            )
        )
        picking = self._create_incoming_picking_with_lot(lot)
        landed_cost_product = self._create_landed_cost_product()
        cost = (
            self.env["stock.landed.cost"]
            .sudo()
            .create(
                {
                    "target_model": "picking",
                    "picking_ids": [(6, 0, [picking.id])],
                    "cost_lines": [
                        (
                            0,
                            0,
                            {
                                "product_id": landed_cost_product.id,
                                "price_unit": 10,
                                "split_method": "equal",
                            },
                        )
                    ],
                }
            )
        )
        cost._l10n_mx_cfid_apply_pedimento_to_lots()
        self.assertFalse(lot.l10n_mx_cfdi_pedimento_id)

    def test_button_validate_applies_pedimento(self):
        pedimento = self._create_pedimento()
        lot = self._create_lot_with_pedimento(pedimento, product=self.comex_product)
        lot.l10n_mx_cfdi_pedimento_id = False
        picking = self._create_incoming_picking_with_lot(lot)
        landed_cost_product = self._create_landed_cost_product()
        cost = (
            self.env["stock.landed.cost"]
            .sudo()
            .create(
                {
                    "target_model": "picking",
                    "picking_ids": [(6, 0, [picking.id])],
                    "cost_lines": [
                        (
                            0,
                            0,
                            {
                                "product_id": landed_cost_product.id,
                                "price_unit": 10,
                                "split_method": "equal",
                            },
                        )
                    ],
                    "l10n_mx_cfdi_pedimento_id": pedimento.id,
                }
            )
        )
        with patch(
            "odoo.addons.stock_landed_costs.models.stock_landed_cost."
            "StockLandedCost.button_validate",
            return_value=True,
        ):
            cost.button_validate()
        self.assertEqual(lot.l10n_mx_cfdi_pedimento_id, pedimento)

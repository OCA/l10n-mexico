from odoo import fields
from odoo.tests.common import tagged

from odoo.addons.l10n_mx_cfdi_account.tests.common import CFDIAccountTestCommon


@tagged("post_install", "-at_install")
class CFDIComexTestCommon(CFDIAccountTestCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customs = cls.env["l10n_mx_catalogs.c_aduana"].search([], limit=1)
        cls.fraccion = cls.env["l10n_mx_catalogs.c_fraccion"].search([], limit=1)
        cls.stock_location = cls.env.ref("stock.stock_location_stock")
        cls.customer_location = cls.env.ref("stock.stock_location_customers")
        cls.supplier_location = cls.env.ref("stock.stock_location_suppliers")
        cls.comex_product = cls.env["product.product"].create(
            {
                "name": "Comex Product",
                "is_storable": True,
                "tracking": "lot",
                "list_price": 100.0,
                "l10n_mx_cfdi_tariff_code": cls.fraccion.id,
                "l10n_mx_cfdi_product_code_id": cls.env.ref(
                    "l10n_mx_catalogs.c_clave_prod_serv_01010101"
                ).id,
                "l10n_mx_cfdi_product_measurement_unit_id": cls.env.ref(
                    "l10n_mx_catalogs.c_clave_unidad_H87"
                ).id,
                "taxes_id": [(6, 0, cls.tax_sale_a.ids)],
            }
        )

    @classmethod
    def _create_pedimento(cls, number="15 48 3009 0001234", **extra):
        vals = {
            "number": number,
            "customs_id": cls.customs.id,
            "date": fields.Date.today(),
        }
        vals.update(extra)
        return cls.env["l10n_mx_cfdi.pedimento"].create(vals)

    @classmethod
    def _create_lot_with_pedimento(cls, pedimento, product=None):
        product = product or cls.comex_product
        return (
            cls.env["stock.lot"]
            .sudo()
            .create(
                {
                    "name": f"LOT-{pedimento.number.replace(' ', '-')}",
                    "product_id": product.id,
                    "company_id": cls.company.id,
                    "l10n_mx_cfdi_pedimento_id": pedimento.id,
                }
            )
        )

    def _create_landed_cost_product(self):
        return (
            self.env["product.product"]
            .sudo()
            .create(
                {
                    "name": "Landed Cost Service",
                    "landed_cost_ok": True,
                }
            )
        )

    def _create_incoming_picking_with_lot(self, lot):
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
                "lot_id": lot.id,
                "location_id": move.location_id.id,
                "location_dest_id": move.location_dest_id.id,
            }
        )
        return picking

    def _create_sale_invoice_with_lot(self, pedimento):
        lot = self._create_lot_with_pedimento(pedimento)
        sale_order = (
            self.env["sale.order"]
            .sudo()
            .create(
                {
                    "partner_id": self.customer.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": self.comex_product.id,
                                "product_uom_qty": 1,
                            },
                        )
                    ],
                }
            )
        )
        sale_order.action_confirm()
        picking = sale_order.picking_ids.sudo()
        picking.action_assign()
        for move in picking.move_ids:
            if move.move_line_ids:
                move.move_line_ids.write(
                    {
                        "lot_id": lot.id,
                        "quantity": 1,
                    }
                )
            else:
                self.env["stock.move.line"].sudo().create(
                    {
                        "move_id": move.id,
                        "product_id": move.product_id.id,
                        "product_uom_id": move.product_uom.id,
                        "quantity": 1,
                        "lot_id": lot.id,
                        "location_id": move.location_id.id,
                        "location_dest_id": move.location_dest_id.id,
                    }
                )
        picking.button_validate()
        invoice = sale_order._create_invoices()
        invoice.action_post()
        return invoice, lot

from odoo.tests import TransactionCase


class TestAccountMoveLine(TransactionCase):
    def setUp(self):
        super().setUp()

        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Partner",
            }
        )

        self.account = self.env["account.account"].search(
            [("account_type", "=", "income")],
            limit=1,
        )

        self.account_iva = self.env["account.account"].create(
            {
                "name": "IVA account",
                "code": "10",
                "account_type": "liability_current",
            }
        )

        self.tax_group = self.env["account.tax.group"].create(
            {
                "name": "IVA",
                "country_id": self.env.ref("base.us").id,
            }
        )

        self.tax = self.env["account.tax"].create(
            {
                "name": "IVA",
                "amount": 16.00,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "country_id": self.env.ref("base.us").id,
                "tax_group_id": self.tax_group.id,
                "invoice_repartition_line_ids": [
                    (0, 0, {"repartition_type": "base"}),
                    (
                        0,
                        0,
                        {
                            "factor_percent": 100.0,
                            "repartition_type": "tax",
                            "account_id": self.account_iva.id,
                        },
                    ),
                ],
            }
        )

        self.product = self.env["product.template"].create(
            {
                "name": "Test Product",
                "default_code": "TP",
                "list_price": "100",
            }
        )

        self.journal = self.env["account.journal"].search(
            [("type", "=", "sale")],
            limit=1,
        )

        self.move_line_1_vals = {
            "product_id": self.env["product.product"]
            .search(
                [("default_code", "=", "TP")],
                limit=1,
            )
            .id,
            "name": "Test Move Line 1",
            "quantity": 2,
            "account_id": self.account.id,
            "price_unit": 100.00,
            "display_type": "product",
            "tax_ids": [(6, 0, [self.tax.id])],
        }

        self.move_vals = {
            "name": "Test Move",
            "move_type": "out_invoice",
            "journal_id": self.journal.id,
            "partner_id": self.partner.id,
            "invoice_line_ids": [(0, 0, self.move_line_1_vals)],
        }

    def test_compute_cfdi_fields(self):
        move = self.env["account.move"].create(self.move_vals)

        move_line_1 = move.invoice_line_ids.search(
            [("name", "=", "Test Move Line 1")],
            limit=1,
        )

        move_line_1._compute_cfdi_fields()

        # Assuming the test logic for computing CFDI fields here...

        self.assertEqual(move_line_1.cfdi_subtotal, 200.00)
        self.assertEqual(move_line_1.cfdi_price_unit, 100.00)

        # Add assertions for move_line_2 if necessary

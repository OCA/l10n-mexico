from odoo.tests import TransactionCase


class TestAccountMoveLine(TransactionCase):
    def setUp(self):
        super().setUp()

        self.company = self.env["res.company"].create(
            {
                "name": "Test Company",
                # Add other required fields here
            }
        )

        self.currency = self.env["res.currency"].create(
            {
                "name": "Test Currency",
                "symbol": "TC",
                "decimal_places": 2,
                # Add other required fields here
            }
        )

        self.tax = self.env["account.tax"].create(
            {
                "name": "IVA",
                "amount": 10,
                "amount_type": "percent",
                "type_tax_use": "sale",
                "country_id": self.env.ref("base.mx").id,
                # Add other required fields here
            }
        )

        self.product = self.env["product.product"].create(
            {
                "name": "Test Product",
                "default_code": "TP",
                # Add other required fields here
            }
        )

        journal_id = (
            self.env["account.journal"].search([("type", "=", "sale")], limit=1).id
        )

        self.move_line_1_vals = {
            "name": "Test Move Line 1",
            "product_id": self.product.id,
            "price_unit": 100,
            "quantity": 2,
            "price_subtotal": 200.00,
            "price_total": 220.00,
            # 'tax_ids': [(6, 0, [self.tax.id])],
            "debit": 200,
            "account_id": self.env.ref(
                "account.data_account_type_revenue"
            ).id,  # Example revenue account
        }

        self.move_line_2_vals = {
            "name": "Test Move Line 2",
            "product_id": self.product.id,
            "price_unit": 200,
            "quantity": 1,
            "price_subtotal": 200.00,
            "price_total": 220.00,
            # 'tax_ids': [(6, 0, [self.tax.id])],
            "credit": 200,
            "account_id": self.env.ref(
                "account.data_account_type_current_assets"
            ).id,  # Example asset account
        }

        self.move_vals = {
            "name": "Test Move",
            "move_type": "out_invoice",
            "currency_id": self.currency.id,
            "company_id": self.company.id,
            "journal_id": journal_id,
            "line_ids": [(0, 0, self.move_line_1_vals), (0, 0, self.move_line_2_vals)],
        }

    def test_compute_cfdi_fields(self):
        move = self.env["account.move"].create(self.move_vals)

        move_line_1 = move.line_ids.filtered(
            lambda line: line.name == "Test Move Line 1"
        )
        move_line_2 = move.line_ids.filtered(
            lambda line: line.name == "Test Move Line 2"
        )

        move_line_1._compute_cfdi_fields()
        move_line_2._compute_cfdi_fields()

        # Assuming the test logic for computing CFDI fields here...

        self.assertEqual(move_line_1.cfdi_subtotal, -200.00)
        self.assertEqual(move_line_1.cfdi_price_unit, -100.00)
        self.assertEqual(move_line_2.cfdi_subtotal, 200.00)
        self.assertEqual(move_line_2.cfdi_price_unit, 200.00)

        # Add assertions for move_line_2 if necessary

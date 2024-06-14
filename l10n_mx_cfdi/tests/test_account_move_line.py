from odoo.tests import TransactionCase
from odoo.exceptions import UserError


class TestAccountMoveLine(TransactionCase):

    def setUp(self):
        super().setUp()
        self.company = self.env['res.company'].create({
            'name': 'Test Company',
            # Add other required fields here
        })
        self.currency = self.env['res.currency'].create({
            'name': 'Test Currency',
            'symbol': 'TC',
            'decimal_places': 2,
            # Add other required fields here
        })
        self.tax = self.env['account.tax'].create({
            'name': 'IVA',
            'amount': 10,
            'amount_type': 'percent',
            'type_tax_use': 'sale',
            'country_id': self.env.ref("base.mx").id
            # Add other required fields here
        })
        self.product = self.env['product.product'].create({
            'name': 'Test Product',
            'default_code': 'TP',
            # 'l10n_mx_cfdi_product_code_id': self.env.ref('01010101'),
            # 'l10n_mx_cfdi_product_measurement_unit_id': self.env.ref('Kilogramo'),
            # Add other required fields here
        })
        self.move = self.env['account.move'].create({
            'name': 'Test Move',
            'move_type': 'out_invoice',
            'currency_id': self.currency.id,
            'company_id': self.company.id,
            # Add other required fields here
        })

    def test_compute_cfdi_fields(self):
        company = self.env.user.company_id
        # default_account_id = company.default_account_id.id
        move_line = self.env['account.move.line'].create({
            'move_id': self.move.id,
            'name': 'Test Move Line',
            'product_id': self.product.id,
            'price_unit': 100,
            'quantity': 2,
            'discount': 10,
            'currency_id': self.currency.id,
            'company_id': self.company.id,
            'tax_ids': [self.tax.id],
            'account_id': self.env.ref('l10n_mx.1_cuenta115_01').id,
        })
        move_line._compute_cfdi_fields()

        self.assertEqual(move_line.cfdi_subtotal, 180.00)
        self.assertEqual(move_line.cfdi_discount, 20.00)
        self.assertEqual(move_line.cfdi_price_unit, 90.00)

from odoo.tests.common import TransactionCase


class TestCFDIServiceTopUp(TransactionCase):

    def setUp(self):
        super().setUp()

        # Create a test CFDI Service TopUp
        self.cfdi_service_topup = self.env['l10n_mx_cfdi.cfdi_service.topup'].create({
            'stamp_number': 10,
            'stamp_price': 5.0,
            'service_id': self.env['l10n_mx_cfdi.cfdi_service'].create({
                'name': 'Test CFDI Service',
                'user': 'test_user',
                'password': 'test_password',
            }).id,
            # Add other required fields
        })

    def test_compute_total(self):
        self.assertEqual(self.cfdi_service_topup.total, 50.0)

    # Add more test methods to cover other functionalities and scenarios...

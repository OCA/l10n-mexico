from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestCFDIService(TransactionCase):
    def setUp(self):
        super().setUp()
        self.cfdi_service = self.env["l10n_mx_cfdi.cfdi_service"].create(
            {
                "name": "Test Service",
                "user": "test_user",
                "password": "test_password",
                "sandbox_mode": True,
            }
        )

    def test_register_csd(self):
        # Test registering CSD
        with self.assertRaises(UserError):
            self.cfdi_service.register_csd("RFC", b"cert", b"key", "password")

    def test_unregister_csd(self):
        # Test unregistering CSD
        with self.assertRaises(UserError):
            self.cfdi_service.unregister_csd("RFC")

    def test_get_csd_status(self):
        # Test getting CSD status
        status = self.cfdi_service.get_csd_status("RFC")
        self.assertEqual(status, {})

    def test_create_cfdi(self):
        # Test creating CFDI
        with self.assertRaises(UserError):
            self.cfdi_service.create_cfdi({})

    def test_cancel_cfdi(self):
        # Test cancelling CFDI
        with self.assertRaises(UserError):
            self.cfdi_service.cancel_cfdi("cfdi_id", "reason", "uuid_replacement")

    def test_get_cancellation_request_proof(self):
        # Test getting cancellation request proof
        with self.assertRaises(UserError):
            self.cfdi_service.get_cancellation_request_proof("cfdi_id")

    def test_check_cfdi_status(self):
        # Test checking CFDI status
        status = self.cfdi_service.check_cfdi_status(
            "uudi", "issuer_rfc", "receiver_rfc", "amount_total"
        )
        self.assertEqual(status, "unknown")

    def test_get_cfdi_pdf(self):
        # Test getting CFDI PDF
        pdf_content = self.cfdi_service.get_cfdi_pdf("cfdi_id")
        self.assertTrue(isinstance(pdf_content, bytes))

    def test_get_cfdi_xml(self):
        # Test getting CFDI XML
        xml_content = self.cfdi_service.get_cfdi_xml("cfdi_id")
        self.assertTrue(isinstance(xml_content, bytes))

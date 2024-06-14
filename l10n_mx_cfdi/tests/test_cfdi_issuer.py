from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from base64 import b64encode

class TestCFDIIssuer(TransactionCase):
    def setUp(self):
        super(TestCFDIIssuer, self).setUp()

        self.service = self.env["l10n_mx_cfdi.cfdi_service"].create({
            "name": "Test service",
            "user": "Test user",
            "password": "12345",
        })

        self.issuer = self.env["l10n_mx_cfdi.issuer"].create({
            "name": "Test Issuer",
            "vat": "RFC123456",
            "certificate_file": b64encode(b"certificate"),
            "key_file": b64encode(b"key"),
            "key_password": "password",
            "service_id": self.service.id,
        })

    def test_default_get_method(self):
        # Test default_get method
        issuer = self.env["l10n_mx_cfdi.issuer"].default_get([])
        self.assertEqual(issuer["country_id"], self.env.ref("base.mx").id)

    def test_slugify_method(self):
        # Test _slugify method
        issuer = self.env["l10n_mx_cfdi.issuer"]
        self.assertEqual(issuer._slugify("Test String"), "test_string")

    def test_create_default_cfdi_sequence_method(self):
        # Test _create_default_cfdi_sequence method
        sequence = self.issuer._create_default_cfdi_sequence("Test")
        self.assertEqual(sequence.name, "Folios CFDI Test")

    def test_register_issuer(self):
        # Test register_issuer method
        with self.assertRaises(UserError):
            self.issuer.register_issuer()

    def test_unregister_issuer(self):
        # Test unregister_issuer method
        with self.assertRaises(UserError):
            self.issuer.unregister_issuer()
